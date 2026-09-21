import json
import io
import uuid
import re
from typing import Optional
import httpx
from fastapi import APIRouter, Query, Response, Form, HTTPException
from PIL import Image, ImageDraw

from app.config import settings
from app.services.chinesebqb_service import ChineseBQBService
from app.core.wechat_service import WeChatService
from app.database import add_item_to_collection

router = APIRouter(prefix="/api/materials", tags=["materials"])
_template_image_cache = {}


@router.get("/categories")
def list_categories(response: Response):
    """
    获取 ChineseBQB 精选表情素材分类与各分类数量统计
    """
    response.headers["Cache-Control"] = "public, max-age=3600"
    categories = ChineseBQBService.get_categories()
    return {"code": 0, "data": categories}


@router.get("/list")
def list_materials(
    response: Response,
    category: str = Query("all", description="分类ID或名称，如 all, bqb-015, 熊猫"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(24, ge=1, le=100, description="每页数量")
):
    """
    分页获取 ChineseBQB 指定分类下的表情素材
    """
    response.headers["Cache-Control"] = "public, max-age=1800"
    data = ChineseBQBService.get_materials(category=category, page=page, page_size=page_size)
    return {"code": 0, "data": data}


@router.get("/search")
def search_materials(
    response: Response,
    q: str = Query("", description="搜索关键词，如 熊猫头、打工人、猫、斗图"),
    category: Optional[str] = Query(None, description="可选限定分类"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(24, ge=1, le=100, description="每页数量")
):
    """
    关键词实时搜索 5,800+ 款 ChineseBQB 公开表情素材
    """
    response.headers["Cache-Control"] = "public, max-age=300"
    data = ChineseBQBService.search_materials(query=q, category=category, page=page, page_size=page_size)
    return {"code": 0, "data": data}


@router.get("/templates")
def list_meme_templates(response: Response):
    """
    获取人工筛选的无字经典表情模板（用于搜索空状态定制、百宝箱模板配字）
    """
    response.headers["Cache-Control"] = "public, max-age=1800"
    tpl_file = settings.STATIC_DIR / "meme_templates" / "templates.json"
    if tpl_file.exists():
        try:
            with open(tpl_file, "r", encoding="utf-8") as f:
                templates = json.load(f)
            return {"code": 0, "data": templates}
        except Exception as e:
            print(f"[materials] Read templates.json failed: {e}")
    return {"code": 0, "data": []}


def _get_meme_template(template_id: str):
    tpl_file = settings.STATIC_DIR / "meme_templates" / "templates.json"
    if not tpl_file.exists():
        return None
    try:
        with open(tpl_file, "r", encoding="utf-8") as f:
            templates = json.load(f)
        return next((item for item in templates if item.get("id") == template_id), None)
    except (OSError, ValueError):
        return None


async def _load_template_image(template: dict) -> Image.Image:
    """只下载清单中指定的 ChineseBQB 素材，不接受客户端传入任意 URL。"""
    source_item = ChineseBQBService.get_item(template.get("source_item_id", ""))
    if not source_item:
        raise HTTPException(status_code=404, detail="表情模板底图不存在")
    source_url = source_item["url"]
    if not source_url.startswith("https://zhaoolee.com/ChineseBQB/"):
        raise HTTPException(status_code=400, detail="表情模板来源不受信任")
    cached = _template_image_cache.get(source_item["id"])
    if cached is not None:
        return cached.copy()
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(source_url)
            response.raise_for_status()
        if len(response.content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="表情模板文件过大")
        image = Image.open(io.BytesIO(response.content)).convert("RGBA")
        if len(_template_image_cache) >= 16:
            _template_image_cache.clear()
        _template_image_cache[source_item["id"]] = image
        return image.copy()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="暂时无法读取表情模板，请稍后重试") from exc


@router.post("/render-meme")
async def render_custom_meme(
    template_id: str = Form(...),
    caption: str = Form(...),
    font_size: int = Form(28),
    color: str = Form("#1e293b"),
    pos: str = Form("bottom"),
    font_style: str = Form("bold"),
    text_stroke: bool = Form(True),
    openid: Optional[str] = Form(None),
    collection_id: Optional[str] = Form(None)
):
    """
    【经典梗图配字合成】接收模版ID与台词，自动将台词排版到表情包模版留白处
    """
    caption_text = caption.strip()
    if not caption_text:
        raise HTTPException(status_code=400, detail="台词内容不能为空")
    if len(caption_text) > 60:
        raise HTTPException(status_code=400, detail="台词不能超过 60 个字符")

    # 安全审核
    is_safe, tip = await WeChatService.check_text_security(caption_text, openid or "")
    if not is_safe:
        raise HTTPException(status_code=400, detail=tip or "内容包含违规敏感信息，请修改后重试")

    template = _get_meme_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="表情模板已下线，请重新选择")

    # 经典斗图样式：主体居上、底部固定大留白，避免文字压住表情。
    source_img = await _load_template_image(template)
    base_img = Image.new("RGBA", (480, 480), (255, 255, 255, 255))
    scale = min(400 / source_img.width, 280 / source_img.height)
    source_img = source_img.resize(
        (max(1, int(source_img.width * scale)), max(1, int(source_img.height * scale))),
        Image.Resampling.LANCZOS,
    )
    source_x = (480 - source_img.width) // 2
    source_y = max(8, (310 - source_img.height) // 2)
    base_img.alpha_composite(source_img, (source_x, source_y))

    w, h = base_img.size
    draw = ImageDraw.Draw(base_img)

    # 字体加载
    f_size = max(18, min(48, font_size))
    from app.api.convert import _get_cjk_font
    safe_font_style = font_style if font_style in {"regular", "bold", "serif"} else "bold"
    def make_font(size):
        return _get_cjk_font(
            size,
            bold=safe_font_style == "bold",
            serif=safe_font_style == "serif",
        )

    # 解析文字颜色
    hex_color = re.compile(r"^#[0-9a-fA-F]{6}$")
    text_color = (30, 41, 59, 255)
    if color and hex_color.fullmatch(color):
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        text_color = (r, g, b, 255)

    # 自动折行计算：单行最多字数
    import textwrap
    while True:
        font = make_font(f_size)
        chars_per_line = max(6, int((w - 48) / f_size))
        lines = textwrap.wrap(caption_text, width=chars_per_line) or [caption_text]
        line_h = int(f_size * 1.35)
        total_text_h = len(lines) * line_h
        if total_text_h <= 140 or f_size == 18:
            break
        f_size = max(18, f_size - 2)

    # 纵向起始位置
    if pos == "top":
        start_y = 30
    elif pos == "center":
        start_y = (h - total_text_h) // 2
    else: # bottom
        start_y = max(320, h - total_text_h - 28)

    # 逐行居中绘制，添加轻微高对比白描边让文字格外清晰
    curr_y = start_y
    stroke_color = (255, 255, 255, 255) if text_color != (255, 255, 255, 255) else (0, 0, 0, 255)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        tx = (w - tw) // 2
        draw.text(
            (tx, curr_y),
            line,
            font=font,
            fill=text_color,
            stroke_width=2 if text_stroke else 0,
            stroke_fill=stroke_color,
        )
        curr_y += line_h

    # 保存合成结果
    task_id = uuid.uuid4().hex
    task_dir = settings.OUTPUT_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    out_file = task_dir / "meme_result.png"
    base_img.save(str(out_file), "PNG")

    rel_url = f"/outputs/{task_id}/meme_result.png"

    # 若指定了合集 ID，顺道加入合集
    saved_to_col = False
    if collection_id and openid:
        try:
            add_item_to_collection(
                collection_id=collection_id,
                gif_url=rel_url,
                title=caption_text[:20],
                openid=openid
            )
            saved_to_col = True
        except Exception as e:
            print(f"[render-meme] Add to col failed: {e}")

    return {
        "code": 0,
        "data": {
            "task_id": task_id,
            "image_url": rel_url,
            "caption": caption_text,
            "template_id": template_id,
            "saved_to_collection": saved_to_col
        }
    }
