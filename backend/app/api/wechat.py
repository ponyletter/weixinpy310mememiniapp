import hashlib
from fastapi import APIRouter, Request, Query, Response
from app.config import settings

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
async def wechat_msg_receive(request: Request):
    """微信公众平台消息推送接收 (POST)"""
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
