import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    app_name: str = Field(default="SSRI API")
    debug: bool = Field(default=False)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    log_level: str = Field(default="INFO")
    cors_origins: list[str] = Field(default=["http://localhost:3000"])

    @classmethod
    def from_env(cls) -> "Settings":
        origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000")
        return cls(
            app_name=os.getenv("APP_NAME", "SSRI API"),
            debug=os.getenv("DEBUG", "false").lower() in ("true", "1", "yes"),
            host=os.getenv("API_HOST", "0.0.0.0"),
            port=int(os.getenv("API_PORT", "8000")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            cors_origins=[
                origin.strip()
                for origin in origins_raw.split(",")
                if origin.strip()
            ],
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings.from_env()
