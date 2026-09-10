import os
import uuid
import shutil
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from PIL import Image

from app.config import settings
from app.core.sprite_processor import SpriteProcessor
from app.core.prompt_templates import PROMPT_TEMPLATES
from app.database import check_and_deduct_quota, refund_quota, get_db

router = APIRouter(prefix="/api", tags=["Meme GIF"])

@router.get("/templates")
def get_templates():
    """获取预设动作模版列表与提示词"""
    data = []
    for t in PROMPT_TEMPLATES:
        data.append({
            "id": t["id"],
            "title": t["title"],
            "desc": t["desc"],
            "action": t["action"],
            "default_caption": t["default_caption"]
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
):
    """根据动作与角色描述，动态生成让 ChatGPT 原生绘制动态跳跃汉字的专用 Prompt"""
    template = next((t for t in PROMPT_TEMPLATES if t["id"] == action_type), PROMPT_TEMPLATES[0])
    final_prompt = template["prompt_builder"](character_desc.strip(), custom_caption.strip(), has_image, is_sketch)

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
    file: Optional[UploadFile] = File(None),
    sample_id: Optional[str] = Form(None),
    fps: int = Form(8),
    make_transparent: bool = Form(True),
    padding_percent: float = Form(2.5),
):
    """处理已有的 4x4 雪碧图：多尺度间隙切割 + 泛洪去白底 + 微信合规动图合成"""
    task_id = str(uuid.uuid4())[:8]
    task_dir = settings.OUTPUT_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    input_path = task_dir / "input_sprite.png"

    # 获取输入图像
    if file and file.filename:
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        source_image = Image.open(input_path).convert("RGB")
    elif sample_id:
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
    frames = SpriteProcessor.slice_grid(source_image, rows=4, cols=4, padding_percent=padding_percent)

    # 2. 生成透明动图 GIF (完美保留原画原生字幕)
    gif_path = task_dir / "meme_result.gif"
    stats = SpriteProcessor.assemble_gif(
        frames=frames,
        output_path=str(gif_path),
        fps=fps,
        make_transparent=make_transparent
    )

    # 3. 生成 16 帧独立 PNG ZIP 包
    zip_path = task_dir / "frames_pack.zip"
    SpriteProcessor.package_zip(
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

    return {
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

@router.post("/generate-and-process")
async def generate_and_process(
    ref_image: Optional[UploadFile] = File(None),
    action_type: str = Form("kiss"),
    custom_caption: str = Form(""),
    character_desc: str = Form(""),
    fps: int = Form(8),
    make_transparent: bool = Form(True),
    padding_percent: float = Form(2.5),
):
    """一键调用 ChatGPT Plus (Images 2.5) 生成 16 宫格雪碧图，并直接切片制作成透明 GIF"""
    import io
    import base64
    import httpx

    # 1. 组装提示词
    has_image = ref_image is not None and getattr(ref_image, "filename", None) not in [None, ""]
    template = next((t for t in PROMPT_TEMPLATES if t["id"] == action_type), PROMPT_TEMPLATES[0])
    prompt = template["prompt_builder"](character_desc.strip(), custom_caption.strip(), has_image)

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
                raise HTTPException(status_code=502, detail=f"AI 出图服务异常 ({resp.status_code}): {resp.text}")
            resp_data = resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI 生成图片超时 (超过150秒)，请稍后重试")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"请求 AI 网关失败: {str(e)}")

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
    task_id = str(uuid.uuid4())[:8]
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
import asyncio
TASK_STORE: dict[str, dict] = {}

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
):
    """后台异步执行完整的生图、切割与动图合成流水线"""
    import io
    import base64
    import httpx

    try:
        # 阶段 1：组装提示词
        stage_desc = "阶段 1/4: 结合手绘草图造型与动作语义对齐..." if is_sketch else "阶段 1/4: 组装角色提示词与人设语义对齐..."
        TASK_STORE[task_id] = {
            "status": "processing",
            "progress": 10,
            "stage": "prompt",
            "stage_text": stage_desc
        }

        has_image = ref_image_bytes is not None and len(ref_image_bytes) > 0
        template = next((t for t in PROMPT_TEMPLATES if t["id"] == action_type), PROMPT_TEMPLATES[0])
        prompt = template["prompt_builder"](character_desc.strip(), custom_caption.strip(), has_image, is_sketch)

        # 阶段 2：请求画质渲染引擎出图
        TASK_STORE[task_id] = {
            "status": "processing",
            "progress": 25,
            "stage": "drawing",
            "stage_text": "阶段 2/4: 智能画质渲染引擎正在逐帧绘制 16 宫格动图..."
        }

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
                raise RuntimeError(f"AI 出图服务异常 ({resp.status_code}): {resp.text}")
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
            raise RuntimeError("未能从 AI 响应中解析出图片数据")

        # 阶段 3：多尺度主间隙物理网格切割
        TASK_STORE[task_id] = {
            "status": "processing",
            "progress": 75,
            "stage": "slicing",
            "stage_text": "阶段 3/4: 多尺度主间隙物理网格切割与角色紧致包络裁剪..."
        }

        task_dir = settings.OUTPUT_DIR / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        input_path = task_dir / "input_sprite.png"
        source_image.save(input_path, format="PNG")

        frames = SpriteProcessor.slice_grid(source_image, rows=4, cols=4, padding_percent=padding_percent)

        # 阶段 4：固定色差泛洪去底与动图生成
        TASK_STORE[task_id] = {
            "status": "processing",
            "progress": 90,
            "stage": "assembling",
            "stage_text": "阶段 4/4: 固定色差泛洪去底并封装微信 GIF 动图..."
        }

        gif_path = task_dir / "meme_result.gif"
        stats = SpriteProcessor.assemble_gif(
            frames=frames,
            output_path=str(gif_path),
            fps=fps,
            make_transparent=make_transparent
        )

        zip_path = task_dir / "frames_pack.zip"
        SpriteProcessor.package_zip(
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

        # 完成
        TASK_STORE[task_id] = {
            "status": "completed",
            "progress": 100,
            "stage": "done",
            "stage_text": "🎉 制作全部完成！正在导出动图预览...",
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

        # 记录到 SQLite 表情包任务库
        if openid:
            try:
                with get_db() as conn:
                    conn.execute('''
                        INSERT INTO meme_tasks (task_id, openid, prompt, preset_key, text_bottom, fps, status, progress, gif_url, sprite_url)
                        VALUES (?, ?, ?, ?, ?, ?, 'completed', 100, ?, ?)
                    ''', (task_id, openid, prompt, action_type, custom_caption, fps, f"/outputs/{task_id}/meme_result.gif", f"/outputs/{task_id}/input_sprite.png"))
                    conn.commit()
            except Exception:
                pass

    except Exception as e:
        if openid:
            refund_quota(openid)
        TASK_STORE[task_id] = {
            "status": "failed",
            "progress": 100,
            "stage": "error",
            "stage_text": "出图失败",
            "error": str(e)
        }

@router.post("/generate-async")
async def generate_async(
    ref_image: Optional[UploadFile] = File(None),
    action_type: str = Form("kiss"),
    custom_caption: str = Form(""),
    character_desc: str = Form(""),
    fps: int = Form(8),
    make_transparent: bool = Form(True),
    padding_percent: float = Form(2.5),
    is_sketch: bool = Form(False),
    openid: Optional[str] = Form(""),
    resolution: Optional[str] = Form("240x240"),
    fast_mode: Optional[str] = Form("1"),
    loop_count: Optional[int] = Form(0),
):
    """【推荐】异步启动动图生图任务，前端通过轮询获取实时进度与结果，绝无 HTTP 超时问题"""
    # 额度扣减审查 (支持游客体验或绑定 openid 扣点)
    if openid:
        quota_res = check_and_deduct_quota(openid)
        if not quota_res.get("allowed"):
            raise HTTPException(status_code=403, detail=quota_res.get("error", "制作次数已耗尽，请签到或开通尝鲜包！"))

    task_id = str(uuid.uuid4())[:8]

    ref_image_bytes = None
    if ref_image is not None and getattr(ref_image, "filename", None) not in [None, ""]:
        ref_image_bytes = await ref_image.read()

    TASK_STORE[task_id] = {
        "status": "processing",
        "progress": 5,
        "stage": "init",
        "stage_text": "正在初始化任务..."
    }

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
        openid=openid or ""
    ))

    return {
        "code": 0,
        "message": "task_started",
        "data": {
            "task_id": task_id,
            "status": "processing"
        }
    }

@router.get("/task-status/{task_id}")
def get_task_status(task_id: str):
    """查询异步任务的实时执行状态与进度"""
    # 先查内存
    if task_id in TASK_STORE:
        task_info = TASK_STORE[task_id]
        return {
            "code": 0,
            "data": task_info
        }

    # 再查磁盘是否已有历史成果 (如 df4492bd 等)
    task_dir = settings.OUTPUT_DIR / task_id
    if (task_dir / "meme_result.gif").exists():
        frames_dir = task_dir / "frames"
        frame_urls = [f"/outputs/{task_id}/frames/{f.name}" for f in sorted(frames_dir.glob("*.png"))]
        return {
            "code": 0,
            "data": {
                "status": "completed",
                "progress": 100,
                "data": {
                    "task_id": task_id,
                    "gif_url": f"/outputs/{task_id}/meme_result.gif",
                    "zip_url": f"/outputs/{task_id}/frames_pack.zip",
                    "input_url": f"/outputs/{task_id}/input_sprite.png",
                    "frames": frame_urls,
                    "stats": {
                        "frame_count": len(frame_urls),
                        "file_size_kb": round((task_dir / "meme_result.gif").stat().st_size / 1024, 1),
                        "duration_per_frame_ms": 125
                    }
                }
            }
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
def list_history(openid: Optional[str] = None):
    """获取用户生成表情包历史或全局作品展示"""
    with get_db() as conn:
        cursor = conn.cursor()
        if openid:
            cursor.execute("SELECT * FROM meme_tasks WHERE openid = ? ORDER BY created_at DESC LIMIT 30", (openid,))
        else:
            cursor.execute("SELECT * FROM meme_tasks WHERE status = 'completed' ORDER BY created_at DESC LIMIT 20")
        rows = [dict(r) for r in cursor.fetchall()]
    return {"code": 0, "data": rows}

