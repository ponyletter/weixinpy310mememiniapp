import logging
import re
import asyncio
import uuid
import shutil
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from PIL import Image

from app.config import settings
from app.core.sprite_processor import SpriteProcessor
from app.core.prompt_templates import (
    PROMPT_TEMPLATES,
    get_active_templates,
    SCENE_TEXT_PACKAGES,
    SCENE_TEXT_TITLES,
    EMOTION_TAGS_16,
    build_sticker16_prompt,
)
from app.core.wechat_service import WeChatService
from app.services.audit_meme_generator import create_audit_meme_gif
from app.services.audit_sticker_generator import create_audit_stickers
from app.database import (
    check_and_deduct_quota,
    refund_quota,
    get_db,
    delete_meme_task,
    meme_task_output_is_referenced,
    rename_meme_task,
    get_estimated_generation_duration,
    format_datetime_china,
    is_audit_mode_active,
    set_app_setting,
)
from app.security import CurrentOpenid, require_same_user
from app.storage_cleanup import mark_failed_task_dir
from app.upload_utils import open_validated_image, read_limited_upload
from app.r2_storage import (
    R2_FINAL_ARTIFACT_NAMES,
    R2_SOURCE_ARTIFACT_NAMES,
    is_public_r2_url,
    is_r2_enabled,
    publish_and_rewrite,
    task_public_url,
)
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["Meme GIF"])
logger = logging.getLogger(__name__)

@router.get("/templates")
def get_templates():
    """获取预设动作模版列表与提示词（审核模式下自动展示去敏合规动作列表）"""
    data = []
    for t in get_active_templates():
        data.append({
            "id": t["id"],
            "title": t["title"],
            "desc": t["desc"],
            "action": t["action"],
            "default_caption": t["default_caption"],
            "is_custom": t.get("is_custom", False)
        })
    return {
        "code": 0,
        "message": "success",
        "data": data
    }

@router.post("/prompt-builder")
def build_prompt(
    character_desc: str = Form(""),
    action_type: str = Form("kiss"),
    custom_caption: str = Form(""),
    has_image: bool = Form(False),
    is_sketch: bool = Form(False),
    custom_action: str = Form(""),
):
    """根据动作与角色描述，动态生成让 ChatGPT 原生绘制动态跳跃汉字的专用 Prompt"""
    templates = get_active_templates()
    template = next((t for t in templates if t["id"] == action_type), templates[0])
    final_prompt = template["prompt_builder"](character_desc.strip(), custom_caption.strip(), has_image, is_sketch, custom_action.strip())

    return {
        "code": 0,
        "data": {
            "template_id": template["id"],
            "action": template["action"],
            "caption": custom_caption.strip(),
            "generated_prompt": final_prompt
        }
    }

@router.post("/process-sprite")
async def process_sprite_sheet(
    current_openid: CurrentOpenid,
    file: Optional[UploadFile] = File(None),
    sample_id: Optional[str] = Form(None),
    fps: int = Form(8),
    make_transparent: bool = Form(True),
    padding_percent: float = Form(2.5),
):
    """处理已有的 4x4 雪碧图：多尺度间隙切割 + 泛洪去白底 + 微信合规动图合成"""
    task_id = uuid.uuid4().hex
    task_dir = settings.OUTPUT_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    input_path = task_dir / "input_sprite.png"

    if not 1 <= fps <= 30 or not 0 <= padding_percent <= 20:
        raise HTTPException(status_code=400, detail="fps 或边距参数超出允许范围")

    # 获取输入图像
    if file and file.filename:
        image_bytes = await read_limited_upload(file, settings.MAX_IMAGE_UPLOAD_MB)
        source_image = open_validated_image(image_bytes, allow_animation=False).convert("RGB")
        source_image.save(input_path, format="PNG")
    elif sample_id:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", sample_id):
            raise HTTPException(status_code=400, detail="样本 ID 不合法")
        sample_path = settings.SAMPLES_DIR / f"{sample_id}.png"
        if not sample_path.exists():
            png_list = list(settings.SAMPLES_DIR.glob("*.png"))
            if not png_list:
                raise HTTPException(status_code=404, detail="样本文件不存在")
            sample_path = png_list[0]
        shutil.copy(sample_path, input_path)
        source_image = Image.open(input_path).convert("RGB")
    else:
        raise HTTPException(status_code=400, detail="请上传文件或选择有效样本")

    # 1. 执行多尺度主间隙网格切割与紧致裁剪
    frames = await asyncio.to_thread(
        SpriteProcessor.slice_grid,
        source_image,
        rows=4,
        cols=4,
        padding_percent=padding_percent,
    )

    # 2. 生成透明动图 GIF (完美保留原画原生字幕)
    gif_path = task_dir / "meme_result.gif"
    stats = await asyncio.to_thread(
        SpriteProcessor.assemble_gif,
        frames=frames,
        output_path=str(gif_path),
        fps=fps,
        make_transparent=make_transparent
    )

    # 3. 生成 16 帧独立 PNG ZIP 包
    zip_path = task_dir / "frames_pack.zip"
    await asyncio.to_thread(
        SpriteProcessor.package_zip,
        frames=frames,
        output_path=str(zip_path),
        make_transparent=make_transparent
    )

    # 4. 保存缩略帧供前端 16 帧画廊预览
    frame_preview_urls = []
    frames_dir = task_dir / "frames"
    frames_dir.mkdir(exist_ok=True)
    for idx, f in enumerate(frames, 1):
        f_thumb_path = frames_dir / f"frame_{idx:02d}.png"
        f_clean = SpriteProcessor.remove_white_bg(f) if make_transparent else f
        f_clean.save(f_thumb_path, format="PNG")
        frame_preview_urls.append(f"/outputs/{task_id}/frames/frame_{idx:02d}.png")

    # 返回成功前确认国内节点已经具备完整产物，避免用户点击后仍看到旧缓存或空目录。
    if not await sync_task_outputs_with_retry(task_id, task_dir):
        raise HTTPException(status_code=503, detail="动图已生成，但同步到国内节点失败，请稍后重试")

    payload = {
        "code": 0,
        "message": "success",
        "data": {
            "task_id": task_id,
            "gif_url": f"/outputs/{task_id}/meme_result.gif",
            "zip_url": f"/outputs/{task_id}/frames_pack.zip",
            "input_url": f"/outputs/{task_id}/input_sprite.png",
            "frames": frame_preview_urls,
            "stats": stats
        }
    }
    return await publish_and_rewrite(task_id, task_dir, payload)

@router.post("/generate-and-process")
async def generate_and_process(
    current_openid: CurrentOpenid,
    ref_image: Optional[UploadFile] = File(None),
    action_type: str = Form("kiss"),
    custom_caption: str = Form(""),
    character_desc: str = Form(""),
    custom_action: str = Form(""),
    fps: int = Form(8),
    make_transparent: bool = Form(True),
    padding_percent: float = Form(2.5),
):
    """一键调用 ChatGPT Plus (Images 2.5) 生成 16 宫格雪碧图，并直接切片制作成透明 GIF"""
    raise HTTPException(status_code=410, detail="同步生成接口已停用，请使用 /api/generate-async")
    import io
    import base64
    import httpx

    # 1. 组装提示词
    has_image = ref_image is not None and getattr(ref_image, "filename", None) not in [None, ""]
    template = next((t for t in PROMPT_TEMPLATES if t["id"] == action_type), PROMPT_TEMPLATES[0])
    prompt = template["prompt_builder"](character_desc.strip(), custom_caption.strip(), has_image, False, custom_action.strip())

    # 2. 调用 CLIProxyAPI (ChatGPT Plus 出海中转网关)
    headers = {
        "Authorization": f"Bearer {settings.CPA_API_KEY}"
    }

    try:
        async with httpx.AsyncClient(timeout=150.0) as client:
            if has_image:
                ref_bytes = await ref_image.read()
                ref_img_pil = Image.open(io.BytesIO(ref_bytes)).convert("RGBA")
                buf = io.BytesIO()
                ref_img_pil.save(buf, format="PNG")
                buf.seek(0)
                files = {
                    "image": ("character.png", buf.getvalue(), "image/png")
                }
                data = {
                    "model": settings.CPA_IMAGE_MODEL,
                    "prompt": prompt,
                    "n": "1",
                    "size": "1024x1024"
                }
                resp = await client.post(
                    f"{settings.CPA_API_BASE}/images/edits",
                    headers=headers,
                    data=data,
                    files=files
                )
            else:
                payload = {
                    "model": settings.CPA_IMAGE_MODEL,
                    "prompt": prompt,
                    "n": 1,
                    "size": "1024x1024"
                }
                resp = await client.post(
                    f"{settings.CPA_API_BASE}/images/generations",
                    headers={**headers, "Content-Type": "application/json"},
                    json=payload
                )

            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"动图生成服务异常 ({resp.status_code}): {resp.text}")
            resp_data = resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="动图生成超时 (超过150秒)，请稍后重试")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"请求服务网关失败: {str(e)}")

    # 3. 解析图片数据
    item = resp_data.get("data", [{}])[0]
    if "b64_json" in item:
        img_bytes = base64.b64decode(item["b64_json"])
        source_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    elif "url" in item:
        async with httpx.AsyncClient(timeout=60.0) as client:
            img_res = await client.get(item["url"])
            source_image = Image.open(io.BytesIO(img_res.content)).convert("RGB")
    else:
        raise HTTPException(status_code=502, detail="未能获取生成的图片数据")

    # 4. 初始化任务目录
    task_id = uuid.uuid4().hex
    task_dir = settings.OUTPUT_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    input_path = task_dir / "input_sprite.png"
    source_image.save(input_path, format="PNG")

    # 5. 执行 16 帧主间隙网格切割与紧致裁剪
    frames = SpriteProcessor.slice_grid(source_image, rows=4, cols=4, padding_percent=padding_percent)

    # 6. 生成透明动图 GIF
    gif_path = task_dir / "meme_result.gif"
    stats = SpriteProcessor.assemble_gif(
        frames=frames,
        output_path=str(gif_path),
        fps=fps,
        make_transparent=make_transparent
    )

    # 7. 生成 16 帧独立 PNG ZIP 包
    zip_path = task_dir / "frames_pack.zip"
    SpriteProcessor.package_zip(
        frames=frames,
        output_path=str(zip_path),
        make_transparent=make_transparent
    )

    # 8. 保存缩略帧供前端展示
    frame_preview_urls = []
    frames_dir = task_dir / "frames"
    frames_dir.mkdir(exist_ok=True)
    for idx, f in enumerate(frames, 1):
        f_thumb_path = frames_dir / f"frame_{idx:02d}.png"
        f_clean = SpriteProcessor.remove_white_bg(f) if make_transparent else f
        f_clean.save(f_thumb_path, format="PNG")
        frame_preview_urls.append(f"/outputs/{task_id}/frames/frame_{idx:02d}.png")

    return {
        "code": 0,
        "message": "success",
        "data": {
            "task_id": task_id,
            "gif_url": f"/outputs/{task_id}/meme_result.gif",
            "zip_url": f"/outputs/{task_id}/frames_pack.zip",
            "input_url": f"/outputs/{task_id}/input_sprite.png",
            "prompt_used": prompt,
            "frames": frame_preview_urls,
            "stats": stats
        }
    }

# 全局异步任务存储
TASK_STORE: dict[str, dict] = {}


def _set_task_progress(
    task_id: str,
    openid: str,
    progress: int,
    stage: str,
    stage_text: str,
) -> None:
    """同时写入内存和数据库，确保多 worker 轮询时也能看到阶段进度。"""
    estimated_duration = get_estimated_generation_duration()
    TASK_STORE[task_id] = {
        "openid": openid,
        "status": "processing",
        "progress": progress,
        "stage": stage,
        "stage_text": stage_text,
        "estimated_duration": estimated_duration,
    }
    try:
        with get_db() as conn:
            conn.execute(
                "UPDATE meme_tasks SET status = 'processing', progress = ?, error_message = '' "
                "WHERE task_id = ? AND openid = ?",
                (progress, task_id, openid),
            )
            conn.commit()
    except Exception:
        # 数据库记录失败不应中断生成任务，内存状态仍可供当前 worker 使用。
        logger.warning("Unable to persist progress for task %s", task_id, exc_info=True)

async def sync_task_outputs_to_domestic(task_id: str, task_dir: Path) -> bool:
    """
    确保动图产物在 /var/www/outputs/{task_id} 就绪。
    如果是本地部署在国内腾讯云，直接本地复制/确保就绪；
    如果是美区沙箱开发，则通过 scp 推送到国内腾讯云。
    返回 True 代表目标节点已经同步完成，未配置同步时也视为成功。
    """
    try:
        durable_names = R2_FINAL_ARTIFACT_NAMES | R2_SOURCE_ARTIFACT_NAMES
        files = sorted(
            path for path in task_dir.rglob("*")
            if path.is_file() and (not is_r2_enabled() or path.name in durable_names)
        )
        local_root = Path(settings.OUTPUT_SYNC_LOCAL_DIR) if settings.OUTPUT_SYNC_LOCAL_DIR else None
        local_target = local_root / task_id if local_root else None
        if local_root:
            local_root.mkdir(parents=True, exist_ok=True)
            if local_target.resolve() != task_dir.resolve():
                for source in files:
                    destination = local_target / source.relative_to(task_dir)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(source), str(destination))
            return True

        if not settings.OUTPUT_SYNC_HOST:
            return True
        remote_dir = f"{settings.OUTPUT_SYNC_DIR.rstrip('/')}/{task_id}"
        remote_dest = f"{settings.OUTPUT_SYNC_HOST}:{remote_dir}/"
        proc = await asyncio.create_subprocess_exec(
            "ssh", "-o", "ConnectTimeout=4", "-o", "BatchMode=yes",
            settings.OUTPUT_SYNC_HOST, "mkdir", "-p", remote_dir
        )
        await proc.wait()
        if proc.returncode != 0:
            return False

        if not is_r2_enabled():
            proc2 = await asyncio.create_subprocess_exec(
                "scp", "-q", "-r", "-o", "ConnectTimeout=4", "-o", "BatchMode=yes",
                str(task_dir / "."), remote_dest,
            )
            await proc2.wait()
            return proc2.returncode == 0

        # R2 启用时只同步源图和最终成品，避免把视频、逐帧 PNG、ZIP
        # 和缩略图复制到国内服务器；R2 未启用时保留原有全量同步兼容性。
        for source in files:
            proc2 = await asyncio.create_subprocess_exec(
                "scp", "-q", "-o", "ConnectTimeout=4", "-o", "BatchMode=yes",
                str(source), f"{remote_dest}{source.name}",
            )
            await proc2.wait()
            if proc2.returncode != 0:
                return False
        return True
    except Exception as e:
        logger.warning("[%s] failed to sync output to domestic node: %s", task_id, e)
        return False


async def sync_task_outputs_with_retry(task_id: str, task_dir: Path, attempts: int = 3) -> bool:
    """Retry short-lived SSH/network failures before exposing completion."""
    for attempt in range(max(1, attempts)):
        if await sync_task_outputs_to_domestic(task_id, task_dir):
            return True
        if attempt + 1 < attempts:
            await asyncio.sleep(2 ** attempt)
    return False

async def run_generate_pipeline(
    task_id: str,
    ref_image_bytes: Optional[bytes],
    action_type: str,
    custom_caption: str,
    character_desc: str,
    fps: int,
    make_transparent: bool,
    padding_percent: float,
    is_sketch: bool = False,
    openid: str = "",
    custom_action: str = "",
    deducted_from: str = "free",
    frame_count: int = 16,
    resolution: str = "240x240",
    output_mode: str = "gif",
    style_preset: str = "chibi_3d",
    composition_preset: str = "bust",
    bg_preset: str = "white",
    text_package: str = "worker",
    custom_texts: Optional[list[str]] = None,
):
    """后台异步执行完整的生图、切割与动图/表情包流水线"""
    import io
    import time
    import base64
    import httpx

    start_time = time.time()
    frame_count = int(frame_count) if frame_count in (2, 4, 8, 9, 16) else 16
    grid_rows_cols = {
        2: (1, 2),
        4: (2, 2),
        8: (2, 4),
        9: (3, 3),
        16: (4, 4),
    }
    rows, cols = grid_rows_cols.get(frame_count, (4, 4))
    try:
        target_size_px = int(str(resolution).lower().split('x')[0])
        target_size_px = max(120, min(720, target_size_px))
    except Exception:
        target_size_px = 256

    try:
        # === 16 款静态独立表情包生成专属流水线 ===
        if output_mode == "sticker16":
            task_dir = settings.OUTPUT_DIR / task_id
            task_dir.mkdir(parents=True, exist_ok=True)
            has_image = ref_image_bytes is not None and len(ref_image_bytes) > 0
            if has_image:
                try:
                    (task_dir / "original_image.png").write_bytes(ref_image_bytes)
                except Exception:
                    pass

            # 1. 审核模式动态分支 (纯本地 PIL 生成，100% 微信合规，0% 深度合成)
            if is_audit_mode_active():
                _set_task_progress(task_id, openid, 25, "processing", "阶段 1/3: 正在读取图片并应用合规微调滤镜...")
                await asyncio.sleep(0.5)

                _set_task_progress(task_id, openid, 70, "rendering", "阶段 2/3: 正在排版渲染 16 款静态表情贴纸...")
                result_data = await asyncio.to_thread(
                    create_audit_stickers,
                    task_id=task_id,
                    task_dir=task_dir,
                    ref_image_bytes=ref_image_bytes,
                    text_package=text_package,
                    custom_texts=custom_texts,
                    target_size_px=target_size_px,
                )

                # 组装 16 帧预览轮播 GIF
                frames_dir = task_dir / "frames"
                preview_frames = [
                    Image.open(frames_dir / f"frame_{i:02d}.png").convert("RGBA")
                    for i in range(1, 17)
                    if (frames_dir / f"frame_{i:02d}.png").exists()
                ]
                if preview_frames:
                    gif_path = task_dir / "meme_result.gif"
                    preview_frames[0].save(
                        gif_path,
                        save_all=True,
                        append_images=preview_frames[1:],
                        duration=1000,
                        loop=0,
                        format="GIF",
                    )
                    result_data["gif_url"] = f"/outputs/{task_id}/meme_result.gif"
                    result_data["thumb_url"] = f"/outputs/{task_id}/frames/frame_01.png"

                if (task_dir / "frames_pack.zip").exists() and not (task_dir / "stickers_pack.zip").exists():
                    shutil.copyfile(task_dir / "frames_pack.zip", task_dir / "stickers_pack.zip")
                result_data["stickers_pack_url"] = f"/outputs/{task_id}/stickers_pack.zip"
                result_data["zip_url"] = f"/outputs/{task_id}/stickers_pack.zip"
                result_data["stickers"] = result_data.get("frames", [])

                _set_task_progress(task_id, openid, 92, "syncing", "阶段 3/3: 正在同步表情贴纸资源...")
                await sync_task_outputs_with_retry(task_id, task_dir)

                duration_seconds = round(time.time() - start_time, 1)
                result_data["duration_seconds"] = duration_seconds
                result_data["stats"]["duration_seconds"] = duration_seconds

                result_data = await publish_and_rewrite(task_id, task_dir, result_data)

                TASK_STORE[task_id] = {
                    "openid": openid,
                    "status": "completed",
                    "progress": 100,
                    "stage": "done",
                    "stage_text": "🎉 16 款表情贴纸制作完成！",
                    "data": result_data,
                }

                if openid:
                    try:
                        with get_db() as conn:
                            conn.execute('''
                                UPDATE meme_tasks
                                SET prompt = ?, preset_key = ?, text_bottom = ?, fps = 1, status = 'completed',
                                    progress = 100, gif_url = ?, sprite_url = ?, error_message = '',
                                    duration_seconds = ?, frame_count = 16, resolution = ?, output_mode = 'sticker16'
                                WHERE task_id = ? AND openid = ?
                            ''', (
                                f"audit_sticker16:{text_package}", f"sticker16:{text_package}", text_package,
                                result_data.get("gif_url", ""), result_data.get("sprite_url", ""),
                                duration_seconds, f"{target_size_px}x{target_size_px}", task_id, openid
                            ))
                            conn.commit()
                    except Exception:
                        pass
                return

            # 2. 全量 AI 模式：调用 CPA 出图并本地切片叠加台词
            _set_task_progress(task_id, openid, 10, "prompt", "阶段 1/4: 组装 4x4 矩阵 16 种无字表情提示词...")
            prompt = build_sticker16_prompt(
                character_desc=character_desc.strip(),
                style=style_preset,
                composition=composition_preset,
                background=bg_preset,
                has_image=has_image,
                is_sketch=is_sketch,
                custom_action=custom_action.strip(),
            )

            _set_task_progress(
                task_id,
                openid,
                25,
                "drawing",
                "阶段 2/4: 正在调用 CPA 绘图引擎绘制 4x4 矩阵 (16 款表情原画)...",
            )

            headers = {
                "Authorization": f"Bearer {settings.CPA_API_KEY}"
            }

            async with httpx.AsyncClient(timeout=180.0) as client:
                if has_image:
                    ref_img_pil = Image.open(io.BytesIO(ref_image_bytes)).convert("RGBA")
                    buf = io.BytesIO()
                    ref_img_pil.save(buf, format="PNG")
                    buf.seek(0)
                    files = {
                        "image": ("character.png", buf.getvalue(), "image/png")
                    }
                    data = {
                        "model": settings.CPA_IMAGE_MODEL,
                        "prompt": prompt,
                        "n": "1",
                        "size": "1024x1024"
                    }
                    resp = await client.post(
                        f"{settings.CPA_API_BASE}/images/edits",
                        headers=headers,
                        data=data,
                        files=files
                    )
                else:
                    payload = {
                        "model": settings.CPA_IMAGE_MODEL,
                        "prompt": prompt,
                        "n": 1,
                        "size": "1024x1024"
                    }
                    resp = await client.post(
                        f"{settings.CPA_API_BASE}/images/generations",
                        headers={**headers, "Content-Type": "application/json"},
                        json=payload
                    )

                if resp.status_code != 200:
                    raise RuntimeError(f"表情包生成服务异常 ({resp.status_code}): {resp.text}")
                resp_data = resp.json()

            item = resp_data.get("data", [{}])[0]
            if "b64_json" in item:
                img_bytes = base64.b64decode(item["b64_json"])
                source_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            elif "url" in item:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    img_res = await client.get(item["url"])
                    source_image = Image.open(io.BytesIO(img_res.content)).convert("RGB")
            else:
                raise RuntimeError("未能从响应中解析出图片数据")

            # 阶段 3：多尺度网格切片
            _set_task_progress(
                task_id,
                openid,
                75,
                "slicing",
                f"阶段 3/4: 4×4 物理间隙网格切片 (16 款表情, {target_size_px}px)...",
            )

            input_path = task_dir / "input_sprite.png"
            source_image.save(input_path, format="PNG")

            frames = await asyncio.to_thread(
                SpriteProcessor.slice_grid,
                source_image,
                rows=4,
                cols=4,
                padding_percent=padding_percent,
                target_size_px=target_size_px,
            )

            # 阶段 4：排版渲染场景台词并生成表情包合辑
            _set_task_progress(
                task_id,
                openid,
                88,
                "annotating",
                "阶段 4/4: 排版渲染场景台词并打包 16 款表情贴纸...",
            )

            if custom_texts and len(custom_texts) >= 16:
                texts = [t.strip() for t in custom_texts[:16]]
            else:
                texts = SCENE_TEXT_PACKAGES.get(text_package, SCENE_TEXT_PACKAGES.get("worker", [""] * 16))

            make_trans = (bg_preset == "transparent") or make_transparent
            annotated_frames = await asyncio.to_thread(
                SpriteProcessor.overlay_text_to_frames,
                frames=frames,
                texts=texts,
                style="stroke",
                make_transparent=make_trans
            )

            stickers_dir = task_dir / "stickers"
            stickers_dir.mkdir(exist_ok=True)
            frames_dir = task_dir / "frames"
            frames_dir.mkdir(exist_ok=True)

            sticker_items = []
            for idx, (af, txt) in enumerate(zip(annotated_frames, texts), 1):
                s_path = stickers_dir / f"sticker_{idx:02d}.png"
                f_path = frames_dir / f"frame_{idx:02d}.png"
                af.save(s_path, format="PNG")
                af.save(f_path, format="PNG")
                emotion = EMOTION_TAGS_16[idx - 1] if idx - 1 < len(EMOTION_TAGS_16) else ""
                sticker_items.append({
                    "index": idx,
                    "url": f"/outputs/{task_id}/stickers/sticker_{idx:02d}.png",
                    "frame_url": f"/outputs/{task_id}/frames/frame_{idx:02d}.png",
                    "text": txt,
                    "caption": txt,
                    "emotion": emotion
                })

            # 打包 ZIP
            zip_path = task_dir / "stickers_pack.zip"
            await asyncio.to_thread(
                SpriteProcessor.package_zip,
                frames=annotated_frames,
                output_path=str(zip_path),
                make_transparent=make_trans
            )
            shutil.copyfile(zip_path, task_dir / "frames_pack.zip")

            # 生成整体预览动图 (每张展示 1 秒)
            gif_path = task_dir / "meme_result.gif"
            await asyncio.to_thread(
                SpriteProcessor.assemble_gif,
                frames=annotated_frames,
                output_path=str(gif_path),
                fps=1,
                make_transparent=make_trans,
                max_file_size_bytes=settings.WECHAT_GIF_MAX_BYTES
            )

            _set_task_progress(task_id, openid, 96, "syncing", "正在同步表情包产物到国内节点与云存储...")
            if not await sync_task_outputs_with_retry(task_id, task_dir):
                raise RuntimeError("表情包已生成，但同步到国内节点失败")

            duration_seconds = round(time.time() - start_time, 1)
            has_orig = has_image and (task_dir / "original_image.png").exists()

            stats = {
                "frame_count": 16,
                "sticker_count": 16,
                "duration_seconds": duration_seconds,
                "resolution": f"{target_size_px}x{target_size_px}",
                "style_preset": style_preset,
                "composition_preset": composition_preset,
                "bg_preset": bg_preset,
                "text_package": text_package,
            }

            result_data = {
                "task_id": task_id,
                "output_mode": "sticker16",
                "style_preset": style_preset,
                "composition_preset": composition_preset,
                "bg_preset": bg_preset,
                "text_package": text_package,
                "stickers": sticker_items,
                "frames": [s["url"] for s in sticker_items],
                "gif_url": f"/outputs/{task_id}/meme_result.gif",
                "thumb_url": f"/outputs/{task_id}/stickers/sticker_01.png",
                "zip_url": f"/outputs/{task_id}/stickers_pack.zip",
                "stickers_pack_url": f"/outputs/{task_id}/stickers_pack.zip",
                "input_url": f"/outputs/{task_id}/input_sprite.png",
                "original_image_url": f"/outputs/{task_id}/original_image.png" if has_orig else "",
                "prompt_used": prompt,
                "stats": stats,
                "duration_seconds": duration_seconds
            }

            result_data = await publish_and_rewrite(task_id, task_dir, result_data)

            TASK_STORE[task_id] = {
                "openid": openid,
                "status": "completed",
                "progress": 100,
                "stage": "done",
                "stage_text": "🎉 16 款表情贴纸全部制作完成！",
                "data": result_data
            }

            if openid:
                try:
                    with get_db() as conn:
                        conn.execute('''
                            UPDATE meme_tasks
                            SET prompt = ?, preset_key = ?, text_bottom = ?, fps = 1, status = 'completed',
                                progress = 100, gif_url = ?, sprite_url = ?, error_message = '',
                                duration_seconds = ?, frame_count = 16, resolution = ?, output_mode = 'sticker16'
                            WHERE task_id = ? AND openid = ?
                        ''', (
                            prompt, f"sticker16:{style_preset}:{text_package}", text_package,
                            result_data["gif_url"], result_data["input_url"], duration_seconds,
                            f"{target_size_px}x{target_size_px}", task_id, openid
                        ))
                        conn.commit()
                except Exception:
                    pass
            return
        # === 审核模式动态分支 (策略 A: 降级为本地纯 PIL 图像微动效处理，秒级出图，0% 深度合成) ===
        if is_audit_mode_active():
            task_dir = settings.OUTPUT_DIR / task_id
            task_dir.mkdir(parents=True, exist_ok=True)

            _set_task_progress(task_id, openid, 25, "processing", "阶段 1/3: 正在读取图片并优化图层...")
            await asyncio.sleep(0.6)

            _set_task_progress(task_id, openid, 70, "rendering", "阶段 2/3: 正在渲染动效画幅与趣味字幕...")

            result_data = await asyncio.to_thread(
                create_audit_meme_gif,
                task_id=task_id,
                task_dir=task_dir,
                ref_image_bytes=ref_image_bytes,
                action_type=action_type,
                custom_caption=custom_caption,
                target_size_px=target_size_px
            )

            _set_task_progress(task_id, openid, 92, "syncing", "阶段 3/3: 正在导出高清动图与同步存储...")
            await sync_task_outputs_with_retry(task_id, task_dir)

            duration_seconds = round(time.time() - start_time, 1)
            result_data["duration_seconds"] = duration_seconds
            result_data["stats"]["duration_seconds"] = duration_seconds

            result_data = await publish_and_rewrite(task_id, task_dir, result_data)

            TASK_STORE[task_id] = {
                "openid": openid,
                "status": "completed",
                "progress": 100,
                "stage": "done",
                "stage_text": "🎉 制作全部完成！正在导出动图预览...",
                "data": result_data
            }

            if openid:
                try:
                    with get_db() as conn:
                        conn.execute('''
                            UPDATE meme_tasks
                            SET prompt = ?, preset_key = ?, text_bottom = ?, fps = ?, status = 'completed',
                                progress = 100, gif_url = ?, sprite_url = ?, error_message = '',
                                duration_seconds = ?, frame_count = ?, resolution = ?
                            WHERE task_id = ? AND openid = ?
                        ''', (
                            f"audit_mode:{action_type}", action_type, custom_caption, fps,
                            result_data["gif_url"], result_data["input_url"],
                            duration_seconds, result_data["stats"]["frame_count"],
                            result_data["stats"]["resolution"], task_id, openid
                        ))
                        conn.commit()
                except Exception:
                    pass

                try:
                    caption_text = (custom_caption or "").strip() or "动效表情包"
                    async def _delayed_send_sub_msg():
                        await asyncio.sleep(1)
                        try:
                            await WeChatService.send_subscribe_message(
                                openid=openid,
                                order_no=task_id,
                                service_type="动效表情包制作",
                                service_item=caption_text[:18],
                                page="pages/index/index"
                            )
                        except Exception:
                            pass
                    asyncio.create_task(_delayed_send_sub_msg())
                except Exception:
                    pass
            return

        # 阶段 1：组装提示词
        stage_desc = f"阶段 1/4: 结合手绘草图造型与动作语义对齐 ({frame_count}帧)..." if is_sketch else f"阶段 1/4: 组装角色提示词与人设语义对齐 ({frame_count}帧)..."
        _set_task_progress(task_id, openid, 10, "prompt", stage_desc)

        has_image = ref_image_bytes is not None and len(ref_image_bytes) > 0
        templates = get_active_templates()
        template = next((t for t in templates if t["id"] == action_type), templates[0])
        prompt = template["prompt_builder"](character_desc.strip(), custom_caption.strip(), has_image, is_sketch, custom_action.strip(), frame_count=frame_count)

        # 阶段 2：请求画质渲染引擎出图
        _set_task_progress(
            task_id,
            openid,
            25,
            "drawing",
            f"阶段 2/4: 智能画质渲染引擎正在绘制 {frame_count} 帧动作拆解图...",
        )

        headers = {
            "Authorization": f"Bearer {settings.CPA_API_KEY}"
        }

        async with httpx.AsyncClient(timeout=180.0) as client:
            if has_image:
                ref_img_pil = Image.open(io.BytesIO(ref_image_bytes)).convert("RGBA")
                buf = io.BytesIO()
                ref_img_pil.save(buf, format="PNG")
                buf.seek(0)
                files = {
                    "image": ("character.png", buf.getvalue(), "image/png")
                }
                data = {
                    "model": settings.CPA_IMAGE_MODEL,
                    "prompt": prompt,
                    "n": "1",
                    "size": "1024x1024"
                }
                resp = await client.post(
                    f"{settings.CPA_API_BASE}/images/edits",
                    headers=headers,
                    data=data,
                    files=files
                )
            else:
                payload = {
                    "model": settings.CPA_IMAGE_MODEL,
                    "prompt": prompt,
                    "n": 1,
                    "size": "1024x1024"
                }
                resp = await client.post(
                    f"{settings.CPA_API_BASE}/images/generations",
                    headers={**headers, "Content-Type": "application/json"},
                    json=payload
                )

            if resp.status_code != 200:
                raise RuntimeError(f"动图生成服务异常 ({resp.status_code}): {resp.text}")
            resp_data = resp.json()

        item = resp_data.get("data", [{}])[0]
        if "b64_json" in item:
            img_bytes = base64.b64decode(item["b64_json"])
            source_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        elif "url" in item:
            async with httpx.AsyncClient(timeout=60.0) as client:
                img_res = await client.get(item["url"])
                source_image = Image.open(io.BytesIO(img_res.content)).convert("RGB")
        else:
            raise RuntimeError("未能从响应中解析出图片数据")

        # 阶段 3：多尺度主间隙物理网格切割
        _set_task_progress(
            task_id,
            openid,
            75,
            "slicing",
            f"阶段 3/4: 多尺度主间隙物理网格切割 ({rows}×{cols}, {target_size_px}px)...",
        )

        task_dir = settings.OUTPUT_DIR / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        # 保存用户原始参考图/手绘图到任务产物目录，确保存入 Cloudflare R2 与国内节点
        if has_image and ref_image_bytes:
            orig_path = task_dir / "original_image.png"
            try:
                orig_path.write_bytes(ref_image_bytes)
                logger.info("[%s] 用户原始上传图像已保存至 %s (%d 字节)", task_id, orig_path.name, len(ref_image_bytes))
            except Exception as e:
                logger.warning("[%s] 保存用户原始上传图像失败: %s", task_id, e)

        input_path = task_dir / "input_sprite.png"
        source_image.save(input_path, format="PNG")

        frames = await asyncio.to_thread(
            SpriteProcessor.slice_grid,
            source_image,
            rows=rows,
            cols=cols,
            padding_percent=padding_percent,
            target_size_px=target_size_px,
        )

        # 阶段 4：固定色差泛洪去底与动图生成
        _set_task_progress(
            task_id,
            openid,
            90,
            "assembling",
            "阶段 4/4: 固定色差泛洪去底并封装微信 GIF 动图...",
        )

        gif_path = task_dir / "meme_result.gif"
        stats = await asyncio.to_thread(
            SpriteProcessor.assemble_gif,
            frames=frames,
            output_path=str(gif_path),
            fps=fps,
            make_transparent=make_transparent,
            max_file_size_bytes=settings.WECHAT_GIF_MAX_BYTES,
        )
        if not stats.get("is_wechat_compliant"):
            stats["warning"] = (
                f"当前 GIF 为 {stats.get('file_size_kb', 0):.1f}KB，超过微信常用的 "
                f"{settings.WECHAT_GIF_MAX_BYTES / 1024:.0f}KB 提醒线；仍可下载到本地，"
                "发送到微信时可能受到平台大小限制。"
            )

        zip_path = task_dir / "frames_pack.zip"
        await asyncio.to_thread(
            SpriteProcessor.package_zip,
            frames=frames,
            output_path=str(zip_path),
            make_transparent=make_transparent
        )

        frame_preview_urls = []
        frames_dir = task_dir / "frames"
        frames_dir.mkdir(exist_ok=True)
        for idx, f in enumerate(frames, 1):
            f_thumb_path = frames_dir / f"frame_{idx:02d}.png"
            f_clean = SpriteProcessor.remove_white_bg(f) if make_transparent else f
            f_clean.save(f_thumb_path, format="PNG")
            frame_preview_urls.append(f"/outputs/{task_id}/frames/frame_{idx:02d}.png")

        # 生成静态缩略图供旧版本地回退使用；R2 发布后会清理该中间文件。
        if frames:
            try:
                frames[0].convert("RGB").resize((160, 160), Image.Resampling.LANCZOS).save(task_dir / "thumb.jpg", format="JPEG", quality=80)
            except Exception:
                pass

        # 在返回完成前同步到国内节点与 R2；耗时统计覆盖整个发布阶段。
        _set_task_progress(task_id, openid, 96, "syncing", "正在同步成品到 R2 与国内节点...")
        if not await sync_task_outputs_with_retry(task_id, task_dir):
            raise RuntimeError("动图已生成，但同步到国内节点失败")

        # 计算并保存实际完成总耗时 (秒)
        duration_seconds = round(time.time() - start_time, 1)
        stats["duration_seconds"] = duration_seconds
        stats["frame_count"] = len(frames)
        stats["resolution"] = f"{target_size_px}x{target_size_px}"

        # 只有本地成品、国内节点和 R2 都准备好后，才向小程序报告完成。
        has_orig = has_image and (task_dir / "original_image.png").exists()
        result_data = {
            "task_id": task_id,
            "gif_url": f"/outputs/{task_id}/meme_result.gif",
            # R2 仅保存源图和最终成品 GIF，不再发布缩略图；相册缩略图直接使用 GIF。
            "thumb_url": f"/outputs/{task_id}/meme_result.gif",
            "zip_url": f"/outputs/{task_id}/frames_pack.zip",
            "input_url": f"/outputs/{task_id}/input_sprite.png",
            "original_image_url": f"/outputs/{task_id}/original_image.png" if has_orig else "",
            "caption": custom_caption,
            "frames": frame_preview_urls,
            "stats": stats,
            "duration_seconds": duration_seconds
        }
        result_data = await publish_and_rewrite(task_id, task_dir, result_data)

        # 完成
        TASK_STORE[task_id] = {
            "openid": openid,
            "status": "completed",
            "progress": 100,
            "stage": "done",
            "stage_text": "🎉 制作全部完成！正在导出动图预览...",
            "data": result_data
        }

        # 记录到 SQLite 表情包任务库
        if openid:
            try:
                with get_db() as conn:
                    conn.execute('''
                        UPDATE meme_tasks
                        SET prompt = ?, preset_key = ?, text_bottom = ?, fps = ?, status = 'completed',
                            progress = 100, gif_url = ?, sprite_url = ?, error_message = '',
                            duration_seconds = ?, frame_count = ?, resolution = ?
                        WHERE task_id = ? AND openid = ?
                    ''', (prompt, action_type, custom_caption, fps, result_data["gif_url"], result_data["input_url"], duration_seconds, frame_count, resolution, task_id, openid))
                    conn.commit()
            except Exception:
                pass

            # 触发微信服务完成通知（一次性订阅消息）
            # 延时 3 秒发送，确保前端动图已下载渲染完毕并可保存相册
            try:
                caption_text = (custom_caption or "").strip() or "定制GIF动图"
                async def _delayed_send_sub_msg():
                    await asyncio.sleep(3)
                    try:
                        await WeChatService.send_subscribe_message(
                            openid=openid,
                            order_no=task_id,
                            service_type="动图表情包制作",
                            service_item=caption_text[:18],
                            page="pages/index/index"
                        )
                    except Exception:
                        pass
                asyncio.create_task(_delayed_send_sub_msg())
            except Exception:
                pass

    except Exception as e:
        logger.exception("Meme generation task %s failed", task_id)
        if openid:
            refund_quota(openid, deducted_from)
        failed_task_dir = settings.OUTPUT_DIR / task_id
        # 保留失败现场一段时间，便于排错；后台任务会延迟清理。
        mark_failed_task_dir(failed_task_dir, str(e))
        TASK_STORE[task_id] = {
            "openid": openid,
            "status": "failed",
            "progress": 100,
            "stage": "error",
            "stage_text": "出图失败",
            "error": "生成服务暂时不可用，请稍后重试"
        }
        try:
            with get_db() as conn:
                conn.execute(
                    "UPDATE meme_tasks SET status = 'failed', progress = 100, error_message = ? WHERE task_id = ? AND openid = ?",
                    (str(e)[:500], task_id, openid),
                )
                conn.commit()
        except Exception:
            pass

@router.post("/generate-async")
async def generate_async(
    current_openid: CurrentOpenid,
    ref_image: Optional[UploadFile] = File(None),
    action_type: str = Form("kiss"),
    custom_caption: str = Form(""),
    character_desc: str = Form(""),
    custom_action: Optional[str] = Form(""),
    fps: int = Form(8),
    make_transparent: bool = Form(True),
    padding_percent: float = Form(2.5),
    is_sketch: bool = Form(False),
    openid: Optional[str] = Form(""),
    resolution: Optional[str] = Form("240x240"),
    frame_count: int = Form(16),
    fast_mode: Optional[str] = Form("1"),
    loop_count: Optional[int] = Form(0),
    output_mode: Optional[str] = Form("gif"),
    style_preset: Optional[str] = Form("chibi_3d"),
    composition_preset: Optional[str] = Form("bust"),
    bg_preset: Optional[str] = Form("white"),
    text_package: Optional[str] = Form("worker"),
    custom_texts: Optional[str] = Form(None),
):
    """【推荐】异步启动动图生图任务，前端通过轮询获取实时进度与结果，绝无 HTTP 超时问题"""
    authenticated_openid = require_same_user(openid, current_openid)
    if not 1 <= fps <= 30 or not 0 <= padding_percent <= 20:
        raise HTTPException(status_code=400, detail="fps 或边距参数超出允许范围")
    if frame_count not in (2, 4, 8, 9, 16):
        frame_count = 16
    if len(custom_caption) > 80 or len(character_desc) > 500 or len(custom_action or "") > 300:
        raise HTTPException(status_code=400, detail="输入文字过长")

    ref_image_bytes = None
    if ref_image is not None and getattr(ref_image, "filename", None) not in [None, ""]:
        ref_image_bytes = await read_limited_upload(ref_image, settings.MAX_IMAGE_UPLOAD_MB)
        open_validated_image(ref_image_bytes, allow_animation=False)

    custom_texts_list = None
    if custom_texts and custom_texts.strip():
        try:
            parsed = json.loads(custom_texts)
            if isinstance(parsed, list):
                custom_texts_list = [str(x).strip() for x in parsed]
        except Exception:
            custom_texts_list = [line.strip() for line in custom_texts.splitlines() if line.strip()]

    # 微信内容安全审查 (检测用户自定义台词、角色描述与上传参考图)
    texts_to_check = [custom_caption, character_desc, custom_action or ""]
    if custom_texts_list:
        texts_to_check.extend(custom_texts_list)
    for txt in texts_to_check:
        if txt and txt.strip():
            is_safe, tip = await WeChatService.check_text_security(txt, authenticated_openid)
            if not is_safe:
                raise HTTPException(status_code=400, detail=tip or "所发布内容包含违规信息，请修改后重试")

    if ref_image_bytes:
        is_safe, tip = await WeChatService.check_image_security(ref_image_bytes)
        if not is_safe:
            raise HTTPException(status_code=400, detail=tip or "所发布内容包含违规信息，请修改后重试")

    quota_res = check_and_deduct_quota(authenticated_openid)
    if not quota_res.get("allowed"):
        raise HTTPException(status_code=403, detail=quota_res.get("error", "制作次数已耗尽，请签到或开通尝鲜包！"))

    task_id = uuid.uuid4().hex
    estimated_duration = get_estimated_generation_duration()

    TASK_STORE[task_id] = {
        "openid": authenticated_openid,
        "status": "processing",
        "progress": 5,
        "stage": "init",
        "stage_text": "正在初始化任务...",
        "estimated_duration": estimated_duration
    }
    if len(TASK_STORE) > 1000:
        for old_task_id, old_task in list(TASK_STORE.items()):
            if old_task_id != task_id and old_task.get("status") in ("completed", "failed"):
                TASK_STORE.pop(old_task_id, None)
                break

    preset_key_val = f"sticker16:{style_preset}:{text_package}" if output_mode == "sticker16" else action_type
    caption_val = (custom_texts_list[0] if custom_texts_list else text_package) if output_mode == "sticker16" else custom_caption
    try:
        with get_db() as conn:
            conn.execute('''
                INSERT INTO meme_tasks (task_id, openid, preset_key, text_bottom, fps, status, progress, frame_count, resolution, output_mode)
                VALUES (?, ?, ?, ?, ?, 'processing', 5, ?, ?, ?)
            ''', (task_id, authenticated_openid, preset_key_val, caption_val, fps, frame_count, resolution, output_mode or "gif"))
            conn.commit()
    except Exception:
        refund_quota(authenticated_openid, quota_res.get("deducted_from", "free"))
        TASK_STORE.pop(task_id, None)
        raise

    # 启动后台协程
    asyncio.create_task(run_generate_pipeline(
        task_id=task_id,
        ref_image_bytes=ref_image_bytes,
        action_type=action_type,
        custom_caption=custom_caption,
        character_desc=character_desc,
        fps=fps,
        make_transparent=make_transparent,
        padding_percent=padding_percent,
        is_sketch=is_sketch,
        openid=authenticated_openid,
        custom_action=custom_action or "",
        deducted_from=quota_res.get("deducted_from", "free"),
        frame_count=frame_count,
        resolution=resolution or "240x240",
        output_mode=output_mode or "gif",
        style_preset=style_preset or "chibi_3d",
        composition_preset=composition_preset or "bust",
        bg_preset=bg_preset or "white",
        text_package=text_package or "worker",
        custom_texts=custom_texts_list,
    ))

    return {
        "code": 0,
        "message": "task_started",
        "data": {
            "task_id": task_id,
            "status": "processing",
            "estimated_duration": estimated_duration
        }
    }

@router.get("/sticker16-packages")
@router.get("/meme/sticker16-packages")
def get_sticker16_packages():
    """获取 16 款表情贴纸预设场景文案包、风格与版型配置"""
    packages = []
    for pkg_id, texts in SCENE_TEXT_PACKAGES.items():
        packages.append({
            "id": pkg_id,
            "title": SCENE_TEXT_TITLES.get(pkg_id, pkg_id),
            "texts": texts,
            "count": len(texts)
        })
    return {
        "code": 0,
        "data": {
            "packages": packages,
            "emotions": EMOTION_TAGS_16,
            "styles": [
                {"id": "chibi_3d", "title": "3D Q版粘土 (推荐)", "desc": "泡泡玛特盲盒质感，饱满圆润，色彩鲜亮"},
                {"id": "anime", "title": "日漫二次元", "desc": "精美动漫画风，神情夸张生动"},
                {"id": "funny_line", "title": "恶搞沙雕简笔画", "desc": "蘑菇头/熊猫头风味，魔性搞笑斗图必备"}
            ],
            "compositions": [
                {"id": "bust", "title": "半身动作 (推荐)", "desc": "包含丰富手势与肢体互动，表现力强"},
                {"id": "closeup", "title": "头部特写", "desc": "聚焦面部神态细节与五官情绪"},
                {"id": "fullbody", "title": "全身动态", "desc": "包含全身奔跑、翻滚、瘫倒动作"}
            ],
            "backgrounds": [
                {"id": "white", "title": "纯白背景 (经典)", "desc": "标准表情包白色实底"},
                {"id": "transparent", "title": "透明去底", "desc": "自动抠除白底，生成纯净透明贴纸"}
            ]
        }
    }


@router.post("/debug/preview-prompt")
def preview_prompt(
    character_desc: str = Form(""),
    style_preset: str = Form("chibi_3d"),
    composition_preset: str = Form("bust"),
    bg_preset: str = Form("white"),
    has_image: bool = Form(True),
    is_sketch: bool = Form(False),
    custom_action: str = Form(""),
):
    """【调试辅助】预览将发送给 CPA 模型的 16 宫格专业英文提示词"""
    prompt = build_sticker16_prompt(
        character_desc=character_desc.strip(),
        style=style_preset,
        composition=composition_preset,
        background=bg_preset,
        has_image=has_image,
        is_sketch=is_sketch,
        custom_action=custom_action.strip(),
    )
    return {
        "code": 0,
        "data": {
            "prompt": prompt,
            "model": settings.CPA_IMAGE_MODEL,
            "cpa_api_base": settings.CPA_API_BASE
        }
    }


@router.post("/debug/test-sticker16")
async def debug_test_sticker16(
    ref_image: Optional[UploadFile] = File(None),
    sample_id: Optional[str] = Form(None),
    character_desc: str = Form(""),
    style_preset: str = Form("chibi_3d"),
    composition_preset: str = Form("bust"),
    bg_preset: str = Form("white"),
    text_package: str = Form("worker"),
    custom_texts: Optional[str] = Form(None),
    resolution: str = Form("256x256"),
    force_audit: bool = Form(False),
):
    """【Web调试台专用】直接测试 16 静态表情包生成，免去小程序鉴权，快速联调"""
    task_id = uuid.uuid4().hex
    ref_image_bytes = None

    if ref_image and getattr(ref_image, "filename", None):
        ref_image_bytes = await read_limited_upload(ref_image, settings.MAX_IMAGE_UPLOAD_MB)
    elif sample_id:
        sample_path = settings.SAMPLES_DIR / f"{sample_id}.png"
        if not sample_path.exists():
            png_list = list(settings.SAMPLES_DIR.glob("*.png"))
            if png_list:
                sample_path = png_list[0]
        if sample_path.exists():
            ref_image_bytes = sample_path.read_bytes()

    custom_texts_list = None
    if custom_texts and custom_texts.strip():
        try:
            parsed = json.loads(custom_texts)
            if isinstance(parsed, list):
                custom_texts_list = [str(x).strip() for x in parsed]
        except Exception:
            custom_texts_list = [line.strip() for line in custom_texts.splitlines() if line.strip()]

    openid = "user_mock_h5_console"
    TASK_STORE[task_id] = {
        "openid": openid,
        "status": "processing",
        "progress": 5,
        "stage": "init",
        "stage_text": "正在初始化 16 宫格表情包流水线...",
        "estimated_duration": 30
    }

    # 启动异步生图流水线
    asyncio.create_task(run_generate_pipeline(
        task_id=task_id,
        ref_image_bytes=ref_image_bytes,
        action_type="sticker16",
        custom_caption="",
        character_desc=character_desc,
        fps=1,
        make_transparent=(bg_preset == "transparent"),
        padding_percent=2.5,
        is_sketch=False,
        openid=openid,
        custom_action="",
        deducted_from="free",
        frame_count=16,
        resolution=resolution,
        output_mode="sticker16",
        style_preset=style_preset,
        composition_preset=composition_preset,
        bg_preset=bg_preset,
        text_package=text_package,
        custom_texts=custom_texts_list,
    ))

    return {
        "code": 0,
        "message": "task_started",
        "data": {
            "task_id": task_id,
            "status": "processing",
            "estimated_duration": 30
        }
    }


@router.get("/debug/task-status/{task_id}")
def debug_get_task_status(task_id: str):
    """【调试专用】无鉴权查询任务状态与进度"""
    if task_id in TASK_STORE:
        task_info = TASK_STORE[task_id]
        public_info = {k: v for k, v in task_info.items() if k != "openid"}
        return {"code": 0, "data": public_info}

    task_dir = settings.OUTPUT_DIR / task_id
    if (task_dir / "stickers_pack.zip").exists() or (task_dir / "meme_result.gif").exists():
        frames_dir = task_dir / "frames"
        stickers_dir = task_dir / "stickers"
        frame_urls = [f"/outputs/{task_id}/frames/{f.name}" for f in sorted(frames_dir.glob("*.png"))] if frames_dir.exists() else []
        sticker_urls = [f"/outputs/{task_id}/stickers/{f.name}" for f in sorted(stickers_dir.glob("*.png"))] if stickers_dir.exists() else []

        return {
            "code": 0,
            "data": {
                "status": "completed",
                "progress": 100,
                "data": {
                    "task_id": task_id,
                    "output_mode": "sticker16",
                    "stickers": sticker_urls or frame_urls,
                    "frames": frame_urls,
                    "gif_url": f"/outputs/{task_id}/meme_result.gif",
                    "zip_url": f"/outputs/{task_id}/stickers_pack.zip",
                    "stickers_pack_url": f"/outputs/{task_id}/stickers_pack.zip",
                    "input_url": f"/outputs/{task_id}/input_sprite.png",
                }
            }
        }
    return {"code": 404, "message": "task_not_found"}


@router.get("/task-status/{task_id}")
def get_task_status(task_id: str, current_openid: CurrentOpenid):
    """查询异步任务的实时执行状态与进度"""
    if not re.fullmatch(r"(?:[0-9a-f]{8}|[0-9a-f]{32})", task_id):
        raise HTTPException(status_code=400, detail="任务 ID 不合法")
    # 先查内存
    if task_id in TASK_STORE:
        task_info = TASK_STORE[task_id]
        if task_info.get("openid") != current_openid:
            raise HTTPException(status_code=404, detail="任务不存在")
        public_task_info = {key: value for key, value in task_info.items() if key != "openid"}
        if "estimated_duration" not in public_task_info:
            public_task_info["estimated_duration"] = get_estimated_generation_duration()
        return {
            "code": 0,
            "data": public_task_info
        }

    # 再查磁盘是否已有历史成果 (如 df4492bd 等)
    with get_db() as conn:
        owner = conn.execute(
            "SELECT openid, status, progress, duration_seconds, gif_url, sprite_url FROM meme_tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
    if not owner or owner["openid"] != current_openid:
        raise HTTPException(status_code=404, detail="任务不存在")
    task_dir = settings.OUTPUT_DIR / task_id
    if owner["status"] == "completed" or (task_dir / "meme_result.gif").exists():
        frames_dir = task_dir / "frames"
        raw_gif_url = owner["gif_url"] or ""
        use_r2 = is_public_r2_url(raw_gif_url) or raw_gif_url.startswith(("http://", "https://"))
        frame_urls = [f"/outputs/{task_id}/frames/{f.name}" for f in sorted(frames_dir.glob("*.png"))] if frames_dir.exists() else []
        gif_file = task_dir / "meme_result.gif"
        file_size_kb = round(gif_file.stat().st_size / 1024, 1) if gif_file.exists() else 0.0
        is_compliant = (gif_file.stat().st_size <= settings.WECHAT_GIF_MAX_BYTES) if gif_file.exists() else True
        result_payload = {
            "task_id": task_id,
            "gif_url": f"/outputs/{task_id}/meme_result.gif",
            "zip_url": f"/outputs/{task_id}/frames_pack.zip" if (task_dir / "frames_pack.zip").exists() else "",
            "input_url": f"/outputs/{task_id}/input_sprite.png",
            "frames": frame_urls,
            "stats": {
                "frame_count": len(frame_urls),
                "file_size_kb": file_size_kb,
                "duration_per_frame_ms": 125,
                "duration_seconds": owner["duration_seconds"] or 0.0,
                "is_wechat_compliant": is_compliant,
                "warning": "当前 GIF 超过微信常用的 1MB 提醒线，仍可下载到本地；发送到微信时可能受到大小限制。"
                if not is_compliant else "",
            }
        }
        r2_link = owner["gif_url"] if use_r2 else (task_public_url(task_id, "meme_result.gif") if is_r2_enabled() else "")
        if r2_link:
            result_payload["r2_url"] = r2_link
        return {
            "code": 0,
            "data": {
                "status": "completed",
                "progress": 100,
                "data": result_payload
            }
        }

    if owner["status"] in ("processing", "pending"):
        progress = int(owner["progress"] or 0)
        persisted_stage = {
            10: ("prompt", "阶段 1/4：正在组装角色提示词与动作语义..."),
            25: ("drawing", "阶段 2/4：智能画质渲染引擎正在绘制动作拆解图..."),
            75: ("slicing", "阶段 3/4：正在切割并整理动图帧..."),
            90: ("assembling", "阶段 4/4：正在封装微信 GIF 动图..."),
            96: ("syncing", "正在同步成品到 R2 与国内节点..."),
        }.get(progress, ("queued", "任务正在处理中..."))
        return {
            "code": 0,
            "data": {
                "status": "processing",
                "progress": progress,
                "stage": persisted_stage[0],
                "stage_text": persisted_stage[1],
                "estimated_duration": get_estimated_generation_duration()
            },
        }
    if owner["status"] == "failed":
        return {
            "code": 0,
            "data": {
                "status": "failed",
                "progress": 100,
                "stage": "error",
                "stage_text": "生成服务暂时不可用，请稍后重试",
            },
        }

    return {
        "code": 404,
        "message": "task_not_found"
    }

@router.get("/samples")
def list_samples():
    """列出可用预置样本"""
    samples = []
    if settings.SAMPLES_DIR.exists():
        for f in settings.SAMPLES_DIR.glob("*.png"):
            samples.append({
                "id": f.stem,
                "name": f.stem,
                "thumb_url": f"/samples/{f.name}"
            })
    return {"code": 0, "data": samples}

@router.get("/history")
@router.get("/meme/history")
def list_history(current_openid: CurrentOpenid, openid: Optional[str] = None):
    """获取用户个人历史动图作品（私密个人创作，凭本人 openid 隔离获取）"""
    openid = require_same_user(openid, current_openid)
    with get_db() as conn:
        cursor = conn.cursor()
        # 绝不暴露 prompt 字段给前端，保障系统提示词与私密安全性
        cursor.execute("""
            SELECT task_id, openid, preset_key, text_bottom, custom_title, fps, status, progress, gif_url, sprite_url, duration_seconds, frame_count, resolution, created_at 
            FROM meme_tasks 
            WHERE openid = ? AND status = 'completed'
            ORDER BY created_at DESC LIMIT 50
        """, (openid.strip(),))
        rows = [dict(r) for r in cursor.fetchall()]

    tpl_map = {
        "kiss": "飞吻示爱表情",
        "battle_chibi": "Q版战斗暴击",
        "slack_worker": "打工人摸鱼表情",
        "pet_idle": "萌宠呆萌待机",
        "heart_dance": "魔性比心摇摆",
        "custom": "自定义个性动图",
        "run_cheer": "奔跑欢呼表情"
    }

    for row in rows:
        custom = (row.get("custom_title") or "").strip()
        text_bottom = (row.get("text_bottom") or "").strip()
        if custom:
            title = custom
        elif text_bottom:
            title = text_bottom
        else:
            title = tpl_map.get(row.get("preset_key") or "", "精选个性动图")
        row["display_title"] = title

        # 格式化展示时间为中国标准时间 (CST UTC+8)，杜绝 UTC 导致的时间前移或未来时间错觉
        row["created_at"] = format_datetime_china(row.get("created_at"))

        # R2 模式不再发布 thumb.jpg，相册缩略图直接使用最终 GIF。
        task_id = row.get("task_id")
        if task_id:
            thumb_path = settings.OUTPUT_DIR / task_id / "thumb.jpg"
            if is_public_r2_url(row.get("gif_url") or ""):
                row["thumb_url"] = row.get("gif_url")
            elif thumb_path.exists():
                row["thumb_url"] = f"/outputs/{task_id}/thumb.jpg"
            elif (settings.OUTPUT_DIR / task_id / "frames" / "frame_01.png").exists():
                row["thumb_url"] = f"/outputs/{task_id}/frames/frame_01.png"
            else:
                row["thumb_url"] = row.get("gif_url")
        else:
            row["thumb_url"] = row.get("gif_url")

        # 移除任何可能的 prompt 字段（防御式保证绝不泄露）
        row.pop("prompt", None)

    return {"code": 0, "data": rows}

class RenameMemeRequest(BaseModel):
    task_id: str
    title: str
    openid: Optional[str] = ""

@router.post("/rename")
@router.post("/meme/rename")
def rename_meme(req: RenameMemeRequest, current_openid: CurrentOpenid):
    """为历史作品添加或修改备注/名称"""
    if not req.task_id or not req.title.strip():
        raise HTTPException(status_code=400, detail="任务ID和新名称不能为空")
    if len(req.title) > 60:
        raise HTTPException(status_code=400, detail="名称长度不能超过 60 个字")
    openid = require_same_user(req.openid, current_openid)
    rename_meme_task(req.task_id, req.title.strip(), openid)
    return {"success": True, "message": "作品备注修改成功", "new_title": req.title.strip()}

@router.get("/estimate")
@router.get("/meme/estimate")
def get_estimate_duration():
    """获取当前基于历史任务平均耗时动态拟合的预估制作时间（秒）"""
    return {
        "code": 0,
        "data": {
            "estimated_seconds": get_estimated_generation_duration()
        }
    }

class DeleteMemeRequest(BaseModel):
    task_id: str
    openid: Optional[str] = ""

@router.post("/delete")
@router.post("/meme/delete")
def delete_meme(req: DeleteMemeRequest, current_openid: CurrentOpenid):
    """从历史创作库中删除指定动图"""
    if not req.task_id:
        raise HTTPException(status_code=400, detail="任务ID不能为空")
    openid = require_same_user(req.openid, current_openid)
    if not re.fullmatch(r"(?:[0-9a-f]{8}|[0-9a-f]{32})", req.task_id):
        raise HTTPException(status_code=400, detail="任务 ID 不合法")
    deleted = delete_meme_task(req.task_id, openid)
    if not deleted:
        raise HTTPException(status_code=404, detail="作品不存在或无权删除")
    # 作品可能已被合集引用；只有未被引用时才删除任务目录。
    if not meme_task_output_is_referenced(req.task_id):
        task_dir = settings.OUTPUT_DIR / req.task_id
        if task_dir.is_dir():
            shutil.rmtree(task_dir, ignore_errors=True)
    return {"success": True, "message": "作品已从历史记录中删除"}


class AuditModeToggleRequest(BaseModel):
    audit_mode: Optional[bool] = None


@router.get("/admin/audit-mode")
def get_audit_mode():
    """获取当前审核模式状态"""
    active = is_audit_mode_active()
    return {
        "code": 0,
        "audit_mode": active,
        "message": "当前处于审核模式 (纯动效合规模式)" if active else "当前处于全量 AI 动图生成模式"
    }


@router.post("/admin/audit-mode")
def set_audit_mode(req: Optional[AuditModeToggleRequest] = None, mode: Optional[str] = None):
    """动态切换审核模式（无需重启服务，即时生效）"""
    target = True
    if req and req.audit_mode is not None:
        target = req.audit_mode
    elif mode is not None:
        target = mode.lower() in ("true", "1", "on", "yes")

    set_app_setting("audit_mode", "true" if target else "false")
    active = is_audit_mode_active()
    return {
        "code": 0,
        "audit_mode": active,
        "message": f"审核模式已{'开启 (纯动效合规模式)' if active else '关闭 (全量 AI 动图模式)'}"
    }

