from fastapi import APIRouter, Query, Response
from typing import Optional
from app.database import get_material_categories, get_materials_list

router = APIRouter(prefix="/api/materials", tags=["materials"])


@router.get("/categories")
def list_categories(response: Response):
    """
    获取精选表情素材分类与各分类数量统计
    服务端设置 1 小时缓存，提升高频访问速度
    """
    response.headers["Cache-Control"] = "public, max-age=3600"
    categories = get_material_categories()
    return {"code": 0, "data": categories}


@router.get("/list")
def list_materials(
    response: Response,
    category: str = Query("all", description="分类ID，如 all, funny, cute, worker, sarcasm, classic"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """
    分页获取指定分类下的精选表情素材
    """
    response.headers["Cache-Control"] = "public, max-age=1800"
    data = get_materials_list(category=category, page=page, page_size=page_size)
    return {"code": 0, "data": data}
