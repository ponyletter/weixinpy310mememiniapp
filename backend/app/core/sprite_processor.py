import io
import os
import zipfile
from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont

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
        智能将白色/浅灰背景转为透明。
        基于外围种子扩散算法 (FloodFill Mask)，只剔除角色外部的白色，
        完整保留角色内部的眼白、白色衣服或白色高光！
        """
        rgba = frame.convert("RGBA")
        w, h = rgba.size
        pixels = rgba.load()

        # 采样 4 个边角的代表背景色 (默认为 255, 255, 255)
        corner_colors = [pixels[0, 0], pixels[w - 1, 0], pixels[0, h - 1], pixels[w - 1, h - 1]]
        # 针对每个角点，检查是否为浅色背景 (R,G,B均接近高亮)
        is_light_bg = any(c[0] > 200 and c[1] > 200 and c[2] > 200 for c in corner_colors)

        if not is_light_bg:
            # 如果背景本身不是白色，直接返回原图，避免误伤
            return rgba

        # 使用 BFS 洪水填充，仅从图像四周边缘向内寻找连续连通的白色区域作为背景
        visited = bytearray(w * h)
        queue = []

        def is_bg_pixel(r, g, b):
            return (255 - r) <= tolerance and (255 - g) <= tolerance and (255 - b) <= tolerance

        # 边缘所有像素作为种子放入队列
        for x in range(w):
            for y in (0, h - 1):
                idx = y * w + x
                r, g, b, _ = pixels[x, y]
                if is_bg_pixel(r, g, b):
                    visited[idx] = 1
                    queue.append((x, y))

        for y in range(h):
            for x in (0, w - 1):
                idx = y * w + x
                if not visited[idx]:
                    r, g, b, _ = pixels[x, y]
                    if is_bg_pixel(r, g, b):
                        visited[idx] = 1
                        queue.append((x, y))

        # BFS 扩散
        head = 0
        while head < len(queue):
            cx, cy = queue[head]
            head += 1
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if 0 <= nx < w and 0 <= ny < h:
                    n_idx = ny * w + nx
                    if not visited[n_idx]:
                        nr, ng, nb, _ = pixels[nx, ny]
                        if is_bg_pixel(nr, ng, nb):
                            visited[n_idx] = 1
                            queue.append((nx, ny))

        # 将外围被标记的背景像素 Alpha 置为 0 (透明)
        for y in range(h):
            for x in range(w):
                if visited[y * w + x]:
                    r, g, b, _ = pixels[x, y]
                    pixels[x, y] = (r, g, b, 0)

        return rgba

    @staticmethod
    def overlay_caption(frame: Image.Image, text: str, font_size: int = 24) -> Image.Image:
        """在帧底部居中绘制带黑色描边的醒目字幕"""
        if not text or not text.strip():
            return frame

        canvas = frame.copy().convert("RGBA")
        draw = ImageDraw.Draw(canvas)
        w, h = canvas.size

        # 尝试加载系统常见中文字体，退化为默认字体
        font = None
        font_candidates = [
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        for path in font_candidates:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, font_size)
                    break
                except Exception:
                    continue

        if font is None:
            font = ImageFont.load_default()

        # 计算文字包围盒以居中
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except Exception:
            tw, th = len(text) * font_size // 2, font_size

        x = (w - tw) // 2
        y = h - th - int(h * 0.08)  # 距底部留白

        # 绘制黑底描边 (8 方向) 确保在任何背景下均清晰可见
        outline_color = (0, 0, 0, 255)
        text_color = (255, 255, 255, 255)
        for dx, dy in ((-2,0), (2,0), (0,-2), (0,2), (-1,-1), (1,-1), (-1,1), (1,1)):
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
        caption: Optional[str] = None
    ) -> dict:
        """
        完整工作流：处理每一帧（透明化 + 加字幕）并合成为标准微信表情 GIF
        """
        duration_ms = int(1000 / max(1, min(fps, 30)))
        processed_frames: List[Image.Image] = []

        for frame in frames:
            f = frame
            if make_transparent:
                f = cls.remove_white_bg(f)
            if caption:
                f = cls.overlay_caption(f, caption)
            processed_frames.append(f)

        # 转换为 GIF 适配模式
        gif_frames = []
        for pf in processed_frames:
            # 保证带透明调色板
            alpha = pf.split()[-1]
            p_img = pf.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=255)
            # 恢复透明通道
            mask = Image.eval(alpha, lambda a: 255 if a <= 128 else 0)
            p_img.paste(255, mask)
            gif_frames.append(p_img)

        # 保存 GIF，设置无限循环 loop=0，并使用 disposal=2 彻底防止上一帧残影
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
        return {
            "output_path": output_path,
            "frame_count": len(frames),
            "fps": fps,
            "duration_per_frame_ms": duration_ms,
            "file_size_bytes": file_size,
            "file_size_kb": round(file_size / 1024, 2),
            "is_wechat_compliant": file_size < (1024 * 1024)  # 微信表情单图 < 1MB
        }

    @classmethod
    def package_zip(cls, frames: List[Image.Image], output_path: str, caption: Optional[str] = None) -> str:
        """打包 16 张独立的透明 PNG 帧为 ZIP"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for idx, frame in enumerate(frames, 1):
                f = cls.remove_white_bg(frame)
                if caption:
                    f = cls.overlay_caption(f, caption)
                buf = io.BytesIO()
                f.save(buf, format="PNG")
                zf.writestr(f"frame_{idx:02d}.png", buf.getvalue())
        return output_path
