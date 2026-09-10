import os
import shutil
import uuid
import httpx
from fastapi import APIRouter, HTTPException, Query, Body, Header, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from app.config import settings
from app.database import (
    get_or_create_user,
    get_user,
    update_user_profile,
    user_daily_checkin,
    redeem_coupon,
    get_user_orders
)

router = APIRouter(prefix="/api/user", tags=["user_and_auth"])

class LoginRequest(BaseModel):
    code: str
    inviter_code: Optional[str] = ""

class UpdateProfileRequest(BaseModel):
    openid: str
    nickname: Optional[str] = ""
    avatar_url: Optional[str] = ""
    bio: Optional[str] = ""
    gender: Optional[str] = "保密"
    birthday: Optional[str] = ""

class RedeemRequest(BaseModel):
    openid: str
    code: str

@router.post("/login")
async def wechat_login(req: LoginRequest):
    """微信小程序登录 (code2session) 或开发模拟登录"""
    code = req.code.strip()
    inviter_code = req.inviter_code.strip() if req.inviter_code else ""

    # 开发环境/测试支持 Mock 快速登录
    if code.startswith("mock_") or code.startswith("test_") or settings.DEBUG and len(code) < 10:
        mock_openid = f"user_{code}"
        mock_session_key = "mock_session_key_secret"
        user = get_or_create_user(mock_openid, mock_session_key, inviter_code)
        return {
            "success": True,
            "openid": mock_openid,
            "user": user,
            "is_mock": True
        }

    # 正式向微信服务器换取 openid 和 session_key
    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": settings.WX_APPID,
        "secret": settings.WX_APPSECRET,
        "js_code": code,
        "grant_type": "authorization_code"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"请求微信鉴权中心失败: {str(e)}")

    if "errcode" in data and data["errcode"] != 0:
        raise HTTPException(status_code=400, detail=f"微信登录失败: {data.get('errmsg', '未知错误')}")

    openid = data.get("openid")
    session_key = data.get("session_key", "")
    if not openid:
        raise HTTPException(status_code=400, detail="未获取到有效 openid")

    user = get_or_create_user(openid, session_key, inviter_code)
    return {
        "success": True,
        "openid": openid,
        "user": user,
        "is_mock": False
    }

@router.get("/profile")
def get_profile(openid: str = Query("")):
    """获取用户个人资料与剩余额度"""
    clean_openid = openid.strip() if openid else ""
    if not clean_openid:
        return {
            "success": True,
            "user": {
                "openid": "",
                "nickname": "新创作者",
                "avatar_url": "",
                "free_quota": 3,
                "purchased_quota": 0,
                "total_quota": 3,
                "is_vip": 0
            }
        }
    user = get_user(clean_openid)
    if not user:
        # 用户可能刚刷新页面或未完成登录创建，自动创建兜底
        user = get_or_create_user(clean_openid)
    user_copy = dict(user)
    user_copy.pop("session_key", None)
    total_quota = user_copy.get("free_quota", 0) + user_copy.get("purchased_quota", 0)
    user_copy["total_quota"] = total_quota
    return {"success": True, "user": user_copy}

@router.post("/update-profile")
def update_profile(req: UpdateProfileRequest):
    """更新用户昵称、头像、个性签名、性别与生日"""
    success = update_user_profile(
        req.openid, 
        req.nickname or "", 
        req.avatar_url or "", 
        req.bio or "", 
        req.gender or "保密", 
        req.birthday or ""
    )
    user = get_user(req.openid)
    user_copy = dict(user) if user else {}
    user_copy.pop("session_key", None)
    return {"success": success, "user": user_copy}

@router.post("/upload-avatar")
async def upload_avatar(file: UploadFile = File(...)):
    """上传自定义用户头像"""
    ext = os.path.splitext(file.filename or "")[1] or ".png"
    if ext.lower() not in [".png", ".jpg", ".jpeg", ".webp"]:
        ext = ".png"
    avatar_dir = settings.STATIC_DIR / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex[:12]}{ext}"
    target_path = avatar_dir / filename
    with open(target_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    url = f"/static/avatars/{filename}"
    return {"success": True, "avatar_url": url}

@router.post("/checkin")
def daily_checkin(openid: str = Body(..., embed=True)):
    """每日签到领取 3 次生成额度"""
    result = user_daily_checkin(openid)
    return result

@router.post("/redeem")
def redeem(req: RedeemRequest):
    """兑换码兑换额度"""
    result = redeem_coupon(req.openid, req.code)
    return result

@router.get("/orders")
def list_orders(openid: str = Query(...)):
    """获取用户充值订单记录"""
    orders = get_user_orders(openid)
    return {"success": True, "orders": orders}
