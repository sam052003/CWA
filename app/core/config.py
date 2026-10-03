"""Application configuration module using pydantic-settings."""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_NAME: str = "CWA Taiwan Weather Forecast"
    ENVIRONMENT: str = "development"
    PORT: int = 8000
    CWA_API_KEY: Optional[str] = None
    DATABASE_URL: Optional[str] = None

    @property
    def app_name(self) -> str:
        return self.APP_NAME

    @property
    def environment(self) -> str:
        return self.ENVIRONMENT

    @property
    def port(self) -> int:
        return self.PORT

    @property
    def cwa_api_key(self) -> Optional[str]:
        return self.CWA_API_KEY

    @property
    def database_url(self) -> Optional[str]:
        return self.DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of application settings."""
    return Settings()
