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
    DATABASE_PATH: Path = BASE_DIR / "meme_miniapp.db"
    JWT_SECRET: str = "meme-secret-key-2026-jwt"

    # 域名与外部基础 URL（如果配置了反代或直接访问）
    PUBLIC_BASE_URL: str = "http://204.44.67.184:8290"
    PUBLIC_DOMAIN: str = "meme.tg-cc755.cn"

    # 微信小程序凭据
    WX_APPID: str = "wx86e299efa495d1f6"
    WX_APPSECRET: str = "967e928c228889894f883d40acc097db"

    # 微信虚拟支付 2.0 (XPay)
    XPAY_OFFER_ID: str = "1450644655"
    XPAY_APP_KEY_SANDBOX: str = "5DvEfstYuA9rzsjkG33qfnhS49aQxltO"
    XPAY_APP_KEY_LIVE: str = "IWQenoFtS11w1qMGdtWcbB08qLsBHvRI"
    XPAY_APP_KEY: str = "IWQenoFtS11w1qMGdtWcbB08qLsBHvRI"
    XPAY_ENV: int = 0  # 0: 现网正式环境, 1: 沙箱测试环境
    WX_MCH_ID: str = "1750438891"

    # 客服微信号
    WX_KEFU_ADMIN: str = "abc1202abc"

    # 微信消息推送配置
    WX_MSG_TOKEN: str = "memeTokenSecret2026"
    WX_MSG_AES_KEY: str = "PobB5dp4ypgFOSz0IYlLSLWwgoJjTt3K5U3MBPFbtZx"
    WX_SUBSCRIBE_TEMPLATE_ID: str = "jsfKx2x1YrKdX600S01pzCcxWe_UjMi_Tx5OtWWfvcs"

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
