import asyncio
import hashlib
import time
from contextlib import asynccontextmanager
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from app.config import settings
from app.database import init_db
from app.r2_storage import is_r2_enabled, task_public_url
from app.storage_cleanup import cleanup_stale_artifacts
from app.api.meme import router as meme_router
from app.api.wechat import router as wechat_router
from app.api.auth import router as auth_router
from app.api.payment import router as payment_router
from app.api.collection import router as collection_router
from app.api.convert import router as convert_router
from app.api.sec_check import router as sec_check_router

# 初始化数据库结构与基础种子
init_db()


async def _storage_cleanup_loop() -> None:
    """Run conservative cleanup without blocking request handling."""
    while True:
        try:
            result = await asyncio.to_thread(cleanup_stale_artifacts)
            if any(result.values()):
                print(f"[storage-cleanup] {result}")
        except asyncio.CancelledError:
            raise
        except Exception:
            print("[storage-cleanup] cleanup pass failed", flush=True)
        await asyncio.sleep(max(60, settings.STORAGE_CLEANUP_INTERVAL_SECONDS))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    cleanup_task = asyncio.create_task(_storage_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
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
    if response.status_code == 200 and request.url.path.startswith(("/outputs/", "/samples/", "/static/")):
        response.headers["Cache-Control"] = "public, max-age=604800, immutable"
    return response

# 挂载 API
app.include_router(meme_router)
app.include_router(wechat_router)
app.include_router(auth_router)
app.include_router(payment_router)
app.include_router(collection_router)
app.include_router(convert_router)
app.include_router(sec_check_router)

# 静态文件映射
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")
app.mount("/samples", StaticFiles(directory=str(settings.SAMPLES_DIR)), name="samples")


@app.get("/outputs/{file_path:path}")
async def serve_outputs(file_path: str):
    """兼顾新旧小程序：优先返回本地文件；若本地已清理或缺失且开启 R2，则 302 重定向到 R2。"""
    try:
        resolved_base = settings.OUTPUT_DIR.resolve()
        local_path = (settings.OUTPUT_DIR / file_path).resolve()
        local_path.relative_to(resolved_base)
    except (ValueError, RuntimeError):
        raise HTTPException(status_code=403, detail="Forbidden")

    if local_path.is_file():
        return FileResponse(str(local_path))

    if is_r2_enabled():
        parts = file_path.strip("/").split("/", 1)
        if len(parts) == 2:
            return RedirectResponse(url=task_public_url(parts[0], parts[1]), status_code=302)
        return RedirectResponse(
            url=f"{settings.R2_PUBLIC_BASE_URL.rstrip('/')}/{file_path.strip('/')}",
            status_code=302
        )

    raise HTTPException(status_code=404, detail="文件不存在")


@app.get("/https:/{rest:path}")
@app.get("/http:/{rest:path}")
async def redirect_malformed_http(rest: str):
    """兜底修复旧版小程序可能因粗暴拼接产生的 https://domain/https://r2... 异常路径。"""
    target = f"https://{rest.lstrip('/')}"
    return RedirectResponse(url=target, status_code=302)

@app.get("/")
def read_root():
    index_path = settings.STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}

@app.get("/health")
def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}
