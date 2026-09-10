import io
import os
import zipfile
from pathlib import Path
from typing import List, Tuple, Optional
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "fonts"

FONT_MAP = {
    "smiley_sans": FONTS_DIR / "SmileySans-Oblique.ttf",
    "noto_sans": FONTS_DIR / "NotoSansSC-Bold.ttf",
}

class SpriteProcessor:
    @staticmethod
    def slice_grid(image: Image.Image, rows: int = 4, cols: int = 4) -> List[Image.Image]:
        """将 4x4 精灵大图精准切分为 16 个小帧"""
        w, h = image.size
        cell_w = w // cols
        cell_h = h // rows

        frames = []
        for r in range(rows):
            for c in range(cols):
                box = (c * cell_w, r * cell_h, (c + 1) * cell_w, (r + 1) * cell_h)
                frame = image.crop(box)
                frames.append(frame)
        return frames

    @staticmethod
    def remove_white_bg(frame: Image.Image, tolerance: int = 28) -> Image.Image:
        """
        超高速 C++ OpenCV 洪水填充去白底算法。
        仅从 4 个边角向内扩散，剔除外围白色背景，
        100% 完整保留角色内部眼白、白衣服或亮斑！
        """
        rgba = np.array(frame.convert("RGBA"))
        h, w = rgba.shape[:2]

        # 采样 4 角背景色
        corners = [rgba[0, 0, :3], rgba[0, w - 1, :3], rgba[h - 1, 0, :3], rgba[h - 1, w - 1, :3]]
        if not any(np.all(c > 190) for c in corners):
            return frame

        bgr = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)
        mask = np.zeros((h + 2, w + 2), np.uint8)

        # 从 4 个边缘角落进行 FloodFill 遮罩标记
        tol = int(tolerance)
        for seed in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
            if mask[seed[1] + 1, seed[0] + 1] == 0:
                cv2.floodFill(
                    bgr, mask, seed, 0,
                    loDiff=(tol, tol, tol),
                    upDiff=(tol, tol, tol),
                    flags=4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY
                )

        # 将被识别为外围背景的像素 Alpha 置零
        bg_mask = mask[1:h + 1, 1:w + 1] == 255
        rgba[bg_mask, 3] = 0

        return Image.fromarray(rgba)

    @classmethod
    def get_font(cls, font_family: str, font_size: int) -> ImageFont.FreeTypeFont:
        """加载开源无版权争议商用字体（得意黑 Smiley Sans / 思源黑体 Noto Sans SC）"""
        target_path = FONT_MAP.get(font_family, FONT_MAP["smiley_sans"])
        if target_path and target_path.exists():
            try:
                return ImageFont.truetype(str(target_path), font_size)
            except Exception:
                pass

        # 系统兜底
        system_noto = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
        if os.path.exists(system_noto):
            try:
                return ImageFont.truetype(system_noto, font_size)
            except Exception:
                pass

        return ImageFont.load_default()

    @classmethod
    def overlay_caption(
        cls,
        frame: Image.Image,
        text: str,
        font_family: str = "smiley_sans",
        font_size: int = 26,
        position: str = "bottom",  # bottom, top, outside_bottom (外挂留白 100%防遮挡)
    ) -> Image.Image:
        """
        在帧上绘制防遮挡、高对比度醒目字幕。
        支持：画内居底、画内居顶、外挂底部留白（100%不遮挡角色主体）
        """
        if not text or not text.strip() or position == "none":
            return frame

        orig_w, orig_h = frame.size

        # 外挂留白模式：在底部拓展一段透明/安全留白区域，专供字幕显示
        if position == "outside_bottom":
            extra_h = max(42, font_size + 18)
            canvas = Image.new("RGBA", (orig_w, orig_h + extra_h), (0, 0, 0, 0))
            canvas.paste(frame.convert("RGBA"), (0, 0))
            w, h = canvas.size
        else:
            canvas = frame.copy().convert("RGBA")
            w, h = canvas.size

        draw = ImageDraw.Draw(canvas)

        # 动态自适应字号：如果文字字数多，自动递减缩小字号避免截断
        adjusted_size = font_size
        font = cls.get_font(font_family, adjusted_size)
        while adjusted_size > 14:
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                tw = bbox[2] - bbox[0]
                if tw <= (w - 20):
                    break
            except Exception:
                break
            adjusted_size -= 2
            font = cls.get_font(font_family, adjusted_size)

        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except Exception:
            tw, th = len(text) * adjusted_size // 2, adjusted_size

        x = (w - tw) // 2

        # 位置计算
        if position == "outside_bottom":
            y = orig_h + (extra_h - th) // 2 - 2
        elif position == "top":
            y = int(h * 0.05)
        else:
            # 默认：画内居底
            y = h - th - int(h * 0.06)

        # 8 方向加粗纯黑描边 (3px) + 纯白文字，任何底色下均清晰可见
        outline_color = (0, 0, 0, 255)
        text_color = (255, 255, 255, 255)
        stroke_offsets = [
            (-2, 0), (2, 0), (0, -2), (0, 2),
            (-2, -2), (2, -2), (-2, 2), (2, 2),
            (-1, -2), (1, -2), (-1, 2), (1, 2),
            (-2, -1), (2, -1), (-2, 1), (2, 1)
        ]
        for dx, dy in stroke_offsets:
            draw.text((x + dx, y + dy), text, font=font, fill=outline_color)

        draw.text((x, y), text, font=font, fill=text_color)

        return canvas

    @classmethod
    def assemble_gif(
        cls,
        frames: List[Image.Image],
        output_path: str,
        fps: int = 8,
        make_transparent: bool = True,
        caption: Optional[str] = None,
        font_family: str = "smiley_sans",
        font_size: int = 26,
        caption_position: str = "bottom"
    ) -> dict:
        """
        完整工作流：处理每一帧（超快去白底 + 防遮挡字幕叠加）并合成为微信标准 GIF
        """
        duration_ms = int(1000 / max(1, min(fps, 30)))
        processed_frames: List[Image.Image] = []

        for frame in frames:
            f = frame
            if make_transparent:
                f = cls.remove_white_bg(f)
            if caption:
                f = cls.overlay_caption(
                    frame=f,
                    text=caption,
                    font_family=font_family,
                    font_size=font_size,
                    position=caption_position
                )
            processed_frames.append(f)

        gif_frames = []
        for pf in processed_frames:
            alpha = pf.split()[-1]
            p_img = pf.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=255)
            mask = Image.eval(alpha, lambda a: 255 if a <= 128 else 0)
            p_img.paste(255, mask)
            gif_frames.append(p_img)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        gif_frames[0].save(
            output_path,
            save_all=True,
            append_images=gif_frames[1:],
            duration=duration_ms,
            loop=0,
            transparency=255,
            disposal=2,
            optimize=True
        )

        file_size = os.path.getsize(output_path)
        out_w, out_h = processed_frames[0].size
        return {
            "output_path": output_path,
            "frame_count": len(frames),
            "width": out_w,
            "height": out_h,
            "fps": fps,
            "duration_per_frame_ms": duration_ms,
            "file_size_bytes": file_size,
            "file_size_kb": round(file_size / 1024, 2),
            "font_family": font_family,
            "caption_position": caption_position,
            "is_wechat_compliant": file_size < (1024 * 1024)
        }

    @classmethod
    def package_zip(
        cls,
        frames: List[Image.Image],
        output_path: str,
        caption: Optional[str] = None,
        font_family: str = "smiley_sans",
        font_size: int = 26,
        caption_position: str = "bottom"
    ) -> str:
        """打包 16 张独立的透明 PNG 帧为 ZIP"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for idx, frame in enumerate(frames, 1):
                f = cls.remove_white_bg(frame)
                if caption:
                    f = cls.overlay_caption(
                        frame=f,
                        text=caption,
                        font_family=font_family,
                        font_size=font_size,
                        position=caption_position
                    )
                buf = io.BytesIO()
                f.save(buf, format="PNG")
                zf.writestr(f"frame_{idx:02d}.png", buf.getvalue())
        return output_path
