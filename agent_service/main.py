import json
import os
import asyncio
import time
from contextlib import suppress
from contextlib import asynccontextmanager
from pathlib import Path

import jwt
import pymysql
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_env_file(path: Path = PROJECT_ROOT / ".env"):
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()

from agent_service.attachments import MAX_IMAGE_BYTES
from agent_service.chat.schemas import MessageRequest
from agent_service.chat.service import WardrobeAgent
from agent_service.config import load_agent_config
from agent_service.memory_worker import MemoryWorker
from agent_service.logging import configure_logging, get_logger
from agent_service.persistence.store import ActionConflict


configure_logging()
logger = get_logger()


class Principal(BaseModel):
    user_id: int


class SessionRequest(BaseModel):
    title: str | None = Field(default=None, max_length=100)


class ActionDecision(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    expected_payload_hash: str = Field(min_length=64, max_length=64)
    client_decision_id: str = Field(min_length=1, max_length=64)
    session_id: str | None = None


class MemoryPatch(BaseModel):
    content: str = Field(min_length=1, max_length=500)


def connect_db():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "fashion_system"),
        charset=os.environ.get("DB_CHARSET", "utf8mb4"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        connect_timeout=5,
        read_timeout=10,
        write_timeout=10,
    )


def connect_read_db():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("AGENT_DB_READ_USER") or os.environ.get("DB_USER", "root"),
        password=os.environ.get("AGENT_DB_READ_PASSWORD") or os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "fashion_system"),
        charset=os.environ.get("DB_CHARSET", "utf8mb4"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        connect_timeout=5,
        read_timeout=10,
        write_timeout=10,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_agent_config()
    checkpoint_path = config.ensure_checkpoint_dir()
    async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path)) as saver:
        app.state.checkpointer = saver
        app.state.agent = WardrobeAgent(connect_db, checkpointer=saver, read_connect=connect_read_db)
        logger.info("agent_started", graph_version="agent-v2-1.0")
        memory_task = asyncio.create_task(MemoryWorker(app.state.agent).run())
        try:
            yield
        finally:
            memory_task.cancel()
            with suppress(asyncio.CancelledError):
                await memory_task


app = FastAPI(title="Smart Wardrobe Agent", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def request_log(request: Request, call_next):
    started = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
    finally:
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code if response else 500,
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
    return response


@app.exception_handler(KeyError)
async def not_found_handler(_request: Request, _error: KeyError):
    return JSONResponse(status_code=404, content={"error": "RESOURCE_NOT_FOUND"})


@app.exception_handler(ValueError)
async def invalid_request_handler(_request: Request, error: ValueError):
    return JSONResponse(status_code=400, content={"error": "INVALID_REQUEST", "message": str(error)})


@app.exception_handler(ActionConflict)
async def action_conflict_handler(_request: Request, error: ActionConflict):
    return JSONResponse(status_code=409, content={"error": "ACTION_CONFLICT", "message": str(error)})


def get_principal(authorization: str = Header(default="")) -> Principal:
    token = authorization.removeprefix("Bearer ").strip()
    config = load_agent_config()
    if not token or not config.jwt_secret:
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
    try:
        payload = jwt.decode(token, config.jwt_secret, algorithms=["HS256"])
        return Principal(user_id=int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED") from exc


def agent(request: Request) -> WardrobeAgent:
    if not load_agent_config().chat_v2_enabled:
        raise HTTPException(status_code=503, detail="CHAT_V2_DISABLED")
    return request.app.state.agent


@app.get("/api/chat/v2/health")
def health(request: Request):
    config = load_agent_config()
    checks = {
        "configuration_errors": config.validate_runtime(),
        "database": False,
        "wardrobe_read_database": False,
        "checkpoint": False,
    }
    with connect_db() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM chat_sessions LIMIT 1")
            cursor.fetchone()
            checks["database"] = True
    with connect_read_db() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM clothes LIMIT 1")
            cursor.fetchone()
            checks["wardrobe_read_database"] = True
    checks["checkpoint"] = config.ensure_checkpoint_dir().parent.is_dir()
    ready = all((checks["database"], checks["wardrobe_read_database"], checks["checkpoint"])) and not checks["configuration_errors"]
    return JSONResponse(status_code=200 if ready else 503, content={"status": "ok" if ready else "degraded", "checks": checks})


@app.post("/api/chat/v2/sessions")
def create_session(body: SessionRequest, principal: Principal = Depends(get_principal), service: WardrobeAgent = Depends(agent)):
    return service.store.create_session(principal.user_id, body.title)


@app.post("/api/chat/v2/uploads")
async def upload_attachment(
    file: UploadFile = File(...),
    principal: Principal = Depends(get_principal),
    service: WardrobeAgent = Depends(agent),
):
    content = await file.read(MAX_IMAGE_BYTES + 1)
    uploaded = service.uploads.save_image(principal.user_id, content)
    logger.info(
        "agent_attachment_saved",
        user_id=principal.user_id,
        upload_id=uploaded["upload_id"],
        mime_type=uploaded["mime_type"],
        size=uploaded["size"],
    )
    return uploaded


@app.post("/api/chat/v2/sessions/{session_id}/messages")
async def send_message(session_id: str, body: MessageRequest, principal: Principal = Depends(get_principal), service: WardrobeAgent = Depends(agent)):
    return await service.chat(principal.user_id, {**body.model_dump(mode="json"), "session_id": session_id})


@app.post("/api/chat/v2/sessions/{session_id}/messages/stream")
async def stream_message(session_id: str, body: MessageRequest, principal: Principal = Depends(get_principal), service: WardrobeAgent = Depends(agent)):
    async def events():
        yield sse("accepted", {"session_id": session_id, "client_message_id": body.client_message_id})
        yield sse("progress", {"stage": "routing", "label": "正在理解你的问题"})
        if body.attachments:
            yield sse("progress", {"stage": "analyzing_image", "label": "正在分析衣物图片"})
        elif any(word in body.text for word in ("搭配", "推荐", "穿搭")):
            yield sse("progress", {"stage": "ranking", "label": "正在召回并比较候选穿搭"})
        else:
            yield sse("progress", {"stage": "searching_wardrobe", "label": "正在查找需要的衣橱事实"})
        task = asyncio.create_task(
            service.chat(principal.user_id, {**body.model_dump(mode="json"), "session_id": session_id})
        )
        try:
            while not task.done():
                done, _ = await asyncio.wait({task}, timeout=15)
                if not done:
                    yield ": heartbeat\n\n"
            result = await task
        finally:
            if not task.done():
                task.cancel()
        if result.get("pending_action"):
            yield sse("confirmation_required", result["pending_action"])
        yield sse("completed", {"answer": result})

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/chat/v2/sessions/{session_id}/messages")
def list_messages(session_id: str, limit: int = 50, principal: Principal = Depends(get_principal), service: WardrobeAgent = Depends(agent)):
    service.store.ensure_session(principal.user_id, session_id)
    return service.store.list_messages(principal.user_id, session_id, limit)


@app.delete("/api/chat/v2/sessions/{session_id}")
async def delete_session(session_id: str, request: Request, principal: Principal = Depends(get_principal), service: WardrobeAgent = Depends(agent)):
    if not service.store.delete_session(principal.user_id, session_id):
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
    await request.app.state.checkpointer.adelete_thread(session_id)
    return {"deleted": True}


@app.post("/api/chat/v2/sessions/{session_id}/cancel")
def cancel_run(session_id: str, principal: Principal = Depends(get_principal), service: WardrobeAgent = Depends(agent)):
    service.store.ensure_session(principal.user_id, session_id)
    return {"cancelled_runs": service.store.cancel_active_run(principal.user_id, session_id)}


@app.post("/api/chat/v2/actions/{action_id}/decision")
async def decide_action(action_id: str, body: ActionDecision, principal: Principal = Depends(get_principal), service: WardrobeAgent = Depends(agent)):
    action = service.store.get_pending_action_for_user(principal.user_id, action_id)
    if not action or body.session_id and body.session_id != action["session_id"]:
        raise HTTPException(status_code=404, detail="ACTION_NOT_FOUND")
    if body.expected_payload_hash != action["payload_hash"]:
        raise ActionConflict("确认摘要已变化，请重新确认")
    return await service.resume_pending_action(
        principal.user_id, action["session_id"], action_id,
        body.decision, body.expected_payload_hash, body.client_decision_id,
    )


@app.get("/api/chat/v2/memories")
def list_memories(principal: Principal = Depends(get_principal), service: WardrobeAgent = Depends(agent)):
    return service.store.list_memories(principal.user_id)


@app.patch("/api/chat/v2/memories/{memory_id}")
def update_memory(memory_id: str, body: MemoryPatch, principal: Principal = Depends(get_principal), service: WardrobeAgent = Depends(agent)):
    changed = service.store.update_memory(principal.user_id, memory_id, body.content)
    if not changed:
        raise HTTPException(status_code=404, detail="MEMORY_NOT_FOUND")
    return {"updated": True}


@app.delete("/api/chat/v2/memories/{memory_id}")
def delete_memory(memory_id: str, principal: Principal = Depends(get_principal), service: WardrobeAgent = Depends(agent)):
    changed = service.store.delete_memory(principal.user_id, memory_id)
    if not changed:
        raise HTTPException(status_code=404, detail="MEMORY_NOT_FOUND")
    return {"deleted": True}


@app.delete("/api/chat/v2/memories")
def delete_all_memories(principal: Principal = Depends(get_principal), service: WardrobeAgent = Depends(agent)):
    return {"deleted": service.store.delete_all_memories(principal.user_id)}


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
