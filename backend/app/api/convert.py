import hashlib
import asyncio
import subprocess
import time
import uuid
from pathlib import Path
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
        "ffmpeg", "-y",
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
    """为 GIF 每帧添加文字条"""
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

            # 动态字体大小
            text_len = max(1, len(caption))
            font_size = max(16, min(30, int(w / (text_len + 2))))
            if font_path.exists():
                font = ImageFont.truetype(str(font_path), size=font_size)

            draw = ImageDraw.Draw(frame_rgba)
            bbox = draw.textbbox((0, 0), caption, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]

            x = (w - text_w) // 2
            y = h - text_h - 12

            # 绘制文字描边 (黑边白字，微信表情包标配)
            outline_range = 2
            for dx in range(-outline_range, outline_range + 1):
                for dy in range(-outline_range, outline_range + 1):
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), caption, font=font, fill=(0, 0, 0, 255))
            draw.text((x, y), caption, font=font, fill=(255, 255, 255, 255))

            frames.append(frame_rgba)
            durations.append(im.info.get("duration", 100) / 1000.0)

        avg_duration = sum(durations) / max(1, len(durations))
        imageio.mimsave(str(gif_path), frames, format="GIF", duration=avg_duration, loop=0)
    except Exception as e:
        raise HTTPException(status_code=422, detail="无法处理该动图") from e
