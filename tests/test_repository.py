"""Unit tests for database session management, repository UPSERT, and query operations.

These tests use mock sessions and statement inspection. They do not connect to live Supabase.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy.dialects import postgresql

from app.db.models import FetchLog, WeatherForecast
from app.repositories.weather_repository import (
    WeatherRepository,
    create_fetch_log,
    get_forecasts_by_region,
    get_latest_fetch_log,
    get_regions,
    prepare_forecast_records,
    to_timezone_aware_datetime,
    upsert_forecasts,
)
from scripts.fetch_weather import sanitize_error, save_to_database


def test_timezone_aware_datetime_conversion():
    """Verify that timezone-aware ISO strings retain +08:00 timezone."""
    iso_str = "2026-10-04T06:00:00+08:00"
    dt = to_timezone_aware_datetime(iso_str)

    assert isinstance(dt, datetime)
    assert dt.tzinfo is not None
    # Check that the timezone offset is +08:00 (28800 seconds)
    offset = dt.utcoffset()
    assert offset == timedelta(hours=8)
    assert dt.year == 2026
    assert dt.month == 10
    assert dt.day == 4
    assert dt.hour == 6

    # Test already timezone-aware datetime instance
    dt_same = to_timezone_aware_datetime(dt)
    assert dt_same is dt

    # Test rejection of naive datetime string
    with pytest.raises(ValueError, match="naive"):
        to_timezone_aware_datetime("2026-10-04T06:00:00")

    # Test rejection of naive datetime object
    with pytest.raises(ValueError, match="naive"):
        to_timezone_aware_datetime(datetime(2026, 10, 4, 6, 0))

    # Test rejection of invalid type
    with pytest.raises(TypeError, match="Expected str or datetime"):
        to_timezone_aware_datetime(12345678)  # type: ignore


def test_forecast_record_mapping():
    """Verify parser dictionary mapping to database schema attributes."""
    raw_records = [
        {
            "dataset_id": "F-C0032-005",
            "region_name": "臺北市",
            "start_time": "2026-10-04T06:00:00+08:00",
            "end_time": "2026-10-04T18:00:00+08:00",
            "weather": "晴時多雲",
            "min_temp": 24,
            "max_temp": 28,
        }
    ]

    mapped = prepare_forecast_records(raw_records)
    assert len(mapped) == 1
    record = mapped[0]

    assert record["dataset_id"] == "F-C0032-005"
    assert record["region_name"] == "臺北市"
    assert record["weather"] == "晴時多雲"
    assert record["min_temp"] == 24.0
    assert record["max_temp"] == 28.0
    assert isinstance(record["min_temp"], float)
    assert isinstance(record["max_temp"], float)

    # Verify datetimes
    assert isinstance(record["start_time"], datetime)
    assert record["start_time"].utcoffset() == timedelta(hours=8)
    assert isinstance(record["end_time"], datetime)
    assert record["end_time"].utcoffset() == timedelta(hours=8)
    assert isinstance(record["fetched_at"], datetime)
    assert record["fetched_at"].tzinfo == timezone.utc


def test_postgresql_upsert_conflict_statement_inspection():
    """Verify PostgreSQL ON CONFLICT columns and DO UPDATE SET assignments."""
    raw_records = [
        {
            "dataset_id": "F-C0032-005",
            "region_name": "臺中市",
            "start_time": "2026-10-04T06:00:00+08:00",
            "end_time": "2026-10-04T18:00:00+08:00",
            "weather": "多雲",
            "min_temp": 25,
            "max_temp": 30,
        }
    ]

    mock_session = MagicMock()
    count = upsert_forecasts(mock_session, raw_records)

    assert count == 1
    assert mock_session.execute.called

    # Inspect the statement passed to session.execute
    stmt = mock_session.execute.call_args[0][0]
    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    # Verify target table
    assert "INSERT INTO weather_forecasts" in compiled

    # Verify conflict columns
    assert "ON CONFLICT (dataset_id, region_name, start_time, end_time)" in compiled

    # Verify update on conflict
    assert "DO UPDATE SET" in compiled
    assert "weather = excluded.weather" in compiled
    assert "min_temp = excluded.min_temp" in compiled
    assert "max_temp = excluded.max_temp" in compiled
    assert "fetched_at = excluded.fetched_at" in compiled


def test_upsert_empty_records():
    """Verify that passing empty records returns 0 without executing queries."""
    mock_session = MagicMock()
    count = upsert_forecasts(mock_session, [])
    assert count == 0
    assert not mock_session.execute.called


def test_duplicate_refresh_upsert_design():
    """Verify that repeated executions target the same unique key and update in place."""
    record = {
        "dataset_id": "F-C0032-005",
        "region_name": "新北市",
        "start_time": "2026-10-04T06:00:00+08:00",
        "end_time": "2026-10-04T18:00:00+08:00",
        "weather": "陰短暫雨",
        "min_temp": 22,
        "max_temp": 26,
    }

    mock_session = MagicMock()
    # First execution
    upsert_forecasts(mock_session, [record])
    stmt1 = mock_session.execute.call_args[0][0]

    # Second execution (e.g. refreshed weather)
    record_updated = dict(record, weather="晴天", max_temp=29)
    upsert_forecasts(mock_session, [record_updated])
    stmt2 = mock_session.execute.call_args[0][0]

    compiled1 = str(stmt1.compile(dialect=postgresql.dialect()))
    compiled2 = str(stmt2.compile(dialect=postgresql.dialect()))

    # Both statements enforce ON CONFLICT on the 4 composite keys
    assert "ON CONFLICT (dataset_id, region_name, start_time, end_time) DO UPDATE SET" in compiled1
    assert "ON CONFLICT (dataset_id, region_name, start_time, end_time) DO UPDATE SET" in compiled2


def test_get_regions_distinct_and_sorted():
    """Verify that get_regions executes DISTINCT and ORDER BY region_name."""
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["南投縣", "嘉義市", "臺北市"]
    mock_session.execute.return_value = mock_result

    regions = get_regions(mock_session)

    assert regions == ["南投縣", "嘉義市", "臺北市"]
    stmt = mock_session.execute.call_args[0][0]
    compiled = str(stmt.compile())

    assert "SELECT DISTINCT weather_forecasts.region_name" in compiled
    assert "ORDER BY weather_forecasts.region_name ASC" in compiled


def test_get_forecasts_by_region_ordered():
    """Verify that get_forecasts_by_region filters by region and orders chronologically."""
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_forecast_1 = MagicMock(spec=WeatherForecast)
    mock_forecast_2 = MagicMock(spec=WeatherForecast)
    mock_result.scalars.return_value.all.return_value = [mock_forecast_1, mock_forecast_2]
    mock_session.execute.return_value = mock_result

    forecasts = get_forecasts_by_region(mock_session, "臺中市")

    assert len(forecasts) == 2
    stmt = mock_session.execute.call_args[0][0]
    compiled = str(stmt.compile())

    assert "WHERE weather_forecasts.region_name = :region_name_1" in compiled
    assert "ORDER BY weather_forecasts.start_time ASC" in compiled


def test_fetch_log_success():
    """Verify create_fetch_log and get_latest_fetch_log."""
    mock_session = MagicMock()

    created_log = create_fetch_log(
        session=mock_session,
        dataset_id="F-C0032-005",
        status="success",
        records_count=330,
        error_message=None,
    )

    assert mock_session.add.called
    assert mock_session.flush.called
    added_obj = mock_session.add.call_args[0][0]
    assert isinstance(added_obj, FetchLog)
    assert added_obj.dataset_id == "F-C0032-005"
    assert added_obj.status == "success"
    assert added_obj.records_count == 330
    assert added_obj.error_message is None
    assert added_obj.fetched_at.tzinfo == timezone.utc

    # Test get_latest_fetch_log
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = created_log
    mock_session.execute.return_value = mock_result

    latest = get_latest_fetch_log(mock_session, dataset_id="F-C0032-005")
    assert latest is created_log

    stmt = mock_session.execute.call_args[0][0]
    compiled = str(stmt.compile())
    assert "WHERE fetch_logs.dataset_id = :dataset_id_1" in compiled
    assert "ORDER BY fetch_logs.fetched_at DESC, fetch_logs.id DESC" in compiled
    assert "LIMIT :param_1" in compiled


def test_transaction_rollback_and_error_behavior():
    """Verify atomic transaction rollback and failure log on persistence error."""
    records = [
        {
            "dataset_id": "F-C0032-005",
            "region_name": "臺北市",
            "start_time": "2026-10-04T06:00:00+08:00",
            "end_time": "2026-10-04T18:00:00+08:00",
            "weather": "晴",
            "min_temp": 24,
            "max_temp": 28,
        }
    ]

    mock_session = MagicMock()
    # Simulate database commit error
    mock_session.commit.side_effect = [Exception("Database connection terminated"), None]

    with patch("scripts.fetch_weather.SessionLocal", return_value=mock_session):
        with pytest.raises(RuntimeError, match="Database transaction failed"):
            save_to_database(records, dataset_id="F-C0032-005")

    # Verify rollback was called for failed transaction
    assert mock_session.rollback.called
    # Verify session was closed in finally
    assert mock_session.close.called


def test_security_sanitization_of_error_message():
    """Verify that credentials, database URLs, and API keys are redacted from error logs."""
    fake_key = "MY_SUPER_SECRET_KEY_123"
    fake_db_url = "postgresql+psycopg://postgres:secret_pass_456@db.supabase.co:5432/postgres"

    with patch("scripts.fetch_weather.get_settings") as mock_settings:
        mock_settings.return_value.cwa_api_key = fake_key
        mock_settings.return_value.database_url = fake_db_url

        raw_exc = Exception(f"Failed to connect to {fake_db_url} using key {fake_key}")
        sanitized = sanitize_error(raw_exc)

        assert fake_key not in sanitized
        assert "secret_pass_456" not in sanitized
        assert "[REDACTED_API_KEY]" in sanitized
        assert "[REDACTED_DATABASE_URL]" in sanitized


def test_database_cached_engine_and_session_factory():
    """Verify cached engine and session factory in app.db.database."""
    from app.db.database import get_engine, get_session_factory, SessionLocal, get_db

    with patch("app.db.database.get_settings") as mock_settings:
        mock_settings.return_value.database_url = "sqlite:///:memory:"
        # Reset globals for isolation
        with patch("app.db.database._engine", None), patch("app.db.database._session_factory", None):
            engine1 = get_engine()
            engine2 = get_engine()
            assert engine1 is engine2

            factory1 = get_session_factory()
            factory2 = get_session_factory()
            assert factory1 is factory2

            session = SessionLocal()
            assert session is not None
            session.close()

            # Test get_db generator
            gen = get_db()
            yielded_db = next(gen)
            assert yielded_db is not None
            with pytest.raises(StopIteration):
                next(gen)


def test_database_engine_transaction_pooler_configuration():
    """Verify that get_engine configures NullPool, pool_pre_ping, and prepare_threshold=None for Transaction Pooler."""
    from sqlalchemy.pool import NullPool
    from app.db.database import get_engine

    with patch("app.db.database.get_settings") as mock_settings, \
         patch("app.db.database.create_engine") as mock_create_engine, \
         patch("app.db.database._engine", None):

        mock_settings.return_value.database_url = "postgresql+psycopg://user:pass@host:6543/postgres"

        get_engine()

        assert mock_create_engine.called
        call_args, call_kwargs = mock_create_engine.call_args
        assert call_args[0] == "postgresql+psycopg://user:pass@host:6543/postgres"
        assert call_kwargs.get("poolclass") is NullPool
        assert call_kwargs.get("pool_pre_ping") is True
        assert call_kwargs.get("connect_args") == {"prepare_threshold": None}

