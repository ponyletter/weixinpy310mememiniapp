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
):
    """根据动作与角色描述，动态生成让 ChatGPT 原生绘制动态跳跃汉字的专用 Prompt"""
    template = next((t for t in PROMPT_TEMPLATES if t["id"] == action_type), PROMPT_TEMPLATES[0])
    
    caption_text = custom_caption.strip() if custom_caption.strip() else template["default_caption"]
    final_prompt = template["prompt_builder"](character_desc.strip(), caption_text)

    return {
        "code": 0,
        "data": {
            "template_id": template["id"],
            "action": template["action"],
            "caption": caption_text,
            "generated_prompt": final_prompt
        }
    }

@router.post("/process-sprite")
async def process_sprite_sheet(
    file: Optional[UploadFile] = File(None),
    sample_id: Optional[str] = Form(None),
    fps: int = Form(8),
    make_transparent: bool = Form(True),
    padding_percent: float = Form(0.03)
):
    """
    核心接口：接收 4x4 精灵大图，执行切片、智能外围去白底、GIF合成与ZIP导出
    （完整保留 ChatGPT 原画中随动作弹跳的原生动态艺术字！）
    """
    task_id = str(uuid.uuid4())[:8]
    task_dir = settings.OUTPUT_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    input_img_path = task_dir / "input_sprite.png"

    if file and file.filename:
        with open(input_img_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    elif sample_id:
        sample_path = settings.SAMPLES_DIR / f"{sample_id}.png"
        if not sample_path.exists():
            raise HTTPException(status_code=404, detail="测试样本图片不存在")
        shutil.copy(sample_path, input_img_path)
    else:
        raise HTTPException(status_code=400, detail="请上传 4x4 精灵大图或选择示例")

    try:
        source_image = Image.open(input_img_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无法解析图片: {str(e)}")

    # 1. 切分为 16 帧 (紧凑包络裁剪，杜绝多余留白)
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
    action_type: str = Form("kiss"),
    custom_caption: str = Form(""),
    character_desc: str = Form("一只萌萌的可爱白色折耳猫"),
    fps: int = Form(8),
    make_transparent: bool = Form(True),
    padding_percent: float = Form(2.5),
):
    """一键调用 ChatGPT Plus (Images 2.5) 生成 16 宫格雪碧图，并直接切片制作成透明 GIF"""
    import io
    import base64
    import httpx

    # 1. 组装提示词
    template = next((t for t in PROMPT_TEMPLATES if t["id"] == action_type), PROMPT_TEMPLATES[0])
    caption_text = custom_caption.strip() if custom_caption.strip() else template["default_caption"]
    prompt = template["prompt_builder"](character_desc.strip(), caption_text)

    # 2. 调用 CLIProxyAPI (ChatGPT Plus 出海中转网关)
    headers = {
        "Authorization": f"Bearer {settings.CPA_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": settings.CPA_IMAGE_MODEL,
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024"
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.CPA_API_BASE}/images/generations",
                headers=headers,
                json=payload
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"AI 出图服务异常 ({resp.status_code}): {resp.text}")
            resp_data = resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI 生成图片超时 (超过120秒)，请稍后重试")
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

