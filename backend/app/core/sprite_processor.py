import io
import os
import zipfile
from pathlib import Path
from typing import List
import numpy as np
import cv2
from PIL import Image

class SpriteProcessor:
    @classmethod
    def slice_grid(cls, image: Image.Image, rows: int = 4, cols: int = 4) -> List[Image.Image]:
        """
        智能自适应网格分割算法 (Adaptive Projection Valley Slicing):
        1. 解决 AI 出图外围留白不对称、行列间距不完全均等导致的切偏错位问题；
        2. 基于投影波谷 (Projection Valleys) 精准定位各行各列之间的真实空白分割带；
        3. 彻底杜绝下一行的文字/头顶被误切到上一行脚底（文字错位跑到下方）的致命 Bug！
        """
        img_rgb = image.convert("RGB")
        img_np = np.array(img_rgb)
        h, w = img_np.shape[:2]

        # 二值化前景图 (前景为 1，白色/浅色背景为 0)
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        inv = 255 - gray
        _, binary = cv2.threshold(inv, 25, 255, cv2.THRESH_BINARY)

        proj_y = np.sum(binary > 0, axis=1)
        proj_x = np.sum(binary > 0, axis=0)

        y_content = np.where(proj_y > 0)[0]
        x_content = np.where(proj_x > 0)[0]

        if len(y_content) == 0 or len(x_content) == 0:
            # 异常兜底：平均切割
            return [image.crop((c * (w // cols), r * (h // rows), (c + 1) * (w // cols), (r + 1) * (h // rows)))
                    for r in range(rows) for c in range(cols)]

        y_min, y_max = y_content[0], y_content[-1]
        x_min, x_max = x_content[0], x_content[-1]
        h_content = y_max - y_min
        w_content = x_max - x_min

        # 智能搜寻 3 条水平空白分割线 (波谷)
        y_cuts = [0]
        for i in range(1, rows):
            expected_y = y_min + int(h_content * i / rows)
            search_radius = max(10, int(h_content / rows * 0.25))
            start_y = max(y_min, expected_y - search_radius)
            end_y = min(y_max, expected_y + search_radius)
            # 在搜索窗口内寻找内容最少（投影值最小）的空白行
            min_idx = start_y + np.argmin(proj_y[start_y:end_y])
            y_cuts.append(int(min_idx))
        y_cuts.append(h)

        # 智能搜寻 3 条垂直空白分割线 (波谷)
        x_cuts = [0]
        for j in range(1, cols):
            expected_x = x_min + int(w_content * j / cols)
            search_radius = max(10, int(w_content / cols * 0.25))
            start_x = max(x_min, expected_x - search_radius)
            end_x = min(x_max, expected_x + search_radius)
            min_idx = start_x + np.argmin(proj_x[start_x:end_x])
            x_cuts.append(int(min_idx))
        x_cuts.append(w)

        # 裁剪出 16 个原始单元格
        raw_cells = []
        for r in range(rows):
            for c in range(cols):
                box = (x_cuts[c], y_cuts[r], x_cuts[c + 1], y_cuts[r + 1])
                raw_cells.append(image.crop(box))

        # 规整化：居中对齐到统一尺寸画布，确保 GIF 播放时不抖动
        target_w = max(cell.width for cell in raw_cells)
        target_h = max(cell.height for cell in raw_cells)
        target_size = max(target_w, target_h)

        uniform_frames = []
        for cell in raw_cells:
            canvas = Image.new("RGBA", (target_size, target_size), (255, 255, 255, 255))
            ox = (target_size - cell.width) // 2
            oy = (target_size - cell.height) // 2
            canvas.paste(cell.convert("RGBA"), (ox, oy))

            # 若单帧分辨率过大，适当缩放到规范的 256x256，进一步压缩体积提升流畅度
            if target_size > 320:
                canvas = canvas.resize((256, 256), Image.Resampling.LANCZOS)

            uniform_frames.append(canvas)

        return uniform_frames

    @staticmethod
    def remove_white_bg(frame: Image.Image, tolerance: int = 28) -> Image.Image:
        """
        超高速 C++ OpenCV 洪水填充去白底算法。
        仅从 4 个边角向内扩散，剔除外围白色背景；
        100% 完整保留角色主体、原画中随动作律动的艺术字及眼白等内部细节！
        """
        rgba = np.array(frame.convert("RGBA"))
        h, w = rgba.shape[:2]

        corners = [rgba[0, 0, :3], rgba[0, w - 1, :3], rgba[h - 1, 0, :3], rgba[h - 1, w - 1, :3]]
        if not any(np.all(c > 190) for c in corners):
            return frame

        bgr = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)
        mask = np.zeros((h + 2, w + 2), np.uint8)

        tol = int(tolerance)
        for seed in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
            if mask[seed[1] + 1, seed[0] + 1] == 0:
                cv2.floodFill(
                    bgr, mask, seed, 0,
                    loDiff=(tol, tol, tol),
                    upDiff=(tol, tol, tol),
                    flags=4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY
                )

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
