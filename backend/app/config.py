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
    HOST: str = "0.0.0.0"
    PORT: int = 8290
    DEBUG: bool = False

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

    MAX_IMAGE_UPLOAD_MB: int = 10
    MAX_VIDEO_UPLOAD_MB: int = 30
    MAX_IMAGE_PIXELS: int = 25_000_000
    MAX_GIF_FRAMES: int = 120
    MAX_IMAGES_PER_GIF: int = 9
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_GENERAL: int = 120
    RATE_LIMIT_EXPENSIVE: int = 10

    WX_APPID: str = ""
    WX_APPSECRET: str = ""

    XPAY_OFFER_ID: str = ""
    XPAY_APP_KEY_SANDBOX: str = ""
    XPAY_APP_KEY_LIVE: str = ""
    XPAY_APP_KEY: str = ""
    XPAY_ENV: int = 1
    WX_MCH_ID: str = ""
    ENABLE_MOCK_PAYMENT: bool = False
    # Configure the callback gateway to send this value in X-XPay-Callback-Token.
    XPAY_CALLBACK_TOKEN: str = ""

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

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_security_settings(self):
        if self.XPAY_ENV not in (0, 1):
            raise ValueError("XPAY_ENV must be 0 (production) or 1 (sandbox)")
        if len(self.JWT_SECRET) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters")
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
            placeholder_prefixes = ("replace_", "wx_your_")
            missing = [
                name
                for name, value in required.items()
                if not value or value.lower().startswith(placeholder_prefixes)
            ]
            if missing:
                raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        return self


settings = Settings()

for directory in (settings.STORAGE_DIR, settings.UPLOAD_DIR, settings.OUTPUT_DIR, settings.SAMPLES_DIR):
    directory.mkdir(parents=True, exist_ok=True)
