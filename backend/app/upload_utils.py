from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import settings


async def read_limited_upload(upload: UploadFile, max_mb: int) -> bytes:
    limit = max_mb * 1024 * 1024
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"上传文件不能超过 {max_mb} MB")
    if not data:
        raise HTTPException(status_code=400, detail="上传文件为空")
    return data


def validate_image(image: Image.Image, *, allow_animation: bool = True) -> None:
    width, height = image.size
    if width <= 0 or height <= 0 or width * height > settings.MAX_IMAGE_PIXELS:
        raise HTTPException(status_code=413, detail="图片像素尺寸过大")
    frames = int(getattr(image, "n_frames", 1))
    if not allow_animation and frames > 1:
        raise HTTPException(status_code=400, detail="该接口只支持静态图片")
    if frames > settings.MAX_GIF_FRAMES:
        raise HTTPException(status_code=413, detail="动图帧数过多")


def safe_image_extension(image: Image.Image) -> str:
    extension = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}.get((image.format or "").upper())
    if not extension:
        raise HTTPException(status_code=415, detail="仅支持 PNG、JPEG 或 WebP 图片")
    return extension


def ensure_within(path: Path, root: Path) -> Path:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise HTTPException(status_code=400, detail="文件路径不合法")
    return resolved_path


def open_validated_image(data: bytes, *, allow_animation: bool = True) -> Image.Image:
    try:
        image = Image.open(BytesIO(data))
        validate_image(image, allow_animation=allow_animation)
        image.verify()
        image = Image.open(BytesIO(data))
        validate_image(image, allow_animation=allow_animation)
        return image
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=415, detail="文件不是有效图片") from exc
