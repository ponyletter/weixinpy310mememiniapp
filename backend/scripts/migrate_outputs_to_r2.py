#!/usr/bin/env python3
"""Migrate existing output artifacts to R2 and remove intermediates.

Default mode is a read-only plan.  Apply changes with:

    python scripts/migrate_outputs_to_r2.py --apply --clean

Only output directories that physically exist below ``settings.OUTPUT_DIR``
are considered.  Existing R2 objects belonging to those same directory names
are reduced to final artifacts; objects for other projects are untouched.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from app.config import settings
from app.r2_storage import (
    R2_FINAL_ARTIFACT_NAMES,
    R2_SOURCE_ARTIFACT_NAMES,
    _client,
    _upload_file,
    is_r2_enabled,
    task_object_key,
    task_public_url,
)


def output_reference(value: str) -> tuple[str, str] | None:
    if not value:
        return None
    path = urlsplit(value).path
    marker = "/outputs/"
    if marker not in path:
        return None
    relative = path.split(marker, 1)[1].strip("/")
    parts = relative.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    return parts[0], parts[1]


def final_reference(task_id: str, relative: str, available: set[str]) -> str | None:
    """Return a durable R2 URL for an old local output reference."""
    if relative in R2_FINAL_ARTIFACT_NAMES and relative in available:
        return task_public_url(task_id, relative)
    # Old collection covers and thumbnails point at derivatives that are no
    # longer published.  The final GIF is the durable replacement.
    if "meme_result.gif" in available:
        if relative == "thumb.jpg" or relative == "frames_pack.zip" or relative.startswith("frames/"):
            return task_public_url(task_id, "meme_result.gif")
    return None


def remove_non_durable_files(directory: Path, allowed: set[str]) -> int:
    removed = 0
    for path in sorted(directory.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_file() and path.relative_to(directory).as_posix() not in allowed:
            path.unlink(missing_ok=True)
            removed += 1
        elif path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass
    return removed


def remove_r2_objects(client, task_id: str, keep_keys: set[str], apply: bool) -> int:
    prefix = f"{settings.R2_TASK_PREFIX.strip('/')}/{task_id}/"
    stale = []
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=settings.R2_BUCKET, Prefix=prefix):
        for item in page.get("Contents", []):
            if item["Key"] not in keep_keys:
                stale.append(item["Key"])
    if apply and stale:
        for start in range(0, len(stale), 1000):
            client.delete_objects(
                Bucket=settings.R2_BUCKET,
                Delete={"Objects": [{"Key": key} for key in stale[start:start + 1000]]},
            )
    return len(stale)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="迁移本项目历史输出到 Cloudflare R2 并清理中间文件")
    parser.add_argument("--apply", action="store_true", help="实际上传、更新数据库并删除文件；默认仅预览")
    parser.add_argument("--clean", action="store_true", help="成功上传后删除本地中间文件和无成品的测试目录")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not is_r2_enabled():
        print("R2 未启用或配置不完整")
        return 1

    output_root = settings.OUTPUT_DIR.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    directories = sorted(path for path in output_root.iterdir() if path.is_dir())
    conn = sqlite3.connect(str(settings.DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    statuses = {
        row["task_id"]: row["status"]
        for row in conn.execute("SELECT task_id, status FROM meme_tasks")
    }

    plans: dict[str, set[str]] = {}
    skipped_active = 0
    for directory in directories:
        if statuses.get(directory.name) in {"processing", "pending"}:
            skipped_active += 1
            continue
        is_showcase = directory.name.startswith("showcase_")
        allowed: set[str] = set()
        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(directory).as_posix()
            name = path.name
            if name in R2_FINAL_ARTIFACT_NAMES or (name in R2_SOURCE_ARTIFACT_NAMES and not is_showcase):
                allowed.add(relative)
        if allowed:
            plans[directory.name] = allowed

    total_upload_bytes = sum(
        (output_root / task_id / relative).stat().st_size
        for task_id, files in plans.items()
        for relative in files
    )
    print(
        f"计划目录={len(plans)} 上传文件={sum(len(files) for files in plans.values())} "
        f"上传大小={total_upload_bytes / 1024 / 1024:.2f}MB 跳过活动任务={skipped_active}"
    )
    if not args.apply:
        print("当前为预览模式，未上传、未修改数据库、未删除文件。")
        conn.close()
        return 0

    client = _client()
    uploaded: dict[str, set[str]] = {}
    try:
        for task_id, files in plans.items():
            directory = output_root / task_id
            uploaded[task_id] = set()
            for relative in sorted(files):
                path = directory / relative
                key = task_object_key(task_id, relative)
                _upload_file(client, path, settings.R2_BUCKET, key)
                uploaded[task_id].add(key)

        # Update all persisted links that point to this project's old local
        # output paths, including official showcase collection entries.
        for task_id, files in plans.items():
            available = {Path(relative).name for relative in files}
            gif_url = task_public_url(task_id, "meme_result.gif") if "meme_result.gif" in available else None
            sprite_url = task_public_url(task_id, "input_sprite.png") if "input_sprite.png" in available else None
            if task_id in statuses and gif_url:
                if sprite_url:
                    conn.execute(
                        "UPDATE meme_tasks SET gif_url = ?, sprite_url = ? WHERE task_id = ?",
                        (gif_url, sprite_url, task_id),
                    )
                else:
                    conn.execute("UPDATE meme_tasks SET gif_url = ? WHERE task_id = ?", (gif_url, task_id))

            for row in conn.execute("SELECT id, gif_url FROM collection_items").fetchall():
                reference = output_reference(row["gif_url"] or "")
                if not reference or reference[0] != task_id:
                    continue
                replacement = final_reference(task_id, reference[1], available)
                if replacement:
                    conn.execute("UPDATE collection_items SET gif_url = ? WHERE id = ?", (replacement, row["id"]))

            for row in conn.execute("SELECT collection_id, cover_url FROM collections").fetchall():
                reference = output_reference(row["cover_url"] or "")
                if not reference or reference[0] != task_id:
                    continue
                replacement = final_reference(task_id, reference[1], available)
                if replacement:
                    conn.execute("UPDATE collections SET cover_url = ? WHERE collection_id = ?", (replacement, row["collection_id"]))
        conn.commit()

        stale_count = 0
        for task_id, keep_keys in uploaded.items():
            stale_count += remove_r2_objects(client, task_id, keep_keys, apply=True)

        removed_local = 0
        removed_dirs = 0
        if args.clean:
            for directory in directories:
                if directory.name in statuses and statuses[directory.name] in {"processing", "pending"}:
                    continue
                allowed = plans.get(directory.name)
                if allowed:
                    removed_local += remove_non_durable_files(directory, allowed)
                else:
                    # These are failed/test-only directories with no durable
                    # artifact. The target is an immediate child of outputs.
                    shutil.rmtree(directory)
                    removed_dirs += 1
            for path in output_root.iterdir():
                if path.is_file() and path.name.startswith("test_"):
                    path.unlink()
                    removed_local += 1

        print(
            f"迁移完成：目录={len(uploaded)} R2保留对象={sum(len(v) for v in uploaded.values())} "
            f"删除R2中间对象={stale_count} 本地删除文件={removed_local} 删除目录={removed_dirs}"
        )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
