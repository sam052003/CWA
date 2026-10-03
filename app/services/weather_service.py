"""Weather service layer - coordinates CWA API fetching, parsing, validation, and repository persistence."""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.clients.cwa_client import CWAClient, CWAClientError
from app.core.config import get_settings
from app.parsers.cwa_parser import parse_cwa_forecast
from app.repositories.weather_repository import (
    create_fetch_log,
    get_active_forecasts_by_region,
    get_latest_fetch_log,
    get_regions,
    upsert_forecasts,
)

TAIPEI_TZ = ZoneInfo("Asia/Taipei")


# ---------------------------------------------------------------------------
# Service Exceptions
# ---------------------------------------------------------------------------

class WeatherServiceError(Exception):
    """Base exception for weather service errors."""
    pass


class RegionNotFoundError(WeatherServiceError):
    """Raised when the specified region does not exist."""
    pass


class ForecastNotFoundError(WeatherServiceError):
    """Raised when no active forecast is available for a region."""
    pass


class WeatherRefreshError(WeatherServiceError):
    """Raised when data fetching, parsing, or validation fails during refresh."""
    pass


class WeatherDatabaseError(WeatherServiceError):
    """Raised when database query or persistence encounters an error."""
    pass


# ---------------------------------------------------------------------------
# Utility Helpers
# ---------------------------------------------------------------------------

def sanitize_error(exc: Union[Exception, str]) -> str:
    """Ensure error message does not contain secrets, URLs, or database passwords."""
    msg = str(exc)
    settings = get_settings()
    if settings.cwa_api_key and settings.cwa_api_key in msg:
        msg = msg.replace(settings.cwa_api_key, "[REDACTED_API_KEY]")
    if settings.database_url and settings.database_url in msg:
        msg = msg.replace(settings.database_url, "[REDACTED_DATABASE_URL]")
    # Redact connection string or password patterns if present
    msg = re.sub(r"postgresql(?:\+\w+)?://[^\s@]+@[^\s/]+/[^\s?]+", "[REDACTED_DATABASE_URL]", msg)
    msg = re.sub(r"://[^:]+:[^@]+@", "://[REDACTED_CREDENTIALS]@", msg)
    return msg


def to_taipei_isoformat(dt: Optional[datetime]) -> Optional[str]:
    """Convert a datetime to Asia/Taipei (+08:00) timezone and return ISO 8601 string."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TAIPEI_TZ).isoformat()


# ---------------------------------------------------------------------------
# Service Functions
# ---------------------------------------------------------------------------

def list_regions(session: Session) -> List[str]:
    """Retrieve distinct list of available regions from database.

    Raises:
        WeatherDatabaseError: If database query fails.
    """
    try:
        return get_regions(session)
    except Exception as exc:
        raise WeatherDatabaseError(f"Failed to retrieve regions: {sanitize_error(exc)}") from exc


def get_forecast(
    session: Session,
    region_name: str,
    current_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Retrieve active forecast records and metadata for a specific region.

    Args:
        session: Active SQLAlchemy session.
        region_name: Region name to query (e.g. '臺中市').
        current_time: Reference timestamp for expiration check (defaults to now UTC).

    Returns:
        Dictionary formatted for ForecastResponse with Asia/Taipei timestamps.

    Raises:
        RegionNotFoundError: If region_name is not found in database.
        ForecastNotFoundError: If region exists but has no active forecasts.
        WeatherDatabaseError: If database operation fails.
    """
    if not region_name or not region_name.strip():
        raise RegionNotFoundError("Region name is required")

    clean_region = region_name.strip()

    # Verify region exists in database
    available = list_regions(session)
    if clean_region not in available:
        raise RegionNotFoundError(f"Region '{clean_region}' not found")

    try:
        forecasts = get_active_forecasts_by_region(
            session=session,
            region_name=clean_region,
            current_time=current_time,
        )
    except Exception as exc:
        raise WeatherDatabaseError(f"Database query failed: {sanitize_error(exc)}") from exc

    if not forecasts:
        raise ForecastNotFoundError(f"No active forecast found for region '{clean_region}'")

    # Determine last updated timestamp from latest successful fetch log
    try:
        latest_log = get_latest_fetch_log(
            session=session,
            dataset_id=CWAClient.DATASET_FORECAST_1WEEK,
            status="success",
        )
    except Exception:
        latest_log = None

    if latest_log and latest_log.fetched_at:
        updated_at = to_taipei_isoformat(latest_log.fetched_at)
    elif forecasts and forecasts[0].fetched_at:
        updated_at = to_taipei_isoformat(forecasts[0].fetched_at)
    else:
        updated_at = to_taipei_isoformat(datetime.now(timezone.utc))

    forecast_items = [
        {
            "start_time": to_taipei_isoformat(f.start_time),
            "end_time": to_taipei_isoformat(f.end_time),
            "weather": f.weather,
            "min_temp": f.min_temp,
            "max_temp": f.max_temp,
        }
        for f in forecasts
    ]

    return {
        "region": clean_region,
        "dataset_id": CWAClient.DATASET_FORECAST_1WEEK,
        "updated_at": updated_at,
        "forecasts": forecast_items,
    }


def _record_failure_log(
    session: Session,
    dataset_id: str,
    error_message: str,
) -> None:
    """Attempt to record a failure log in the database using a separate rollback/commit cycle.

    Swallows internal logging errors to preserve the original exception category.
    """
    try:
        session.rollback()
        create_fetch_log(
            session=session,
            dataset_id=dataset_id,
            status="failure",
            records_count=0,
            error_message=sanitize_error(error_message)[:1000],
        )
        session.commit()
    except Exception:
        try:
            session.rollback()
        except Exception:
            pass


def refresh_forecasts(
    session: Session,
    client: Optional[CWAClient] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute complete data refresh workflow from CWA API to PostgreSQL UPSERT.

    Coordinates: CWAClient -> parse_cwa_forecast -> validate -> upsert_forecasts -> fetch_log -> commit.

    Args:
        session: Active database session.
        client: Optional CWAClient instance (created if None).
        payload: Optional pre-fetched CWA JSON response dictionary. If provided,
                 network fetch from CWA API is skipped to prevent duplicate requests.

    Returns:
        Summary dictionary with counts and updated_at timestamp from the fetch log.

    Raises:
        WeatherRefreshError: If CWA request fails, parsing fails, or validation fails.
        WeatherDatabaseError: If database persistence transaction fails.
    """
    if client is None:
        client = CWAClient()

    dataset_id = getattr(client, "DATASET_FORECAST_1WEEK", "F-C0032-005")

    # Step 1: Obtain raw payload (use pre-provided payload or fetch from CWA API)
    if payload is not None:
        data = payload
    else:
        try:
            data = client.fetch_forecast_1week()
        except CWAClientError as exc:
            err_msg = f"CWA API request failed: {sanitize_error(exc)}"
            _record_failure_log(session=session, dataset_id=dataset_id, error_message=err_msg)
            raise WeatherRefreshError(err_msg) from exc
        except Exception as exc:
            err_msg = f"Unexpected error during CWA fetch: {sanitize_error(exc)}"
            _record_failure_log(session=session, dataset_id=dataset_id, error_message=err_msg)
            raise WeatherRefreshError(err_msg) from exc

    # Step 2: Parse raw JSON into structured forecast records
    try:
        parsed_records = parse_cwa_forecast(data)
    except Exception as exc:
        err_msg = f"Failed to parse CWA payload: {sanitize_error(exc)}"
        _record_failure_log(session=session, dataset_id=dataset_id, error_message=err_msg)
        raise WeatherRefreshError(err_msg) from exc

    # Step 3: Validate parsed records
    if not parsed_records:
        err_msg = "No valid forecast records parsed from CWA response"
        _record_failure_log(session=session, dataset_id=dataset_id, error_message=err_msg)
        raise WeatherRefreshError(err_msg)

    distinct_regions = sorted(set(r["region_name"] for r in parsed_records))
    if len(distinct_regions) != 22:
        err_msg = f"Validation failed: expected 22 regions from CWA API, got {len(distinct_regions)}"
        _record_failure_log(session=session, dataset_id=dataset_id, error_message=err_msg)
        raise WeatherRefreshError(err_msg)

    required_fields = ("dataset_id", "region_name", "start_time", "end_time", "weather", "min_temp", "max_temp")
    for idx, r in enumerate(parsed_records):
        for f in required_fields:
            if r.get(f) is None:
                err_msg = f"Validation failed: record {idx} missing required field '{f}'"
                _record_failure_log(session=session, dataset_id=dataset_id, error_message=err_msg)
                raise WeatherRefreshError(err_msg)

    # Step 4: Persist via UPSERT in an atomic transaction
    try:
        upserted_count = upsert_forecasts(session, parsed_records)
        success_log = create_fetch_log(
            session=session,
            dataset_id=dataset_id,
            status="success",
            records_count=upserted_count,
            error_message=None,
        )
        session.commit()
    except Exception as exc:
        sanitized_msg = sanitize_error(exc)
        _record_failure_log(session=session, dataset_id=dataset_id, error_message=sanitized_msg)
        raise WeatherDatabaseError(f"Database transaction failed during refresh: {sanitized_msg}") from exc

    # Step 5: Format updated_at using actual success fetch_log timestamp
    fetched_at = getattr(success_log, "fetched_at", None)
    if isinstance(fetched_at, datetime):
        updated_at = to_taipei_isoformat(fetched_at)
    else:
        updated_at = to_taipei_isoformat(datetime.now(timezone.utc))
    return {
        "status": "success",
        "dataset_id": dataset_id,
        "records_count": upserted_count,
        "regions_count": len(distinct_regions),
        "updated_at": updated_at,
    }


class WeatherService:
    """Service class grouping weather domain operations."""

    list_regions = staticmethod(list_regions)
    get_forecast = staticmethod(get_forecast)
    refresh_forecasts = staticmethod(refresh_forecasts)
    to_taipei_isoformat = staticmethod(to_taipei_isoformat)
    sanitize_error = staticmethod(sanitize_error)
