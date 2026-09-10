import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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

app = FastAPI(title=settings.PROJECT_NAME, debug=settings.DEBUG)

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
