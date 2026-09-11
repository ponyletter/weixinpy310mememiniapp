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

def create_xpay_order(openid: str, package_id: str) -> Dict[str, Any]:
    """生成微信小程序虚拟支付 2.0 下单参数与签名"""
    pkg = get_package_by_id(package_id)
    if not pkg:
        raise ValueError(f"道具档位 {package_id} 不存在")

    # 25 chars, leaving room for a 6-char retry suffix while retaining 96 bits of entropy.
    order_id = f"M{uuid.uuid4().hex[:24]}"
    amount = pkg['price']  # 单位：分
    quota = pkg['quota']

    active_app_key = settings.XPAY_APP_KEY_LIVE if settings.XPAY_ENV == 0 else (settings.XPAY_APP_KEY_SANDBOX or settings.XPAY_APP_KEY)
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
    active_app_key = settings.XPAY_APP_KEY_LIVE if settings.XPAY_ENV == 0 else (settings.XPAY_APP_KEY_SANDBOX or settings.XPAY_APP_KEY)
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
    """处理微信虚拟支付发货/付款成功回调"""
    out_trade_no = notify_data.get("outTradeNo", "")
    wx_order_id = notify_data.get("wechatPayOrderId", "")
    if not out_trade_no:
        return False

    # 优先从 attach 解析出关联的主订单号
    target_id = out_trade_no
    attach_raw = notify_data.get("attach", "")
    if attach_raw:
        try:
            attach_data = json.loads(attach_raw)
            if "order_id" in attach_data:
                target_id = attach_data["order_id"]
        except Exception:
            pass

    order = get_order_by_id(target_id)
    if not order:
        return False

    # Never trust attach for price, product, or beneficiary. The database is authoritative.
    product_id = notify_data.get("productId")
    goods_price = notify_data.get("goodsPrice")
    offer_id = notify_data.get("offerId")
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
