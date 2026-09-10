import hashlib
from fastapi import APIRouter, Request, Query, Response
from app.config import settings

router = APIRouter(prefix="/api/wechat", tags=["wechat"])

@router.get("/callback")
async def wechat_verify(
    signature: str = Query(default=""),
    timestamp: str = Query(default=""),
    nonce: str = Query(default=""),
    echostr: str = Query(default="")
):
    """微信公众平台服务器配置/消息推送握手验证 (GET)"""
    token = settings.WX_MSG_TOKEN
    # 按照字典序排序 token, timestamp, nonce
    items = sorted([token, timestamp, nonce])
    temp_str = "".join(items)
    sha1_hash = hashlib.sha1(temp_str.encode("utf-8")).hexdigest()

    if sha1_hash == signature:
        # 验证通过，原样返回 echostr
        return Response(content=echostr, media_type="text/plain")
    return Response(content="Invalid signature", status_code=403, media_type="text/plain")

@router.post("/callback")
async def wechat_msg_receive(request: Request):
    """微信公众平台消息推送接收 (POST)"""
    # 微信要求收到消息后在 5 秒内回复 success 或空串
    body = await request.body()
    # 后续可在后台处理客服消息转发、发货通知等
    return Response(content="success", media_type="text/plain")

@router.get("/info")
def get_wechat_public_info():
    """供前端或自检调用的微信基础公开配置"""
    return {
        "app_id": settings.WX_APPID,
        "offer_id": settings.XPAY_OFFER_ID,
        "env": settings.XPAY_ENV,
        "kefu_admin": settings.WX_KEFU_ADMIN,
        "base_url": settings.PUBLIC_BASE_URL
    }
