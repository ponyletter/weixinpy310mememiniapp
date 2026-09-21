import asyncio
import io

from PIL import Image

from app.core.wechat_service import WeChatService


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, "PNG")
    return buffer.getvalue()


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeClient:
    payload = {"errcode": 0, "errmsg": "ok"}
    post_calls = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def post(self, *_args, **_kwargs):
        type(self).post_calls += 1
        return _FakeResponse(type(self).payload)


def _check_image(monkeypatch, payload):
    async def token(_cls):
        return "test-token"

    _FakeClient.payload = payload
    _FakeClient.post_calls = 0
    WeChatService._image_check_cache.clear()
    monkeypatch.setattr(WeChatService, "get_access_token", classmethod(token))
    monkeypatch.setattr("app.core.wechat_service.httpx.AsyncClient", _FakeClient)
    return asyncio.run(WeChatService.check_image_security(_png_bytes()))


def test_image_security_blocks_explicit_violation(monkeypatch):
    result = _check_image(monkeypatch, {"errcode": 87014, "errmsg": "risky content"})
    assert result == (False, "所发布内容包含违规信息，请修改后重试")


def test_image_security_does_not_mislabel_api_error_as_violation(monkeypatch):
    result = _check_image(monkeypatch, {"errcode": 45009, "errmsg": "reach max api daily quota limit"})
    assert result == (True, "")


def test_image_security_reuses_recent_verdict(monkeypatch):
    async def token(_cls):
        return "test-token"

    _FakeClient.payload = {"errcode": 0, "errmsg": "ok"}
    _FakeClient.post_calls = 0
    WeChatService._image_check_cache.clear()
    monkeypatch.setattr(WeChatService, "get_access_token", classmethod(token))
    monkeypatch.setattr("app.core.wechat_service.httpx.AsyncClient", _FakeClient)
    image = _png_bytes()
    assert asyncio.run(WeChatService.check_image_security(image)) == (True, "")
    assert asyncio.run(WeChatService.check_image_security(image)) == (True, "")
    assert _FakeClient.post_calls == 1
