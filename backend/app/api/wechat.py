import hashlib
import hmac
import json
import logging
import xml.etree.ElementTree as ET
from fastapi import APIRouter, HTTPException, Request, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from app.config import settings
from app.security import CurrentOpenid, require_same_user
from app.core.wechat_service import WeChatService
from app.payment import handle_wechat_message_notify

router = APIRouter(tags=["wechat"])
logger = logging.getLogger(__name__)


def _verify_message_signature(signature: str, timestamp: str, nonce: str) -> bool:
    """Verify the SHA1 URL signature used by Mini Program Message Push."""
    if not signature or not timestamp or not nonce or not settings.WX_MSG_TOKEN:
        return False
    expected = hashlib.sha1(
        "".join(sorted([settings.WX_MSG_TOKEN, timestamp, nonce])).encode("utf-8")
    ).hexdigest()
    return hmac_compare(signature, expected)


def hmac_compare(left: str, right: str) -> bool:
    """Constant-time comparison for the short SHA1 handshake values."""
    return hmac.compare_digest(left, right)


def _xml_to_dict(element: ET.Element) -> dict:
    result = {}
    for child in element:
        if len(child):
            result[child.tag] = _xml_to_dict(child)
        else:
            result[child.tag] = child.text or ""
    return result


def _parse_message_push(body: bytes) -> tuple[dict, bool]:
    text = body.decode("utf-8", errors="ignore").strip()
    if text.startswith("<"):
        root = ET.fromstring(text)
        return _xml_to_dict(root), True
    parsed = json.loads(text) if text else {}
    if not isinstance(parsed, dict):
        raise ValueError("消息推送 JSON 必须是对象")
    return parsed, False


def _message_push_response(is_xml: bool, success: bool):
    err_code = 0 if success else 1
    err_msg = "success" if success else "payment callback validation failed"
    if is_xml:
        xml = f"<xml><ErrCode>{err_code}</ErrCode><ErrMsg><![CDATA[{err_msg}]]></ErrMsg></xml>"
        return Response(content=xml, media_type="application/xml")
    return JSONResponse(content={"ErrCode": err_code, "ErrMsg": err_msg})

@router.get("/api/wechat/msg_push")
@router.get("/api/wechat/callback")
async def wechat_verify(
    signature: str = Query(default=""),
    timestamp: str = Query(default=""),
    nonce: str = Query(default=""),
    echostr: str = Query(default="")
):
    """微信公众平台服务器配置/消息推送握手验证 (GET)"""
    if _verify_message_signature(signature, timestamp, nonce):
        return Response(content=echostr, media_type="text/plain")
    return Response(content="Invalid signature", status_code=403, media_type="text/plain")

@router.post("/api/wechat/msg_push")
@router.post("/api/wechat/callback")
async def wechat_msg_receive(
    request: Request,
    signature: str = Query(default=""),
    timestamp: str = Query(default=""),
    nonce: str = Query(default=""),
):
    """微信公众平台消息推送接收 (POST)"""
    if not _verify_message_signature(signature, timestamp, nonce):
        return Response(content="Invalid signature", status_code=403, media_type="text/plain")
    try:
        body, is_xml = _parse_message_push(await request.body())
    except (ET.ParseError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("wechat message push parse failed: %s", exc)
        return _message_push_response(False, False)

    event = str(body.get("Event") or body.get("event") or "")
    if event != settings.XPAY_CALLBACK_EVENT:
        # Message Push also carries non-payment events.  Acknowledge those so
        # WeChat does not retry unrelated messages indefinitely.
        return _message_push_response(is_xml, True)

    success = handle_wechat_message_notify(body)
    if not success:
        logger.warning(
            "wechat payment message rejected: event=%s out_trade_no=%s",
            event,
            body.get("OutTradeNo") or body.get("outTradeNo"),
        )
    else:
        logger.info(
            "wechat payment message accepted: out_trade_no=%s",
            body.get("OutTradeNo") or body.get("outTradeNo"),
        )
    return _message_push_response(is_xml, success)

@router.get("/api/wechat/info")
def get_wechat_public_info():
    """微信公开配置"""
    return {
        "app_id": settings.WX_APPID,
        "offer_id": settings.XPAY_OFFER_ID,
        "env": settings.XPAY_ENV,
        "kefu_admin": settings.WX_KEFU_ADMIN,
        "order_center_path": "pages/order/order",
        "base_url": "https://meme.tg-cc755.cn",
        "message_push_url": settings.WX_MSG_PUSH_URL,
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
