import io
import os
import zipfile
from pathlib import Path
from typing import List, Optional
import numpy as np
import cv2
from PIL import Image

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
        仅从 4 个边角向内扩散，剔除外围白色背景；
        100% 完整保留角色主体、原画中随动作律动的艺术字及眼白等内部细节！
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

        # 将被识别为外围纯白背景的像素 Alpha 置零
        bg_mask = mask[1:h + 1, 1:w + 1] == 255
        rgba[bg_mask, 3] = 0

        return Image.fromarray(rgba)

    @classmethod
    def assemble_gif(
        cls,
        frames: List[Image.Image],
        output_path: str,
        fps: int = 8,
        make_transparent: bool = True
    ) -> dict:
        """
        完整工作流：处理每一帧（超高速外围去白底）并合成为微信标准无限循环 GIF。
        完全保留 ChatGPT 原画中随动作弹跳的原生艺术字体！
        """
        duration_ms = int(1000 / max(1, min(fps, 30)))
        processed_frames: List[Image.Image] = []

        for frame in frames:
            f = frame
            if make_transparent:
                f = cls.remove_white_bg(f)
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
            "is_wechat_compliant": file_size < (1024 * 1024)
        }

    @classmethod
    def package_zip(cls, frames: List[Image.Image], output_path: str, make_transparent: bool = True) -> str:
        """打包 16 张独立的透明 PNG 帧为 ZIP"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for idx, frame in enumerate(frames, 1):
                f = cls.remove_white_bg(frame) if make_transparent else frame
                buf = io.BytesIO()
                f.save(buf, format="PNG")
                zf.writestr(f"frame_{idx:02d}.png", buf.getvalue())
        return output_path
