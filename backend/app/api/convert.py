import os
import subprocess
import uuid
import shutil
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from PIL import Image, ImageDraw, ImageFont
import imageio

from app.config import settings

router = APIRouter(prefix="/api/convert", tags=["conversion_and_remix"])

@router.post("/video-to-gif")
async def video_to_gif(
    video: UploadFile = File(...),
    start_time: float = Form(0.0),
    duration: float = Form(3.0),
    fps: int = Form(10),
    width: int = Form(240),
    caption: str = Form(""),
):
    """【聊天视频直转动图】利用本地 ffmpeg 高质量双通道调色板生成微信合规 GIF"""
    task_id = str(uuid.uuid4())[:8]
    task_dir = settings.OUTPUT_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    input_path = task_dir / f"input_video{Path(video.filename or 'video.mp4').suffix}"
    output_gif_path = task_dir / "meme_result.gif"

    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)

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
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"视频转动图处理失败: {e.stderr.decode('utf-8', errors='ignore')[:200]}")

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
    files: List[UploadFile] = File(...),
    fps: int = Form(4),
    caption: str = Form("")
):
    """【多图拼接动图】多张连续照片一键合成动图"""
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="至少需要 2 张图片才能合成动图")

    task_id = str(uuid.uuid4())[:8]
    task_dir = settings.OUTPUT_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    frames = []
    target_size = (300, 300)

    for idx, f in enumerate(files):
        img_raw = Image.open(f.file).convert("RGBA")
        img_resized = img_raw.resize(target_size, Image.Resampling.LANCZOS)
        frames.append(img_resized)

    output_gif_path = task_dir / "meme_result.gif"
    duration_sec = 1.0 / max(1, fps)
    imageio.mimsave(str(output_gif_path), frames, format="GIF", duration=duration_sec, loop=0)

    if caption.strip():
        _add_caption_to_gif(output_gif_path, caption.strip())

    file_size_kb = round(output_gif_path.stat().st_size / 1024, 1)
    return {
        "success": True,
        "task_id": task_id,
        "gif_url": f"/outputs/{task_id}/meme_result.gif",
        "file_size_kb": file_size_kb
    }

@router.post("/edit-caption")
async def edit_caption(
    gif_file: Optional[UploadFile] = File(None),
    gif_url: Optional[str] = Form(None),
    caption: str = Form(""),
):
    """【表情包改字与二创】为已有动图重新覆盖/追加爆笑字幕"""
    if not caption.strip():
        raise HTTPException(status_code=400, detail="新文字不能为空")

    task_id = str(uuid.uuid4())[:8]
    task_dir = settings.OUTPUT_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    target_gif = task_dir / "meme_result.gif"

    if gif_file and gif_file.filename:
        with open(target_gif, "wb") as buffer:
            shutil.copyfileobj(gif_file.file, buffer)
    elif gif_url:
        clean_url = gif_url.split("?")[0].lstrip("/")
        local_src = settings.BASE_DIR / clean_url
        if not local_src.exists():
            # 尝试 outputs 查找
            local_src = settings.OUTPUT_DIR / clean_url.replace("outputs/", "")
        if local_src.exists():
            shutil.copy(local_src, target_gif)
        else:
            raise HTTPException(status_code=404, detail="源动图文件不存在")
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
        print(f"Warning: Failed to add caption to gif: {e}")
