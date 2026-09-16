import io
import time
import httpx
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from PIL import Image
from app.config import settings

logger = logging.getLogger(__name__)

class WeChatService:
    _access_token: Optional[str] = None
    _token_expires_at: float = 0

    @classmethod
    async def get_access_token(cls) -> Optional[str]:
        """获取微信小程序接口全局 Access Token (带内存缓存与自动续期)"""
        now = time.time()
        if cls._access_token and now < cls._token_expires_at:
            return cls._access_token

        url = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": settings.WX_APPID,
            "secret": settings.WX_APPSECRET
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
                data = resp.json()
                if "access_token" in data:
                    cls._access_token = data["access_token"]
                    # 微信 Token 有效期 7200 秒，提前 300 秒刷新
                    expires_in = data.get("expires_in", 7200)
                    cls._token_expires_at = now + expires_in - 300
                    logger.info(f"成功获取微信 Access Token，有效期 {expires_in} 秒")
                    return cls._access_token
                else:
                    logger.error(f"获取微信 Access Token 失败: {data}")
                    return None
        except Exception as e:
            logger.error(f"请求微信 Access Token 异常: {e}")
            return None

    @classmethod
    async def send_subscribe_message(
        cls,
        openid: str,
        template_id: Optional[str] = None,
        order_no: Optional[str] = None,
        service_type: str = "动图表情包制作",
        finish_time: Optional[str] = None,
        service_item: str = "定制GIF表情",
        page: str = "pages/index/index",
        miniprogram_state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送微信小程序订阅消息（服务完成通知）
        模板 ID: jsfKx2x1YrKdX600S01pzCcxWe_UjMi_Tx5OtWWfvcs
        关键词字段说明：
          - character_string1: 订单编号 (<=32位，数字字母)
          - thing2: 服务类型 (<=20字)
          - time3: 完成时间 (标准时间格式)
          - thing5: 服务项目 (<=20字)
        """
        if not openid or openid.startswith("user_mock_") or openid.startswith("mock_"):
            return {"success": False, "errcode": -1, "errmsg": "Mock用户无需发送微信服务通知"}

        target_template_id = template_id or getattr(settings, "WX_SUBSCRIBE_TEMPLATE_ID", "jsfKx2x1YrKdX600S01pzCcxWe_UjMi_Tx5OtWWfvcs")
        
        token = await cls.get_access_token()
        if not token:
            return {"success": False, "errcode": -2, "errmsg": "无法获取有效的微信 Access Token"}

        now_str = finish_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe_order_no = (order_no or f"M{int(time.time()*1000) % 1000000000}")[:32]
        safe_service_type = (service_type or "动图表情包制作")[:20]
        safe_service_item = (service_item or "定制GIF动图")[:20]

        # 默认开发环境传 developer，线上正式传 formal
        env_state = miniprogram_state or ("developer" if settings.DEBUG else "formal")

        url = f"https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={token}"
        payload = {
            "touser": openid,
            "template_id": target_template_id,
            "page": page,
            "miniprogram_state": env_state,
            "lang": "zh_CN",
            "data": {
                "character_string1": {
                    "value": safe_order_no
                },
                "thing2": {
                    "value": safe_service_type
                },
                "time3": {
                    "value": now_str
                },
                "thing5": {
                    "value": safe_service_item
                }
            }
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                result = resp.json()
                logger.info(f"微信订阅消息发送结果: {result}")
                
                # errcode: 0 成功, 43101 用户拒绝/未订阅
                if result.get("errcode") == 0:
                    return {"success": True, "errcode": 0, "errmsg": "ok", "data": result}
                else:
                    return {
                        "success": False,
                        "errcode": result.get("errcode"),
                        "errmsg": result.get("errmsg"),
                        "data": result
                    }
        except Exception as e:
            logger.error(f"发送订阅消息异常: {e}")
            return {"success": False, "errcode": -3, "errmsg": str(e)}

    @classmethod
    async def check_text_security(cls, text: str, openid: Optional[str] = None) -> Tuple[bool, str]:
        """
        调用微信小程序内容安全接口 security.msgSecCheck 检测文本是否合规
        返回: (is_safe: bool, tip_message: str)
        """
        if not text or not text.strip():
            return True, ""

        token = await cls.get_access_token()
        if not token:
            return True, ""

        url = f"https://api.weixin.qq.com/wxa/msg_sec_check?access_token={token}"
        clean_text = text.strip()

        payload: Dict[str, Any] = {"content": clean_text}
        if openid and not openid.startswith("mock_") and not openid.startswith("user_mock_"):
            payload = {
                "openid": openid,
                "scene": 1,
                "version": 2,
                "content": clean_text
            }

        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.post(url, json=payload)
                data = resp.json()
                logger.info(f"微信文本安全检测结果: text='{clean_text[:20]}' res={data}")

                errcode = data.get("errcode", 0)
                if errcode == 87014:
                    return False, "所发布内容包含违规信息，请修改后重试"

                result = data.get("result", {})
                if result.get("suggest") in ("risky", "review"):
                    return False, "所发布内容包含违规信息，请修改后重试"
                if result.get("label") not in (None, 100):
                    return False, "所发布内容包含违规信息，请修改后重试"

                # 若报 openid 不匹配等错误，降级回退 v1 简单接口再次校验
                if errcode == 40003:
                    fb_resp = await client.post(url, json={"content": clean_text})
                    fb_data = fb_resp.json()
                    if fb_data.get("errcode") == 87014:
                        return False, "所发布内容包含违规信息，请修改后重试"

                return True, ""
        except Exception as e:
            logger.error(f"微信文本安全检测异常: {e}")
            return True, ""

    @classmethod
    async def check_image_security(cls, image_bytes: bytes) -> Tuple[bool, str]:
        """
        调用微信官方接口 security.imgSecCheck 同步校验图片安全
        若图片过大或分辨率过高，先在内存中压缩至 600x600 JPEG 再送检
        返回: (is_safe: bool, tip_message: str)
        """
        if not image_bytes:
            return True, ""

        token = await cls.get_access_token()
        if not token:
            return True, ""

        try:
            im = Image.open(io.BytesIO(image_bytes))
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.thumbnail((600, 600))
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=85)
            check_bytes = buf.getvalue()

            url = f"https://api.weixin.qq.com/wxa/img_sec_check?access_token={token}"
            async with httpx.AsyncClient(timeout=8.0) as client:
                files = {"media": ("check.jpg", check_bytes, "image/jpeg")}
                resp = await client.post(url, files=files)
                data = resp.json()
                logger.info(f"微信图片安全检测结果: res={data}")

                errcode = data.get("errcode", 0)
                if errcode == 87014:
                    return False, "上传图片包含违规信息，请更换后重试"

                return True, ""
        except Exception as e:
            logger.error(f"微信图片安全检测异常: {e}")
            return True, ""
