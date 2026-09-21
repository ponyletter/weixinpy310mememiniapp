import json
import uuid
import re
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Query, Response, Form, HTTPException, Request
from PIL import Image, ImageDraw, ImageFont

from app.config import settings
from app.services.chinesebqb_service import ChineseBQBService
from app.core.wechat_service import WeChatService
from app.database import add_item_to_collection

router = APIRouter(prefix="/api/materials", tags=["materials"])


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
    关键词实时搜索 5,800+ 款 ChineseBQB 开源表情素材
    """
    response.headers["Cache-Control"] = "public, max-age=300"
    data = ChineseBQBService.search_materials(query=q, category=category, page=page, page_size=page_size)
    return {"code": 0, "data": data}


@router.get("/templates")
def list_meme_templates(response: Response):
    """
    获取 20 款经典表情包底图模版列表（用于搜索空状态定制、百宝箱模版配字）
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


@router.post("/render-meme")
async def render_custom_meme(
    template_id: str = Form("tpl_panda_question"),
    caption: str = Form(...),
    font_size: int = Form(28),
    color: str = Form("#1e293b"),
    pos: str = Form("bottom"),
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

    # 载入底图模板
    tpl_path = settings.STATIC_DIR / "meme_templates" / f"{template_id}.png"
    if not tpl_path.exists():
        # 回退默认
        tpl_path = settings.STATIC_DIR / "meme_templates" / "tpl_panda_question.png"
    if not tpl_path.exists():
        raise HTTPException(status_code=404, detail="表情模版底图不存在")

    # 打开底图
    try:
        base_img = Image.open(tpl_path).convert("RGBA")
    except Exception as exc:
        raise HTTPException(status_code=500, detail="无法读取底图模板") from exc

    w, h = base_img.size
    draw = ImageDraw.Draw(base_img)

    # 字体加载
    f_size = max(18, min(48, font_size))
    from app.api.convert import _get_cjk_font
    font = _get_cjk_font(f_size, bold=True)

    # 解析文字颜色
    hex_color = re.compile(r"^#[0-9a-fA-F]{6}$")
    text_color = (30, 41, 59, 255)
    if color and hex_color.fullmatch(color):
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        text_color = (r, g, b, 255)

    # 自动折行计算：单行最多字数
    chars_per_line = max(6, int((w - 40) / f_size))
    import textwrap
    lines = textwrap.wrap(caption_text, width=chars_per_line) or [caption_text]
    line_h = int(f_size * 1.35)
    total_text_h = len(lines) * line_h

    # 纵向起始位置
    if pos == "top":
        start_y = 30
    elif pos == "center":
        start_y = (h - total_text_h) // 2
    else: # bottom
        # 模版底部留白区域在 y=270~380 之间
        start_y = max(270, h - total_text_h - 25)

    # 逐行居中绘制，添加轻微高对比白描边让文字格外清晰
    curr_y = start_y
    stroke_color = (255, 255, 255, 255) if text_color != (255, 255, 255, 255) else (0, 0, 0, 255)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        tx = (w - tw) // 2
        # 绘制描边
        draw.text((tx, curr_y), line, font=font, fill=text_color, stroke_width=2, stroke_fill=stroke_color)
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
