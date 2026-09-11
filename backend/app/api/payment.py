import hmac
import logging

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel
from app.config import settings
from app.database import (
    get_packages,
    mark_order_paid,
    cancel_order_record,
    get_order_by_id,
    format_datetime_china,
)
from app.payment import create_xpay_order, resume_xpay_order, handle_payment_notify
from app.security import CurrentOpenid, require_same_user

router = APIRouter(prefix="/api/pay", tags=["virtual_payment"])
logger = logging.getLogger(__name__)

class CreateOrderRequest(BaseModel):
    openid: str
    package_id: str

class RepayOrderRequest(BaseModel):
    openid: str
    order_id: str

class CancelOrderRequest(BaseModel):
    openid: str
    order_id: str

class MockPayRequest(BaseModel):
    order_id: str

@router.get("/goods")
def get_goods_list():
    """获取所有可用虚拟支付道具档位包"""
    packages = get_packages()
    return {
        "success": True,
        "packages": packages,
        "offer_id": settings.XPAY_OFFER_ID,
        "env": settings.XPAY_ENV
    }

@router.post("/create-order")
def create_payment_order(req: CreateOrderRequest, current_openid: CurrentOpenid):
    """创建微信虚拟支付 2.0 订单并返回前端拉起收银台所需签名"""
    try:
        data = create_xpay_order(require_same_user(req.openid, current_openid), req.package_id)
        return {"success": True, "data": data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成支付订单失败: {str(e)}")

@router.post("/repay-order")
def repay_order_endpoint(req: RepayOrderRequest, current_openid: CurrentOpenid):
    """为待付款订单重新计算并返回拉起微信虚拟支付收银台所需参数"""
    try:
        data = resume_xpay_order(require_same_user(req.openid, current_openid), req.order_id)
        return {"success": True, "data": data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"恢复支付失败: {str(e)}")

@router.post("/cancel-order")
def cancel_order_endpoint(req: CancelOrderRequest, current_openid: CurrentOpenid):
    """取消未支付的待付款订单"""
    success = cancel_order_record(req.order_id, require_same_user(req.openid, current_openid))
    if not success:
        raise HTTPException(status_code=400, detail="订单不存在或当前状态不可取消")
    return {"success": True, "message": "订单已成功取消"}


@router.get("/order-status")
def payment_order_status(response: Response, current_openid: CurrentOpenid, order_id: str = Query(..., min_length=6, max_length=64)):
    """Return the server-confirmed state of a user's payment order.

    A successful ``wx.requestVirtualPayment`` callback only means the
    payment UI completed.  The server callback is the source of truth for
    crediting quota, so the mini program polls this endpoint briefly after
    the payment UI closes.
    """
    order = get_order_by_id(order_id.strip())
    if not order or order["openid"] != current_openid:
        raise HTTPException(status_code=404, detail="订单不存在")
    response.headers["Cache-Control"] = "no-store"
    return {
        "success": True,
        "order_id": order["order_id"],
        "status": order["status"],
        "paid": order["status"] == "PAID",
        "quota_reward": order["quota_reward"],
        "pay_time": format_datetime_china(order.get("pay_time")),
        "timezone": "Asia/Shanghai",
    }

@router.post("/mock-pay")
def mock_pay_success(req: MockPayRequest, current_openid: CurrentOpenid):
    """开发测试环境模拟支付成功直接结算发放额度"""
    if not settings.DEBUG or not settings.ENABLE_MOCK_PAYMENT or settings.XPAY_ENV != 1:
        raise HTTPException(status_code=404, detail="接口不存在")
    order = get_order_by_id(req.order_id)
    if not order or order["openid"] != current_openid:
        raise HTTPException(status_code=404, detail="订单不存在")
    success = mark_order_paid(req.order_id, wx_order_id=f"MOCK_{req.order_id}")
    if not success:
        raise HTTPException(status_code=404, detail="订单不存在或已被结算")
    return {"success": True, "message": "模拟支付成功，额度已实时到账！"}

@router.post("/notify")
async def payment_notify(request: Request):
    """微信虚拟支付发货/扣费回调通知"""
    supplied_token = request.headers.get("X-XPay-Callback-Token", "")
    if not settings.XPAY_CALLBACK_TOKEN or not hmac.compare_digest(supplied_token, settings.XPAY_CALLBACK_TOKEN):
        raise HTTPException(status_code=401, detail="支付回调认证失败")
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="支付回调不是有效 JSON") from exc
    if not handle_payment_notify(body):
        logger.warning(
            "payment callback rejected: event=%s event_type=%s out_trade_no=%s",
            body.get("event"),
            body.get("eventType"),
            body.get("outTradeNo"),
        )
        raise HTTPException(status_code=400, detail="支付回调校验或结算失败")
    logger.info("payment callback accepted: out_trade_no=%s", body.get("outTradeNo"))
    # Tencent Super App expects this response shape.  Returning only the
    # legacy errcode/errmsg pair makes a valid callback look failed and causes
    # retries, while the order remains pending from the user's perspective.
    return {"returnCode": "0", "returnMessage": "success", "data": "ok"}
