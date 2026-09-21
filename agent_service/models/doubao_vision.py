import base64
import binascii
import ipaddress
import json
import os
import socket
import time
from typing import Literal
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field

from agent_service.logging import get_logger


logger = get_logger()


class ImageAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal["上装", "下装", "套装", "未知"]
    sub_category: str = ""
    semantic_role: Literal["top", "bottom", "suit", "outerwear", "unknown"]
    style: list[str] = Field(default_factory=list)
    colors: list[str] = Field(default_factory=list)
    season: list[str] = Field(default_factory=list)
    material_guess: list[str] = Field(default_factory=list)
    occasion: list[str] = Field(default_factory=list)
    description: str
    uncertain_fields: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class DoubaoVisionPort:
    def __init__(self, token: str | None = None, base_url: str | None = None, model: str | None = None):
        self.token = token or os.environ.get("ARK_API_TOKEN", "")
        base = base_url or os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
        self.url = base.rstrip("/") + "/responses"
        self.model = model or os.environ.get("ARK_MODEL", "doubao-seed-2-0-lite-260428")

    async def analyze(self, image_url: str, task: str = "识别这件衣物的属性") -> ImageAnalysis:
        is_data_url = image_url.startswith("data:")
        validate_data_image_url(image_url) if is_data_url else validate_public_https_url(image_url)
        if not self.token:
            raise RuntimeError("ARK_API_TOKEN 未配置")
        schema = ImageAnalysis.model_json_schema()
        prompt = (
            "你是衣物图像属性分析器。不可见或不可靠的材质必须放入 uncertain_fields。"
            f"任务：{task}。只返回符合此 Schema 的 JSON：{json.dumps(schema, ensure_ascii=False)}"
        )
        payload = {
            "model": self.model,
            "input": [{
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": image_url},
                    {"type": "input_text", "text": prompt},
                ],
            }],
            "reasoning": {"effort": "none"},
        }
        started = time.perf_counter()
        logger.info("model_call_started", provider="doubao", model=self.model, purpose="image_analysis")
        async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
            if not is_data_url:
                metadata = await client.head(image_url)
                metadata.raise_for_status()
                content_type = metadata.headers.get("content-type", "").split(";", 1)[0].lower()
                content_length = int(metadata.headers.get("content-length", "0") or 0)
                if not content_type.startswith("image/"):
                    raise ValueError("附件 URL 不是图片")
                if content_length > 10 * 1024 * 1024:
                    raise ValueError("附件图片超过 10 MB")
            response = await client.post(
                self.url,
                headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
        raw = response.json()
        text = response_output_text(raw)
        analysis = ImageAnalysis.model_validate_json(text)
        usage = raw.get("usage", {})
        logger.info(
            "model_call_finished",
            provider="doubao",
            model=self.model,
            purpose="image_analysis",
            status="succeeded",
            http_status=response.status_code,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
        return analysis


def response_output_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    for output in payload.get("output", []):
        for content in output.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                return content["text"]
    raise ValueError("豆包响应中没有文本结果")


def validate_public_https_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("图片必须是不含凭据的 HTTPS URL")
    hostname = parsed.hostname.lower()
    if is_trusted_image_host(hostname):
        return
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, 443)}
    except socket.gaierror as exc:
        raise ValueError("图片域名无法解析") from exc
    if any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("图片 URL 不得指向本地或私有网络")


def validate_data_image_url(value: str) -> None:
    try:
        header, encoded = value.split(",", 1)
        if header not in {"data:image/jpeg;base64", "data:image/png;base64", "data:image/webp;base64"}:
            raise ValueError
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("本地附件编码无效") from exc
    if not content or len(content) > 10 * 1024 * 1024:
        raise ValueError("本地附件超过 10 MB")


def is_trusted_image_host(hostname: str) -> bool:
    configured = os.environ.get(
        "AGENT_TRUSTED_IMAGE_HOSTS",
        "ark-project.tos-cn-beijing.volces.com,.imgdb.cn",
    )
    for rule in (item.strip().lower() for item in configured.split(",")):
        if not rule:
            continue
        if hostname == rule.lstrip(".") or (rule.startswith(".") and hostname.endswith(rule)):
            return True
    return False
