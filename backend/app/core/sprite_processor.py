import io
import os
import zipfile
from pathlib import Path
from typing import List
import numpy as np
import cv2
from PIL import Image

class SpriteProcessor:
    @staticmethod
    def _find_optimal_dividers(proj: np.ndarray, length: int, num_divisions: int = 4) -> List[int]:
        """
        核心智能分割带寻界算法：
        自动寻找行间/列间真正的主空白带（Major Gaps），
        彻底规避人物脚底与自身字幕之间仅几像素的微小缝隙，杜绝把字幕切断或错位的 Bug！
        """
        content_indices = np.where(proj > 0)[0]
        if len(content_indices) == 0:
            return [int(length * i / num_divisions) for i in range(num_divisions + 1)]

        first_c, last_c = content_indices[0], content_indices[-1]
        thresh = max(10, np.max(proj) * 0.02)

        # 提取全部连续投影接近零的空白缝隙
        gaps = []
        in_gap = False
        start = 0
        for i in range(first_c, last_c + 1):
            if proj[i] <= thresh:
                if not in_gap:
                    in_gap = True
                    start = i
            else:
                if in_gap:
                    in_gap = False
                    gaps.append((start, i, i - start))
        if in_gap:
            gaps.append((start, last_c, last_c - start))

        content_len = last_c - first_c
        cuts = [0]

        for k in range(1, num_divisions):
            expected_pos = first_c + content_len * k / num_divisions
            window_radius = content_len / num_divisions * 0.35
            # 在预期分割线附近搜索候选缝隙
            candidate_gaps = [g for g in gaps if abs((g[0] + g[1]) / 2.0 - expected_pos) <= window_radius]
            if candidate_gaps:
                # 关键判据：选择【缝隙宽度最宽】的缝隙作为行间真实分界线！
                best_gap = max(candidate_gaps, key=lambda g: (g[2], -abs((g[0] + g[1]) / 2.0 - expected_pos)))
                cut_point = (best_gap[0] + best_gap[1]) // 2
            else:
                start_search = max(first_c, int(expected_pos - window_radius))
                end_search = min(last_c, int(expected_pos + window_radius))
                cut_point = start_search + np.argmin(proj[start_search:end_search])

            cuts.append(int(cut_point))

        cuts.append(length)
        return cuts

    @classmethod
    def slice_grid(cls, image: Image.Image, rows: int = 4, cols: int = 4, padding_percent: float = 0.03) -> List[Image.Image]:
        """
        多尺度自适应网格分割算法 (Robust Multi-scale Grid Slicing):
        1. 自动识别整图外边距与行间真实主隔离带，100% 保证人物与专属字幕被完整保留在同一帧内；
        2. 计算 16 帧统一最大包络，剔除无效大白边，内容饱满紧凑；
        3. 输出统一 256×256 标准微信表情动图，零残影、零抖动。
        """
        img_rgb = image.convert("RGB")
        img_np = np.array(img_rgb)
        h, w = img_np.shape[:2]

        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        inv = 255 - gray
        # 使用更灵敏的前景阈值 (12)，防止文字浅色渐变或边缘发丝细节被误判为背景
        _, binary = cv2.threshold(inv, 12, 255, cv2.THRESH_BINARY)

        proj_y = np.sum(binary > 0, axis=1)
        proj_x = np.sum(binary > 0, axis=0)

        # 1. 精准寻找 4 行与 4 列的真实分界线
        y_cuts = cls._find_optimal_dividers(proj_y, h, rows)
        x_cuts = cls._find_optimal_dividers(proj_x, w, cols)

        # 2. 裁剪出 16 个完整单元格 (角色+自身字幕一体化提取)
        raw_crops = []
        for r in range(rows):
            for c in range(cols):
                cell = image.crop((x_cuts[c], y_cuts[r], x_cuts[c + 1], y_cuts[r + 1]))
                arr = np.array(cell.convert("RGB"))
                _, c_bin = cv2.threshold(255 - cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY), 12, 255, cv2.THRESH_BINARY)
                ys, xs = np.where(c_bin > 0)
                if len(ys) > 0:
                    crop = cell.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
                else:
                    crop = cell
                raw_crops.append(crop)

        # 3. 计算 16 帧全局最大包络，保持动画尺寸稳定
        max_w = max(c.width for c in raw_crops)
        max_h = max(c.height for c in raw_crops)

        # 最小安全边距
        pad = max(4, int(max(max_w, max_h) * padding_percent))
        target_size = max(max_w, max_h) + pad * 2

        uniform_frames = []
        for c in raw_crops:
            canvas = Image.new("RGBA", (target_size, target_size), (255, 255, 255, 255))
            ox = (target_size - c.width) // 2
            oy = (target_size - c.height) // 2
            canvas.paste(c.convert("RGBA"), (ox, oy))

            # 缩放至统一标准的 256×256
            canvas = canvas.resize((256, 256), Image.Resampling.LANCZOS)
            uniform_frames.append(canvas)

        return uniform_frames

    @staticmethod
    def remove_white_bg(frame: Image.Image, tolerance: int = 15) -> Image.Image:
        """
        超高速 C++ OpenCV 洪水填充去白底算法 (定距基准模式 FLOODFILL_FIXED_RANGE)。
        
        关键优化：
        1. 必须使用 cv2.FLOODFILL_FIXED_RANGE，比较基准严格锁定为边缘纯白种子点(255,255,255)；
           彻底杜绝原先浮动范围模式下一阶一阶向字体内侵蚀渗透、把文字吃成空心或吃没的 Bug！
        2. 宽容度精细控制为 15，既能彻底剥离纯白背景，又绝不伤及文字边缘微弱抗锯齿渐变！
        """
        rgba = np.array(frame.convert("RGBA"))
        h, w = rgba.shape[:2]

        corners = [rgba[0, 0, :3], rgba[0, w - 1, :3], rgba[h - 1, 0, :3], rgba[h - 1, w - 1, :3]]
        if not any(np.all(c > 190) for c in corners):
            return frame

        bgr = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)
        mask = np.zeros((h + 2, w + 2), np.uint8)

        tol = int(tolerance)
        # 强制 FIXED_RANGE：只与 seed 颜色比较，不随扩散连续滑动漂移
        flags = 4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE

        for seed in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
            if mask[seed[1] + 1, seed[0] + 1] == 0:
                cv2.floodFill(
                    bgr, mask, seed, 0,
                    loDiff=(tol, tol, tol),
                    upDiff=(tol, tol, tol),
                    flags=flags
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
