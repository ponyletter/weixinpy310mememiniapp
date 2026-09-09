import os
import uuid
import shutil
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image

from app.config import settings
from app.core.sprite_processor import SpriteProcessor
from app.core.prompt_templates import PROMPT_TEMPLATES

router = APIRouter(prefix="/api", tags=["Meme GIF"])

@router.get("/templates")
def get_templates():
    """获取预设动作模版列表与提示词"""
    return {
        "code": 0,
        "message": "success",
        "data": PROMPT_TEMPLATES
    }

@router.post("/prompt-builder")
def build_prompt(
    character_desc: str = Form(""),
    action_type: str = Form("kiss"),
    custom_caption: str = Form(""),
):
    """根据动作与角色描述，动态生成符合 ChatGPT Images 2.5 格式的最佳 Prompt"""
    template = next((t for t in PROMPT_TEMPLATES if t["id"] == action_type), PROMPT_TEMPLATES[0])
    
    caption_text = custom_caption.strip() or template["default_caption"]
    
    char_part = f"使用图中角色（{character_desc.strip()}）作为参考，" if character_desc.strip() else "使用上传图片中的角色作为参考，"
    
    final_prompt = (
        f"{char_part}制作一套 4列×4行 共16帧的连贯循环动作拆分图集。\n"
        f"动作主题：【{template['action']}】。连贯分解动作，最后一帧流畅循环回到第一帧。\n"
        f"规格要求：1024×1024 画布，每格尺寸完全一致，居中摆放并留足四周纯白安全边距。\n"
        f"背景要求：纯白色背景（RGB 255,255,255），严禁网格分割线、无多余水印。\n"
        f"附带字幕：建议每帧底部预留位置或搭配文字“{caption_text}”。"
    )

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
    caption: str = Form("")
):
    """
    核心接口：接收 4x4 精灵大图，执行切片、去白底、打标、GIF合成与ZIP导出
    """
    task_id = str(uuid.uuid4())[:8]
    task_dir = settings.OUTPUT_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    input_img_path = task_dir / "input_sprite.png"

    if file and file.filename:
        # 用户上传了图片
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

    # 1. 切分为 16 帧
    frames = SpriteProcessor.slice_grid(source_image, rows=4, cols=4)

    # 2. 生成透明/带文字的动图 GIF
    gif_path = task_dir / "meme_result.gif"
    stats = SpriteProcessor.assemble_gif(
        frames=frames,
        output_path=str(gif_path),
        fps=fps,
        make_transparent=make_transparent,
        caption=caption.strip() if caption else None
    )

    # 3. 生成 16 帧独立 PNG ZIP 包
    zip_path = task_dir / "frames_pack.zip"
    SpriteProcessor.package_zip(
        frames=frames,
        output_path=str(zip_path),
        caption=caption.strip() if caption else None
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
