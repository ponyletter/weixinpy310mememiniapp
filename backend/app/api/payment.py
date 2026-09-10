from fastapi import APIRouter, HTTPException, Query, Body, Request
from pydantic import BaseModel
from typing import Dict, Any, Optional
from app.config import settings
from app.database import get_packages, get_package_by_id, get_user_orders, mark_order_paid
from app.payment import create_xpay_order, handle_payment_notify

router = APIRouter(prefix="/api/pay", tags=["virtual_payment"])

class CreateOrderRequest(BaseModel):
    openid: str
    package_id: str

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
def create_payment_order(req: CreateOrderRequest):
    """创建微信虚拟支付 2.0 订单并返回前端拉起收银台所需签名"""
    try:
        data = create_xpay_order(req.openid, req.package_id)
        return {"success": True, "data": data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成支付订单失败: {str(e)}")

@router.post("/mock-pay")
def mock_pay_success(req: MockPayRequest):
    """开发测试环境模拟支付成功直接结算发放额度"""
    success = mark_order_paid(req.order_id, wx_order_id="MOCK_WX_PAY_123456")
    if not success:
        raise HTTPException(status_code=404, detail="订单不存在或已被结算")
    return {"success": True, "message": "模拟支付成功，额度已实时到账！"}

@router.post("/notify")
async def payment_notify(request: Request):
    """微信虚拟支付发货/扣费回调通知"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    handle_payment_notify(body)
    return {"errcode": 0, "errmsg": "OK"}
