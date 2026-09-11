import hmac
import hashlib
import json
import uuid
from typing import Dict, Any
from app.config import settings
from app.database import (
    get_package_by_id,
    get_order_by_id,
    update_order_trade_no,
    create_order_record,
    mark_order_paid,
    get_user_session_key
)

def hmac_sha256(data: str, key: str) -> str:
    """HMAC-SHA256 基础摘要算法"""
    return hmac.new(key.encode('utf-8'), data.encode('utf-8'), hashlib.sha256).hexdigest()

def calc_pay_sig(uri: str, post_body: str, appkey: str) -> str:
    """计算微信虚拟支付 2.0 paySig: HMAC-SHA256(uri + '&' + post_body, appkey)"""
    msg = f"{uri}&{post_body}"
    return hmac_sha256(msg, appkey)

def calc_signature(post_body: str, session_key: str) -> str:
    """计算微信虚拟支付 2.0 用户态 signature: HMAC-SHA256(post_body, session_key)"""
    return hmac_sha256(post_body, session_key)


def get_active_app_key() -> str:
    """Return the payment key for the currently selected environment."""
    return (
        settings.XPAY_APP_KEY_LIVE
        if settings.XPAY_ENV == 0
        else (settings.XPAY_APP_KEY_SANDBOX or settings.XPAY_APP_KEY)
    )


def calc_pay_event_sig(event: str, payload: str, appkey: str) -> str:
    """Calculate Tencent Super App virtual-payment callback signature."""
    return hmac_sha256(f"{event}&{payload}", appkey)

def create_xpay_order(openid: str, package_id: str) -> Dict[str, Any]:
    """生成微信小程序虚拟支付 2.0 下单参数与签名"""
    pkg = get_package_by_id(package_id)
    if not pkg:
        raise ValueError(f"道具档位 {package_id} 不存在")

    # 25 chars, leaving room for a 6-char retry suffix while retaining 96 bits of entropy.
    order_id = f"M{uuid.uuid4().hex[:24]}"
    amount = pkg['price']  # 单位：分
    quota = pkg['quota']

    active_app_key = get_active_app_key()
    if not active_app_key:
        raise ValueError("支付密钥未配置")
    session_key = get_user_session_key(openid)
    if not session_key:
        raise ValueError("微信登录态已失效，请重新登录后支付")

    # 1. 记录到订单库
    create_order_record(order_id, openid, package_id, amount, quota)

    # 2. 构造 signData 字符串 (符合微信官方虚拟支付 2.0 规范)
    sign_data_dict = {
        "offerId": settings.XPAY_OFFER_ID,
        "buyQuantity": 1,
        "env": settings.XPAY_ENV,  # 0: 现网正式, 1: 沙箱测试
        "currencyType": "CNY",
        "productId": package_id,
        "goodsPrice": amount,
        "outTradeNo": order_id,
        "attach": json.dumps({"openid": openid, "pkg_id": package_id, "quota": quota}, separators=(',', ':'))
    }

    sign_data_str = json.dumps(sign_data_dict, separators=(',', ':'))
    # 现网环境严格使用现网正式 AppKey 计算签名
    pay_sig = calc_pay_sig("requestVirtualPayment", sign_data_str, active_app_key)
    signature = calc_signature(sign_data_str, session_key)

    return {
        "order_id": order_id,
        "title": pkg['title'],
        "amount": amount,
        "quota": quota,
        "payment_params": {
            "signData": sign_data_str,
            "paySig": pay_sig,
            "signature": signature,
            "mode": "short_series_goods"
        },
        "is_sandbox": (settings.XPAY_ENV == 1)
    }

def resume_xpay_order(openid: str, order_id: str) -> Dict[str, Any]:
    """为待付款状态 (PENDING) 的已有订单重新计算签名并返回拉起收银台参数"""
    order = get_order_by_id(order_id)
    if not order:
        raise ValueError("订单不存在")
    if order['openid'] != openid:
        raise ValueError("无权操作此订单")
    if order['status'] != 'PENDING':
        raise ValueError(f"订单当前状态为【{order['status']}】，无法继续支付")

    package_id = order['package_id']
    pkg = get_package_by_id(package_id)
    title = pkg['title'] if pkg else "动图制作额度充值"
    amount = order['amount']
    quota = order['quota_reward']

    # 生成 iOS 友好的全新独立支付流水单号 (严格控制在 <= 32 字符安全长度)
    # 原始 order_id 如 MEME_1789080653_64a74d (22位)，新流水如 MEME_1789080653_64a74d_R8f2a (28位)
    retry_suffix = uuid.uuid4().hex[:4]
    pay_trade_no = f"{order_id}_R{retry_suffix}"

    # 记录该待付款订单最新的支付流水号
    update_order_trade_no(order_id, pay_trade_no)

    sign_data_dict = {
        "offerId": settings.XPAY_OFFER_ID,
        "buyQuantity": 1,
        "env": settings.XPAY_ENV,
        "currencyType": "CNY",
        "productId": package_id,
        "goodsPrice": amount,
        "outTradeNo": pay_trade_no,
        "attach": json.dumps({"openid": openid, "order_id": order_id, "pkg_id": package_id, "quota": quota}, separators=(',', ':'))
    }

    sign_data_str = json.dumps(sign_data_dict, separators=(',', ':'))
    active_app_key = get_active_app_key()
    if not active_app_key:
        raise ValueError("支付密钥未配置")
    pay_sig = calc_pay_sig("requestVirtualPayment", sign_data_str, active_app_key)
    session_key = get_user_session_key(openid)
    if not session_key:
        raise ValueError("微信登录态已失效，请重新登录后支付")
    signature = calc_signature(sign_data_str, session_key)

    return {
        "order_id": order_id,
        "trade_no": pay_trade_no,
        "title": title,
        "amount": amount,
        "quota": quota,
        "payment_params": {
            "signData": sign_data_str,
            "paySig": pay_sig,
            "signature": signature,
            "mode": "short_series_goods"
        },
        "is_sandbox": (settings.XPAY_ENV == 1)
    }

def handle_payment_notify(notify_data: Dict[str, Any]) -> bool:
    """处理并验签微信虚拟支付发货/付款成功回调。

    Tencent's virtual-payment callback signs the exact payload string with
    ``HMAC-SHA256(app_key, event + '&' + payload)``.  The payload is kept as
    a string here intentionally: parsing and re-serialising it before
    verification could change whitespace/escaping and invalidate the
    signature.
    """
    if not isinstance(notify_data, dict):
        return False
    if notify_data.get("eventType") != "TRANSACTION.SUCCESS":
        return False

    event = str(notify_data.get("event", ""))
    if event != settings.XPAY_CALLBACK_EVENT:
        return False

    payload_raw = notify_data.get("payload")
    if not isinstance(payload_raw, str) or not payload_raw:
        return False
    pay_event_sig = str(notify_data.get("payEventSig", ""))
    active_app_key = get_active_app_key()
    if not active_app_key or not pay_event_sig:
        return False
    expected_sig = calc_pay_event_sig(event, payload_raw, active_app_key)
    if not hmac.compare_digest(pay_event_sig, expected_sig):
        return False

    try:
        payload = json.loads(payload_raw)
    except (TypeError, ValueError):
        return False
    if not isinstance(payload, dict):
        return False

    goods_info = payload.get("GoodsInfo")
    if not isinstance(goods_info, dict):
        goods_info = {}
    pay_info = payload.get("PayInfo")
    if not isinstance(pay_info, dict):
        pay_info = {}

    top_out_trade_no = str(notify_data.get("outTradeNo", "") or "")
    payload_out_trade_no = str(payload.get("OutTradeNo", "") or "")
    if top_out_trade_no and payload_out_trade_no and top_out_trade_no != payload_out_trade_no:
        return False
    out_trade_no = top_out_trade_no or payload_out_trade_no
    if not out_trade_no:
        return False

    wx_order_id = str(
        notify_data.get("wechatPayOrderId")
        or notify_data.get("transactionId")
        or pay_info.get("TransactionId")
        or payload.get("TransactionId")
        or ""
    )

    # 优先从 attach 解析出关联的主订单号
    target_id = out_trade_no
    attach_raw = notify_data.get("attach") or goods_info.get("Attach") or goods_info.get("attach") or ""
    if attach_raw:
        try:
            attach_data = json.loads(attach_raw) if isinstance(attach_raw, str) else attach_raw
            if not isinstance(attach_data, dict):
                attach_data = {}
            if "order_id" in attach_data:
                target_id = attach_data["order_id"]
        except Exception:
            pass

    order = get_order_by_id(target_id)
    if not order:
        return False

    # Never trust attach for price, product, or beneficiary. The database is authoritative.
    product_id = notify_data.get("productId") or goods_info.get("ProductId")
    goods_price = notify_data.get("goodsPrice")
    if goods_price is None:
        goods_price = goods_info.get("ActualPrice")
    if goods_price is None:
        goods_price = goods_info.get("OrigPrice")
    offer_id = notify_data.get("offerId")
    callback_openid = payload.get("OpenId")
    if callback_openid and str(callback_openid) != str(order["openid"]):
        return False
    quantity = goods_info.get("Quantity")
    if quantity is not None:
        try:
            if int(quantity) != 1:
                return False
        except (TypeError, ValueError):
            return False
    if product_id is not None and str(product_id) != str(order["package_id"]):
        return False
    if goods_price is not None:
        try:
            if int(goods_price) != int(order["amount"]):
                return False
        except (TypeError, ValueError):
            return False
    if offer_id is not None and str(offer_id) != str(settings.XPAY_OFFER_ID):
        return False

    return mark_order_paid(target_id, wx_order_id)


def handle_wechat_message_notify(notify_data: Dict[str, Any]) -> bool:
    """Handle the raw JSON/XML event sent by Mini Program Message Push.

    The WeChat Console's message-push channel sends the event fields directly
    (``Event``, ``OpenId``, ``OutTradeNo`` and so on), unlike the Tencent SAS
    envelope handled by :func:`handle_payment_notify`.
    """
    if not isinstance(notify_data, dict):
        return False
    event = str(notify_data.get("Event") or notify_data.get("event") or "")
    if event != settings.XPAY_CALLBACK_EVENT:
        return False

    out_trade_no = str(
        notify_data.get("OutTradeNo")
        or notify_data.get("outTradeNo")
        or notify_data.get("out_trade_no")
        or ""
    )
    if not out_trade_no:
        return False

    def as_dict(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str) and value:
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except (TypeError, ValueError):
                return {}
        return {}

    goods_info = as_dict(notify_data.get("GoodsInfo"))
    pay_info = as_dict(notify_data.get("WeChatPayInfo"))
    attach_raw = (
        notify_data.get("Attach")
        or notify_data.get("attach")
        or goods_info.get("Attach")
        or goods_info.get("attach")
        or ""
    )

    target_id = out_trade_no
    if attach_raw:
        attach_data = as_dict(attach_raw)
        if attach_data.get("order_id"):
            target_id = str(attach_data["order_id"])

    order = get_order_by_id(target_id)
    if not order:
        return False

    callback_openid = notify_data.get("OpenId") or notify_data.get("openid") or notify_data.get("FromUserName")
    if callback_openid and str(callback_openid) != str(order["openid"]):
        return False

    callback_env = notify_data.get("Env")
    if callback_env is not None:
        try:
            if int(callback_env) != int(settings.XPAY_ENV):
                return False
        except (TypeError, ValueError):
            return False

    product_id = (
        notify_data.get("ProductId")
        or notify_data.get("productId")
        or goods_info.get("ProductId")
        or goods_info.get("productId")
    )
    goods_price = (
        notify_data.get("ActualPrice")
        or notify_data.get("actualPrice")
        or goods_info.get("ActualPrice")
        or goods_info.get("actualPrice")
        or notify_data.get("GoodsPrice")
        or goods_info.get("OrigPrice")
    )
    quantity = notify_data.get("Quantity") or goods_info.get("Quantity")
    if quantity is not None:
        try:
            if int(quantity) != 1:
                return False
        except (TypeError, ValueError):
            return False
    if product_id is not None and str(product_id) != str(order["package_id"]):
        return False
    if goods_price is not None:
        try:
            if int(goods_price) != int(order["amount"]):
                return False
        except (TypeError, ValueError):
            return False

    wx_order_id = str(
        pay_info.get("TransactionId")
        or pay_info.get("transaction_id")
        or pay_info.get("MchOrderNo")
        or notify_data.get("TransactionId")
        or notify_data.get("wechatPayOrderId")
        or ""
    )
    return mark_order_paid(target_id, wx_order_id)
