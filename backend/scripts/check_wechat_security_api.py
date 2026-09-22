"""以脱敏输出单独诊断微信文本/图片内容安全接口。

示例：
  python scripts/check_wechat_security_api.py --image /tmp/test.png
  python scripts/check_wechat_security_api.py --text 测试 --openid REAL_OPENID
  python scripts/check_wechat_security_api.py --media-url https://example.com/test.png --openid REAL_OPENID
"""

import argparse
import asyncio
import io
import json
import sys
from pathlib import Path

import httpx
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.wechat_service import WeChatService  # noqa: E402


def _safe_fields(data: dict) -> dict:
    return {
        key: data.get(key)
        for key in ("errcode", "errmsg", "trace_id", "result", "detail")
        if key in data
    }


async def _post_json(url: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, json=payload)
        return response.json()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path)
    parser.add_argument("--text")
    parser.add_argument("--media-url")
    parser.add_argument("--openid")
    args = parser.parse_args()

    token = await WeChatService.get_access_token()
    if not token:
        raise SystemExit("无法获取微信 access_token，请检查小程序配置")
    print(json.dumps({"token_acquired": True}, ensure_ascii=False))

    if args.image:
        source = Image.open(args.image)
        if source.mode not in ("RGB", "L"):
            source = source.convert("RGB")
        source.thumbnail((600, 600))
        buffer = io.BytesIO()
        source.save(buffer, "JPEG", quality=85)
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"https://api.weixin.qq.com/wxa/img_sec_check?access_token={token}",
                files={"media": ("check.jpg", buffer.getvalue(), "image/jpeg")},
            )
            data = response.json()
        print(json.dumps({"imgSecCheck_v1": _safe_fields(data)}, ensure_ascii=False))

    if args.text:
        if not args.openid:
            raise SystemExit("msgSecCheck 2.0 测试必须提供真实 --openid")
        data = await _post_json(
            f"https://api.weixin.qq.com/wxa/msg_sec_check?access_token={token}",
            {"content": args.text, "version": 2, "scene": 2, "openid": args.openid},
        )
        print(json.dumps({"msgSecCheck_v2": _safe_fields(data)}, ensure_ascii=False))

    if args.media_url:
        if not args.openid:
            raise SystemExit("mediaCheckAsync 2.0 测试必须提供真实 --openid")
        data = await _post_json(
            f"https://api.weixin.qq.com/wxa/media_check_async?access_token={token}",
            {
                "media_url": args.media_url,
                "media_type": 2,
                "version": 2,
                "scene": 2,
                "openid": args.openid,
            },
        )
        print(
            json.dumps({"mediaCheckAsync_v2": _safe_fields(data)}, ensure_ascii=False)
        )


if __name__ == "__main__":
    asyncio.run(main())
