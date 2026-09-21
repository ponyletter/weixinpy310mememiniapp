"""Cloudflare R2 publication helpers.

The mini program never talks to R2 directly.  The API server writes a result
to the local task directory first, publishes the completed artifact directory
to R2, and only then exposes the R2 URLs to the client.
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

from app.config import settings


logger = logging.getLogger(__name__)

# Only source material and final deliverables are durable objects.  Frame PNGs,
# ZIP packages, thumbnails, debug images, input videos and cleanup markers are
# deliberately excluded so a shared bucket is not filled by intermediates.
R2_FINAL_ARTIFACT_NAMES = frozenset({
    "meme_result.gif",
    "stickers_preview.gif",
    "stickers_pack.zip",
    "frames_pack.zip",
    "compressed.gif",
    "compressed.jpg",
    "compressed.png",
    "card.png",
    "matting_result.png",
    "stitched.jpg",
})
R2_SOURCE_ARTIFACT_NAMES = frozenset({
    "input_sprite.png",
    "original_image.png",
    "original_image.jpg",
})


def is_r2_enabled() -> bool:
    return bool(
        settings.R2_ENABLED
        and settings.R2_ENDPOINT_URL
        and settings.R2_ACCESS_KEY_ID
        and settings.R2_SECRET_ACCESS_KEY
        and settings.R2_BUCKET
        and settings.R2_PUBLIC_BASE_URL
    )


def _client():
    if not is_r2_enabled():
        raise RuntimeError("R2 is not configured")
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - dependency is installed in production
        raise RuntimeError("R2 已启用，但服务器缺少 boto3 依赖") from exc

    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL.rstrip("/"),
        region_name=settings.R2_REGION,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    )


def _public_url(key: str) -> str:
    encoded_key = quote(key.lstrip("/"), safe="/~.-_")
    return f"{settings.R2_PUBLIC_BASE_URL.rstrip('/')}/{encoded_key}"


def task_object_key(task_id: str, relative_path: str) -> str:
    prefix = settings.R2_TASK_PREFIX.strip("/")
    relative = relative_path.replace("\\", "/").lstrip("/")
    return f"{prefix}/{task_id}/{relative}" if prefix else f"{task_id}/{relative}"


def task_public_url(task_id: str, relative_path: str) -> str:
    return _public_url(task_object_key(task_id, relative_path))


def _content_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _upload_file(client, path: Path, bucket: str, key: str) -> None:
    client.upload_file(
        str(path),
        bucket,
        key,
        ExtraArgs={
            "ContentType": _content_type(path),
            "CacheControl": "public, max-age=31536000, immutable",
        },
    )


def _is_durable_artifact(name: str) -> bool:
    return name in (R2_FINAL_ARTIFACT_NAMES | R2_SOURCE_ARTIFACT_NAMES) or (name.startswith("sticker_") and name.endswith(".png"))


def cleanup_local_intermediates(task_dir: Path) -> None:
    """Remove non-durable processing files after a successful R2 publish."""
    for path in sorted(task_dir.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_file() and not _is_durable_artifact(path.name):
            path.unlink(missing_ok=True)
        elif path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass


async def publish_task_directory(task_id: str, task_dir: Path) -> dict[str, str]:
    """Upload every completed task artifact and return relative-path URLs.

    An empty mapping means R2 is disabled, which keeps local development and
    the existing local-output fallback working.  When R2 is enabled, any
    upload error is raised so a task cannot be reported as completed before
    its public artifacts are actually available.
    """
    if not is_r2_enabled():
        return {}

    files = sorted(
        path for path in task_dir.rglob("*")
        if path.is_file()
        and _is_durable_artifact(path.name)
    )
    if not files:
        raise RuntimeError(f"R2 发布失败：任务目录为空 ({task_id})")

    client = await asyncio.to_thread(_client)
    published: dict[str, str] = {}
    for path in files:
        relative = path.relative_to(task_dir).as_posix()
        key = task_object_key(task_id, relative)
        await asyncio.to_thread(_upload_file, client, path, settings.R2_BUCKET, key)
        published[relative] = _public_url(key)
    logger.info("[%s] published %d artifacts to R2", task_id, len(published))
    return published


async def publish_avatar(path: Path, filename: str) -> str:
    """Publish one avatar and return its public URL when R2 is enabled."""
    if not is_r2_enabled():
        return ""
    prefix = settings.R2_AVATAR_PREFIX.strip("/")
    key = f"{prefix}/{filename}" if prefix else filename
    client = await asyncio.to_thread(_client)
    await asyncio.to_thread(_upload_file, client, path, settings.R2_BUCKET, key)
    return _public_url(key)


def is_public_r2_url(value: str) -> bool:
    if not value or not settings.R2_PUBLIC_BASE_URL:
        return False
    expected = urlsplit(settings.R2_PUBLIC_BASE_URL)
    actual = urlsplit(value)
    return (
        actual.scheme == "https"
        and actual.netloc == expected.netloc
        and actual.path.startswith(expected.path.rstrip("/") + "/")
    )


def attach_r2_urls(value: Any, task_id: str, published: dict[str, str]) -> Any:
    """Attach r2_url while preserving relative /outputs URLs for backward compatibility.

    Old miniapp versions in production directly prepend baseURL: `${baseURL}${gifPath}`.
    If the API returns an absolute HTTPS URL, old miniapps produce malformed URLs
    like `https://api.domain.comhttps://r2.domain.com/...`, leading to blank preview.
    By keeping `/outputs/{task_id}/...` as the primary URL, old miniapps cleanly resolve
    `${baseURL}/outputs/...`, while newly submitted miniapps (using `toAbsoluteUrl`)
    also cleanly resolve `${baseURL}/outputs/...`.
    """
    if not published:
        return value
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            result[k] = attach_r2_urls(v, task_id, published)
        for key in ("gif_url", "output_url", "image_url", "thumb_url", "zip_url", "input_url", "original_image_url"):
            val = result.get(key)
            if isinstance(val, str) and val:
                filename = Path(val).name
                if filename in published:
                    if key in ("gif_url", "output_url", "image_url"):
                        result.setdefault("r2_url", published[filename])
                    if val.startswith("http://") or val.startswith("https://"):
                        result[key] = f"/outputs/{task_id}/{filename}"
        return result
    if isinstance(value, list):
        return [attach_r2_urls(item, task_id, published) for item in value]
    if isinstance(value, tuple):
        return tuple(attach_r2_urls(item, task_id, published) for item in value)
    return value


def rewrite_output_urls(value: Any, task_id: str, published: dict[str, str]) -> Any:
    """Compatibility wrapper preserving relative URLs and attaching r2_url."""
    return attach_r2_urls(value, task_id, published)


async def publish_and_rewrite(task_id: str, task_dir: Path, payload: Any) -> Any:
    published = await publish_task_directory(task_id, task_dir)
    if published:
        await asyncio.to_thread(cleanup_local_intermediates, task_dir)
    return attach_r2_urls(payload, task_id, published)
