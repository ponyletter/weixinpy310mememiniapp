import hashlib
import time
from collections import defaultdict, deque

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.database import init_db
from app.api.meme import router as meme_router
from app.api.wechat import router as wechat_router
from app.api.auth import router as auth_router
from app.api.payment import router as payment_router
from app.api.collection import router as collection_router
from app.api.convert import router as convert_router

# 初始化数据库结构与基础种子
init_db()

app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

_request_windows: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def rate_limit_requests(request, call_next):
    """Small per-process safety net; the reverse proxy should enforce a global limit too."""
    path = request.url.path
    expensive = path.startswith(("/api/generate", "/api/process-sprite", "/api/convert/"))
    limit = settings.RATE_LIMIT_EXPENSIVE if expensive else settings.RATE_LIMIT_GENERAL
    identity = request.headers.get("authorization") or (request.client.host if request.client else "unknown")
    identity_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    key = f"{identity_hash}:{'expensive' if expensive else 'general'}"
    now = time.monotonic()
    window = _request_windows[key]
    cutoff = now - settings.RATE_LIMIT_WINDOW_SECONDS
    while window and window[0] < cutoff:
        window.popleft()
    if len(window) >= limit:
        return JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后再试"})
    window.append(now)
    if len(_request_windows) > 10_000:
        stale = [entry for entry, values in _request_windows.items() if not values or values[-1] < cutoff]
        for entry in stale:
            _request_windows.pop(entry, None)
    return await call_next(request)

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态资源强缓存中间件：为生成的动图和缩略图添加 Cache-Control，避免微信客户端重复加载
@app.middleware("http")
async def add_cache_control_header(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/outputs/", "/samples/", "/static/")):
        response.headers["Cache-Control"] = "public, max-age=604800, immutable"
    return response

# 挂载 API
app.include_router(meme_router)
app.include_router(wechat_router)
app.include_router(auth_router)
app.include_router(payment_router)
app.include_router(collection_router)
app.include_router(convert_router)

# 静态文件映射
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")
app.mount("/outputs", StaticFiles(directory=str(settings.OUTPUT_DIR)), name="outputs")
app.mount("/samples", StaticFiles(directory=str(settings.SAMPLES_DIR)), name="samples")

@app.get("/")
def read_root():
    index_path = settings.STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}

@app.get("/health")
def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}
