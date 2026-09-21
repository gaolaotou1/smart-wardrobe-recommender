import asyncio
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agent_service.memory import review_memory_operations


class MemoryOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["upsert", "delete"] = "upsert"
    memory_type: Literal["preference", "avoidance", "wardrobe_fact", "correction", "habit", "episodic"]
    memory_key: str = Field(pattern=r"^[a-z0-9_.-]{3,191}$")
    content: str
    structured_value: dict = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)


class MemoryReview(BaseModel):
    operations: list[MemoryOperation] = Field(default_factory=list, max_length=5)


class MemoryWorker:
    def __init__(self, service):
        self.service = service

    async def run(self):
        while True:
            job = self.service.store.claim_memory_review_job()
            if not job:
                await asyncio.sleep(2)
                continue
            try:
                operations = await self.review(job)
                self.service.store.finish_memory_review_job(job, operations)
            except Exception as exc:
                self.service.store.fail_memory_review_job(job["id"], job["attempts"] + 1, exc.__class__.__name__)

    async def review(self, job):
        context = job["input"]
        if job["review_type"] == "gate":
            context = self.service.store.memory_gate_context(
                job["user_id"], job["session_id"], job["turn_to"] - job["turn_from"] + 1,
            )
        text = context.get("user_text", "")
        if not self.service.config.long_term_memory_enabled:
            return []
        from agent_service.chat.service import model_ready

        if not model_ready(self.service.config):
            messages = context.get("user_messages", [text])
            operations = [
                {"op": "upsert", **item}
                for message in messages
                for item in review_memory_operations(message)
            ]
            return list({item["memory_key"]: item for item in operations}.values())
        result = await self.service.text_model.structured(
            purpose="memory_review",
            model=self.service.config.fast_model,
            system=(
                "仅从用户原话中审查与衣橱/穿搭有关、未来可复用、明确表达的原子记忆。"
                "可用 upsert/delete/noop；冲突用同一 memory_key 的新 upsert 覆盖。"
                "不保存一次性条件、位置、身体信息、凭据或助手推测。无需写入时返回空 operations。"
            ),
            messages=[{"role": "user", "content": str(context)[:6_000]}],
            schema=MemoryReview.model_json_schema(),
        )
        review = MemoryReview.model_validate(result.content)
        return [item.model_dump(mode="json") for item in review.operations]
