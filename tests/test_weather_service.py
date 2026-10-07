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
    clear_short_term_cache,
    clear_short_term_map_cache,
    get_forecast,
    get_short_term_forecast,
    get_short_term_map_data,
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


def test_refresh_forecasts_with_preprovided_payload_skips_fetch():
    """Verify refresh_forecasts(payload=...) does not invoke client.fetch_forecast_1week."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.DATASET_FORECAST_1WEEK = "F-C0032-005"

    preprovided_payload = {"cwaopendata": {"dataset": {"location": []}}}

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

        refresh_forecasts(mock_session, client=mock_client, payload=preprovided_payload)

        # Ensure client.fetch_forecast_1week was NEVER called
        assert not mock_client.fetch_forecast_1week.called


def test_cli_save_db_only_fetches_cwa_once():
    """Verify that CLI scripts.fetch_weather --save-db calls CWA API exactly once."""
    from scripts.fetch_weather import fetch_and_summarize

    mock_client = MagicMock()
    mock_client.DATASET_FORECAST_1WEEK = "F-C0032-005"
    mock_client.fetch_forecast_1week.return_value = {
        "cwaopendata": {
            "dataset": {
                "datasetInfo": {"datasetDescription": "一週預報"},
                "location": [{"locationName": "臺中市", "weatherElement": [{"elementName": "Wx"}]}],
            }
        }
    }

    mock_summary = {
        "status": "success",
        "dataset_id": "F-C0032-005",
        "records_count": 330,
        "regions_count": 22,
        "updated_at": "2026-10-04T00:00:00+08:00",
    }

    with patch("scripts.fetch_weather.get_settings") as mock_settings, \
         patch("scripts.fetch_weather.CWAClient", return_value=mock_client), \
         patch("scripts.fetch_weather.SessionLocal") as mock_session_factory, \
         patch("scripts.fetch_weather.refresh_forecasts", return_value=mock_summary) as mock_refresh:

        mock_settings.return_value.cwa_api_key = "dummy_key"
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session

        fetch_and_summarize(save_fixture=False, save_db=True)

        # CWA API must only be called ONCE
        assert mock_client.fetch_forecast_1week.call_count == 1
        # refresh_forecasts must receive the fetched payload
        assert mock_refresh.call_count == 1
        call_kwargs = mock_refresh.call_args[1]
        assert call_kwargs.get("payload") is not None


def test_refresh_forecasts_cwa_failure():
    """Verify refresh_forecasts records failure fetch_log and raises WeatherRefreshError on CWAClient failure."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.DATASET_FORECAST_1WEEK = "F-C0032-005"
    mock_client.fetch_forecast_1week.side_effect = CWATimeoutError("CWA API timeout")

    with patch("app.services.weather_service.create_fetch_log") as mock_log:
        with pytest.raises(WeatherRefreshError, match="CWA API request failed"):
            refresh_forecasts(mock_session, client=mock_client)

        # Failure log must be attempted
        assert mock_log.called
        assert mock_log.call_args[1]["status"] == "failure"
        assert mock_log.call_args[1]["records_count"] == 0
        assert mock_session.commit.called


def test_refresh_forecasts_parser_failure_records_failure_log():
    """Verify parser failure records failure fetch_log and raises WeatherRefreshError."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.DATASET_FORECAST_1WEEK = "F-C0032-005"
    mock_client.fetch_forecast_1week.return_value = {"cwaopendata": "corrupt"}

    with patch("app.services.weather_service.parse_cwa_forecast", side_effect=ValueError("Corrupt JSON structure")), \
         patch("app.services.weather_service.create_fetch_log") as mock_log:

        with pytest.raises(WeatherRefreshError, match="Failed to parse CWA payload"):
            refresh_forecasts(mock_session, client=mock_client)

        assert mock_log.called
        assert mock_log.call_args[1]["status"] == "failure"


def test_refresh_forecasts_empty_records_rejected():
    """Verify refresh_forecasts rejects empty parsed records and logs failure."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.DATASET_FORECAST_1WEEK = "F-C0032-005"
    mock_client.fetch_forecast_1week.return_value = {"cwaopendata": {}}

    with patch("app.services.weather_service.parse_cwa_forecast", return_value=[]), \
         patch("app.services.weather_service.create_fetch_log") as mock_log:

        with pytest.raises(WeatherRefreshError, match="No valid forecast records"):
            refresh_forecasts(mock_session, client=mock_client)

        assert mock_log.called
        assert mock_log.call_args[1]["status"] == "failure"


def test_refresh_forecasts_incomplete_regions_rejected():
    """Verify refresh_forecasts rejects payload with fewer than 22 regions and logs failure."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.DATASET_FORECAST_1WEEK = "F-C0032-005"
    mock_client.fetch_forecast_1week.return_value = {"cwaopendata": {}}

    # Only 2 regions instead of 22
    incomplete_records = [
        {"dataset_id": "F-C0032-005", "region_name": "臺北市", "start_time": "2026-10-04T06:00:00+08:00", "end_time": "2026-10-04T18:00:00+08:00", "weather": "晴", "min_temp": 24, "max_temp": 28},
        {"dataset_id": "F-C0032-005", "region_name": "新北市", "start_time": "2026-10-04T06:00:00+08:00", "end_time": "2026-10-04T18:00:00+08:00", "weather": "陰", "min_temp": 22, "max_temp": 26},
    ]

    with patch("app.services.weather_service.parse_cwa_forecast", return_value=incomplete_records), \
         patch("app.services.weather_service.create_fetch_log") as mock_log:

        with pytest.raises(WeatherRefreshError, match="expected 22 regions"):
            refresh_forecasts(mock_session, client=mock_client)

        assert mock_log.called
        assert mock_log.call_args[1]["status"] == "failure"


def test_refresh_forecasts_missing_field_rejected():
    """Verify validation failure when record misses required field."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.DATASET_FORECAST_1WEEK = "F-C0032-005"
    mock_client.fetch_forecast_1week.return_value = {"cwaopendata": {}}

    # 22 regions, but first record lacks 'weather'
    bad_records = [
        {
            "dataset_id": "F-C0032-005",
            "region_name": f"Region_{i}",
            "start_time": "2026-10-04T06:00:00+08:00",
            "end_time": "2026-10-04T18:00:00+08:00",
            "weather": None if i == 0 else "晴",
            "min_temp": 20.0,
            "max_temp": 28.0,
        }
        for i in range(22)
    ]

    with patch("app.services.weather_service.parse_cwa_forecast", return_value=bad_records), \
         patch("app.services.weather_service.create_fetch_log") as mock_log:

        with pytest.raises(WeatherRefreshError, match="missing required field 'weather'"):
            refresh_forecasts(mock_session, client=mock_client)

        assert mock_log.called
        assert mock_log.call_args[1]["status"] == "failure"


def test_refresh_forecasts_success_updated_at_from_fetch_log():
    """Verify successful refresh uses success fetch_log timestamp for updated_at."""
    mock_session = MagicMock()
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

    specific_timestamp = datetime(2026, 10, 4, 12, 34, 56, tzinfo=timezone.utc)
    mock_success_log = FetchLog(
        dataset_id="F-C0032-005",
        status="success",
        records_count=22,
        fetched_at=specific_timestamp,
    )

    with patch("app.services.weather_service.parse_cwa_forecast", return_value=mock_records), \
         patch("app.services.weather_service.upsert_forecasts", return_value=22), \
         patch("app.services.weather_service.create_fetch_log", return_value=mock_success_log):

        summary = refresh_forecasts(mock_session, client=mock_client)

        assert summary["status"] == "success"
        # 12:34:56 UTC is 20:34:56 in Asia/Taipei (+08:00)
        assert summary["updated_at"] == "2026-10-04T20:34:56+08:00"


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
         patch("app.services.weather_service.create_fetch_log") as mock_log:

        with pytest.raises(WeatherDatabaseError, match="Database transaction failed"):
            refresh_forecasts(mock_session, client=mock_client)

        assert mock_session.rollback.called


def test_failure_log_error_does_not_mask_original_exception():
    """Verify that if recording failure log itself fails, the original exception is preserved."""
    mock_session = MagicMock()
    mock_session.rollback.side_effect = None
    mock_client = MagicMock()
    mock_client.DATASET_FORECAST_1WEEK = "F-C0032-005"
    mock_client.fetch_forecast_1week.side_effect = CWATimeoutError("CWA connection dropped")

    # Simulate database crash during failure logging
    with patch("app.services.weather_service.create_fetch_log", side_effect=Exception("Database down entirely")):
        with pytest.raises(WeatherRefreshError, match="CWA API request failed"):
            refresh_forecasts(mock_session, client=mock_client)


# ==============================================================================
# Phase 8B: Short-term 36h Living Forecast Service & Cache Tests
# ==============================================================================

from app.services.weather_service import (
    clear_short_term_cache,
    get_short_term_forecast,
)


@pytest.fixture(autouse=True)
def reset_short_term_cache():
    """Ensure clean short-term cache state for every test."""
    clear_short_term_cache()
    yield
    clear_short_term_cache()


def test_get_short_term_forecast_validation_empty_region():
    """Verify get_short_term_forecast raises RegionNotFoundError for empty region."""
    with pytest.raises(RegionNotFoundError, match="Region name is required"):
        get_short_term_forecast("")

    with pytest.raises(RegionNotFoundError, match="Region name is required"):
        get_short_term_forecast("   ")


def test_get_short_term_forecast_validation_unknown_region():
    """Verify get_short_term_forecast raises RegionNotFoundError for non-existent region."""
    with pytest.raises(RegionNotFoundError, match="Region '火星市' not found"):
        get_short_term_forecast("火星市")


def test_get_short_term_forecast_success():
    """Verify get_short_term_forecast fetches, parses, and normalizes 36h forecast without DB."""
    mock_client = MagicMock()
    mock_client.fetch_forecast_36h.return_value = {
        "records": {
            "location": [
                {
                    "locationName": "臺中市",
                    "weatherElement": [
                        {
                            "elementName": "Wx",
                            "time": [
                                {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "多雲短暫陣雨", "parameterValue": "08"}},
                                {"startTime": "2026-10-06 06:00:00", "endTime": "2026-10-06 18:00:00", "parameter": {"parameterName": "晴午後雷陣雨", "parameterValue": "22"}},
                            ],
                        },
                        {
                            "elementName": "PoP",
                            "time": [
                                {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "40"}},
                                {"startTime": "2026-10-06 06:00:00", "endTime": "2026-10-06 18:00:00", "parameter": {"parameterName": "70"}},
                            ],
                        },
                        {
                            "elementName": "CI",
                            "time": [
                                {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "舒適"}},
                                {"startTime": "2026-10-06 06:00:00", "endTime": "2026-10-06 18:00:00", "parameter": {"parameterName": "悶熱"}},
                            ],
                        },
                        {
                            "elementName": "MinT",
                            "time": [
                                {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "25"}},
                                {"startTime": "2026-10-06 06:00:00", "endTime": "2026-10-06 18:00:00", "parameter": {"parameterName": "26"}},
                            ],
                        },
                        {
                            "elementName": "MaxT",
                            "time": [
                                {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "29"}},
                                {"startTime": "2026-10-06 06:00:00", "endTime": "2026-10-06 18:00:00", "parameter": {"parameterName": "33"}},
                            ],
                        },
                    ],
                }
            ]
        }
    }

    data = get_short_term_forecast("臺中市", client=mock_client)
    assert data["region"] == "臺中市"
    assert data["dataset_id"] == "F-C0032-001"
    assert len(data["forecasts"]) == 2
    f0 = data["forecasts"][0]
    assert f0["weather"] == "多雲短暫陣雨"
    assert f0["weather_code"] == "08"
    assert f0["pop"] == 40
    assert f0["comfort_index"] == "舒適"
    assert f0["min_temp"] == 25.0
    assert f0["max_temp"] == 29.0


def test_get_short_term_forecast_ttl_cache_behavior():
    """Verify in-memory process cache returns cached result on subsequent calls within TTL."""
    mock_client = MagicMock()
    mock_client.fetch_forecast_36h.return_value = {
        "records": {
            "location": [
                {
                    "locationName": "臺北市",
                    "weatherElement": [
                        {
                            "elementName": "Wx",
                            "time": [
                                {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "晴"}},
                            ],
                        },
                    ],
                }
            ]
        }
    }

    t0 = 1000.0
    # First call at t0: calls client
    data1 = get_short_term_forecast("臺北市", client=mock_client, current_time=t0)
    assert mock_client.fetch_forecast_36h.call_count == 1
    assert data1["region"] == "臺北市"

    # Second call at t0 + 300s (5 min, within 15 min TTL): hits cache without calling client again
    data2 = get_short_term_forecast("臺北市", client=mock_client, current_time=t0 + 300.0)
    assert mock_client.fetch_forecast_36h.call_count == 1
    assert data2 == data1

    # Third call at t0 + 1000s (after 15 min / 900s TTL): cache expired, re-fetches
    data3 = get_short_term_forecast("臺北市", client=mock_client, current_time=t0 + 1000.0)
    assert mock_client.fetch_forecast_36h.call_count == 2
    assert data3["region"] == "臺北市"


def test_get_short_term_forecast_cache_county_isolation():
    """Verify cached result for one county does not return for another county."""
    mock_client = MagicMock()
    mock_client.fetch_forecast_36h.side_effect = lambda region_name: {
        "records": {
            "location": [
                {
                    "locationName": region_name,
                    "weatherElement": [
                        {"elementName": "Wx", "time": [{"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": f"{region_name}天氣"}}]}
                    ],
                }
            ]
        }
    }

    t0 = 1000.0
    data_tc = get_short_term_forecast("臺中市", client=mock_client, current_time=t0)
    data_kh = get_short_term_forecast("高雄市", client=mock_client, current_time=t0)

    assert data_tc["region"] == "臺中市"
    assert data_kh["region"] == "高雄市"
    assert data_tc["forecasts"][0]["weather"] == "臺中市天氣"
    assert data_kh["forecasts"][0]["weather"] == "高雄市天氣"
    assert mock_client.fetch_forecast_36h.call_count == 2


def test_get_short_term_forecast_exception_not_cached():
    """Verify exceptions (e.g. CWA network failure) are not cached."""
    mock_client = MagicMock()
    mock_client.fetch_forecast_36h.side_effect = CWATimeoutError("CWA timeout")

    with pytest.raises(CWATimeoutError):
        get_short_term_forecast("臺中市", client=mock_client)

    # Recovery: client succeeds next time
    mock_client.fetch_forecast_36h.side_effect = None
    mock_client.fetch_forecast_36h.return_value = {
        "records": {
            "location": [
                {
                    "locationName": "臺中市",
                    "weatherElement": [
                        {"elementName": "Wx", "time": [{"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "多雲"}}]}
                    ],
                }
            ]
        }
    }

    data = get_short_term_forecast("臺中市", client=mock_client)
    assert data["region"] == "臺中市"
    assert data["forecasts"][0]["weather"] == "多雲"


# ==============================================================================
# Phase 8B2: get_short_term_map_data Tests (Rainfall Map Mode F-C0032-001)
# ==============================================================================

def _make_dummy_36h_all_counties_payload():
    return {
        "cwaopendata": {
            "sent": "2026-10-05T17:00:00+08:00",
            "dataset": {
                "location": [
                    {
                        "locationName": "臺北市",
                        "weatherElement": [
                            {
                                "elementName": "Wx",
                                "time": [
                                    {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "晴", "parameterValue": "01"}},
                                    {"startTime": "2026-10-06 06:00:00", "endTime": "2026-10-06 18:00:00", "parameter": {"parameterName": "多雲", "parameterValue": "02"}},
                                    {"startTime": "2026-10-06 18:00:00", "endTime": "2026-10-07 06:00:00", "parameter": {"parameterName": "陰", "parameterValue": "03"}},
                                ],
                            },
                            {
                                "elementName": "MinT",
                                "time": [
                                    {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "23"}},
                                    {"startTime": "2026-10-06 06:00:00", "endTime": "2026-10-06 18:00:00", "parameter": {"parameterName": "25"}},
                                    {"startTime": "2026-10-06 18:00:00", "endTime": "2026-10-07 06:00:00", "parameter": {"parameterName": "22"}},
                                ],
                            },
                            {
                                "elementName": "MaxT",
                                "time": [
                                    {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "27"}},
                                    {"startTime": "2026-10-06 06:00:00", "endTime": "2026-10-06 18:00:00", "parameter": {"parameterName": "31"}},
                                    {"startTime": "2026-10-06 18:00:00", "endTime": "2026-10-07 06:00:00", "parameter": {"parameterName": "28"}},
                                ],
                            },
                            {
                                "elementName": "PoP",
                                "time": [
                                    {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "10"}},
                                    {"startTime": "2026-10-06 06:00:00", "endTime": "2026-10-06 18:00:00", "parameter": {"parameterName": "20"}},
                                    {"startTime": "2026-10-06 18:00:00", "endTime": "2026-10-07 06:00:00", "parameter": {"parameterName": "40"}},
                                ],
                            },
                            {
                                "elementName": "CI",
                                "time": [
                                    {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "舒適"}},
                                    {"startTime": "2026-10-06 06:00:00", "endTime": "2026-10-06 18:00:00", "parameter": {"parameterName": "悶熱"}},
                                    {"startTime": "2026-10-06 18:00:00", "endTime": "2026-10-07 06:00:00", "parameter": {"parameterName": "舒適"}},
                                ],
                            },
                        ],
                    },
                    {
                        "locationName": "臺中市",
                        "weatherElement": [
                            {
                                "elementName": "Wx",
                                "time": [
                                    {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "多雲短暫陣雨", "parameterValue": "08"}},
                                    {"startTime": "2026-10-06 06:00:00", "endTime": "2026-10-06 18:00:00", "parameter": {"parameterName": "多雲", "parameterValue": "02"}},
                                    {"startTime": "2026-10-06 18:00:00", "endTime": "2026-10-07 06:00:00", "parameter": {"parameterName": "晴", "parameterValue": "01"}},
                                ],
                            },
                            {
                                "elementName": "MinT",
                                "time": [
                                    {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "25"}},
                                    {"startTime": "2026-10-06 06:00:00", "endTime": "2026-10-06 18:00:00", "parameter": {"parameterName": "26"}},
                                    {"startTime": "2026-10-06 18:00:00", "endTime": "2026-10-07 06:00:00", "parameter": {"parameterName": "24"}},
                                ],
                            },
                            {
                                "elementName": "MaxT",
                                "time": [
                                    {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "29"}},
                                    {"startTime": "2026-10-06 06:00:00", "endTime": "2026-10-06 18:00:00", "parameter": {"parameterName": "33"}},
                                    {"startTime": "2026-10-06 18:00:00", "endTime": "2026-10-07 06:00:00", "parameter": {"parameterName": "30"}},
                                ],
                            },
                            {
                                "elementName": "PoP",
                                "time": [
                                    {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "60"}},
                                    {"startTime": "2026-10-06 06:00:00", "endTime": "2026-10-06 18:00:00", "parameter": {"parameterName": "30"}},
                                    {"startTime": "2026-10-06 18:00:00", "endTime": "2026-10-07 06:00:00", "parameter": {"parameterName": "10"}},
                                ],
                            },
                            {
                                "elementName": "CI",
                                "time": [
                                    {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "舒適至悶熱"}},
                                    {"startTime": "2026-10-06 06:00:00", "endTime": "2026-10-06 18:00:00", "parameter": {"parameterName": "悶熱"}},
                                    {"startTime": "2026-10-06 18:00:00", "endTime": "2026-10-07 06:00:00", "parameter": {"parameterName": "舒適"}},
                                ],
                            },
                        ],
                    },
                ]
            }
        }
    }


def test_get_short_term_map_data_success():
    """Verify get_short_term_map_data fetches all counties in 1 call, sorts periods and forecasts, and preserves PoP/CI."""
    clear_short_term_map_cache()
    mock_client = MagicMock()
    mock_client.fetch_forecast_36h.return_value = _make_dummy_36h_all_counties_payload()

    data = get_short_term_map_data(client=mock_client)

    # Exactly 1 CWA call with region_name=None (no N+1 22 requests)
    assert mock_client.fetch_forecast_36h.call_count == 1
    assert mock_client.fetch_forecast_36h.call_args[1].get("region_name") is None

    # Dataset ID
    assert data["dataset_id"] == "F-C0032-001"
    assert "updated_at" in data

    # Unique periods derived and sorted chronologically
    periods = data["periods"]
    assert len(periods) == 3
    for i in range(len(periods) - 1):
        assert periods[i]["start_time"] <= periods[i + 1]["start_time"]

    # Forecasts sorted deterministically (start_time ASC, region_name ASC)
    forecasts = data["forecasts"]
    assert len(forecasts) == 6  # 2 counties x 3 intervals
    for i in range(len(forecasts) - 1):
        curr_key = (forecasts[i]["start_time"], forecasts[i]["region_name"])
        next_key = (forecasts[i + 1]["start_time"], forecasts[i + 1]["region_name"])
        assert curr_key <= next_key

    # Preserves PoP and CI
    tc_first = next(f for f in forecasts if f["region_name"] == "臺中市" and "18:00" in f["start_time"])
    assert tc_first["pop"] == 60
    assert tc_first["comfort_index"] == "舒適至悶熱"
    assert tc_first["weather"] == "多雲短暫陣雨"
    assert tc_first["weather_code"] == "08"


def test_get_short_term_map_data_ttl_cache_behavior():
    """Verify all-county map cache serves cached data within TTL and refetches when expired."""
    clear_short_term_map_cache()
    mock_client = MagicMock()
    mock_client.fetch_forecast_36h.return_value = _make_dummy_36h_all_counties_payload()

    t0 = 5000.0
    # First call at t0: calls CWA client
    res1 = get_short_term_map_data(client=mock_client, current_time=t0)
    assert mock_client.fetch_forecast_36h.call_count == 1

    # Second call at t0 + 300s (5 min, within 15 min TTL): cache hit, no CWA client call
    res2 = get_short_term_map_data(client=mock_client, current_time=t0 + 300.0)
    assert mock_client.fetch_forecast_36h.call_count == 1
    assert res2 == res1

    # Third call at t0 + 1000s (exceeds 900s TTL): cache expired, re-fetches
    res3 = get_short_term_map_data(client=mock_client, current_time=t0 + 1000.0)
    assert mock_client.fetch_forecast_36h.call_count == 2
    assert res3["dataset_id"] == "F-C0032-001"


def test_get_short_term_map_data_partial_counties_allowed():
    """Verify partial counties payload does not fail the entire map."""
    clear_short_term_map_cache()
    mock_client = MagicMock()
    # Payload contains only 1 county
    single_county_payload = {
        "records": {
            "location": [
                {
                    "locationName": "澎湖縣",
                    "weatherElement": [
                        {"elementName": "Wx", "time": [{"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "晴"}}]},
                        {"elementName": "PoP", "time": [{"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "0"}}]},
                    ],
                }
            ]
        }
    }
    mock_client.fetch_forecast_36h.return_value = single_county_payload

    data = get_short_term_map_data(client=mock_client)
    assert data["dataset_id"] == "F-C0032-001"
    assert len(data["forecasts"]) == 1
    assert data["forecasts"][0]["region_name"] == "澎湖縣"


def test_get_short_term_map_data_no_records_raises_forecast_not_found():
    """Verify empty/unusable records raises ForecastNotFoundError."""
    clear_short_term_map_cache()
    mock_client = MagicMock()
    mock_client.fetch_forecast_36h.return_value = {"records": {"location": []}}

    with pytest.raises(ForecastNotFoundError, match="No active short-term map forecasts found"):
        get_short_term_map_data(client=mock_client)


def test_get_short_term_map_data_exception_not_cached():
    """Verify upstream exceptions are not cached so recovery succeeds immediately."""
    clear_short_term_map_cache()
    mock_client = MagicMock()
    mock_client.fetch_forecast_36h.side_effect = CWATimeoutError("CWA network timeout")

    with pytest.raises(CWATimeoutError):
        get_short_term_map_data(client=mock_client)

    # Next call succeeds
    mock_client.fetch_forecast_36h.side_effect = None
    mock_client.fetch_forecast_36h.return_value = _make_dummy_36h_all_counties_payload()

    data = get_short_term_map_data(client=mock_client)
    assert data["dataset_id"] == "F-C0032-001"
    assert len(data["forecasts"]) == 6



