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
    """Verify root endpoint returns 200 OK and HTML dashboard content."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Taiwan Weather Forecast" in response.text


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


# ---------------------------------------------------------------------------
# GET /api/map-data Tests
# ---------------------------------------------------------------------------

def test_get_map_data_success():
    """Verify GET /api/map-data returns 200 with MapDataResponse schema."""
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    mock_map_data = {
        "dataset_id": "F-C0032-005",
        "updated_at": "2026-10-04T00:00:00+08:00",
        "periods": [
            {
                "start_time": "2026-10-04T06:00:00+08:00",
                "end_time": "2026-10-04T18:00:00+08:00",
            }
        ],
        "forecasts": [
            {
                "region_name": "臺中市",
                "start_time": "2026-10-04T06:00:00+08:00",
                "end_time": "2026-10-04T18:00:00+08:00",
                "weather": "多雲",
                "min_temp": 24.0,
                "max_temp": 31.0,
            }
        ],
    }

    try:
        with patch("app.api.routes.weather_service.get_map_data", return_value=mock_map_data):
            response = client.get("/api/map-data")
            assert response.status_code == 200
            data = response.json()

            assert data["dataset_id"] == "F-C0032-005"
            assert "+08:00" in data["updated_at"]
            assert len(data["periods"]) == 1
            assert len(data["forecasts"]) == 1
            assert data["forecasts"][0]["region_name"] == "臺中市"
            assert data["forecasts"][0]["max_temp"] == 31.0
    finally:
        app.dependency_overrides.clear()


def test_get_map_data_database_error():
    """Verify GET /api/map-data returns 503 on database service failure."""
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        with patch("app.api.routes.weather_service.get_map_data", side_effect=WeatherDatabaseError("DB connection failed")):
            response = client.get("/api/map-data")
            assert response.status_code == 503
            assert response.json()["detail"] == "Database service unavailable"
    finally:
        app.dependency_overrides.clear()


def test_get_map_data_never_leaks_secrets():
    """Verify GET /api/map-data never leaks database credentials or tracebacks."""
    mock_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_session
    leak_candidate = "postgresql+psycopg://postgres:secret_pass@db.supabase.co:6543/postgres"

    try:
        with patch("app.api.routes.weather_service.get_map_data", side_effect=Exception(f"Connection failed: {leak_candidate}")):
            response = client.get("/api/map-data")
            assert response.status_code == 503
            assert "secret_pass" not in response.text
            assert "Traceback" not in response.text
            assert "postgresql+psycopg" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_map_data_and_forecast_latest_batch_rule_sqlite():
    """Integration test verifying Latest Batch Rule for both /api/map-data and /api/forecast.

    Proves:
    1. Only rows from the newest batch (MAX(fetched_at)) are returned.
    2. Stale overlapping rows from older batches are excluded.
    3. Expired rows (end_time <= now) are excluded.
    4. Deterministic sorting (start_time ASC, region_name ASC).
    5. Unique periods.
    """
    from datetime import datetime, timezone
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.db.models import Base, WeatherForecast

    # Create isolated in-memory SQLite database supporting multi-threading in TestClient
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()

    t_old = datetime(2026, 10, 4, 0, 0, 0, tzinfo=timezone.utc)
    t_new = datetime(2026, 10, 4, 6, 0, 0, tzinfo=timezone.utc)
    now_ref = datetime(2026, 10, 4, 12, 0, 0, tzinfo=timezone.utc)

    # Batch 1 (Old Batch, fetched_at = t_old)
    # - Stale overlapping row for 臺中市 (12:00 to 00:00, overlapping future period)
    row_old_1 = WeatherForecast(
        id=1,
        dataset_id="F-C0032-005",
        region_name="臺中市",
        start_time=datetime(2026, 10, 4, 12, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 5, 0, 0, 0, tzinfo=timezone.utc),
        weather="舊預報多雲",
        min_temp=20.0,
        max_temp=26.0,
        fetched_at=t_old,
    )
    # - Stale row for 臺北市
    row_old_2 = WeatherForecast(
        id=2,
        dataset_id="F-C0032-005",
        region_name="臺北市",
        start_time=datetime(2026, 10, 4, 12, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 5, 0, 0, 0, tzinfo=timezone.utc),
        weather="舊預報雨天",
        min_temp=18.0,
        max_temp=22.0,
        fetched_at=t_old,
    )

    # Batch 2 (Newest Batch, fetched_at = t_new)
    # - Expired row in newest batch (end_time <= now_ref)
    row_new_expired = WeatherForecast(
        id=3,
        dataset_id="F-C0032-005",
        region_name="臺中市",
        start_time=datetime(2026, 10, 4, 0, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 4, 6, 0, 0, tzinfo=timezone.utc),
        weather="過期預報",
        min_temp=21.0,
        max_temp=27.0,
        fetched_at=t_new,
    )
    # - Active row 1 for 臺中市 (Period 1)
    row_new_tc_1 = WeatherForecast(
        id=4,
        dataset_id="F-C0032-005",
        region_name="臺中市",
        start_time=datetime(2026, 10, 4, 18, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 5, 6, 0, 0, tzinfo=timezone.utc),
        weather="最新預報晴天",
        min_temp=22.0,
        max_temp=28.0,
        fetched_at=t_new,
    )
    # - Active row 2 for 臺中市 (Period 2)
    row_new_tc_2 = WeatherForecast(
        id=5,
        dataset_id="F-C0032-005",
        region_name="臺中市",
        start_time=datetime(2026, 10, 5, 6, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 5, 18, 0, 0, tzinfo=timezone.utc),
        weather="最新預報多雲",
        min_temp=23.0,
        max_temp=30.0,
        fetched_at=t_new,
    )
    # - Active row for 臺北市 (Period 1)
    row_new_tp = WeatherForecast(
        id=6,
        dataset_id="F-C0032-005",
        region_name="臺北市",
        start_time=datetime(2026, 10, 4, 18, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 5, 6, 0, 0, tzinfo=timezone.utc),
        weather="最新預報陰天",
        min_temp=20.0,
        max_temp=24.0,
        fetched_at=t_new,
    )
    # - Active row for 高雄市 (Period 1)
    row_new_kh = WeatherForecast(
        id=7,
        dataset_id="F-C0032-005",
        region_name="高雄市",
        start_time=datetime(2026, 10, 4, 18, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 5, 6, 0, 0, tzinfo=timezone.utc),
        weather="最新預報大晴天",
        min_temp=25.0,
        max_temp=32.0,
        fetched_at=t_new,
    )

    session.add_all([
        row_old_1, row_old_2,
        row_new_expired,
        row_new_tc_1, row_new_tc_2,
        row_new_tp, row_new_kh,
    ])
    session.commit()
    session.close()

    # Override get_db to yield a session connected to the in-memory SQLite database
    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        # Patch current_time in weather_repository to now_ref
        with patch("app.repositories.weather_repository.datetime") as mock_dt:
            mock_dt.now.return_value = now_ref
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            # 1. Test GET /api/map-data
            map_res = client.get("/api/map-data")
            assert map_res.status_code == 200
            map_data = map_res.json()

            # Periods verification: exactly 2 active periods, sorted chronologically
            assert len(map_data["periods"]) == 2
            assert map_data["periods"][0]["start_time"] < map_data["periods"][1]["start_time"]

            # Forecasts verification:
            # - Old batch rows excluded (no "舊預報多雲", "舊預報雨天")
            # - Expired row excluded (no "過期預報")
            forecasts = map_data["forecasts"]
            assert len(forecasts) == 4

            weathers = [f["weather"] for f in forecasts]
            assert "舊預報多雲" not in weathers
            assert "舊預報雨天" not in weathers
            assert "過期預報" not in weathers
            assert set(weathers) == {"最新預報晴天", "最新預報多雲", "最新預報陰天", "最新預報大晴天"}

            # Deterministic ordering verification: start_time ASC, region_name ASC
            # Note: Unicode order for 臺中市 ('\u4e2d') < 臺北市 ('\u5317') < 高雄市 ('\u9ad8')
            assert forecasts[0]["region_name"] == "臺中市"  # Period 1
            assert forecasts[1]["region_name"] == "臺北市"  # Period 1
            assert forecasts[2]["region_name"] == "高雄市"  # Period 1
            assert forecasts[3]["region_name"] == "臺中市"  # Period 2

            # 2. Regression Test: GET /api/forecast?region=臺中市
            fc_res = client.get("/api/forecast?region=臺中市")
            assert fc_res.status_code == 200
            fc_data = fc_res.json()

            # Verify stale overlapping rows from older batches are excluded
            fc_forecasts = fc_data["forecasts"]
            assert len(fc_forecasts) == 2

            fc_weathers = [f["weather"] for f in fc_forecasts]
            assert "舊預報多雲" not in fc_weathers
            assert "過期預報" not in fc_weathers
            assert fc_weathers == ["最新預報晴天", "最新預報多雲"]
            assert fc_forecasts[0]["max_temp"] == 28.0
            assert fc_forecasts[1]["max_temp"] == 30.0

    finally:
        app.dependency_overrides.clear()
        engine.dispose()


# ==============================================================================
# Phase 8B: GET /api/forecast/short-term Endpoint Tests
# ==============================================================================

from app.clients.cwa_client import CWAClientError, CWATimeoutError


def test_get_short_term_forecast_api_success():
    """Verify GET /api/forecast/short-term returns 200 with chronological 36h forecasts including PoP and CI."""
    mock_data = {
        "region": "臺中市",
        "dataset_id": "F-C0032-001",
        "updated_at": "2026-10-05T18:00:00+08:00",
        "forecasts": [
            {
                "start_time": "2026-10-05T18:00:00+08:00",
                "end_time": "2026-10-06T06:00:00+08:00",
                "weather": "多雲短暫陣雨",
                "weather_code": "08",
                "min_temp": 25.0,
                "max_temp": 29.0,
                "pop": 40,
                "comfort_index": "舒適至悶熱",
            },
            {
                "start_time": "2026-10-06T06:00:00+08:00",
                "end_time": "2026-10-06T18:00:00+08:00",
                "weather": "多雲午後雷陣雨",
                "weather_code": "22",
                "min_temp": 26.0,
                "max_temp": 33.0,
                "pop": 70,
                "comfort_index": "悶熱",
            },
        ],
    }

    with patch("app.api.routes.weather_service.get_short_term_forecast", return_value=mock_data) as mock_service:
        response = client.get("/api/forecast/short-term?region=臺中市")
        assert response.status_code == 200
        mock_service.assert_called_once_with(region_name="臺中市")

        body = response.json()
        assert body["region"] == "臺中市"
        assert body["dataset_id"] == "F-C0032-001"
        assert len(body["forecasts"]) == 2
        assert body["forecasts"][0]["pop"] == 40
        assert body["forecasts"][0]["comfort_index"] == "舒適至悶熱"
        assert body["forecasts"][1]["pop"] == 70


def test_get_short_term_forecast_api_empty_region():
    """Verify empty region returns 400 Bad Request."""
    response = client.get("/api/forecast/short-term?region=")
    assert response.status_code == 400
    assert "Region query parameter must not be empty" in response.json()["detail"]


def test_get_short_term_forecast_api_unknown_region():
    """Verify unknown region returns 404 Not Found."""
    with patch(
        "app.api.routes.weather_service.get_short_term_forecast",
        side_effect=RegionNotFoundError("Region '火星市' not found"),
    ):
        response = client.get("/api/forecast/short-term?region=火星市")
        assert response.status_code == 404
        assert "Region '火星市' not found" in response.json()["detail"]


def test_get_short_term_forecast_api_upstream_cwa_failure():
    """Verify CWA upstream failure returns 502 Bad Gateway without leaking internal details."""
    with patch(
        "app.api.routes.weather_service.get_short_term_forecast",
        side_effect=CWAClientError("CWA API 503 gateway unavailable with CWA-KEY-12345"),
    ):
        response = client.get("/api/forecast/short-term?region=臺中市")
        assert response.status_code == 502
        assert response.json()["detail"] == "Upstream weather data service unavailable"
        # Verify no secret leaked
        assert "CWA-KEY" not in response.text


def test_get_short_term_forecast_api_unexpected_internal_error():
    """Verify unexpected internal failure returns 500 without leaking raw traces."""
    with patch(
        "app.api.routes.weather_service.get_short_term_forecast",
        side_effect=RuntimeError("Unexpected unhandled server crash with secret postgresql://user:pwd@db.host/db"),
    ):
        response = client.get("/api/forecast/short-term?region=臺中市")
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error occurred while retrieving short-term forecast"
        assert "postgresql://" not in response.text
        assert "pwd" not in response.text


# ==============================================================================
# Phase 8B2: GET /api/map-data/short-term Endpoint Tests
# ==============================================================================

def test_get_short_term_map_data_api_success():
    """Verify GET /api/map-data/short-term returns 200 with ShortTermMapDataResponse."""
    mock_data = {
        "dataset_id": "F-C0032-001",
        "updated_at": "2026-10-05T18:00:00+08:00",
        "periods": [
            {
                "start_time": "2026-10-05T18:00:00+08:00",
                "end_time": "2026-10-06T06:00:00+08:00",
            }
        ],
        "forecasts": [
            {
                "region_name": "臺中市",
                "start_time": "2026-10-05T18:00:00+08:00",
                "end_time": "2026-10-06T06:00:00+08:00",
                "weather": "多雲短暫陣雨",
                "weather_code": "08",
                "min_temp": 25.0,
                "max_temp": 29.0,
                "pop": 40,
                "comfort_index": "舒適",
            }
        ],
    }

    with patch("app.api.routes.weather_service.get_short_term_map_data", return_value=mock_data) as mock_service:
        response = client.get("/api/map-data/short-term")
        assert response.status_code == 200
        mock_service.assert_called_once()

        body = response.json()
        assert body["dataset_id"] == "F-C0032-001"
        assert len(body["periods"]) == 1
        assert len(body["forecasts"]) == 1
        assert body["forecasts"][0]["region_name"] == "臺中市"
        assert body["forecasts"][0]["pop"] == 40
        assert body["forecasts"][0]["comfort_index"] == "舒適"


def test_get_short_term_map_data_api_not_found():
    """Verify 404 when no short-term map data is found."""
    with patch(
        "app.api.routes.weather_service.get_short_term_map_data",
        side_effect=ForecastNotFoundError("No active short-term map forecasts found"),
    ):
        response = client.get("/api/map-data/short-term")
        assert response.status_code == 404
        assert "No active short-term map forecasts found" in response.json()["detail"]


def test_get_short_term_map_data_api_upstream_cwa_failure():
    """Verify 502 Bad Gateway when upstream CWA fails without leaking secrets."""
    with patch(
        "app.api.routes.weather_service.get_short_term_map_data",
        side_effect=CWAClientError("CWA timeout with secret key CWA-SECRET-99999"),
    ):
        response = client.get("/api/map-data/short-term")
        assert response.status_code == 502
        assert response.json()["detail"] == "Upstream weather data service unavailable"
        assert "CWA-SECRET-99999" not in response.text


def test_get_short_term_map_data_api_unexpected_internal_error():
    """Verify 500 when unexpected error occurs without leaking traces or credentials."""
    with patch(
        "app.api.routes.weather_service.get_short_term_map_data",
        side_effect=Exception("Database crash with postgresql://admin:secretpass@db:5432/cwa"),
    ):
        response = client.get("/api/map-data/short-term")
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error occurred while retrieving short-term map data"
        assert "secretpass" not in response.text
        assert "postgresql://" not in response.text


# ==============================================================================
# Phase 8C: GET /api/observations Endpoint Tests
# ==============================================================================

def test_get_observations_api_success():
    """Verify GET /api/observations returns 200 with ObservationResponse."""
    mock_data = {
        "dataset_id": "O-A0001",
        "updated_at": "2026-10-07T18:00:00+08:00",
        "stations": [
            {
                "station_id": "467490",
                "station_name": "臺中",
                "observation_time": "2026-10-07T18:00:00+08:00",
                "county_name": "臺中市",
                "town_name": "北區",
                "latitude": 24.1453,
                "longitude": 120.6841,
                "altitude": 84.0,
                "weather": "多雲",
                "temperature": 27.4,
                "relative_humidity": 76,
                "wind_direction": 220,
                "wind_direction_text": "西南風",
                "wind_speed": 2.1,
                "air_pressure": 1008.4,
                "precipitation": 0.0,
                "precipitation_status": None,
                "peak_gust_speed": 5.4,
            }
        ],
    }

    with patch("app.api.routes.weather_service.get_observations", return_value=mock_data) as mock_service:
        response = client.get("/api/observations")
        assert response.status_code == 200
        mock_service.assert_called_once()

        body = response.json()
        assert body["dataset_id"] == "O-A0001"
        assert body["updated_at"] == "2026-10-07T18:00:00+08:00"
        assert len(body["stations"]) == 1
        st = body["stations"][0]
        assert st["station_id"] == "467490"
        assert st["station_name"] == "臺中"
        assert st["temperature"] == 27.4
        assert st["precipitation"] == 0.0
        assert st["wind_direction_text"] == "西南風"


def test_get_observations_api_not_found():
    """Verify 404 when no observations are available."""
    with patch(
        "app.api.routes.weather_service.get_observations",
        side_effect=ForecastNotFoundError("No active weather observation records found"),
    ):
        response = client.get("/api/observations")
        assert response.status_code == 404
        assert "No active weather observation records found" in response.json()["detail"]


def test_get_observations_api_upstream_cwa_failure():
    """Verify 502 Bad Gateway when upstream CWA fails without leaking secrets."""
    with patch(
        "app.api.routes.weather_service.get_observations",
        side_effect=CWAClientError("CWA timeout with secret key CWA-SECRET-88888"),
    ):
        response = client.get("/api/observations")
        assert response.status_code == 502
        assert response.json()["detail"] == "Upstream weather data service unavailable"
        assert "CWA-SECRET-88888" not in response.text


def test_get_observations_api_unexpected_internal_error():
    """Verify 500 when unexpected error occurs without leaking traces or credentials."""
    with patch(
        "app.api.routes.weather_service.get_observations",
        side_effect=Exception("Database crash with postgresql://admin:secretpass@db:5432/cwa"),
    ):
        response = client.get("/api/observations")
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error occurred while retrieving weather observations"
        assert "secretpass" not in response.text
        assert "postgresql://" not in response.text


# ==============================================================================
# Phase 8D: GET /api/radar Endpoint Tests
# ==============================================================================

from app.services.weather_service import WeatherServiceError


def test_get_radar_api_success():
    """Verify GET /api/radar returns 200 with valid RadarMetadataResponse."""
    mock_data = {
        "dataset_id": "O-A0058-001",
        "image_url": "https://cwaopendata.s3.ap-northeast-1.amazonaws.com/Observation/O-A0058-001.png",
        "radar_time": "2026-10-07T20:30:00+08:00",
        "time_source": "radar_datetime",
        "bounds": {
            "south": 17.75,
            "west": 115.00,
            "north": 29.25,
            "east": 126.50,
        },
        "image_width": 3600,
        "image_height": 3600,
        "updated_at": "2026-10-07T20:36:26+08:00",
    }

    with patch("app.api.routes.weather_service.get_radar_metadata", return_value=mock_data) as mock_service:
        response = client.get("/api/radar")
        assert response.status_code == 200
        mock_service.assert_called_once()

        body = response.json()
        assert body["dataset_id"] == "O-A0058-001"
        assert body["image_url"] == "https://cwaopendata.s3.ap-northeast-1.amazonaws.com/Observation/O-A0058-001.png"
        assert body["radar_time"] == "2026-10-07T20:30:00+08:00"
        assert body["time_source"] == "radar_datetime"
        assert body["bounds"]["south"] == 17.75
        assert body["bounds"]["west"] == 115.00
        assert body["bounds"]["north"] == 29.25
        assert body["bounds"]["east"] == 126.50
        assert body["image_width"] == 3600
        assert body["image_height"] == 3600


def test_get_radar_api_fallback_with_last_modified():
    """Verify GET /api/radar returns safe fallback metadata when XML is unavailable."""
    mock_fallback_data = {
        "dataset_id": "O-A0058-001",
        "image_url": "https://cwaopendata.s3.ap-northeast-1.amazonaws.com/Observation/O-A0058-001.png",
        "radar_time": None,
        "time_source": "last_modified",
        "bounds": {
            "south": 17.75,
            "west": 115.00,
            "north": 29.25,
            "east": 126.50,
        },
        "image_width": 3600,
        "image_height": 3600,
        "updated_at": "2026-10-07T20:46:15+08:00",
    }

    with patch("app.api.routes.weather_service.get_radar_metadata", return_value=mock_fallback_data):
        response = client.get("/api/radar")
        assert response.status_code == 200
        body = response.json()
        assert body["dataset_id"] == "O-A0058-001"
        assert body["radar_time"] is None
        assert body["time_source"] == "last_modified"
        assert body["updated_at"] == "2026-10-07T20:46:15+08:00"


def test_get_radar_api_upstream_service_error():
    """Verify 502 Bad Gateway when weather_service raises WeatherServiceError."""
    with patch(
        "app.api.routes.weather_service.get_radar_metadata",
        side_effect=WeatherServiceError("Complete failure with CWA-API-KEY-SECRET"),
    ):
        response = client.get("/api/radar")
        assert response.status_code == 502
        assert response.json()["detail"] == "Upstream radar data service unavailable"
        assert "CWA-API-KEY-SECRET" not in response.text


def test_get_radar_api_unexpected_internal_error():
    """Verify 500 when unexpected error occurs without leaking credentials."""
    with patch(
        "app.api.routes.weather_service.get_radar_metadata",
        side_effect=Exception("Database crash postgresql://user:pass@host/cwa"),
    ):
        response = client.get("/api/radar")
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error occurred while retrieving radar metadata"
        assert "postgresql://" not in response.text
        assert "pass" not in response.text





