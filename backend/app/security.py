import base64
import hashlib
import hmac
import json
import time
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings


bearer_scheme = HTTPBearer(auto_error=False)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(openid: str) -> str:
    now = int(time.time())
    payload = {"sub": openid, "iat": now, "exp": now + settings.AUTH_TOKEN_TTL_SECONDS}
    encoded = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(settings.JWT_SECRET.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_b64encode(signature)}"


def verify_access_token(token: str) -> str:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected = hmac.new(settings.JWT_SECRET.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(supplied_signature)):
            raise ValueError("bad signature")
        payload = json.loads(_b64decode(encoded))
        if not payload.get("sub") or int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("expired token")
        return str(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="登录状态无效或已过期，请重新登录") from exc


def get_current_openid(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="请先登录")
    return verify_access_token(credentials.credentials)


CurrentOpenid = Annotated[str, Depends(get_current_openid)]


def require_same_user(requested_openid: str | None, current_openid: str) -> str:
    if requested_openid and requested_openid.strip() != current_openid:
        raise HTTPException(status_code=403, detail="无权访问其他用户的数据")
    return current_openid
