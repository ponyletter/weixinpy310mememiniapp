import hashlib
from fastapi import APIRouter, HTTPException, Request, Query, Response
from pydantic import BaseModel
from typing import Optional
from app.config import settings
from app.security import CurrentOpenid, require_same_user
from app.core.wechat_service import WeChatService

router = APIRouter(tags=["wechat"])

@router.get("/api/wechat/callback")
async def wechat_verify(
    signature: str = Query(default=""),
    timestamp: str = Query(default=""),
    nonce: str = Query(default=""),
    echostr: str = Query(default="")
):
    """微信公众平台服务器配置/消息推送握手验证 (GET)"""
    token = settings.WX_MSG_TOKEN
    items = sorted([token, timestamp, nonce])
    temp_str = "".join(items)
    sha1_hash = hashlib.sha1(temp_str.encode("utf-8")).hexdigest()

    if sha1_hash == signature:
        return Response(content=echostr, media_type="text/plain")
    return Response(content="Invalid signature", status_code=403, media_type="text/plain")

@router.post("/api/wechat/callback")
async def wechat_msg_receive(
    request: Request,
    signature: str = Query(default=""),
    timestamp: str = Query(default=""),
    nonce: str = Query(default=""),
):
    """微信公众平台消息推送接收 (POST)"""
    expected = hashlib.sha1("".join(sorted([settings.WX_MSG_TOKEN, timestamp, nonce])).encode("utf-8")).hexdigest()
    if not signature or expected != signature:
        return Response(content="Invalid signature", status_code=403, media_type="text/plain")
    return Response(content="success", media_type="text/plain")

@router.get("/api/wechat/info")
def get_wechat_public_info():
    """微信公开配置"""
    return {
        "app_id": settings.WX_APPID,
        "offer_id": settings.XPAY_OFFER_ID,
        "env": settings.XPAY_ENV,
        "kefu_admin": settings.WX_KEFU_ADMIN,
        "order_center_path": "pages/order/order",
        "base_url": "https://meme.tg-cc755.cn"
    }

@router.get("/pages/order/order")
@router.get("/order/order")
@router.get("/api/order/center")
def order_center_page():
    """小程序订单中心端点"""
    return {
        "status": "ok",
        "path": "pages/order/order",
        "title": "我的订单与充值记录",
        "app_id": settings.WX_APPID,
        "orders": []
    }

class SendSubscribeMsgRequest(BaseModel):
    openid: str
    template_id: Optional[str] = None
    order_no: Optional[str] = None
    service_type: Optional[str] = "动图表情包制作"
    finish_time: Optional[str] = None
    service_item: Optional[str] = "定制GIF表情"
    page: Optional[str] = "pages/index/index"
    miniprogram_state: Optional[str] = None

@router.post("/api/send-subscribe-msg")
async def send_subscribe_msg_endpoint(req: SendSubscribeMsgRequest, current_openid: CurrentOpenid):
    """主动发送微信小程序订阅消息 (服务完成通知)"""
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="接口不存在")
    res = await WeChatService.send_subscribe_message(
        openid=require_same_user(req.openid, current_openid),
        template_id=req.template_id,
        order_no=req.order_no,
        service_type=req.service_type or "动图表情包制作",
        finish_time=req.finish_time,
        service_item=req.service_item or "定制GIF表情",
        page=req.page or "pages/index/index",
        miniprogram_state=req.miniprogram_state
    )
    return res
