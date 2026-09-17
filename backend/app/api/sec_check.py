import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel, Field

from app.core.wechat_service import WeChatService
from app.security import get_optional_openid
from app.upload_utils import read_limited_upload

router = APIRouter(prefix="/api/check", tags=["security_check"])
logger = logging.getLogger(__name__)


class CheckTextRequest(BaseModel):
    text: str = Field(default="", max_length=500)


@router.post("/image")
async def check_image_endpoint(
    file: UploadFile = File(...),
    openid: Optional[str] = Depends(get_optional_openid),
):
    """
    即时图片内容安全检测接口：
    用户在小程序相册或拍照选取图片后，前端立即调用此接口进行预检。
    如果违规直接返回 400 并附带官方标准错误提示；合规则返回 200。
    """
    content = await read_limited_upload(file, max_mb=10)
    is_safe, tip = await WeChatService.check_image_security(content)
    if not is_safe:
        raise HTTPException(
            status_code=400,
            detail=tip or "所发布内容包含违规信息，请修改后重试"
        )
    return {"safe": True, "message": "通过检测"}


@router.post("/text")
async def check_text_endpoint(
    req: CheckTextRequest,
    openid: Optional[str] = Depends(get_optional_openid),
):
    """
    即时文本内容安全检测接口：
    用户在输入框输入文案失焦 (bindblur) 或提交前，前端调用此接口预检。
    如果违规直接返回 400 并附带官方标准错误提示；合规则返回 200。
    """
    is_safe, tip = await WeChatService.check_text_security(req.text, openid)
    if not is_safe:
        raise HTTPException(
            status_code=400,
            detail=tip or "所发布内容包含违规信息，请修改后重试"
        )
    return {"safe": True, "message": "通过检测"}
