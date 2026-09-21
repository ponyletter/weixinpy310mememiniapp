from fastapi import APIRouter, Query, Response
from typing import Optional
from app.services.chinesebqb_service import ChineseBQBService

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
