import base64
import os
import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError


MAX_IMAGE_BYTES = 10 * 1024 * 1024
MIN_IMAGE_SIDE = 14
FORMAT_TO_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
FORMAT_TO_SUFFIX = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


class LocalAttachmentStore:
    def __init__(self, root: str | None = None):
        configured = root or os.environ.get("AGENT_UPLOAD_DIR", "./data/agent_uploads")
        self.root = Path(configured).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save_image(self, user_id: int, content: bytes) -> dict:
        image_format, width, height = inspect_image(content)
        upload_id = f"up_{uuid.uuid4().hex}"
        user_dir = self.root / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        path = user_dir / f"{upload_id}{FORMAT_TO_SUFFIX[image_format]}"
        path.write_bytes(content)
        return {
            "upload_id": upload_id,
            "mime_type": FORMAT_TO_MIME[image_format],
            "size": len(content),
            "width": width,
            "height": height,
        }

    def data_url(self, user_id: int, upload_id: str) -> str:
        if not upload_id.startswith("up_") or len(upload_id) != 35:
            raise ValueError("附件引用无效")
        user_dir = self.root / str(user_id)
        matches = [
            path
            for suffix in FORMAT_TO_SUFFIX.values()
            if (path := user_dir / f"{upload_id}{suffix}").is_file()
        ]
        if len(matches) != 1:
            raise ValueError("附件不存在或不属于当前用户")
        content = matches[0].read_bytes()
        image_format, _, _ = inspect_image(content)
        encoded = base64.b64encode(content).decode("ascii")
        return f"data:{FORMAT_TO_MIME[image_format]};base64,{encoded}"


def inspect_image(content: bytes) -> tuple[str, int, int]:
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise ValueError("图片大小必须在 1 B 到 10 MB 之间")
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            image_format = image.format or ""
            width, height = image.size
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("附件不是有效图片") from exc
    if image_format not in FORMAT_TO_MIME:
        raise ValueError("仅支持 JPEG、PNG 和 WebP 图片")
    if min(width, height) < MIN_IMAGE_SIDE:
        raise ValueError("图片宽高不得小于 14 像素")
    return image_format, width, height
