"""Tests for Phase 6 Vercel production deployment preparation.

Covers:
- Protected cron endpoint GET /api/cron/refresh authentication and errors
- Production environment lock for POST /api/refresh
- Config CRON_SECRET handling
- Pinned Chart.js CDN dependency in templates
- AbortController request race condition protection in frontend JS
- Zero-config vercel.json structure and cron schedule
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.database import get_db
from app.main import app
from app.services.weather_service import WeatherDatabaseError, WeatherRefreshError

client = TestClient(app)

TEST_SECRET = "super_secure_test_cron_secret_12345"


# ---------------------------------------------------------------------------
# Protected Cron Refresh Endpoint Tests
# ---------------------------------------------------------------------------

def test_cron_refresh_missing_authorization():
    """Verify GET /api/cron/refresh returns 401 when Authorization header is missing."""
    with patch("app.api.routes.get_settings") as mock_settings:
        mock_settings.return_value.CRON_SECRET = TEST_SECRET
        response = client.get("/api/cron/refresh")
        assert response.status_code == 401
        assert response.json()["detail"] == "Unauthorized"


def test_cron_refresh_invalid_bearer_token():
    """Verify GET /api/cron/refresh returns 401 when token does not match CRON_SECRET."""
    with patch("app.api.routes.get_settings") as mock_settings:
        mock_settings.return_value.CRON_SECRET = TEST_SECRET
        response = client.get(
            "/api/cron/refresh",
            headers={"Authorization": "Bearer wrong_invalid_secret"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Unauthorized"


def test_cron_refresh_non_bearer_authorization():
    """Verify GET /api/cron/refresh returns 401 when Authorization scheme is not Bearer."""
    with patch("app.api.routes.get_settings") as mock_settings:
        mock_settings.return_value.CRON_SECRET = TEST_SECRET
        response = client.get(
            "/api/cron/refresh",
            headers={"Authorization": f"Basic {TEST_SECRET}"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Unauthorized"


def test_cron_refresh_fails_closed_when_secret_unset():
    """Verify GET /api/cron/refresh fails closed (401) when CRON_SECRET is not configured."""
    with patch("app.api.routes.get_settings") as mock_settings:
        mock_settings.return_value.CRON_SECRET = None
        response = client.get(
            "/api/cron/refresh",
            headers={"Authorization": f"Bearer {TEST_SECRET}"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Unauthorized"


def test_cron_refresh_success():
    """Verify GET /api/cron/refresh returns 200 and calls refresh_forecasts with valid token."""
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    mock_summary = {
        "status": "success",
        "dataset_id": "F-C0032-005",
        "records_count": 330,
        "regions_count": 22,
        "updated_at": "2026-10-04T08:00:00+08:00",
    }

    try:
        with patch("app.api.routes.get_settings") as mock_settings, \
             patch("app.api.routes.weather_service.refresh_forecasts", return_value=mock_summary) as mock_refresh:

            mock_settings.return_value.CRON_SECRET = TEST_SECRET
            response = client.get(
                "/api/cron/refresh",
                headers={"Authorization": f"Bearer {TEST_SECRET}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["dataset_id"] == "F-C0032-005"
            assert data["records_count"] == 330
            assert data["regions_count"] == 22
            assert mock_refresh.call_count == 1
    finally:
        app.dependency_overrides.clear()


def test_cron_refresh_cwa_failure():
    """Verify GET /api/cron/refresh returns 502 when CWA fetch fails."""
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        with patch("app.api.routes.get_settings") as mock_settings, \
             patch("app.api.routes.weather_service.refresh_forecasts", side_effect=WeatherRefreshError("CWA Timeout")):

            mock_settings.return_value.CRON_SECRET = TEST_SECRET
            response = client.get(
                "/api/cron/refresh",
                headers={"Authorization": f"Bearer {TEST_SECRET}"},
            )

            assert response.status_code == 502
            assert "Failed to fetch data from Central Weather Administration API" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_cron_refresh_database_failure():
    """Verify GET /api/cron/refresh returns 503 when DB UPSERT fails."""
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        with patch("app.api.routes.get_settings") as mock_settings, \
             patch("app.api.routes.weather_service.refresh_forecasts", side_effect=WeatherDatabaseError("DB Pool Exhausted")):

            mock_settings.return_value.CRON_SECRET = TEST_SECRET
            response = client.get(
                "/api/cron/refresh",
                headers={"Authorization": f"Bearer {TEST_SECRET}"},
            )

            assert response.status_code == 503
            assert "Database service unavailable during refresh" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_cron_refresh_does_not_leak_secret():
    """Verify neither success nor error responses contain the CRON_SECRET."""
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        with patch("app.api.routes.get_settings") as mock_settings, \
             patch("app.api.routes.weather_service.refresh_forecasts", side_effect=Exception(f"Boom {TEST_SECRET}")):

            mock_settings.return_value.CRON_SECRET = TEST_SECRET

            # Test 401 missing auth
            r1 = client.get("/api/cron/refresh")
            assert TEST_SECRET not in r1.text

            # Test 500 error
            r2 = client.get("/api/cron/refresh", headers={"Authorization": f"Bearer {TEST_SECRET}"})
            assert r2.status_code == 500
            assert TEST_SECRET not in r2.text
    finally:
        app.dependency_overrides.clear()


def test_production_post_refresh_remains_forbidden():
    """Verify POST /api/refresh remains forbidden (403) in production environment."""
    with patch("app.api.routes.get_settings") as mock_settings:
        mock_settings.return_value.ENVIRONMENT = "production"
        response = client.post("/api/refresh")
        assert response.status_code == 403
        assert "disabled in production" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Config CRON_SECRET Tests
# ---------------------------------------------------------------------------

def test_config_cron_secret_default_none():
    """Verify Settings default value for CRON_SECRET is None."""
    settings = Settings(
        APP_NAME="Test",
        ENVIRONMENT="test",
        CWA_API_KEY="test_key",
        DATABASE_URL="postgresql+psycopg://test:pass@host:6543/db",
    )
    assert settings.CRON_SECRET is None
    assert settings.cron_secret is None


def test_config_cron_secret_from_env(monkeypatch):
    """Verify Settings loads CRON_SECRET when set in environment."""
    monkeypatch.setenv("CRON_SECRET", "custom_secret_abc")
    settings = Settings(
        APP_NAME="Test",
        ENVIRONMENT="test",
        CWA_API_KEY="test_key",
        DATABASE_URL="postgresql+psycopg://test:pass@host:6543/db",
    )
    assert settings.CRON_SECRET == "custom_secret_abc"
    assert settings.cron_secret == "custom_secret_abc"


# ---------------------------------------------------------------------------
# Frontend Pinned Dependencies & Hardening Tests
# ---------------------------------------------------------------------------

def test_chartjs_pinned_version_in_html():
    """Verify index.html imports pinned Chart.js version 4.5.1 instead of unpinned latest."""
    response = client.get("/")
    assert response.status_code == 200
    assert "https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js" in response.text
    assert 'src="https://cdn.jsdelivr.net/npm/chart.js"' not in response.text


def test_app_js_has_abort_controller_protection():
    """Verify app.js implements AbortController cancellation for rapid region switching."""
    response = client.get("/static/js/app.js")
    assert response.status_code == 200
    js = response.text
    assert "AbortController" in js
    assert "forecastAbortController" in js
    assert "forecastAbortController.abort()" in js
    assert "err.name === \"AbortError\"" in js or "err.name === 'AbortError'" in js


# ---------------------------------------------------------------------------
# Vercel Configuration Tests
# ---------------------------------------------------------------------------

def test_vercel_json_zero_config_and_cron():
    """Verify vercel.json contains zero-config format without legacy catch-all rewrites."""
    vercel_path = Path(__file__).resolve().parent.parent / "vercel.json"
    assert vercel_path.exists(), "vercel.json must exist in project root"

    with open(vercel_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Legacy catch-all rewrites must be removed
    assert "rewrites" not in data, "Legacy catch-all rewrites must not be in vercel.json"
    assert "builds" not in data, "Legacy builds must not be in vercel.json"

    # Cron schedule must be present
    assert "crons" in data, "vercel.json must define crons schedule"
    crons = data["crons"]
    assert len(crons) >= 1
    assert crons[0]["path"] == "/api/cron/refresh"
    assert crons[0]["schedule"] == "0 0 * * *"
