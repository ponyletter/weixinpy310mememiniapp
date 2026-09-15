from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field
from typing import Optional, List
from app.database import (
    create_collection,
    add_item_to_collection,
    get_collection_detail,
    get_collection_visibility,
    get_user_collections,
    get_public_collections,
    delete_collection,
    delete_collection_item,
    move_collection_item,
    update_collection_item_title,
    reorder_collection_items
)
from app.security import CurrentOpenid, OptionalOpenid, require_same_user

router = APIRouter(prefix="/api/collection", tags=["collections"])


def _disable_cache(response: Response) -> None:
    """Collection counts and contents are mutable; never serve a stale GET response."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"

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

class MoveItemRequest(BaseModel):
    item_id: int
    target_collection_id: str
    openid: Optional[str] = ""

class RenameItemRequest(BaseModel):
    item_id: int
    title: str = Field(min_length=1, max_length=80)
    openid: Optional[str] = ""

class ReorderItemsRequest(BaseModel):
    collection_id: str
    item_ids: List[int] = Field(min_length=1)
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

@router.post("/item/move")
def move_item(req: MoveItemRequest, current_openid: CurrentOpenid):
    """将表情从当前合集移动到目标合集"""
    openid = require_same_user(req.openid, current_openid)
    move_collection_item(req.item_id, req.target_collection_id, openid)
    return {"success": True, "message": "表情已成功移动至新合集"}

@router.post("/item/rename")
def rename_item(req: RenameItemRequest, current_openid: CurrentOpenid):
    """修改合集中单张表情的备注/名称"""
    openid = require_same_user(req.openid, current_openid)
    update_collection_item_title(req.item_id, req.title.strip(), openid)
    return {"success": True, "message": "表情备注已更新", "new_title": req.title.strip()}

@router.post("/item/reorder")
def reorder_items(req: ReorderItemsRequest, current_openid: CurrentOpenid):
    """合集表情自定义调整排序"""
    openid = require_same_user(req.openid, current_openid)
    reorder_collection_items(req.collection_id, req.item_ids, openid)
    return {"success": True, "message": "表情排序已保存"}

@router.post("/add-item")
def add_gif_to_collection(req: AddItemRequest, current_openid: CurrentOpenid):
    """向指定合集中添加表情包"""
    if not req.collection_id or not req.gif_url:
        raise HTTPException(status_code=400, detail="合集ID和表情包URL不能为空")
    res = add_item_to_collection(req.collection_id, req.gif_url, req.title, current_openid)
    return {"success": True, "data": res}

@router.get("/detail")
def get_detail(response: Response, collection_id: str = Query(...), current_openid: OptionalOpenid = None):
    """获取合集详情及其包含的表情包列表 (支持微信分享打开直接查看)"""
    _disable_cache(response)
    visibility = get_collection_visibility(collection_id)
    if not visibility:
        raise HTTPException(status_code=404, detail="合集不存在或已被删除")
    # 公开合集可匿名查看；私有合集只能由创建者查看，避免猜测 collection_id 泄露内容。
    if not visibility.get("is_public") and visibility.get("openid") != current_openid:
        raise HTTPException(status_code=404, detail="合集不存在或已被删除")
    res = get_collection_detail(collection_id)
    if not res:
        raise HTTPException(status_code=404, detail="合集不存在或已被删除")
    return {"success": True, "data": res}

@router.get("/my")
@router.get("/list")
def get_my_collections(response: Response, current_openid: CurrentOpenid, openid: str = Query("")):
    """获取我创建的所有表情包合集 (兼容 /my 和 /list)"""
    _disable_cache(response)
    res = get_user_collections(require_same_user(openid, current_openid))
    return {"success": True, "data": res}

@router.get("/explore")
def explore_collections(response: Response, limit: int = Query(default=15)):
    """精选热门表情包合集广场 (用于冷启动展示与直接收藏)"""
    _disable_cache(response)
    res = get_public_collections(limit)
    return {"success": True, "data": res}
