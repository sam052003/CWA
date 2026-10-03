"""Unit tests for weather service layer business logic, validations, and conversions."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo
import pytest

from app.clients.cwa_client import CWATimeoutError
from app.db.models import FetchLog, WeatherForecast
from app.services.weather_service import (
    ForecastNotFoundError,
    RegionNotFoundError,
    WeatherDatabaseError,
    WeatherRefreshError,
    get_forecast,
    list_regions,
    refresh_forecasts,
    sanitize_error,
    to_taipei_isoformat,
)


def test_to_taipei_isoformat_from_utc():
    """Verify conversion of UTC datetime to Asia/Taipei (+08:00) ISO string."""
    utc_dt = datetime(2026, 10, 4, 10, 0, 0, tzinfo=timezone.utc)
    taipei_iso = to_taipei_isoformat(utc_dt)
    assert taipei_iso == "2026-10-04T18:00:00+08:00"


def test_to_taipei_isoformat_preserves_instant():
    """Verify that a datetime already in Asia/Taipei retains its exact representation."""
    taipei_tz = ZoneInfo("Asia/Taipei")
    orig_dt = datetime(2026, 10, 4, 18, 0, 0, tzinfo=taipei_tz)
    taipei_iso = to_taipei_isoformat(orig_dt)
    assert taipei_iso == "2026-10-04T18:00:00+08:00"


def test_to_taipei_isoformat_none():
    """Verify that None returns None."""
    assert to_taipei_isoformat(None) is None


def test_sanitize_error_redacts_credentials():
    """Verify that API keys, database URLs, and passwords are fully redacted."""
    fake_key = "CWA_SECRET_KEY_12345"
    fake_db = "postgresql+psycopg://postgres:secret_pass@db.host.supabase.co:6543/postgres"

    with patch("app.services.weather_service.get_settings") as mock_settings:
        mock_settings.return_value.cwa_api_key = fake_key
        mock_settings.return_value.database_url = fake_db

        raw_msg = f"Error querying {fake_db} with key {fake_key}"
        sanitized = sanitize_error(raw_msg)

        assert fake_key not in sanitized
        assert "secret_pass" not in sanitized
        assert "[REDACTED_API_KEY]" in sanitized
        assert "[REDACTED_DATABASE_URL]" in sanitized


def test_list_regions_success():
    """Verify list_regions retrieves and returns regions from repository."""
    mock_session = MagicMock()
    with patch("app.services.weather_service.get_regions", return_value=["南投縣", "臺中市"]):
        regions = list_regions(mock_session)
        assert regions == ["南投縣", "臺中市"]


def test_list_regions_database_error():
    """Verify list_regions wraps database exceptions in WeatherDatabaseError."""
    mock_session = MagicMock()
    with patch("app.services.weather_service.get_regions", side_effect=Exception("DB down")):
        with pytest.raises(WeatherDatabaseError, match="Failed to retrieve regions"):
            list_regions(mock_session)


def test_get_forecast_region_validation_empty():
    """Verify get_forecast rejects empty region name."""
    mock_session = MagicMock()
    with pytest.raises(RegionNotFoundError, match="Region name is required"):
        get_forecast(mock_session, "   ")


def test_get_forecast_region_not_found():
    """Verify get_forecast raises RegionNotFoundError for non-existent region."""
    mock_session = MagicMock()
    with patch("app.services.weather_service.list_regions", return_value=["臺北市", "臺中市"]):
        with pytest.raises(RegionNotFoundError, match="Region '火星市' not found"):
            get_forecast(mock_session, "火星市")


def test_get_forecast_no_active_forecasts():
    """Verify get_forecast raises ForecastNotFoundError when region has only expired forecasts."""
    mock_session = MagicMock()
    with patch("app.services.weather_service.list_regions", return_value=["臺中市"]), \
         patch("app.services.weather_service.get_active_forecasts_by_region", return_value=[]):
        with pytest.raises(ForecastNotFoundError, match="No active forecast found for region '臺中市'"):
            get_forecast(mock_session, "臺中市")


def test_get_forecast_success():
    """Verify get_forecast returns formatted dictionary with Asia/Taipei timestamps."""
    mock_session = MagicMock()
    taipei_tz = ZoneInfo("Asia/Taipei")

    f1 = WeatherForecast(
        dataset_id="F-C0032-005",
        region_name="臺中市",
        start_time=datetime(2026, 10, 4, 0, 0, 0, tzinfo=taipei_tz),
        end_time=datetime(2026, 10, 4, 12, 0, 0, tzinfo=taipei_tz),
        weather="晴時多雲",
        min_temp=24.0,
        max_temp=30.0,
        fetched_at=datetime(2026, 10, 3, 23, 0, 0, tzinfo=timezone.utc),
    )

    fetch_log = FetchLog(
        dataset_id="F-C0032-005",
        status="success",
        fetched_at=datetime(2026, 10, 3, 23, 30, 0, tzinfo=timezone.utc),
    )

    with patch("app.services.weather_service.list_regions", return_value=["臺中市"]), \
         patch("app.services.weather_service.get_active_forecasts_by_region", return_value=[f1]), \
         patch("app.services.weather_service.get_latest_fetch_log", return_value=fetch_log):

        data = get_forecast(mock_session, "臺中市")

        assert data["region"] == "臺中市"
        assert data["dataset_id"] == "F-C0032-005"
        assert "+08:00" in data["updated_at"]
        assert len(data["forecasts"]) == 1

        item = data["forecasts"][0]
        assert item["weather"] == "晴時多雲"
        assert item["min_temp"] == 24.0
        assert item["max_temp"] == 30.0
        assert item["start_time"] == "2026-10-04T00:00:00+08:00"
        assert item["end_time"] == "2026-10-04T12:00:00+08:00"


def test_refresh_forecasts_cwa_failure():
    """Verify refresh_forecasts raises WeatherRefreshError on CWAClient failure."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.fetch_forecast_1week.side_effect = CWATimeoutError("CWA API timeout")

    with pytest.raises(WeatherRefreshError, match="CWA API request failed"):
        refresh_forecasts(mock_session, client=mock_client)


def test_refresh_forecasts_empty_records_rejected():
    """Verify refresh_forecasts rejects empty parsed records."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.fetch_forecast_1week.return_value = {"cwaopendata": {}}

    with patch("app.services.weather_service.parse_cwa_forecast", return_value=[]):
        with pytest.raises(WeatherRefreshError, match="No valid forecast records"):
            refresh_forecasts(mock_session, client=mock_client)


def test_refresh_forecasts_incomplete_regions_rejected():
    """Verify refresh_forecasts rejects payload with fewer than 22 regions."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.fetch_forecast_1week.return_value = {"cwaopendata": {}}

    # Only 2 regions instead of 22
    incomplete_records = [
        {"dataset_id": "F-C0032-005", "region_name": "臺北市", "start_time": "2026-10-04T06:00:00+08:00", "end_time": "2026-10-04T18:00:00+08:00", "weather": "晴", "min_temp": 24, "max_temp": 28},
        {"dataset_id": "F-C0032-005", "region_name": "新北市", "start_time": "2026-10-04T06:00:00+08:00", "end_time": "2026-10-04T18:00:00+08:00", "weather": "陰", "min_temp": 22, "max_temp": 26},
    ]

    with patch("app.services.weather_service.parse_cwa_forecast", return_value=incomplete_records):
        with pytest.raises(WeatherRefreshError, match="expected 22 regions"):
            refresh_forecasts(mock_session, client=mock_client)


def test_refresh_forecasts_success():
    """Verify successful refresh workflow commits transaction and returns summary."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.DATASET_FORECAST_1WEEK = "F-C0032-005"
    mock_client.fetch_forecast_1week.return_value = {"cwaopendata": {}}

    # Generate 22 mock regions
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

    with patch("app.services.weather_service.parse_cwa_forecast", return_value=mock_records), \
         patch("app.services.weather_service.upsert_forecasts", return_value=22), \
         patch("app.services.weather_service.create_fetch_log") as mock_log:

        summary = refresh_forecasts(mock_session, client=mock_client)

        assert summary["status"] == "success"
        assert summary["dataset_id"] == "F-C0032-005"
        assert summary["records_count"] == 22
        assert summary["regions_count"] == 22
        assert "+08:00" in summary["updated_at"]

        assert mock_session.commit.called
        assert mock_log.called
        assert mock_log.call_args[1]["status"] == "success"


def test_refresh_forecasts_database_rollback_on_error():
    """Verify transaction rollback and failure log on persistence error."""
    mock_session = MagicMock()
    mock_session.commit.side_effect = Exception("DB Disk Full")
    mock_client = MagicMock()
    mock_client.DATASET_FORECAST_1WEEK = "F-C0032-005"

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

    with patch("app.services.weather_service.parse_cwa_forecast", return_value=mock_records), \
         patch("app.services.weather_service.upsert_forecasts", return_value=22), \
         patch("app.services.weather_service.create_fetch_log"):

        with pytest.raises(WeatherDatabaseError, match="Database transaction failed"):
            refresh_forecasts(mock_session, client=mock_client)

        assert mock_session.rollback.called
