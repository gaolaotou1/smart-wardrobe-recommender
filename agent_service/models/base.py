from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StructuredModelResult:
    content: dict
    raw_text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_hit_tokens: int | None = None
    cache_miss_tokens: int | None = None


class ModelPort(Protocol):
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
        ...
