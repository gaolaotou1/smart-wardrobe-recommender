import atexit
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

import jwt
import pymysql
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("JWT_SECRET", "local-e2e-only-secret-with-at-least-32-chars")
os.environ.setdefault("DEEPSEEK_API_KEY", "")
os.environ.setdefault("IMAGE_ANALYSIS_ENABLED", "false")
os.environ.setdefault("AGENT_CHECKPOINT_PATH", str(ROOT / "data" / "e2e_checkpoints.sqlite3"))

from agent_service.main import app, connect_db
from agent_service.memory_worker import MemoryWorker
from agent_service.persistence.store import AgentStore, load_json


def main():
    with connect_db() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT u.id, COUNT(c.id) AS clothes_count FROM users u "
                "LEFT JOIN clothes c ON c.user_id=u.id GROUP BY u.id ORDER BY clothes_count DESC, u.id LIMIT 2"
            )
            users = cursor.fetchall()
    if not users:
        raise RuntimeError("端到端测试需要至少一个本地用户")
    user = users[0]

    token = jwt.encode({"sub": str(user["id"])}, os.environ["JWT_SECRET"], algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}
    cleanup_state = {"session_id": None, "outfit_id": None}

    def cleanup():
        with connect_db() as connection:
            with connection.cursor() as cursor:
                if cleanup_state["session_id"]:
                    cursor.execute(
                        "DELETE FROM chat_sessions WHERE id=%s AND user_id=%s",
                        (cleanup_state["session_id"], user["id"]),
                    )
                if cleanup_state["outfit_id"]:
                    cursor.execute(
                        "DELETE FROM outfits WHERE id=%s AND user_id=%s",
                        (cleanup_state["outfit_id"], user["id"]),
                    )
            connection.commit()

    atexit.register(cleanup)
    with TestClient(app) as client:
        session_response = client.post("/api/chat/v2/sessions", headers=headers, json={"title": "e2e"})
        session_response.raise_for_status()
        session_id = session_response.json()["session_id"]
        cleanup_state["session_id"] = session_id

        answer_response = client.post(
            f"/api/chat/v2/sessions/{session_id}/messages/stream",
            headers=headers,
            json={
                "client_message_id": str(uuid.uuid4()),
                "text": "我有几件衣服？",
                "attachments": [],
                "selected_clothes_ids": [],
            },
        )
        answer_response.raise_for_status()
        assert "event: accepted" in answer_response.text
        assert "event: progress" in answer_response.text
        completed = next(
            block for block in answer_response.text.split("\n\n")
            if block.startswith("event: completed")
        )
        answer = json.loads(next(line[6:] for line in completed.splitlines() if line.startswith("data: ")))["answer"]
        assert answer["route"] == "wardrobe_query"
        assert answer["facts"] and answer["facts"][0]["type"] == "count"
        assert answer["facts"][0]["value"] == user["clothes_count"]
        assert answer["evidence_ids"]

        recommendation = client.post(
            f"/api/chat/v2/sessions/{session_id}/messages",
            headers=headers,
            json={
                "client_message_id": str(uuid.uuid4()),
                "text": "帮我搭一套日常穿搭",
                "attachments": [],
                "selected_clothes_ids": [],
            },
        )
        recommendation.raise_for_status()
        recommendation_answer = recommendation.json()
        assert recommendation_answer["route"] == "outfit_recommendation"
        assert recommendation_answer["outfits"]

        prepare = client.post(
            f"/api/chat/v2/sessions/{session_id}/messages",
            headers=headers,
            json={
                "client_message_id": str(uuid.uuid4()),
                "text": "保存第一套为E2E临时穿搭",
                "attachments": [],
                "selected_clothes_ids": [],
            },
        )
        prepare.raise_for_status()
        pending = prepare.json()["pending_action"]
        assert pending

        commit = client.post(
            f"/api/chat/v2/actions/{pending['action_id']}/decision",
            headers=headers,
            json={
                "decision": "approve",
                "expected_payload_hash": pending["payload_hash"],
                "client_decision_id": str(uuid.uuid4()),
                "session_id": session_id,
            },
        )
        commit.raise_for_status()
        created_outfit_id = commit.json()["outfits"][0]["id"]
        cleanup_state["outfit_id"] = created_outfit_id

        repeated_commit = client.post(
            f"/api/chat/v2/actions/{pending['action_id']}/decision",
            headers=headers,
            json={
                "decision": "approve",
                "expected_payload_hash": pending["payload_hash"],
                "client_decision_id": str(uuid.uuid4()),
                "session_id": session_id,
            },
        )
        repeated_commit.raise_for_status()
        assert repeated_commit.json()["outfits"][0]["id"] == created_outfit_id

        conflict_prepare = client.post(
            f"/api/chat/v2/sessions/{session_id}/messages",
            headers=headers,
            json={
                "client_message_id": str(uuid.uuid4()),
                "text": f"将穿搭 #{created_outfit_id} 重命名为不应覆盖",
                "attachments": [],
                "selected_clothes_ids": [],
            },
        )
        conflict_prepare.raise_for_status()
        conflict_action = conflict_prepare.json()["pending_action"]
        with connect_db() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE outfits SET name=%s, update_time=DATE_ADD(update_time, INTERVAL 1 SECOND) "
                    "WHERE id=%s AND user_id=%s",
                    ("E2E并发新值", created_outfit_id, user["id"]),
                )
            connection.commit()
        conflict_commit = client.post(
            f"/api/chat/v2/actions/{conflict_action['action_id']}/decision",
            headers=headers,
            json={
                "decision": "approve",
                "expected_payload_hash": conflict_action["payload_hash"],
                "client_decision_id": str(uuid.uuid4()),
                "session_id": session_id,
            },
        )
        assert conflict_commit.status_code == 409
        assert conflict_commit.json()["error"] == "ACTION_CONFLICT"
        with connect_db() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT name FROM outfits WHERE id=%s AND user_id=%s", (created_outfit_id, user["id"]))
                assert cursor.fetchone()["name"] == "E2E并发新值"

        history_response = client.get(f"/api/chat/v2/sessions/{session_id}/messages", headers=headers)
        history_response.raise_for_status()
        assert len(history_response.json()) >= 6

        with connect_db() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) AS total, SUM(primary_route IS NULL) AS missing_route "
                    "FROM agent_runs WHERE session_id=%s AND user_id=%s",
                    (session_id, user["id"]),
                )
                run_audit = cursor.fetchone()
                cursor.execute(
                    "SELECT COUNT(*) AS total FROM agent_tool_calls "
                    "WHERE run_id IN (SELECT id FROM agent_runs WHERE session_id=%s)",
                    (session_id,),
                )
                tool_audit = cursor.fetchone()
                cursor.execute(
                    "SELECT summary_json, summary_through_message_id FROM chat_sessions "
                    "WHERE id=%s AND user_id=%s",
                    (session_id, user["id"]),
                )
                summary = cursor.fetchone()
        assert run_audit["total"] >= 3 and run_audit["missing_route"] == 0
        assert tool_audit["total"] >= 3
        assert summary["summary_json"] and summary["summary_through_message_id"]

        if len(users) > 1:
            other_token = jwt.encode({"sub": str(users[1]["id"])}, os.environ["JWT_SECRET"], algorithm="HS256")
            isolation = client.get(
                f"/api/chat/v2/sessions/{session_id}/messages",
                headers={"Authorization": f"Bearer {other_token}"},
            )
            assert isolation.status_code == 404

        running_id = client.app.state.agent.store.create_run(user["id"], session_id, None, "fashion_qa")
        cancel_response = client.post(f"/api/chat/v2/sessions/{session_id}/cancel", headers=headers)
        cancel_response.raise_for_status()
        assert cancel_response.json()["cancelled_runs"] == 1
        with connect_db() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT status FROM agent_runs WHERE id=%s", (running_id,))
                assert cursor.fetchone()["status"] == "cancelled"

        delete_response = client.delete(f"/api/chat/v2/sessions/{session_id}", headers=headers)
        delete_response.raise_for_status()
    cleanup()
    atexit.unregister(cleanup)
    test_memory_gate_e2e()
    print("agent e2e passed")


def test_memory_gate_e2e():
    username = f"memory_e2e_{uuid.uuid4().hex[:12]}"
    with connect_db() as connection:
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, "not-used"))
            user_id = cursor.lastrowid
        connection.commit()
    try:
        store = AgentStore(connect_db)
        session_id = store.create_session(user_id, "memory-e2e")["session_id"]
        last_message_id = None
        for turn in range(1, 11):
            text = "以后不要给我推荐全黑" if turn == 3 else f"第 {turn} 轮临时问题"
            last_message_id = store.add_message(
                user_id=user_id, session_id=session_id, role="user", content=text,
                client_message_id=str(uuid.uuid4()),
            )
        store.enqueue_memory_reviews(user_id, session_id, last_message_id, "第 10 轮临时问题", 10)
        with connect_db() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM memory_review_jobs WHERE user_id=%s AND review_type='gate'",
                    (user_id,),
                )
                job = cursor.fetchone()
        job["input"] = load_json(job.pop("input_json")) or {}

        class Config:
            long_term_memory_enabled = True
            text_model_provider = "deepseek"
            deepseek_api_key = ""
            ark_api_token = ""

        class Service:
            pass

        service = Service()
        service.store = store
        service.config = Config()
        operations = asyncio.run(MemoryWorker(service).review(job))
        store.finish_memory_review_job(job, operations)
        assert store.list_memories(user_id)[0]["memory_key"] == "outfit.color.all_black"
        context = store.session_context(user_id, session_id)
        assert context["last_memory_gate_turn"] == 10
    finally:
        with connect_db() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM users WHERE id=%s AND username=%s", (user_id, username))
            connection.commit()


if __name__ == "__main__":
    main()
