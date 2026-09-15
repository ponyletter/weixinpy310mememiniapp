"""Safe, delayed cleanup for temporary processing artifacts.

Successful user results and original sprite images are retained. Frames, ZIP
packages, thumbnails, debug images, and uploaded videos are temporary and are
removed after a grace period.
"""

import logging
import shutil
import time
from pathlib import Path

from app.config import settings


logger = logging.getLogger(__name__)
FAILED_MARKER = ".cleanup_failed"

# These files represent a usable result and must never be removed by the
# background cleanup job. A task directory containing one of them is retained
# even when a later optional step fails.
SUCCESS_ARTIFACT_NAMES = frozenset({
    "meme_result.gif",
    "compressed.gif",
    "compressed.jpg",
    "compressed.png",
    "card.png",
    "matting_result.png",
    "stitched.jpg",
})
PRESERVED_ARTIFACT_NAMES = SUCCESS_ARTIFACT_NAMES | frozenset({"input_sprite.png"})


def mark_failed_task_dir(task_dir: Path, reason: str = "") -> None:
    """Mark a failed task for delayed cleanup instead of deleting it inline."""
    try:
        task_dir.mkdir(parents=True, exist_ok=True)
        marker = task_dir / FAILED_MARKER
        marker.write_text((reason or "processing failed")[:2000], encoding="utf-8")
    except OSError:
        logger.warning("Unable to mark failed task directory: %s", task_dir, exc_info=True)


def _is_old(path: Path, cutoff: float) -> bool:
    try:
        return path.stat().st_mtime < cutoff
    except OSError:
        return False


def _has_success_artifact(task_dir: Path) -> bool:
    return any((task_dir / name).is_file() for name in SUCCESS_ARTIFACT_NAMES)


def _cleanup_old_intermediates(task_dir: Path, cutoff: float) -> tuple[int, int]:
    """Delete expired temporary files, returning (all_files, input_videos)."""
    removed = 0
    removed_inputs = 0
    for path in sorted(task_dir.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if (
            path.is_file()
            and path.name != FAILED_MARKER
            and path.name not in PRESERVED_ARTIFACT_NAMES
            and _is_old(path, cutoff)
        ):
            try:
                path.unlink()
                removed += 1
                if path.name.startswith("input_video."):
                    removed_inputs += 1
            except OSError:
                logger.debug("Unable to remove temporary artifact: %s", path, exc_info=True)
        elif path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass
    return removed, removed_inputs


def _cleanup_staged_images(cutoff: float) -> int:
    staging_root = settings.UPLOAD_DIR / "image_staging"
    if not staging_root.is_dir():
        return 0

    removed = 0
    for staged_file in staging_root.rglob("*.png"):
        if _is_old(staged_file, cutoff):
            try:
                staged_file.unlink()
                removed += 1
            except OSError:
                logger.debug("Unable to remove staged file: %s", staged_file, exc_info=True)
    return removed


def cleanup_stale_artifacts(now: float | None = None) -> dict[str, int]:
    """Remove only expired temporary artifacts and explicitly failed tasks.

    The function is deliberately conservative: it never removes an output
    directory merely because it is old, and it never removes a directory that
    contains a known successful result.
    """
    current_time = now if now is not None else time.time()
    cutoff = current_time - max(60, settings.TEMP_ARTIFACT_TTL_SECONDS)
    removed_inputs = 0
    removed_intermediates = 0
    removed_failed_tasks = 0
    removed_staged_images = _cleanup_staged_images(cutoff)

    output_root = settings.OUTPUT_DIR
    if not output_root.is_dir():
        return {
            "input_videos": removed_inputs,
            "intermediate_files": removed_intermediates,
            "failed_tasks": removed_failed_tasks,
            "staged_images": removed_staged_images,
        }

    for task_dir in output_root.iterdir():
        if not task_dir.is_dir() or not task_dir.name:
            continue

        cleaned, cleaned_inputs = _cleanup_old_intermediates(task_dir, cutoff)
        removed_intermediates += cleaned
        removed_inputs += cleaned_inputs

        marker = task_dir / FAILED_MARKER
        if marker.is_file() and _is_old(marker, cutoff):
            if _has_success_artifact(task_dir):
                # A later step may have failed after a usable result was
                # written. Keep the result and stop treating this as a failed
                # directory on subsequent cleanup passes.
                try:
                    marker.unlink()
                except OSError:
                    logger.debug("Unable to remove cleanup marker: %s", marker, exc_info=True)
                continue
            try:
                # task_dir is an immediate child of the configured output root;
                # no broad or unresolved recursive target is used here.
                shutil.rmtree(task_dir)
                removed_failed_tasks += 1
            except OSError:
                logger.warning("Unable to remove failed task directory: %s", task_dir, exc_info=True)

    return {
        "input_videos": removed_inputs,
        "intermediate_files": removed_intermediates,
        "failed_tasks": removed_failed_tasks,
        "staged_images": removed_staged_images,
    }
