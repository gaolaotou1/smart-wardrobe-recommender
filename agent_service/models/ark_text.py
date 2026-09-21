import json
import os
import time

import httpx

from .base import StructuredModelResult
from .doubao_vision import response_output_text
from agent_service.logging import get_logger


logger = get_logger()


class ArkTextModelPort:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        self.token = api_key or os.environ.get("ARK_API_TOKEN", "")
        self.model = model or os.environ.get("ARK_TEXT_MODEL", "doubao-seed-2-0-lite-260428")
        base = base_url or os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
        self.url = base.rstrip("/") + "/responses"

    async def structured(self, *, purpose, system, messages, schema, model=None, timeout_seconds=60):
        if not self.token:
            raise RuntimeError("ARK_API_TOKEN 未配置")
        input_messages = [{"role": "system", "content": system}, *messages]
        input_messages.append({
            "role": "user",
            "content": "仅返回符合这份 JSON Schema 的 JSON 对象："
            + json.dumps(schema, ensure_ascii=False, separators=(",", ":")),
        })
        selected_model = model or self.model
        payload = {
            "model": selected_model,
            "input": input_messages,
            "reasoning": {"effort": "none"},
        }
        started = time.perf_counter()
        logger.info("model_call_started", provider="ark", model=selected_model, purpose=purpose)
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=False) as client:
            response = await client.post(
                self.url,
                headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
        body = response.json()
        raw_text = response_output_text(body)
        content = json.loads(raw_text)
        usage = body.get("usage", {})
        input_details = usage.get("input_tokens_details", {})
        logger.info(
            "model_call_finished",
            provider="ark",
            model=selected_model,
            purpose=purpose,
            status="succeeded",
            http_status=response.status_code,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
        return StructuredModelResult(
            content=content,
            raw_text=raw_text,
            model=selected_model,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            cache_hit_tokens=input_details.get("cached_tokens"),
        )
