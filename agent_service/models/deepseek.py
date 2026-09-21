import json
import os
import time

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from .base import StructuredModelResult
from agent_service.logging import get_logger


logger = get_logger()


class ModelResponseError(RuntimeError):
    pass


class DeepSeekModelPort:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = base_url or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = model or os.environ.get("AGENT_MODEL", "deepseek-v4-flash")
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url) if self.api_key else None

    @retry(
        retry=retry_if_exception_type((APITimeoutError, APIConnectionError)),
        wait=wait_random_exponential(multiplier=0.5, max=4),
        stop=stop_after_attempt(2),
        reraise=True,
    )
    async def structured(
        self,
        *,
        purpose: str,
        system: str,
        messages: list[dict],
        schema: dict,
        model: str | None = None,
        timeout_seconds: int = 60,
    ) -> StructuredModelResult:
        if not self.client:
            raise ModelResponseError("DEEPSEEK_API_KEY 未配置")

        selected_model = model or self.model
        started = time.perf_counter()
        logger.info("model_call_started", provider="deepseek", model=selected_model, purpose=purpose)
        response = await self.client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system},
                *messages,
                {
                    "role": "user",
                    "content": "仅返回符合下列 JSON Schema 的 JSON 对象，不要 Markdown 或解释："
                    + json.dumps(schema, ensure_ascii=False, separators=(",", ":")),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            timeout=timeout_seconds,
            extra_body={"thinking": {"type": "disabled"}},
        )
        choice = response.choices[0]
        raw_text = choice.message.content or ""
        if choice.finish_reason == "length" or not raw_text.strip():
            raise ModelResponseError("模型 JSON 为空或被截断")
        try:
            content = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ModelResponseError("模型未返回合法 JSON") from exc

        usage = response.usage
        prompt_details = getattr(usage, "prompt_tokens_details", None)
        logger.info(
            "model_call_finished",
            provider="deepseek",
            model=selected_model,
            purpose=purpose,
            status="succeeded",
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
        return StructuredModelResult(
            content=content,
            raw_text=raw_text,
            model=selected_model,
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            cache_hit_tokens=getattr(prompt_details, "cached_tokens", None),
            cache_miss_tokens=None,
        )
