import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "FitDesi"
    app_env: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    secret_key: str = "change-me-to-a-long-random-string"
    access_token_minutes: int = 30
    refresh_token_days: int = 14
    database_url: str = "sqlite:///./fitdesi.db"
    cors_origins: str = "*"

    admin_email: str = ""
    admin_password: str = ""
    seed_demo: bool = False
    demo_email: str = "demo@fitdesi.local"
    demo_password: str = "change-me-demo"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@fitdesi.local"

    ai_provider: str = "groq"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_chat_model: str = "gpt-4o-mini"
    openai_vision_model: str = "gpt-4o-mini"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_chat_model: str = "openai/gpt-oss-20b"
    groq_vision_model: str = ""

    usda_api_key: str = ""
    payment_provider: str = "none"
    payment_api_key: str = ""
    payment_webhook_secret: str = ""

    storage_backend: str = "local"
    storage_local_dir: str = "storage"
    s3_bucket: str = ""
    s3_region: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_endpoint_url: str = ""
    public_base_url: str = "http://127.0.0.1:8000"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def storage_path(self) -> Path:
        if os.environ.get("VERCEL"):
            path = Path("/tmp/fitdesi-storage")
        else:
            path = Path(self.storage_local_dir)
            if not path.is_absolute():
                path = BACKEND_ROOT / path
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
