import io
import os
import shutil
import zipfile
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

from PIL import Image, ImageDraw, ImageOps, ImageEnhance, ImageFilter
from app.config import settings
from app.api.convert import _get_cjk_font
from app.core.prompt_templates import SCENE_TEXT_PACKAGES, EMOTION_TAGS_16
from app.core.sprite_processor import SpriteProcessor

logger = logging.getLogger(__name__)

AUDIT_STICKER_EMOJIS = [
    "👍", "✌", "💻", "☕",
    "🤯", "😭", "😡", "😱",
    "🙄", "❓", "😎", "😳",
    "🙏", "🍉", "😴", "🏃"
]

COLOR_FILTERS = [
    (1.0, 1.0, 1.0),   # 01 原色
    (1.08, 1.05, 1.0), # 02 暖阳
    (0.98, 1.05, 1.1), # 03 清爽冷色
    (1.1, 1.0, 0.95),  # 04 奶茶温暖
    (1.15, 0.95, 0.95),# 05 怒意微红
    (0.92, 0.96, 1.12),# 06 泪目幽蓝
    (1.2, 0.9, 0.9),   # 07 炽热高燃
    (1.05, 1.1, 0.98), # 08 惊艳浅绿
    (1.0, 1.0, 1.05),  # 09 沉静白眼
    (1.05, 1.02, 1.08),# 10 疑惑微紫
    (0.95, 0.95, 0.95),# 11 酷黑降调
    (1.15, 1.02, 1.08),# 12 羞涩粉嫩
    (1.06, 1.04, 0.96),# 13 诚恳麦金
    (1.0, 1.12, 1.02), # 14 清甜瓜绿
    (0.92, 0.92, 1.05),# 15 睡意昏暗
    (1.1, 1.08, 1.0)   # 16 冲刺生机
]


def _generate_default_avatar(size: tuple[int, int]) -> Image.Image:
    """生成一个规整的默认卡通头像"""
    img = Image.new("RGBA", size, (241, 245, 249, 255))
    draw = ImageDraw.Draw(img)
    w, h = size
    # 绘制可爱的圆脸轮廓
    pad = int(w * 0.15)
    draw.ellipse([pad, pad, w - pad, h - pad], fill=(254, 226, 226, 255), outline=(239, 68, 68, 255), width=4)
    # 眼睛
    eye_r = int(w * 0.05)
    draw.ellipse([int(w * 0.35) - eye_r, int(h * 0.42) - eye_r, int(w * 0.35) + eye_r, int(h * 0.42) + eye_r], fill=(30, 41, 59, 255))
    draw.ellipse([int(w * 0.65) - eye_r, int(h * 0.42) - eye_r, int(w * 0.65) + eye_r, int(h * 0.42) + eye_r], fill=(30, 41, 59, 255))
    # 腮红
    draw.ellipse([int(w * 0.28) - eye_r, int(h * 0.52) - eye_r, int(w * 0.28) + eye_r, int(h * 0.52) + eye_r], fill=(252, 165, 165, 180))
    draw.ellipse([int(w * 0.72) - eye_r, int(h * 0.52) - eye_r, int(w * 0.72) + eye_r, int(h * 0.52) + eye_r], fill=(252, 165, 165, 180))
    # 微笑
    draw.arc([int(w * 0.38), int(h * 0.46), int(w * 0.62), int(h * 0.62)], 0, 180, fill=(30, 41, 59, 255), width=4)
    return img


def create_audit_stickers(
    task_id: str,
    task_dir: Path,
    ref_image_bytes: Optional[bytes],
    text_package: str = "none",
    custom_texts: Optional[List[str]] = None,
    target_size_px: int = 256
) -> Dict[str, Any]:
    """
    审核模式专用 16 款静态表情贴纸本地生成器。
    100% 运行于本地 PIL 图像处理引擎，不调用任何 AI 大模型接口。
    合规属性：工具 - 图片文字处理。
    """
    task_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = task_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    target_size_px = max(240, min(512, target_size_px or 256))
    size = (target_size_px, target_size_px)

    # 1. 解析基础人像
    has_image = ref_image_bytes is not None and len(ref_image_bytes) > 0
    if has_image:
        try:
            raw_img = Image.open(io.BytesIO(ref_image_bytes)).convert("RGBA")
            raw_img.save(task_dir / "original_image.png", format="PNG")
        except Exception as e:
            logger.warning("解析用户原始图失败，回退到默认卡片: %s", e)
            raw_img = _generate_default_avatar(size)
    else:
        raw_img = _generate_default_avatar(size)
        raw_img.save(task_dir / "original_image.png", format="PNG")

    # 居中裁切成正方形
    base_char = ImageOps.fit(raw_img, (int(target_size_px * 0.85), int(target_size_px * 0.85)), Image.Resampling.LANCZOS)

    # 2. 准备文字
    if custom_texts and len(custom_texts) >= 16:
        texts = [t.strip() for t in custom_texts[:16]]
    else:
        texts = SCENE_TEXT_PACKAGES.get(text_package, [""] * 16)

    emoji_font = _get_cjk_font(size=int(target_size_px * 0.16), bold=True)

    frames: List[Image.Image] = []
    frame_preview_items: List[Dict[str, Any]] = []

    for i in range(16):
        canvas = Image.new("RGBA", size, (255, 255, 255, 255))

        # 色调微调
        rf, gf, bf = COLOR_FILTERS[i % len(COLOR_FILTERS)]
        r, g, b, a = base_char.split()
        r = r.point(lambda p: min(255, int(p * rf)))
        g = g.point(lambda p: min(255, int(p * gf)))
        b = b.point(lambda p: min(255, int(p * bf)))
        filtered_char = Image.merge("RGBA", (r, g, b, a))

        # 居中粘贴
        cx = (target_size_px - filtered_char.width) // 2
        cy = int(target_size_px * 0.06)
        canvas.paste(filtered_char, (cx, cy), filtered_char)

        # 叠加趣味 Emoji 角标
        draw = ImageDraw.Draw(canvas)
        emoji_char = AUDIT_STICKER_EMOJIS[i]
        em_x = int(target_size_px * 0.78)
        em_y = int(target_size_px * 0.08)
        try:
            draw.text((em_x, em_y), emoji_char, font=emoji_font, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 200))
        except Exception:
            pass

        frames.append(canvas)

    # 3. 叠加规则排版文字
    if text_package != "none" or any(texts):
        frames = SpriteProcessor.overlay_text_to_frames(frames, texts, style="stroke")

    # 4. 保存 16 张 PNG 与 ZIP
    stickers_dir = task_dir / "stickers"
    stickers_dir.mkdir(parents=True, exist_ok=True)
    sticker_preview_items: List[Dict[str, Any]] = []

    for idx, f in enumerate(frames, 1):
        f_thumb_path = frames_dir / f"frame_{idx:02d}.png"
        s_thumb_path = stickers_dir / f"sticker_{idx:02d}.png"
        f.save(f_thumb_path, format="PNG")
        f.save(s_thumb_path, format="PNG")
        caption = texts[idx - 1] if idx - 1 < len(texts) else ""
        emotion = EMOTION_TAGS_16[idx - 1] if idx - 1 < len(EMOTION_TAGS_16) else ""
        item_data = {
            "index": idx,
            "url": f"/outputs/{task_id}/stickers/sticker_{idx:02d}.png",
            "frame_url": f"/outputs/{task_id}/frames/frame_{idx:02d}.png",
            "text": caption,
            "caption": caption,
            "emotion": emotion
        }
        frame_preview_items.append(item_data)
        sticker_preview_items.append(item_data)

    # 组装 4x4 雪碧图 input_sprite.png
    sprite_sheet = Image.new("RGBA", (1024, 1024), (255, 255, 255, 255))
    for idx, f in enumerate(frames):
        row = idx // 4
        col = idx % 4
        scaled_f = f.resize((256, 256), Image.Resampling.LANCZOS)
        sprite_sheet.paste(scaled_f, (col * 256, row * 256))
    sprite_sheet.save(task_dir / "input_sprite.png", format="PNG")

    zip_path = task_dir / "stickers_pack.zip"
    SpriteProcessor.package_zip(frames, str(zip_path), make_transparent=False)
    shutil.copyfile(zip_path, task_dir / "frames_pack.zip")

    return {
        "task_id": task_id,
        "output_mode": "sticker16",
        "style_preset": "keep_orig",
        "composition_preset": "bust",
        "bg_preset": "white",
        "text_package": text_package,
        "frames": frame_preview_items,
        "stickers": sticker_preview_items,
        "sprite_url": f"/outputs/{task_id}/input_sprite.png",
        "zip_url": f"/outputs/{task_id}/stickers_pack.zip",
        "stickers_pack_url": f"/outputs/{task_id}/stickers_pack.zip",
        "stats": {
            "frame_count": 16,
            "duration_seconds": 0.8,
            "resolution": f"{target_size_px}x{target_size_px}",
            "is_audit": True
        }
    }
