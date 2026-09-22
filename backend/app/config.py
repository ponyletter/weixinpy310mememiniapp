from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BASE_DIR.parent


class Settings(BaseSettings):
    """Settings whose secrets come only from the environment or an ignored .env file."""

    model_config = SettingsConfigDict(
        env_file=(str(REPO_DIR / ".env"), str(BASE_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "GIF表情包制作神器 Web H5 API"
    API_REVISION: str = "review-compliance-20260922-v4"
    HOST: str = "0.0.0.0"
    PORT: int = 8290
    DEBUG: bool = False
    # Fail closed: a fresh deployment starts as a local image-processing tool.
    # AI capabilities may only be enabled in a separately reviewed release.
    AUDIT_MODE: bool = True

    STORAGE_DIR: Path = BASE_DIR / "storage"
    UPLOAD_DIR: Path = BASE_DIR / "storage" / "uploads"
    OUTPUT_DIR: Path = BASE_DIR / "storage" / "outputs"
    SAMPLES_DIR: Path = BASE_DIR / "storage" / "samples"
    STATIC_DIR: Path = BASE_DIR / "static"
    DATABASE_PATH: Path = BASE_DIR / "meme_miniapp.db"

    PUBLIC_BASE_URL: str = "https://meme.tg-cc755.cn"
    PUBLIC_DOMAIN: str = "meme.tg-cc755.cn"
    ALLOWED_ORIGINS: str = "https://meme.tg-cc755.cn"

    JWT_SECRET: str = ""
    AUTH_TOKEN_TTL_SECONDS: int = 7 * 24 * 60 * 60

    MAX_IMAGE_UPLOAD_MB: int = 25
    MAX_VIDEO_UPLOAD_MB: int = 100
    MAX_IMAGE_PIXELS: int = 25_000_000
    MAX_GIF_FRAMES: int = 120
    MAX_IMAGES_PER_GIF: int = 9
    # 个人微信自定义 GIF 的常用提醒线；超过后仍保留并返回成品，前端提示用户。
    WECHAT_GIF_MAX_BYTES: int = 1024 * 1024
    # 仅清理明确的临时/失败产物；成功结果不会按时间删除。
    TEMP_ARTIFACT_TTL_SECONDS: int = 2 * 60 * 60
    STORAGE_CLEANUP_INTERVAL_SECONDS: int = 15 * 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_GENERAL: int = 120
    RATE_LIMIT_EXPENSIVE: int = 10

    WX_APPID: str = ""
    WX_APPSECRET: str = ""
    WX_MSG_PUSH_URL: str = "https://meme.tg-cc755.cn/api/wechat/msg_push"

    XPAY_OFFER_ID: str = ""
    XPAY_APP_KEY_SANDBOX: str = ""
    XPAY_APP_KEY_LIVE: str = ""
    XPAY_APP_KEY: str = ""
    XPAY_ENV: int = 1
    WX_MCH_ID: str = ""
    ENABLE_MOCK_PAYMENT: bool = False
    # Internal callback guard injected by the reverse proxy.
    XPAY_CALLBACK_TOKEN: str = ""
    # Event name sent by the virtual-payment delivery notification.
    XPAY_CALLBACK_EVENT: str = "xpay_goods_deliver_notify"

    WX_KEFU_ADMIN: str = ""
    WX_MSG_TOKEN: str = ""
    WX_MSG_AES_KEY: str = ""
    WX_SUBSCRIBE_TEMPLATE_ID: str = ""

    CPA_API_BASE: str = "http://127.0.0.1:8317/v1"
    CPA_API_KEY: str = ""
    CPA_IMAGE_MODEL: str = "gpt-image-2"
    FFMPEG_BIN: str = "ffmpeg"

    OUTPUT_SYNC_LOCAL_DIR: str = ""
    OUTPUT_SYNC_HOST: str = ""
    OUTPUT_SYNC_DIR: str = "/var/www/outputs"

    # Cloudflare R2 is used by the backend only. Never put these values in the
    # mini program bundle or commit them to Git.
    R2_ENABLED: bool = False
    R2_ENDPOINT_URL: str = ""
    R2_REGION: str = "auto"
    R2_BUCKET: str = "memo"
    R2_PUBLIC_BASE_URL: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_TASK_PREFIX: str = "tasks"
    R2_AVATAR_PREFIX: str = "avatars"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_security_settings(self):
        if self.XPAY_ENV not in (0, 1):
            raise ValueError("XPAY_ENV must be 0 (production) or 1 (sandbox)")
        if len(self.JWT_SECRET) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters")
        placeholder_prefixes = ("replace_", "wx_your_")
        if not self.DEBUG:
            required = {
                "JWT_SECRET": self.JWT_SECRET,
                "WX_APPID": self.WX_APPID,
                "WX_APPSECRET": self.WX_APPSECRET,
                "CPA_API_KEY": self.CPA_API_KEY,
            }
            if self.XPAY_ENV == 0:
                required.update({
                    "XPAY_OFFER_ID": self.XPAY_OFFER_ID,
                    "XPAY_APP_KEY_LIVE": self.XPAY_APP_KEY_LIVE,
                    "XPAY_CALLBACK_TOKEN": self.XPAY_CALLBACK_TOKEN,
                })
            missing = [
                name
                for name, value in required.items()
                if not value or value.lower().startswith(placeholder_prefixes)
            ]
            if missing:
                raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        if self.R2_ENABLED:
            r2_required = {
                "R2_ENDPOINT_URL": self.R2_ENDPOINT_URL,
                "R2_BUCKET": self.R2_BUCKET,
                "R2_PUBLIC_BASE_URL": self.R2_PUBLIC_BASE_URL,
                "R2_ACCESS_KEY_ID": self.R2_ACCESS_KEY_ID,
                "R2_SECRET_ACCESS_KEY": self.R2_SECRET_ACCESS_KEY,
            }
            r2_missing = [
                name for name, value in r2_required.items()
                if not value or value.lower().startswith(placeholder_prefixes)
            ]
            if r2_missing:
                raise ValueError(f"R2_ENABLED=true but missing environment variables: {', '.join(r2_missing)}")
        return self


settings = Settings()

for directory in (settings.STORAGE_DIR, settings.UPLOAD_DIR, settings.OUTPUT_DIR, settings.SAMPLES_DIR):
    directory.mkdir(parents=True, exist_ok=True)
