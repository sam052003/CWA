"""Tests for application settings and configuration."""

from app.core.config import Settings, get_settings


def test_settings_defaults():
    """Verify default settings values when initialized."""
    settings = Settings()
    assert settings.APP_NAME == "CWA Taiwan Weather Forecast"
    assert settings.ENVIRONMENT == "development"
    assert settings.PORT == 8000
    assert settings.app_name == "CWA Taiwan Weather Forecast"
    assert settings.environment == "development"
    assert settings.port == 8000


def test_get_settings_lru_cache():
    """Verify get_settings returns the same cached instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_settings_properties():
    """Verify property accessors for database_url and cwa_api_key."""
    settings = Settings(
        CWA_API_KEY="test_key_123",
        DATABASE_URL="postgresql+psycopg://test:pass@localhost:5432/testdb",
    )
    assert settings.cwa_api_key == "test_key_123"
    assert settings.CWA_API_KEY == "test_key_123"
    assert settings.database_url == "postgresql+psycopg://test:pass@localhost:5432/testdb"
    assert settings.DATABASE_URL == "postgresql+psycopg://test:pass@localhost:5432/testdb"
