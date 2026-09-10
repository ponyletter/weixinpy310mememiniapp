import time
import httpx
import logging
from datetime import datetime
from typing import Optional, Dict, Any
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
