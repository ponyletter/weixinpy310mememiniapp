import uuid
import httpx
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field
from typing import Optional
from app.config import settings
from app.security import CurrentOpenid, create_access_token, require_same_user
from app.upload_utils import open_validated_image, read_limited_upload, safe_image_extension
from app.database import (
    get_db,
    get_or_create_user,
    get_user,
    update_user_profile,
    user_daily_checkin,
    redeem_coupon,
    get_user_orders
)

router = APIRouter(prefix="/api/user", tags=["user_and_auth"])

class LoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)
    inviter_code: Optional[str] = Field(default="", max_length=32)

class UpdateProfileRequest(BaseModel):
    openid: str
    nickname: Optional[str] = Field(default="", max_length=40)
    avatar_url: Optional[str] = Field(default="", max_length=500)
    bio: Optional[str] = Field(default="", max_length=160)
    gender: Optional[str] = Field(default="保密", max_length=8)
    birthday: Optional[str] = Field(default="", max_length=10)

class RedeemRequest(BaseModel):
    openid: str
    code: str = Field(min_length=1, max_length=64)

@router.post("/login")
async def wechat_login(req: LoginRequest):
    """微信小程序登录 (code2session) 或开发模拟登录"""
    code = req.code.strip()
    inviter_code = req.inviter_code.strip() if req.inviter_code else ""

    # 开发环境/测试支持 Mock 快速登录
    if settings.DEBUG and (code.startswith("mock_") or code.startswith("test_")):
        mock_openid = f"user_{code}"
        mock_session_key = "mock_session_key_secret"
        user = get_or_create_user(mock_openid, mock_session_key, inviter_code)
        safe_user = dict(user)
        safe_user.pop("session_key", None)
        return {
            "success": True,
            "openid": mock_openid,
            "user": safe_user,
            "access_token": create_access_token(mock_openid),
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
    safe_user = dict(user)
    safe_user.pop("session_key", None)
    return {
        "success": True,
        "openid": openid,
        "user": safe_user,
        "access_token": create_access_token(openid),
        "is_mock": False
    }

@router.get("/profile")
def get_profile(current_openid: CurrentOpenid, openid: str = Query("")):
    """获取用户个人资料与剩余额度"""
    clean_openid = require_same_user(openid, current_openid)
    user = get_user(clean_openid)
    if not user:
        # 用户可能刚刷新页面或未完成登录创建，自动创建兜底
        user = get_or_create_user(clean_openid)
    user_copy = dict(user)
    user_copy.pop("session_key", None)
    total_quota = user_copy.get("free_quota", 0) + user_copy.get("purchased_quota", 0)
    user_copy["total_quota"] = total_quota

    # 统计用户当前作品相册中实际存在的动图数量，删除后实时更新
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM meme_tasks WHERE openid = ? AND status = 'completed'", (clean_openid,))
        w_row = cursor.fetchone()
        works_cnt = w_row[0] if w_row else 0
    user_copy["works_count"] = works_cnt
    user_copy["total_generated"] = works_cnt
    return {"success": True, "user": user_copy}

@router.post("/update-profile")
def update_profile(req: UpdateProfileRequest, current_openid: CurrentOpenid):
    """更新用户昵称、头像、个性签名、性别与生日"""
    openid = require_same_user(req.openid, current_openid)
    success = update_user_profile(
        openid,
        req.nickname or "", 
        req.avatar_url or "", 
        req.bio or "", 
        req.gender or "保密", 
        req.birthday or ""
    )
    user = get_user(openid)
    user_copy = dict(user) if user else {}
    user_copy.pop("session_key", None)
    return {"success": success, "user": user_copy}

@router.post("/upload-avatar")
async def upload_avatar(current_openid: CurrentOpenid, file: UploadFile = File(...)):
    """上传自定义用户头像"""
    data = await read_limited_upload(file, settings.MAX_IMAGE_UPLOAD_MB)
    image = open_validated_image(data, allow_animation=False)
    ext = safe_image_extension(image)
    avatar_dir = settings.STATIC_DIR / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    target_path = avatar_dir / filename
    image.convert("RGB" if ext == ".jpg" else "RGBA").save(target_path)
    url = f"/static/avatars/{filename}"
    return {"success": True, "avatar_url": url}

@router.post("/checkin")
def daily_checkin(current_openid: CurrentOpenid):
    """每日签到领取 3 次生成额度"""
    result = user_daily_checkin(current_openid)
    return result

@router.post("/redeem")
def redeem(req: RedeemRequest, current_openid: CurrentOpenid):
    """兑换码兑换额度"""
    openid = require_same_user(req.openid, current_openid)
    result = redeem_coupon(openid, req.code)
    return result

@router.get("/orders")
def list_orders(current_openid: CurrentOpenid, openid: str = Query("")):
    """获取用户充值订单记录"""
    orders = get_user_orders(require_same_user(openid, current_openid))
    return {"success": True, "orders": orders}
