"""Tests for FastAPI endpoints."""

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.db.database import get_db
from app.main import app
from app.services.weather_service import (
    ForecastNotFoundError,
    RegionNotFoundError,
    WeatherDatabaseError,
    WeatherRefreshError,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Existing Health & Root Tests
# ---------------------------------------------------------------------------

def test_root_endpoint():
    """Verify root endpoint returns 200 OK and expected message."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["status"] == "online"


def test_health_check_endpoint():
    """Verify /health endpoint returns 200 OK and healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_api_health_check_endpoint():
    """Verify /api/health endpoint returns 200 OK."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


# ---------------------------------------------------------------------------
# GET /api/regions Tests
# ---------------------------------------------------------------------------

def test_get_regions_success():
    """Verify GET /api/regions returns 200 with sorted distinct regions."""
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        with patch("app.api.routes.weather_service.list_regions", return_value=["南投縣", "臺中市", "臺北市"]):
            response = client.get("/api/regions")
            assert response.status_code == 200
            data = response.json()
            assert "regions" in data
            assert data["regions"] == ["南投縣", "臺中市", "臺北市"]
    finally:
        app.dependency_overrides.clear()


def test_get_regions_database_error():
    """Verify GET /api/regions returns 503 on database service failure."""
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        with patch("app.api.routes.weather_service.list_regions", side_effect=WeatherDatabaseError("DB down")):
            response = client.get("/api/regions")
            assert response.status_code == 503
            assert response.json()["detail"] == "Database service unavailable"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/forecast Tests
# ---------------------------------------------------------------------------

def test_get_forecast_success():
    """Verify GET /api/forecast returns 200 with chronological forecasts and +08:00 datetimes."""
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    mock_data = {
        "region": "臺中市",
        "dataset_id": "F-C0032-005",
        "updated_at": "2026-10-04T00:00:00+08:00",
        "forecasts": [
            {
                "start_time": "2026-10-04T06:00:00+08:00",
                "end_time": "2026-10-04T18:00:00+08:00",
                "weather": "晴時多雲",
                "min_temp": 24.0,
                "max_temp": 30.0,
            },
            {
                "start_time": "2026-10-04T18:00:00+08:00",
                "end_time": "2026-10-05T06:00:00+08:00",
                "weather": "多雲",
                "min_temp": 23.0,
                "max_temp": 29.0,
            },
        ],
    }

    try:
        with patch("app.api.routes.weather_service.get_forecast", return_value=mock_data):
            response = client.get("/api/forecast?region=臺中市")
            assert response.status_code == 200
            data = response.json()

            # Schema verification
            assert data["region"] == "臺中市"
            assert data["dataset_id"] == "F-C0032-005"
            assert "+08:00" in data["updated_at"]
            assert len(data["forecasts"]) == 2

            # Chronological order verification
            fc1 = data["forecasts"][0]
            fc2 = data["forecasts"][1]
            assert fc1["start_time"] < fc2["start_time"]

            # Timezone awareness verification
            assert "+08:00" in fc1["start_time"]
            assert "+08:00" in fc1["end_time"]
    finally:
        app.dependency_overrides.clear()


def test_get_forecast_unknown_region():
    """Verify GET /api/forecast returns 404 for unknown region."""
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        with patch("app.api.routes.weather_service.get_forecast", side_effect=RegionNotFoundError("Region '未知市' not found")):
            response = client.get("/api/forecast?region=未知市")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_get_forecast_no_active_forecast():
    """Verify GET /api/forecast returns 404 when no active forecast is available."""
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        with patch("app.api.routes.weather_service.get_forecast", side_effect=ForecastNotFoundError("No active forecast found")):
            response = client.get("/api/forecast?region=臺中市")
            assert response.status_code == 404
            assert "No active forecast found" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_get_forecast_database_error():
    """Verify GET /api/forecast returns 503 on database failure."""
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        with patch("app.api.routes.weather_service.get_forecast", side_effect=WeatherDatabaseError("DB failure")):
            response = client.get("/api/forecast?region=臺中市")
            assert response.status_code == 503
            assert response.json()["detail"] == "Database service unavailable"
    finally:
        app.dependency_overrides.clear()


def test_get_forecast_missing_region_param():
    """Verify GET /api/forecast returns 422 or 400 when region query param is missing or empty."""
    # Missing query param
    resp1 = client.get("/api/forecast")
    assert resp1.status_code in (400, 422)

    # Empty query param
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp2 = client.get("/api/forecast?region=")
        assert resp2.status_code == 400
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/refresh Tests
# ---------------------------------------------------------------------------

def test_refresh_forecast_development_success():
    """Verify POST /api/refresh returns 200 and expected record count in development."""
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    mock_summary = {
        "status": "success",
        "dataset_id": "F-C0032-005",
        "records_count": 330,
        "regions_count": 22,
        "updated_at": "2026-10-04T00:00:00+08:00",
    }

    try:
        with patch("app.api.routes.get_settings") as mock_settings, \
             patch("app.api.routes.weather_service.refresh_forecasts", return_value=mock_summary) as mock_refresh:

            mock_settings.return_value.ENVIRONMENT = "development"
            response = client.post("/api/refresh")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["records_count"] == 330
            assert data["regions_count"] == 22
            assert "+08:00" in data["updated_at"]

            # Verify refresh_forecasts was called with session and without payload
            assert mock_refresh.called
            call_kwargs = mock_refresh.call_args[1]
            assert call_kwargs.get("payload") is None
    finally:
        app.dependency_overrides.clear()


def test_refresh_forecast_endpoint_calls_client_fetch_when_no_payload():
    """Verify that POST /api/refresh without payload invokes client.fetch_forecast_1week."""
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    mock_client = MagicMock()
    mock_client.DATASET_FORECAST_1WEEK = "F-C0032-005"
    mock_client.fetch_forecast_1week.return_value = {"cwaopendata": {}}

    mock_records = [
        {
            "dataset_id": "F-C0032-005",
            "region_name": f"Region_{i}",
            "start_time": "2026-10-04T06:00:00+08:00",
            "end_time": "2026-10-04T18:00:00+08:00",
            "weather": "晴",
            "min_temp": 20.0,
            "max_temp": 28.0,
        }
        for i in range(22)
    ]

    try:
        with patch("app.api.routes.get_settings") as mock_settings, \
             patch("app.services.weather_service.CWAClient", return_value=mock_client), \
             patch("app.services.weather_service.parse_cwa_forecast", return_value=mock_records), \
             patch("app.services.weather_service.upsert_forecasts", return_value=22), \
             patch("app.services.weather_service.create_fetch_log") as mock_create_log:

            from datetime import datetime, timezone
            mock_success_log = MagicMock()
            mock_success_log.fetched_at = datetime(2026, 10, 4, 12, 0, 0, tzinfo=timezone.utc)
            mock_create_log.return_value = mock_success_log

            mock_settings.return_value.ENVIRONMENT = "development"
            response = client.post("/api/refresh")

            assert response.status_code == 200
            assert mock_client.fetch_forecast_1week.call_count == 1
    finally:
        app.dependency_overrides.clear()


def test_refresh_forecast_production_forbidden():
    """Verify POST /api/refresh returns 403 when ENVIRONMENT is production."""
    with patch("app.api.routes.get_settings") as mock_settings:
        mock_settings.return_value.ENVIRONMENT = "production"
        response = client.post("/api/refresh")
        assert response.status_code == 403
        assert "disabled in production" in response.json()["detail"]


def test_refresh_forecast_cwa_failure():
    """Verify POST /api/refresh returns 502 when CWA API request fails."""
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        with patch("app.api.routes.get_settings") as mock_settings, \
             patch("app.api.routes.weather_service.refresh_forecasts", side_effect=WeatherRefreshError("CWA timeout")):

            mock_settings.return_value.ENVIRONMENT = "development"
            response = client.post("/api/refresh")

            assert response.status_code == 502
            assert "Failed to fetch data from Central Weather Administration API" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_refresh_forecast_database_failure():
    """Verify POST /api/refresh returns 503 when database transaction fails."""
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        with patch("app.api.routes.get_settings") as mock_settings, \
             patch("app.api.routes.weather_service.refresh_forecasts", side_effect=WeatherDatabaseError("DB connection dead")):

            mock_settings.return_value.ENVIRONMENT = "development"
            response = client.post("/api/refresh")

            assert response.status_code == 503
            assert "Database service unavailable during refresh" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_api_responses_never_contain_secrets_or_tracebacks():
    """Verify error responses do not leak tracebacks or database credentials."""
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    leak_candidate = "postgresql+psycopg://postgres:secret_pass@db.supabase.co:6543/postgres"

    try:
        with patch("app.api.routes.weather_service.list_regions", side_effect=Exception(f"Connection failed: {leak_candidate}")):
            response = client.get("/api/regions")
            resp_text = response.text
            assert "secret_pass" not in resp_text
            assert "Traceback" not in resp_text
            assert "postgresql+psycopg" not in resp_text
    finally:
        app.dependency_overrides.clear()
