import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "GIF表情包制作神器 Web H5 API"
    HOST: str = "0.0.0.0"
    PORT: int = 8290
    DEBUG: bool = True

    # 存储目录
    STORAGE_DIR: Path = BASE_DIR / "storage"
    UPLOAD_DIR: Path = BASE_DIR / "storage" / "uploads"
    OUTPUT_DIR: Path = BASE_DIR / "storage" / "outputs"
    SAMPLES_DIR: Path = BASE_DIR / "storage" / "samples"
    STATIC_DIR: Path = BASE_DIR / "static"

    # 域名与外部基础 URL（如果配置了反代或直接访问）
    PUBLIC_BASE_URL: str = ""

    # CLIProxyAPI 反代配置 (ChatGPT Plus 出海中转)
    CPA_API_BASE: str = "http://127.0.0.1:8317/v1"
    CPA_API_KEY: str = "sk-meme-cliproxy-secret-2026"
    CPA_IMAGE_MODEL: str = "gpt-image-2"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# 确保目录存在
for d in [settings.STORAGE_DIR, settings.UPLOAD_DIR, settings.OUTPUT_DIR, settings.SAMPLES_DIR]:
    d.mkdir(parents=True, exist_ok=True)
