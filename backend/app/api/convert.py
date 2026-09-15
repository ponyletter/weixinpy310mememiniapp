import io
import hashlib
import asyncio
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from textwrap import wrap
from typing import Optional, List
from urllib.parse import urlsplit
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, Field
from PIL import Image, ImageDraw, ImageFont
import imageio

from app.config import settings
from app.security import CurrentOpenid
from app.upload_utils import ensure_within, open_validated_image, read_limited_upload

router = APIRouter(prefix="/api/convert", tags=["conversion_and_remix"])


def _resolve_ffmpeg() -> str:
    """Resolve ffmpeg once per request and return a useful deployment error."""
    configured = settings.FFMPEG_BIN.strip() or "ffmpeg"
    executable = configured if Path(configured).is_file() else shutil.which(configured)
    if not executable:
        raise HTTPException(
            status_code=503,
            detail="服务器未安装 FFmpeg，暂时无法处理视频；请联系管理员安装 ffmpeg。",
        )
    return executable


class ComposeImagesRequest(BaseModel):
    upload_ids: list[str] = Field(min_length=2)
    fps: int = 4
    caption: str = ""


def _user_stage_dir(openid: str) -> Path:
    user_key = hashlib.sha256(openid.encode("utf-8")).hexdigest()[:24]
    directory = settings.UPLOAD_DIR / "image_staging" / user_key
    directory.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - 3600
    for staged_file in directory.glob("*.png"):
        try:
            if staged_file.stat().st_mtime < cutoff:
                staged_file.unlink()
        except OSError:
            pass
    return directory


def _save_frames_as_gif(frames: list[Image.Image], fps: int, caption: str) -> dict:
    task_id = uuid.uuid4().hex
    task_dir = settings.OUTPUT_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    output_gif_path = task_dir / "meme_result.gif"
    imageio.mimsave(str(output_gif_path), frames, format="GIF", duration=1.0 / fps, loop=0)
    if caption.strip():
        _add_caption_to_gif(output_gif_path, caption.strip())
    return {
        "success": True,
        "task_id": task_id,
        "gif_url": f"/outputs/{task_id}/meme_result.gif",
        "file_size_kb": round(output_gif_path.stat().st_size / 1024, 1),
    }

@router.post("/video-to-gif")
async def video_to_gif(
    current_openid: CurrentOpenid,
    video: UploadFile = File(...),
    start_time: float = Form(0.0),
    duration: float = Form(3.0),
    fps: int = Form(10),
    width: int = Form(240),
    caption: str = Form(""),
):
    """【聊天视频直转动图】利用本地 ffmpeg 高质量双通道调色板生成微信合规 GIF"""
    if not 1 <= fps <= 20 or not 64 <= width <= 720:
        raise HTTPException(status_code=400, detail="fps 或输出宽度超出允许范围")
    if len(caption) > 80:
        raise HTTPException(status_code=400, detail="字幕不能超过 80 个字符")
    ffmpeg_bin = _resolve_ffmpeg()
    type_suffixes = {"video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm", "video/x-m4v": ".m4v"}
    filename_suffix = Path(video.filename or "").suffix.lower()
    if video.content_type not in type_suffixes and not (
        video.content_type == "application/octet-stream" and filename_suffix in {".mp4", ".mov", ".m4v", ".webm"}
    ):
        raise HTTPException(status_code=415, detail="仅支持 MP4、MOV、M4V 或 WebM 视频")
    video_bytes = await read_limited_upload(video, settings.MAX_VIDEO_UPLOAD_MB)

    task_id = uuid.uuid4().hex
    task_dir = settings.OUTPUT_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    suffix = type_suffixes.get(video.content_type, filename_suffix)
    input_path = task_dir / f"input_video{suffix}"
    output_gif_path = task_dir / "meme_result.gif"

    input_path.write_bytes(video_bytes)

    # 构造 ffmpeg 高品质 palettegen / paletteuse 转换滤镜
    vf_filter = f"fps={fps},scale={width}:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer"

    cmd = [
        ffmpeg_bin, "-y",
        "-ss", str(max(0.0, start_time)),
        "-t", str(min(10.0, max(0.5, duration))),
        "-i", str(input_path),
        "-vf", vf_filter,
        str(output_gif_path)
    ]

    try:
        await asyncio.to_thread(
            subprocess.run,
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"视频转动图处理失败: {e.stderr.decode('utf-8', errors='ignore')[:200]}")
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="视频处理超时") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="服务器未安装 FFmpeg，暂时无法处理视频") from exc

    # 如果需要加字幕
    if caption.strip() and output_gif_path.exists():
        _add_caption_to_gif(output_gif_path, caption.strip())

    file_size_kb = round(output_gif_path.stat().st_size / 1024, 1)
    return {
        "success": True,
        "task_id": task_id,
        "gif_url": f"/outputs/{task_id}/meme_result.gif",
        "file_size_kb": file_size_kb,
        "caption": caption.strip()
    }

@router.post("/images-to-gif")
async def images_to_gif(
    current_openid: CurrentOpenid,
    files: List[UploadFile] = File(...),
    fps: int = Form(4),
    caption: str = Form("")
):
    """【多图拼接动图】多张连续照片一键合成动图"""
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="至少需要 2 张图片才能合成动图")
    if len(files) > settings.MAX_IMAGES_PER_GIF:
        raise HTTPException(status_code=400, detail=f"最多支持 {settings.MAX_IMAGES_PER_GIF} 张图片")
    if not 1 <= fps <= 20 or len(caption) > 80:
        raise HTTPException(status_code=400, detail="fps 或字幕长度超出允许范围")

    frames = []
    target_size = (300, 300)

    for f in files:
        image_bytes = await read_limited_upload(f, settings.MAX_IMAGE_UPLOAD_MB)
        img_raw = open_validated_image(image_bytes, allow_animation=False).convert("RGBA")
        img_resized = img_raw.resize(target_size, Image.Resampling.LANCZOS)
        frames.append(img_resized)

    return _save_frames_as_gif(frames, fps, caption)


@router.post("/images-to-gif/frame")
async def stage_image_frame(current_openid: CurrentOpenid, file: UploadFile = File(...)):
    """Stage one validated image; wx.uploadFile only supports one local file per call."""
    image_bytes = await read_limited_upload(file, settings.MAX_IMAGE_UPLOAD_MB)
    image = open_validated_image(image_bytes, allow_animation=False).convert("RGBA")
    upload_id = uuid.uuid4().hex
    image.save(_user_stage_dir(current_openid) / f"{upload_id}.png", format="PNG")
    return {"success": True, "upload_id": upload_id}


@router.post("/images-to-gif/compose")
def compose_staged_images(req: ComposeImagesRequest, current_openid: CurrentOpenid):
    if len(req.upload_ids) > settings.MAX_IMAGES_PER_GIF:
        raise HTTPException(status_code=400, detail=f"最多支持 {settings.MAX_IMAGES_PER_GIF} 张图片")
    if not 1 <= req.fps <= 20 or len(req.caption) > 80:
        raise HTTPException(status_code=400, detail="fps 或字幕长度超出允许范围")

    stage_dir = _user_stage_dir(current_openid)
    source_paths: list[Path] = []
    frames: list[Image.Image] = []
    try:
        for upload_id in req.upload_ids:
            if len(upload_id) != 32 or any(ch not in "0123456789abcdef" for ch in upload_id):
                raise HTTPException(status_code=400, detail="上传 ID 不合法")
            source = ensure_within(stage_dir / f"{upload_id}.png", stage_dir)
            if not source.is_file():
                raise HTTPException(status_code=404, detail="暂存图片不存在或已经过期")
            source_paths.append(source)
            frames.append(open_validated_image(source.read_bytes(), allow_animation=False).convert("RGBA").resize((300, 300), Image.Resampling.LANCZOS))
        return _save_frames_as_gif(frames, req.fps, req.caption)
    finally:
        for source in source_paths:
            source.unlink(missing_ok=True)

@router.post("/edit-caption")
async def edit_caption(
    current_openid: CurrentOpenid,
    gif_file: Optional[UploadFile] = File(None),
    gif_url: Optional[str] = Form(None),
    caption: str = Form(""),
):
    """【表情包改字与二创】为已有动图重新覆盖/追加爆笑字幕"""
    if not caption.strip():
        raise HTTPException(status_code=400, detail="新文字不能为空")
    if len(caption) > 80:
        raise HTTPException(status_code=400, detail="字幕不能超过 80 个字符")

    task_id = uuid.uuid4().hex
    task_dir = settings.OUTPUT_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    target_gif = task_dir / "meme_result.gif"

    if gif_file and gif_file.filename:
        gif_bytes = await read_limited_upload(gif_file, settings.MAX_IMAGE_UPLOAD_MB)
        open_validated_image(gif_bytes, allow_animation=True)
        target_gif.write_bytes(gif_bytes)
    elif gif_url:
        clean_path = urlsplit(gif_url).path
        if not clean_path.startswith("/outputs/"):
            raise HTTPException(status_code=400, detail="仅支持本站生成的动图 URL")
        relative_path = clean_path.removeprefix("/outputs/")
        local_src = ensure_within(settings.OUTPUT_DIR / relative_path, settings.OUTPUT_DIR)
        if not local_src.is_file():
            raise HTTPException(status_code=404, detail="源动图文件不存在")
        source_bytes = local_src.read_bytes()
        open_validated_image(source_bytes, allow_animation=True)
        target_gif.write_bytes(source_bytes)
    else:
        raise HTTPException(status_code=400, detail="请上传动图或提供动图 URL")

    _add_caption_to_gif(target_gif, caption.strip())
    file_size_kb = round(target_gif.stat().st_size / 1024, 1)
    return {
        "success": True,
        "task_id": task_id,
        "gif_url": f"/outputs/{task_id}/meme_result.gif",
        "file_size_kb": file_size_kb,
        "new_caption": caption.strip()
    }

@router.post("/caption-suggest")
def caption_suggest(keyword: str = Form(""), style: str = Form("all")):
    """【爆笑文案/台词推荐】一键生成多种风格文案嘴替"""
    keyword = keyword.strip() or "打工"
    presets = {
        "crazy": [
            f"别卷了，再卷我就要变成{keyword}了！",
            "只要我摆烂够快，压力就追不上我",
            f"今日状态：随时准备对世界发疯 ({keyword}版)",
            "累了，想当一只不用上班的修狗"
        ],
        "sarcastic": [
            "差不多得了，听懂掌声",
            f"你说得对，但我选择当一个可爱的{keyword}",
            "你开心就好，不用管我的死活",
            "建议把脑子拿去水洗烘干一下"
        ],
        "cute": [
            f"今天也是软萌可爱的{keyword}鸭~",
            "乖巧坐好，坐等贴贴",
            "收到收到，收到你的小心心！",
            "生活很苦，但有你很甜"
        ],
        "workplace": [
            "收到，正在处理中（摸鱼中）",
            "周一了，灵魂已经出窍",
            "催催催，生产队的驴都不敢这么赶",
            "工资不到位，干活全靠演"
        ]
    }

    if style in presets:
        results = presets[style]
    else:
        results = [
            {"style": "发疯风", "text": presets["crazy"][0]},
            {"style": "阴阳风", "text": presets["sarcastic"][0]},
            {"style": "软萌风", "text": presets["cute"][0]},
            {"style": "职场风", "text": presets["workplace"][0]},
            {"style": "发疯风", "text": presets["crazy"][1]}
        ]

    return {
        "success": True,
        "keyword": keyword,
        "suggestions": results
    }

def _add_caption_to_gif(gif_path: Path, caption: str):
    """在 GIF 每帧下方增加独立的白色文字区，避免覆盖原图内容。"""
    try:
        im = Image.open(gif_path)
        frames = []
        durations = []

        font_path = settings.STATIC_DIR / "fonts" / "NotoSansSC-Bold.ttf"
        font = None
        if font_path.exists():
            font = ImageFont.truetype(str(font_path), size=24)
        else:
            font = ImageFont.load_default()

        for frame_idx in range(getattr(im, "n_frames", 1)):
            im.seek(frame_idx)
            frame_rgba = im.convert("RGBA")
            w, h = frame_rgba.size

            # 动态字体大小，并按画布宽度将长文案拆成最多两行。
            text_len = max(1, len(caption))
            font_size = max(16, min(30, int(w / (text_len + 2))))
            if font_path.exists():
                font = ImageFont.truetype(str(font_path), size=font_size)

            max_chars = max(6, int((w - 32) / max(font_size * 0.58, 1)))
            lines = wrap(caption, width=max_chars, break_long_words=True, break_on_hyphens=False) or [caption]
            if len(lines) > 2:
                lines = lines[:2]
                lines[-1] = lines[-1][:-1].rstrip() + "…"

            line_height = max(font_size + 10, 28)
            panel_height = line_height * len(lines) + 18
            canvas = Image.new("RGBA", (w, h + panel_height), (255, 255, 255, 255))
            canvas.alpha_composite(frame_rgba, (0, 0))
            draw = ImageDraw.Draw(canvas)
            for line_idx, line in enumerate(lines):
                bbox = draw.textbbox((0, 0), line, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                x = (w - text_w) // 2
                y = h + 9 + line_idx * line_height + max(0, (line_height - text_h) // 2)
                draw.text(
                    (x, y),
                    line,
                    font=font,
                    fill=(15, 23, 42, 255),
                    stroke_width=1,
                    stroke_fill=(255, 255, 255, 255),
                )

            frames.append(canvas)
            durations.append(im.info.get("duration", 100) / 1000.0)

        avg_duration = sum(durations) / max(1, len(durations))
        imageio.mimsave(str(gif_path), frames, format="GIF", duration=avg_duration, loop=0)
    except Exception as e:
        raise HTTPException(status_code=422, detail="无法处理该动图") from e


@router.post("/stitch-images")
async def stitch_images(
    current_openid: CurrentOpenid,
    files: Optional[List[UploadFile]] = File(None),
    upload_ids: Optional[str] = Form(None),
    mode: str = Form("vertical"),
    subtitle_ratio: float = Form(0.25),
    spacing: int = Form(0),
    max_width: int = Form(720),
):
    """【多图智能拼接】支持竖向长图、横向拼接、电影台词/字幕无缝拼接"""
    loaded_images: list[Image.Image] = []
    source_paths: list[Path] = []
    stage_dir = _user_stage_dir(current_openid)

    try:
        if upload_ids:
            import json
            ids = []
            try:
                ids = json.loads(upload_ids)
            except Exception:
                ids = [x.strip() for x in upload_ids.split(",") if x.strip()]
            for uid in ids:
                source = ensure_within(stage_dir / f"{uid}.png", stage_dir)
                if source.is_file():
                    source_paths.append(source)
                    loaded_images.append(open_validated_image(source.read_bytes(), allow_animation=False).convert("RGB"))
        elif files:
            for f in files:
                b = await read_limited_upload(f, settings.MAX_IMAGE_UPLOAD_MB)
                im = open_validated_image(b, allow_animation=False).convert("RGB")
                loaded_images.append(im)

        if len(loaded_images) < 2:
            raise HTTPException(status_code=400, detail="拼接至少需要 2 张图片")
        if len(loaded_images) > 20:
            raise HTTPException(status_code=400, detail="最多支持 20 张图片拼接")
        if mode not in ("vertical", "horizontal", "subtitle"):
            mode = "vertical"

        task_id = uuid.uuid4().hex
        task_dir = settings.OUTPUT_DIR / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        if mode == "vertical":
            target_w = min(max_width, max(im.width for im in loaded_images))
            resized = []
            for im in loaded_images:
                h = int(im.height * (target_w / im.width))
                resized.append(im.resize((target_w, h), Image.Resampling.LANCZOS))
            total_h = sum(im.height for im in resized) + spacing * (len(resized) - 1)
            canvas = Image.new("RGB", (target_w, total_h), (255, 255, 255))
            curr_y = 0
            for im in resized:
                canvas.paste(im, (0, curr_y))
                curr_y += im.height + spacing

        elif mode == "horizontal":
            target_h = min(max_width, max(im.height for im in loaded_images))
            resized = []
            for im in loaded_images:
                w = int(im.width * (target_h / im.height))
                resized.append(im.resize((w, target_h), Image.Resampling.LANCZOS))
            total_w = sum(im.width for im in resized) + spacing * (len(resized) - 1)
            canvas = Image.new("RGB", (total_w, target_h), (255, 255, 255))
            curr_x = 0
            for im in resized:
                canvas.paste(im, (curr_x, 0))
                curr_x += im.width + spacing

        else:  # subtitle 模式 (经典影视截图台词拼接：第一张保留全部画面，后续每张仅截取底部字幕条)
            ratio = max(0.1, min(0.6, float(subtitle_ratio)))
            base_w = min(max_width, loaded_images[0].width)
            base_h = int(loaded_images[0].height * (base_w / loaded_images[0].width))
            first_img = loaded_images[0].resize((base_w, base_h), Image.Resampling.LANCZOS)
            slices = [first_img]
            for im in loaded_images[1:]:
                scaled_h = int(im.height * (base_w / im.width))
                scaled_im = im.resize((base_w, scaled_h), Image.Resampling.LANCZOS)
                cut_y = int(scaled_h * (1.0 - ratio))
                subtitle_crop = scaled_im.crop((0, cut_y, base_w, scaled_h))
                slices.append(subtitle_crop)
            total_h = sum(s.height for s in slices) + spacing * (len(slices) - 1)
            canvas = Image.new("RGB", (base_w, total_h), (255, 255, 255))
            curr_y = 0
            for s in slices:
                canvas.paste(s, (0, curr_y))
                curr_y += s.height + spacing

        out_path = task_dir / "stitched.jpg"
        canvas.save(out_path, format="JPEG", quality=90)
        file_size_kb = round(out_path.stat().st_size / 1024, 1)
        return {
            "success": True,
            "task_id": task_id,
            "image_url": f"/outputs/{task_id}/stitched.jpg",
            "file_size_kb": file_size_kb,
            "width": canvas.width,
            "height": canvas.height,
            "mode": mode
        }
    finally:
        for p in source_paths:
            p.unlink(missing_ok=True)


@router.post("/compress-image")
async def compress_image(
    current_openid: CurrentOpenid,
    file: UploadFile = File(...),
    target_kb: int = Form(500),
    max_width: int = Form(0),
    quality: int = Form(80),
):
    """【图片/动图压缩瘦身】支持将超大图片或动图压缩至微信表情合规限制 (如 500KB 或 1MB)"""
    file_bytes = await read_limited_upload(file, settings.MAX_IMAGE_UPLOAD_MB)
    orig_size_kb = round(len(file_bytes) / 1024, 1)

    task_id = uuid.uuid4().hex
    task_dir = settings.OUTPUT_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    is_gif = False
    try:
        probe = Image.open(io.BytesIO(file_bytes))
        is_gif = getattr(probe, "is_animated", False) or probe.format == "GIF"
    except Exception:
        pass

    if is_gif:
        out_path = task_dir / "compressed.gif"
        im = Image.open(io.BytesIO(file_bytes))
        frames = []
        durations = []
        scale_ratio = 1.0
        if max_width > 0 and im.width > max_width:
            scale_ratio = max_width / im.width
        elif orig_size_kb > target_kb:
            scale_ratio = min(1.0, (target_kb / orig_size_kb) ** 0.5)

        for i in range(getattr(im, "n_frames", 1)):
            im.seek(i)
            frame = im.convert("RGBA")
            if scale_ratio < 0.95:
                nw = max(64, int(frame.width * scale_ratio))
                nh = max(64, int(frame.height * scale_ratio))
                frame = frame.resize((nw, nh), Image.Resampling.LANCZOS)
            frames.append(frame)
            durations.append(im.info.get("duration", 100) / 1000.0)

        avg_dur = sum(durations) / max(1, len(durations))
        imageio.mimsave(str(out_path), frames, format="GIF", duration=avg_dur, loop=0)
        out_url = f"/outputs/{task_id}/compressed.gif"
    else:
        im = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        if max_width > 0 and im.width > max_width:
            nh = int(im.height * (max_width / im.width))
            im = im.resize((max_width, nh), Image.Resampling.LANCZOS)

        out_path = task_dir / "compressed.jpg"
        q = max(30, min(95, quality))
        im.save(out_path, format="JPEG", quality=q, optimize=True)
        while out_path.stat().st_size / 1024 > target_kb and q > 35:
            q -= 10
            im.save(out_path, format="JPEG", quality=q, optimize=True)
        out_url = f"/outputs/{task_id}/compressed.jpg"

    file_size_kb = round(out_path.stat().st_size / 1024, 1)
    return {
        "success": True,
        "task_id": task_id,
        "output_url": out_url,
        "file_size_kb": file_size_kb,
        "original_size_kb": orig_size_kb
    }


def _get_cjk_font(size: int, bold: bool = False, serif: bool = False) -> ImageFont.ImageFont:
    """优先加载系统安装的开源 Noto CJK 中文字体，若未安装则平滑回退"""
    candidates = []
    if serif:
        if bold:
            candidates.append(("/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc", 2))
        candidates.append(("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", 2))
    else:
        if bold:
            candidates.append(("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 2))
        candidates.append(("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 2))
    # 静态目录备选
    static_font = settings.STATIC_DIR / "fonts" / "NotoSansSC-Bold.ttf"
    if static_font.exists():
        candidates.append((str(static_font), None))
    # Linux 文泉驿中文字体备选
    candidates.append(("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0))
    candidates.append(("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0))

    for path, idx in candidates:
        if Path(path).exists():
            try:
                if idx is not None:
                    return ImageFont.truetype(path, size=size, index=idx)
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


@router.post("/text-to-image")
async def text_to_image(
    current_openid: CurrentOpenid,
    text: str = Form(...),
    theme: str = Form("classic"),
    title: str = Form(""),
    author: str = Form(""),
    font_size: int = Form(32),
):
    """【金句台词卡片生成器】将金句、名言或梗图文案一键排版生成精致卡片"""
    if not text.strip():
        raise HTTPException(status_code=400, detail="文本内容不能为空")
    if len(text) > 300:
        raise HTTPException(status_code=400, detail="文本内容不能超过 300 字")

    task_id = uuid.uuid4().hex
    task_dir = settings.OUTPUT_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    card_w = 640
    themes = {
        "classic": ((255, 255, 255), (15, 23, 42), (99, 102, 241)),
        "dark": ((24, 24, 27), (244, 244, 245), (244, 63, 94)),
        "gold": ((254, 252, 232), (113, 63, 18), (202, 138, 4)),
        "cute": ((255, 241, 242), (159, 18, 57), (244, 63, 94)),
        "minimal": ((248, 250, 252), (51, 65, 85), (79, 70, 229)),
    }
    bg_col, text_col, accent_col = themes.get(theme, themes["classic"])

    f_size = max(20, min(56, font_size))
    # 金句和极简风格采用优雅宋体，其他采用黑体
    use_serif = theme in ("gold", "classic", "minimal")
    body_font = _get_cjk_font(f_size, bold=False, serif=use_serif)
    small_font = _get_cjk_font(max(16, int(f_size * 0.6)), bold=False, serif=False)

    title_str = title.strip()
    author_str = author.strip()
    is_pure_quote = not title_str and not author_str
    line_h = int(f_size * 1.65)

    if is_pure_quote:
        # 纯金句模式：去除左侧强调竖线与冗余尾注，紧凑排版
        pad_x = 48
        line_w = max(10, int((card_w - pad_x * 2) / max(f_size * 0.95, 1)))
        lines = wrap(text.strip(), width=line_w) or [text.strip()]
        body_h = len(lines) * line_h
        card_h = max(140, 48 * 2 + body_h)
        canvas = Image.new("RGB", (card_w, card_h), bg_col)
        draw = ImageDraw.Draw(canvas)

        curr_y = (card_h - body_h) // 2
        for line in lines:
            draw.text((pad_x, curr_y), line, font=body_font, fill=text_col)
            curr_y += line_h
    else:
        # 附带标题或作者模式：保留左侧竖条，作者紧贴正文下方，不留巨大空隙
        pad_x = 64
        line_w = max(10, int((card_w - pad_x - 48) / max(f_size * 0.95, 1)))
        lines = wrap(text.strip(), width=line_w) or [text.strip()]
        body_h = len(lines) * line_h
        title_h = (int(f_size * 0.9) + 16) if title_str else 0
        author_h = (int(f_size * 0.8) + 20) if author_str else 0
        card_h = max(160, 40 + title_h + body_h + author_h + 36)
        canvas = Image.new("RGB", (card_w, card_h), bg_col)
        draw = ImageDraw.Draw(canvas)

        draw.rectangle([36, 36, 42, card_h - 36], fill=accent_col)

        curr_y = 40
        if title_str:
            draw.text((pad_x, curr_y), title_str, font=small_font, fill=accent_col)
            curr_y += title_h

        for line in lines:
            draw.text((pad_x, curr_y), line, font=body_font, fill=text_col)
            curr_y += line_h

        if author_str:
            curr_y += 10
            draw.text((pad_x, curr_y), f"— {author_str}", font=small_font, fill=accent_col)

    out_path = task_dir / "card.png"
    canvas.save(out_path, format="PNG")
    file_size_kb = round(out_path.stat().st_size / 1024, 1)

    return {
        "success": True,
        "task_id": task_id,
        "image_url": f"/outputs/{task_id}/card.png",
        "file_size_kb": file_size_kb,
        "width": card_w,
        "height": card_h
    }
