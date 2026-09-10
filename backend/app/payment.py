import hmac
import hashlib
import json
import time
import uuid
from typing import Dict, Any, Optional
from app.config import settings
from app.database import (
    get_package_by_id,
    create_order_record,
    mark_order_paid,
    get_user_session_key,
    get_user,
    get_db
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

    order_id = f"MEME_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    amount = pkg['price']  # 单位：分
    quota = pkg['quota']

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
    active_app_key = settings.XPAY_APP_KEY_LIVE if settings.XPAY_ENV == 0 else (settings.XPAY_APP_KEY_SANDBOX or settings.XPAY_APP_KEY)
    pay_sig = calc_pay_sig("requestVirtualPayment", sign_data_str, active_app_key)
    session_key = get_user_session_key(openid) or active_app_key
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

def handle_payment_notify(notify_data: Dict[str, Any]) -> bool:
    """处理微信虚拟支付发货/付款成功回调"""
    order_id = notify_data.get("outTradeNo")
    wx_order_id = notify_data.get("wechatPayOrderId", "")
    if not order_id:
        return False
    return mark_order_paid(order_id, wx_order_id)
