import io
import os
import math
import zipfile
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

from PIL import Image, ImageDraw, ImageOps, ImageEnhance
from app.config import settings
from app.api.convert import _get_cjk_font

logger = logging.getLogger(__name__)

THEME_STICKERS = {
    "kiss": "❤",
    "heart_dance": "❤",
    "battle_chibi": "★",
    "slack_worker": "☕",
    "pet_idle": "🐾",
    "custom": "✨"
}

THEME_STICKER_COLORS = {
    "kiss": (244, 63, 94, 255),       # Rose
    "heart_dance": (236, 72, 153, 255), # Pink
    "battle_chibi": (234, 179, 8, 255),  # Yellow Gold
    "slack_worker": (59, 130, 246, 255), # Blue
    "pet_idle": (16, 185, 129, 255),    # Emerald
    "custom": (168, 85, 247, 255)       # Purple
}


def create_audit_meme_gif(
    task_id: str,
    task_dir: Path,
    ref_image_bytes: Optional[bytes],
    action_type: str,
    custom_caption: str,
    target_size_px: int = 256
) -> Dict[str, Any]:
    """
    审核模式专用静态表情包/纯图像动效生成器。
    100% 运行于本地 PIL 图像处理引擎，不调用任何深度合成或 AI 大模型接口。
    合规属性：工具 - 图片处理。
    """
    task_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = task_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    target_size_px = max(240, min(512, target_size_px or 256))
    size = (target_size_px, target_size_px)

    # 1. 准备原始基础图片
    has_image = ref_image_bytes is not None and len(ref_image_bytes) > 0
    if has_image:
        try:
            raw_img = Image.open(io.BytesIO(ref_image_bytes)).convert("RGBA")
            # 保存原始图
            raw_img.save(task_dir / "original_image.png", format="PNG")
        except Exception as e:
            logger.warning("解析用户原始图失败，回退到默认卡片: %s", e)
            raw_img = _generate_default_avatar(size)
    else:
        raw_img = _generate_default_avatar(size)
        raw_img.save(task_dir / "original_image.png", format="PNG")

    # 居中缩放并裁剪为正方形
    base_character = ImageOps.fit(raw_img, (int(target_size_px * 0.82), int(target_size_px * 0.82)), Image.Resampling.LANCZOS)

    # 2. 准备字体与文字
    caption = custom_caption.strip() if custom_caption else "么么哒"
    font_size = max(18, min(36, int(target_size_px * 0.11)))
    font = _get_cjk_font(size=font_size, bold=True)
    sticker_font = _get_cjk_font(size=int(font_size * 1.3), bold=True)

    sticker_char = THEME_STICKERS.get(action_type, "✨")
    sticker_color = THEME_STICKER_COLORS.get(action_type, (168, 85, 247, 255))

    # 3. 生成 4 帧富有动感的趣味表情包
    # 动效原理：轻量级弹性缩放 + 文字跃动 + 贴纸闪烁（纯图形学关键帧仿射）
    scales = [1.0, 1.03, 1.055, 1.02]
    text_y_offsets = [0, -3, -6, -2]
    sticker_scales = [0.85, 1.05, 1.25, 1.0]

    pil_frames: List[Image.Image] = []
    frame_preview_urls: List[str] = []

    for i in range(4):
        # 画布底板
        canvas = Image.new("RGBA", size, color=(255, 255, 255, 255))

        # 角色图弹性缩放
        sc = scales[i]
        cw = int(base_character.width * sc)
        ch = int(base_character.height * sc)
        scaled_char = base_character.resize((cw, ch), Image.Resampling.LANCZOS)
        cx = (target_size_px - cw) // 2
        cy = int((target_size_px * 0.42) - (ch // 2)) + (text_y_offsets[i] // 2)

        # 粘贴角色图
        canvas.paste(scaled_char, (cx, cy), scaled_char)

        draw = ImageDraw.Draw(canvas)

        # 绘制动态装饰贴纸 (右上角)
        st_x = int(target_size_px * 0.80)
        st_y = int(target_size_px * 0.12) + (text_y_offsets[i])
        try:
            draw.text(
                (st_x, st_y),
                sticker_char,
                font=sticker_font,
                fill=sticker_color,
                stroke_width=2,
                stroke_fill=(255, 255, 255, 255)
            )
        except Exception:
            pass

        # 绘制底部文字 (经典表情包粗边描摹)
        t_bbox = draw.textbbox((0, 0), caption, font=font)
        tw = t_bbox[2] - t_bbox[0]
        th = t_bbox[3] - t_bbox[1]
        tx = (target_size_px - tw) // 2
        ty = int(target_size_px * 0.84) + text_y_offsets[i]

        # 绘制文字阴影背景椭圆衬底 (提升任何背景上的可读性)
        pill_pad_x = 16
        pill_pad_y = 6
        pill_box = [
            tx - pill_pad_x,
            ty - pill_pad_y,
            tx + tw + pill_pad_x,
            ty + th + pill_pad_y
        ]
        draw.rounded_rectangle(pill_box, radius=12, fill=(30, 41, 59, 215))

        # 居中绘制高亮文字
        draw.text(
            (tx, ty - 2),
            caption,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=1,
            stroke_fill=(15, 23, 42, 255)
        )

        # 保存为独立帧 PNG
        frame_filename = f"frame_{i:02d}.png"
        frame_path = frames_dir / frame_filename
        canvas.save(frame_path, format="PNG")
        frame_preview_urls.append(f"/outputs/{task_id}/frames/{frame_filename}")

        # 转换为带调色板的 GIF 帧
        gif_frame = canvas.convert("P", palette=Image.Palette.ADAPTIVE)
        pil_frames.append(gif_frame)

    # 4. 导出合成表情动图 meme_result.gif
    gif_out_path = task_dir / "meme_result.gif"
    pil_frames[0].save(
        gif_out_path,
        format="GIF",
        save_all=True,
        append_images=pil_frames[1:],
        duration=260,  # 260ms 帧间隔
        loop=0,
        optimize=True
    )

    # 5. 导出 2x2 input_sprite.png (用于兼容网格与缩略图展示)
    sprite_w = target_size_px * 2
    sprite_h = target_size_px * 2
    sprite_canvas = Image.new("RGBA", (sprite_w, sprite_h), (255, 255, 255, 255))
    coords = [(0, 0), (target_size_px, 0), (0, target_size_px), (target_size_px, target_size_px)]
    for idx, (gx, gy) in enumerate(coords):
        if idx < len(pil_frames):
            frame_img = Image.open(frames_dir / f"frame_{idx:02d}.png")
            sprite_canvas.paste(frame_img, (gx, gy))
    sprite_canvas.save(task_dir / "input_sprite.png", format="PNG")

    # 6. 导出 ZIP 打包
    zip_path = task_dir / "frames_pack.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f_name in sorted(os.listdir(frames_dir)):
            zf.write(frames_dir / f_name, arcname=f_name)
        zf.write(gif_out_path, arcname="meme_result.gif")

    file_size_kb = round(gif_out_path.stat().st_size / 1024, 1)

    return {
        "task_id": task_id,
        "gif_url": f"/outputs/{task_id}/meme_result.gif",
        "thumb_url": f"/outputs/{task_id}/meme_result.gif",
        "zip_url": f"/outputs/{task_id}/frames_pack.zip",
        "input_url": f"/outputs/{task_id}/input_sprite.png",
        "original_image_url": f"/outputs/{task_id}/original_image.png",
        "caption": caption,
        "frames": frame_preview_urls,
        "stats": {
            "frame_count": 4,
            "file_size_kb": file_size_kb,
            "duration_per_frame_ms": 260,
            "duration_seconds": 2.1,
            "is_wechat_compliant": True,
            "resolution": f"{target_size_px}x{target_size_px}"
        },
        "duration_seconds": 2.1
    }


def _generate_default_avatar(size: tuple[int, int]) -> Image.Image:
    """生成合规的默认可爱简约头像卡片"""
    w, h = size
    img = Image.new("RGBA", (w, h), color=(241, 245, 249, 255))
    draw = ImageDraw.Draw(img)

    # 绘制可爱的圆脸萌物
    r = int(min(w, h) * 0.38)
    cx, cy = w // 2, h // 2
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(99, 102, 241, 255))

    # 眼睛
    eye_r = max(4, int(r * 0.12))
    draw.ellipse([cx - int(r * 0.35) - eye_r, cy - int(r * 0.15) - eye_r, cx - int(r * 0.35) + eye_r, cy - int(r * 0.15) + eye_r], fill=(255, 255, 255, 255))
    draw.ellipse([cx + int(r * 0.35) - eye_r, cy - int(r * 0.15) - eye_r, cx + int(r * 0.35) + eye_r, cy - int(r * 0.15) + eye_r], fill=(255, 255, 255, 255))

    # 腮红
    blush_r = int(eye_r * 1.3)
    draw.ellipse([cx - int(r * 0.45) - blush_r, cy + int(r * 0.1) - blush_r, cx - int(r * 0.45) + blush_r, cy + int(r * 0.1) + blush_r], fill=(251, 113, 133, 180))
    draw.ellipse([cx + int(r * 0.45) - blush_r, cy + int(r * 0.1) - blush_r, cx + int(r * 0.45) + blush_r, cy + int(r * 0.1) + blush_r], fill=(251, 113, 133, 180))

    # 微笑弧线
    draw.arc([cx - int(r * 0.25), cy - int(r * 0.05), cx + int(r * 0.25), cy + int(r * 0.35)], start=10, end=170, fill=(255, 255, 255, 255), width=max(2, int(r * 0.06)))

    return img
