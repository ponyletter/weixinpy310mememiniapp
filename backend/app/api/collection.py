from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from app.database import (
    create_collection,
    add_item_to_collection,
    get_collection_detail,
    get_user_collections,
    get_public_collections,
    delete_collection,
    delete_collection_item
)
from app.security import CurrentOpenid, require_same_user

router = APIRouter(prefix="/api/collection", tags=["collections"])

class CreateCollectionRequest(BaseModel):
    openid: str
    title: str = Field(min_length=1, max_length=60)
    description: Optional[str] = Field(default="", max_length=300)
    cover_url: Optional[str] = Field(default="", max_length=500)

class AddItemRequest(BaseModel):
    collection_id: str
    gif_url: str = Field(min_length=1, max_length=500)
    title: Optional[str] = Field(default="", max_length=80)

class DeleteCollectionRequest(BaseModel):
    collection_id: str
    openid: Optional[str] = ""

class DeleteItemRequest(BaseModel):
    item_id: int
    openid: Optional[str] = ""

@router.post("/create")
def create_new_collection(req: CreateCollectionRequest, current_openid: CurrentOpenid):
    """创建新的表情包合集/小抽屉"""
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="合集标题不能为空")
    openid = require_same_user(req.openid, current_openid)
    res = create_collection(openid, req.title.strip(), req.description, req.cover_url)
    return {"success": True, "data": res}

@router.post("/delete")
def delete_col(req: DeleteCollectionRequest, current_openid: CurrentOpenid):
    """删除合集及其关联表情"""
    if not req.collection_id:
        raise HTTPException(status_code=400, detail="合集ID不能为空")
    openid = require_same_user(req.openid, current_openid)
    delete_collection(req.collection_id, openid)
    return {"success": True, "message": "合集已成功删除"}

@router.post("/item/delete")
def delete_item(req: DeleteItemRequest, current_openid: CurrentOpenid):
    """删除合集中的某个单张表情"""
    openid = require_same_user(req.openid, current_openid)
    delete_collection_item(req.item_id, openid)
    return {"success": True, "message": "表情条目已删除"}

@router.post("/add-item")
def add_gif_to_collection(req: AddItemRequest, current_openid: CurrentOpenid):
    """向指定合集中添加表情包"""
    if not req.collection_id or not req.gif_url:
        raise HTTPException(status_code=400, detail="合集ID和表情包URL不能为空")
    res = add_item_to_collection(req.collection_id, req.gif_url, req.title, current_openid)
    return {"success": True, "data": res}

@router.get("/detail")
def get_detail(collection_id: str = Query(...)):
    """获取合集详情及其包含的表情包列表 (支持微信分享打开直接查看)"""
    res = get_collection_detail(collection_id)
    if not res:
        raise HTTPException(status_code=404, detail="合集不存在或已被删除")
    return {"success": True, "data": res}

@router.get("/my")
@router.get("/list")
def get_my_collections(current_openid: CurrentOpenid, openid: str = Query("")):
    """获取我创建的所有表情包合集 (兼容 /my 和 /list)"""
    res = get_user_collections(require_same_user(openid, current_openid))
    return {"success": True, "data": res}

@router.get("/explore")
def explore_collections(limit: int = Query(default=15)):
    """精选热门表情包合集广场 (用于冷启动展示与直接收藏)"""
    res = get_public_collections(limit)
    return {"success": True, "data": res}
