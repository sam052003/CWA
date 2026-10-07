import email.utils
import re
import requests
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

import time
from app.clients.cwa_client import CWAClient, CWAClientError
from app.core.config import get_settings
from app.parsers.cwa_parser import (
    parse_cwa_forecast,
    parse_observation_stations,
    parse_radar_metadata_xml,
    parse_short_term_forecast,
    parse_typhoon_data,
)
from app.repositories.weather_repository import (
    create_fetch_log,
    get_active_forecasts_by_region,
    get_latest_fetch_log,
    get_map_forecasts,
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


def get_map_data(
    session: Session,
    dataset_id: str = CWAClient.DATASET_FORECAST_1WEEK,
    current_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Retrieve active forecast records across all regions for the latest batch.

    Applies the Latest Batch Rule:
    - Filters forecasts from the latest batch only.
    - Only includes active/non-expired intervals (end_time > current_time).
    - Sorts forecasts deterministically by start_time ASC, region_name ASC.
    - Derives unique sorted periods.

    Args:
        session: Active SQLAlchemy session.
        dataset_id: Target dataset ID (defaults to 'F-C0032-005').
        current_time: Optional reference time for active interval filtering.

    Returns:
        Dictionary formatted for MapDataResponse with dataset_id, updated_at, periods, and forecasts.

    Raises:
        WeatherDatabaseError: If database operation fails.
    """
    try:
        forecasts = get_map_forecasts(
            session=session,
            dataset_id=dataset_id,
            current_time=current_time,
        )
    except Exception as exc:
        raise WeatherDatabaseError(f"Database query failed for map data: {sanitize_error(exc)}") from exc

    # Determine last updated timestamp from latest successful fetch log or first forecast
    try:
        latest_log = get_latest_fetch_log(
            session=session,
            dataset_id=dataset_id,
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

    # Derive unique periods sorted chronologically
    unique_periods_map: Dict[tuple, Dict[str, str]] = {}
    for f in forecasts:
        key = (f.start_time, f.end_time)
        if key not in unique_periods_map:
            unique_periods_map[key] = {
                "start_time": to_taipei_isoformat(f.start_time),
                "end_time": to_taipei_isoformat(f.end_time),
            }

    periods = sorted(unique_periods_map.values(), key=lambda p: (p["start_time"], p["end_time"]))

    forecast_items = [
        {
            "region_name": f.region_name,
            "start_time": to_taipei_isoformat(f.start_time),
            "end_time": to_taipei_isoformat(f.end_time),
            "weather": f.weather,
            "min_temp": f.min_temp,
            "max_temp": f.max_temp,
        }
        for f in forecasts
    ]

    return {
        "dataset_id": dataset_id,
        "updated_at": updated_at,
        "periods": periods,
        "forecasts": forecast_items,
    }


# ---------------------------------------------------------------------------
# Phase 8B: Short-term 36h Living Forecast Service & In-Memory TTL Cache
# ---------------------------------------------------------------------------

VALID_TAIWAN_REGIONS = {
    "基隆市", "臺北市", "新北市", "桃園市", "新竹市", "新竹縣", "苗栗縣",
    "臺中市", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣", "臺南市",
    "高雄市", "屏東縣", "宜蘭縣", "花蓮縣", "臺東縣", "澎湖縣", "金門縣", "連江縣",
}

_short_term_cache: Dict[str, Dict[str, Any]] = {}
SHORT_TERM_CACHE_TTL_SECONDS = 900  # 15 minutes TTL

_short_term_map_cache: Dict[str, Dict[str, Any]] = {}
SHORT_TERM_MAP_CACHE_TTL_SECONDS = 900  # 15 minutes TTL

_observation_cache: Dict[str, Dict[str, Any]] = {}
OBSERVATION_CACHE_TTL_SECONDS = 600  # 10 minutes TTL

_radar_metadata_cache: Dict[str, Dict[str, Any]] = {}
RADAR_CACHE_TTL_SECONDS = 300  # 5 minutes TTL


def clear_short_term_cache() -> None:
    """Clear in-memory short-term forecast cache (used for test isolation)."""
    _short_term_cache.clear()


def clear_short_term_map_cache() -> None:
    """Clear in-memory short-term all-county map data cache (used for test isolation)."""
    _short_term_map_cache.clear()


def clear_observation_cache() -> None:
    """Clear in-memory weather station observation cache (used for test isolation)."""
    _observation_cache.clear()


def clear_radar_cache() -> None:
    """Clear in-memory radar metadata cache (used for test isolation)."""
    _radar_metadata_cache.clear()


def _to_taipei_iso(time_str: str) -> str:
    """Normalize a time string like '2026-10-05 18:00:00' to ISO 8601 with Asia/Taipei offset."""
    if not time_str:
        return time_str
    if "T" in time_str and ("+" in time_str or time_str.endswith("Z")):
        return time_str
    cleaned = time_str.replace(" ", "T")
    if "+" not in cleaned and not cleaned.endswith("Z"):
        return f"{cleaned}+08:00"
    return cleaned


def get_short_term_forecast(
    region_name: str,
    client: Optional[CWAClient] = None,
    current_time: Optional[float] = None,
) -> Dict[str, Any]:
    """Retrieve 36-hour rich county forecast (F-C0032-001) for a specific region.

    Uses an in-memory process-local best-effort TTL cache (15 min).
    Does NOT require a database session.

    Args:
        region_name: Target region name, e.g. '臺中市'.
        client: Optional CWAClient instance for dependency injection / testing.
        current_time: Optional unix timestamp float for deterministic cache testing.

    Returns:
        Dictionary formatted for ShortTermForecastResponse.

    Raises:
        RegionNotFoundError: If region_name is empty or not one of the 22 Taiwan counties.
        ForecastNotFoundError: If region has no forecast intervals in CWA response.
        CWAClientError / Exception: If upstream CWA request fails.
    """
    if not region_name or not region_name.strip():
        raise RegionNotFoundError("Region name is required")

    clean_region = region_name.strip().replace("台", "臺")
    if clean_region not in VALID_TAIWAN_REGIONS:
        raise RegionNotFoundError(f"Region '{clean_region}' not found")

    now = current_time if current_time is not None else time.time()

    # Check process-local best-effort cache
    cached_entry = _short_term_cache.get(clean_region)
    if cached_entry and cached_entry.get("expires_at", 0) > now:
        cached_data = cached_entry.get("data")
        if cached_data and cached_data.get("region") == clean_region:
            return cached_data

    # Fetch from CWA client
    if client is None:
        client = CWAClient()

    raw_data = client.fetch_forecast_36h(region_name=clean_region)

    # Parse using dedicated short-term parser
    all_records = parse_short_term_forecast(raw_data)

    # Filter for exact requested region
    region_records = [r for r in all_records if r["region_name"] == clean_region]
    if not region_records:
        raise ForecastNotFoundError(f"No active short-term forecast found for region '{clean_region}'")

    # Sort chronologically by start_time
    region_records.sort(key=lambda r: r["start_time"])

    # Determine updated_at timestamp
    updated_at_str = None
    if isinstance(raw_data, dict):
        cwa_sent = raw_data.get("cwaopendata", {}).get("sent") if isinstance(raw_data.get("cwaopendata"), dict) else None
        if cwa_sent and isinstance(cwa_sent, str):
            updated_at_str = _to_taipei_iso(cwa_sent)
    if not updated_at_str:
        updated_at_str = to_taipei_isoformat(datetime.now(timezone.utc))

    forecast_items = [
        {
            "start_time": _to_taipei_iso(r["start_time"]),
            "end_time": _to_taipei_iso(r["end_time"]),
            "weather": r["weather"],
            "weather_code": r["weather_code"],
            "min_temp": r["min_temp"],
            "max_temp": r["max_temp"],
            "pop": r["pop"],
            "comfort_index": r["comfort_index"],
        }
        for r in region_records
    ]

    response_data = {
        "region": clean_region,
        "dataset_id": "F-C0032-001",
        "updated_at": updated_at_str,
        "forecasts": forecast_items,
    }

    # Store in process-local TTL cache
    _short_term_cache[clean_region] = {
        "data": response_data,
        "expires_at": now + SHORT_TERM_CACHE_TTL_SECONDS,
    }

    return response_data


def get_short_term_map_data(
    client: Optional[CWAClient] = None,
    current_time: Optional[float] = None,
) -> Dict[str, Any]:
    """Retrieve 36-hour rich living forecasts across all Taiwan regions (F-C0032-001) for rainfall map.

    Uses an in-memory process-local best-effort TTL cache (15 min).
    Does NOT require a database session.
    Fetches the complete all-county F-C0032-001 dataset in ONE CWA request (no 22-request N+1).

    Args:
        client: Optional CWAClient instance for dependency injection / testing.
        current_time: Optional unix timestamp float for deterministic cache testing.

    Returns:
        Dictionary formatted for ShortTermMapDataResponse.

    Raises:
        ForecastNotFoundError: If no valid short-term forecast intervals exist in response.
        CWAClientError / Exception: If upstream CWA request fails.
    """
    now = current_time if current_time is not None else time.time()

    # 1. Check process-local best-effort cache
    cached_entry = _short_term_map_cache.get("all_counties")
    if cached_entry and cached_entry.get("expires_at", 0) > now:
        cached_data = cached_entry.get("data")
        if cached_data:
            return cached_data

    # 2. Fetch from CWA client without region filter (all 22 counties in 1 request)
    if client is None:
        client = CWAClient()

    raw_data = client.fetch_forecast_36h(region_name=None)

    # 3. Parse using dedicated short-term parser
    all_records = parse_short_term_forecast(raw_data)
    if not all_records:
        raise ForecastNotFoundError("No active short-term map forecasts found")

    # 4. Filter for recognized Taiwan regions if desired, allowing partial counties
    valid_records = [r for r in all_records if r.get("region_name") in VALID_TAIWAN_REGIONS]
    if not valid_records:
        valid_records = all_records

    # Format and sort deterministically: start_time ASC, region_name ASC
    formatted_records = []
    for r in valid_records:
        iso_start = _to_taipei_iso(r["start_time"])
        iso_end = _to_taipei_iso(r["end_time"])
        formatted_records.append({
            "region_name": r["region_name"],
            "start_time": iso_start,
            "end_time": iso_end,
            "weather": r.get("weather"),
            "weather_code": r.get("weather_code"),
            "min_temp": r.get("min_temp"),
            "max_temp": r.get("max_temp"),
            "pop": r.get("pop"),
            "comfort_index": r.get("comfort_index"),
        })

    formatted_records.sort(key=lambda r: (r["start_time"], r["region_name"]))

    # 5. Derive unique periods sorted chronologically
    unique_period_keys = sorted(
        list({(r["start_time"], r["end_time"]) for r in formatted_records}),
        key=lambda p: (p[0], p[1]),
    )
    periods = [
        {"start_time": p[0], "end_time": p[1]}
        for p in unique_period_keys
    ]

    # 6. Build forecast items for all available counties
    forecast_items = formatted_records

    # Determine updated_at timestamp
    updated_at_str = None
    if isinstance(raw_data, dict):
        cwa_sent = raw_data.get("cwaopendata", {}).get("sent") if isinstance(raw_data.get("cwaopendata"), dict) else None
        if cwa_sent and isinstance(cwa_sent, str):
            updated_at_str = _to_taipei_iso(cwa_sent)
    if not updated_at_str:
        updated_at_str = to_taipei_isoformat(datetime.now(timezone.utc))

    response_data = {
        "dataset_id": "F-C0032-001",
        "updated_at": updated_at_str,
        "periods": periods,
        "forecasts": forecast_items,
    }

    # 7. Cache successful result only
    _short_term_map_cache["all_counties"] = {
        "data": response_data,
        "expires_at": now + SHORT_TERM_MAP_CACHE_TTL_SECONDS,
    }

    return response_data


# ==============================================================================
# Phase 8C: Current Weather Observations Service (O-A0001)
# ==============================================================================

def get_observations(
    client: Optional[CWAClient] = None,
    current_time: Optional[float] = None,
) -> Dict[str, Any]:
    """Retrieve current weather station observations (O-A0001).

    Uses an in-memory process-local best-effort TTL cache (10 min).
    Does NOT require a database session.
    Fetches the all-station dataset in ONE CWA request.

    Args:
        client: Optional CWAClient instance for dependency injection / testing.
        current_time: Optional unix timestamp float for deterministic cache testing.

    Returns:
        Dictionary formatted for ObservationResponse.

    Raises:
        ForecastNotFoundError: If no valid station observations exist in response.
        CWAClientError / Exception: If upstream CWA request fails.
    """
    now = current_time if current_time is not None else time.time()

    # 1. Check process-local best-effort cache
    cached_entry = _observation_cache.get("all_stations")
    if cached_entry and cached_entry.get("expires_at", 0) > now:
        cached_data = cached_entry.get("data")
        if cached_data:
            return cached_data

    # 2. Fetch from CWA client
    if client is None:
        client = CWAClient()

    raw_data = client.fetch_observations()

    # 3. Parse using dedicated observation parser
    stations = parse_observation_stations(raw_data)
    if not stations:
        raise ForecastNotFoundError("No active weather observation records found")

    # Determine updated_at timestamp
    updated_at_str = None
    if isinstance(raw_data, dict):
        cwa_sent = raw_data.get("cwaopendata", {}).get("sent") if isinstance(raw_data.get("cwaopendata"), dict) else None
        if cwa_sent and isinstance(cwa_sent, str):
            updated_at_str = _to_taipei_iso(cwa_sent)

    if not updated_at_str:
        # Fall back to the LATEST valid station observation_time across all stations
        valid_times = []
        for s in stations:
            obs_time = s.get("observation_time")
            if obs_time and isinstance(obs_time, str):
                try:
                    dt = datetime.fromisoformat(obs_time)
                    valid_times.append((dt, obs_time))
                except Exception:
                    pass
        if valid_times:
            # Sort by datetime ascending; last element is the latest observation
            valid_times.sort(key=lambda item: item[0])
            updated_at_str = valid_times[-1][1]

    if not updated_at_str:
        updated_at_str = to_taipei_isoformat(datetime.now(timezone.utc))

    response_data = {
        "dataset_id": "O-A0001",
        "updated_at": updated_at_str,
        "stations": stations,
    }

    # Cache successful result only
    _observation_cache["all_stations"] = {
        "data": response_data,
        "expires_at": now + OBSERVATION_CACHE_TTL_SECONDS,
    }

    return response_data


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


# ==============================================================================
# Phase 8D: Radar Reflectivity Overlay Service (O-A0058-001)
# ==============================================================================

RADAR_DATASET_ID = "O-A0058-001"
RADAR_PRODUCT_URL = "https://cwaopendata.s3.ap-northeast-1.amazonaws.com/Observation/O-A0058-001.png"
RADAR_BOUNDS = {
    "south": 17.75,
    "west": 115.00,
    "north": 29.25,
    "east": 126.50,
}
RADAR_IMAGE_WIDTH = 3600
RADAR_IMAGE_HEIGHT = 3600


def _fetch_product_last_modified(url: str, timeout: float = 5.0) -> Optional[str]:
    """Perform server-side HTTP HEAD request against official ProductURL to read Last-Modified.

    Converts HTTP Date format to ISO 8601 string in Asia/Taipei timezone (+08:00).
    Returns None if header is missing, non-200 status, or request fails.
    """
    try:
        response = requests.head(url, timeout=timeout)
        if response.status_code == 200:
            last_mod = response.headers.get("Last-Modified")
            if last_mod:
                dt = email.utils.parsedate_to_datetime(last_mod)
                return to_taipei_isoformat(dt)
    except Exception:
        pass
    return None


def get_radar_metadata(
    client: Optional[CWAClient] = None,
    current_time: Optional[float] = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Retrieve radar reflectivity metadata (O-A0058-001) for map overlay.

    First attempts to obtain official XML metadata via CWA File API.
    If unavailable or on failure, falls back safely to official documented constants
    and reads Last-Modified via server-side HTTP HEAD for freshness.

    Uses an in-memory process-local best-effort TTL cache (5 min).
    Does NOT require a database session.
    Never caches failed requests.

    Args:
        client: Optional CWAClient instance for dependency injection / testing.
        current_time: Optional unix timestamp float for deterministic cache testing.
        force_refresh: If True, bypasses cache and performs live acquisition.

    Returns:
        Dictionary formatted for RadarMetadataResponse.

    Raises:
        WeatherServiceError: If complete inability to produce usable metadata occurs.
    """
    now = current_time if current_time is not None else time.time()

    # 1. Check in-memory process-local cache unless force_refresh
    if not force_refresh:
        cached_entry = _radar_metadata_cache.get("latest")
        if cached_entry and cached_entry.get("expires_at", 0) > now:
            cached_data = cached_entry.get("data")
            if cached_data:
                return cached_data

    # 2. Strategy A: Attempt to fetch and parse official XML metadata
    if client is None:
        client = CWAClient()

    xml_content: Optional[str] = None
    try:
        xml_content = client.fetch_radar_metadata()
    except Exception:
        xml_content = None

    if xml_content:
        try:
            parsed = parse_radar_metadata_xml(xml_content)
        except Exception:
            parsed = {}

        if parsed:
            image_url = parsed.get("product_url") or RADAR_PRODUCT_URL
            radar_time = parsed.get("radar_time")

            if all(k in parsed for k in ("south", "west", "north", "east")):
                bounds = {
                    "south": parsed["south"],
                    "west": parsed["west"],
                    "north": parsed["north"],
                    "east": parsed["east"],
                }
            else:
                bounds = dict(RADAR_BOUNDS)

            image_width = parsed.get("image_width", RADAR_IMAGE_WIDTH)
            image_height = parsed.get("image_height", RADAR_IMAGE_HEIGHT)

            if radar_time:
                time_source = "radar_datetime"
                updated_at = parsed.get("sent_time") or radar_time
            else:
                last_mod = _fetch_product_last_modified(image_url)
                if last_mod:
                    time_source = "last_modified"
                    updated_at = last_mod
                else:
                    time_source = "fallback"
                    updated_at = parsed.get("sent_time") or to_taipei_isoformat(datetime.now(timezone.utc))

            response_data = {
                "dataset_id": RADAR_DATASET_ID,
                "image_url": image_url,
                "radar_time": radar_time,
                "time_source": time_source,
                "bounds": bounds,
                "image_width": image_width,
                "image_height": image_height,
                "updated_at": updated_at,
            }

            _radar_metadata_cache["latest"] = {
                "data": response_data,
                "expires_at": now + RADAR_CACHE_TTL_SECONDS,
            }
            return response_data

    # 3. Strategy B: Safe fallback to official documented constants
    image_url = RADAR_PRODUCT_URL
    bounds = dict(RADAR_BOUNDS)
    image_width = RADAR_IMAGE_WIDTH
    image_height = RADAR_IMAGE_HEIGHT

    last_mod = _fetch_product_last_modified(RADAR_PRODUCT_URL)
    if last_mod:
        radar_time = None
        time_source = "last_modified"
        updated_at = last_mod
    else:
        radar_time = None
        time_source = "fallback"
        updated_at = to_taipei_isoformat(datetime.now(timezone.utc))

    response_data = {
        "dataset_id": RADAR_DATASET_ID,
        "image_url": image_url,
        "radar_time": radar_time,
        "time_source": time_source,
        "bounds": bounds,
        "image_width": image_width,
        "image_height": image_height,
        "updated_at": updated_at,
    }

    _radar_metadata_cache["latest"] = {
        "data": response_data,
        "expires_at": now + RADAR_CACHE_TTL_SECONDS,
    }
    return response_data


# ==============================================================================
# Phase 8E: Typhoon Center / Tropical Cyclone Track (W-C0034-005)
# ==============================================================================

TYPHOON_DATASET_ID = "W-C0034-005"
TYPHOON_ACTIVE_CACHE_TTL_SECONDS = 900.0   # 15 minutes when active cyclones exist
TYPHOON_EMPTY_CACHE_TTL_SECONDS = 3600.0   # 60 minutes when no active cyclones exist

_typhoon_cache: Dict[str, Any] = {}


def clear_typhoon_cache() -> None:
    """Clear in-memory typhoon cache (primarily for unit/integration tests)."""
    global _typhoon_cache
    _typhoon_cache.clear()


def get_typhoon_data(
    client: Optional[CWAClient] = None,
    current_time: Optional[float] = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Retrieve active tropical cyclone / typhoon tracks dataset (W-C0034-005).

    Uses an in-memory process-local best-effort TTL cache (15 min if active, 60 min if empty).
    Does NOT require a database session.
    Never caches failed requests.

    Args:
        client: Optional CWAClient instance for dependency injection / testing.
        current_time: Optional unix timestamp float for deterministic cache testing.
        force_refresh: If True, bypasses cache and performs live acquisition.

    Returns:
        Dictionary formatted for TyphoonResponse.

    Raises:
        WeatherServiceError: If upstream CWA client fails or returns unparseable content.
    """
    now = current_time if current_time is not None else time.time()

    # 1. Check in-memory cache unless force_refresh
    if not force_refresh:
        cached_entry = _typhoon_cache.get("latest")
        if cached_entry and cached_entry.get("expires_at", 0) > now:
            cached_data = cached_entry.get("data")
            if cached_data:
                return cached_data

    # 2. Fetch live data from CWA Open Data API
    if client is None:
        client = CWAClient()

    try:
        raw_data = client.fetch_typhoon_data()
    except CWAClientError as exc:
        raise WeatherServiceError(f"CWA API request for typhoon data failed: {sanitize_error(exc)}") from exc
    except Exception as exc:
        raise WeatherServiceError(f"Unexpected error while fetching typhoon data: {sanitize_error(exc)}") from exc

    # 3. Parse and normalize dataset
    try:
        parsed_data = parse_typhoon_data(raw_data)
    except Exception as exc:
        raise WeatherServiceError(f"Failed to parse typhoon dataset: {sanitize_error(exc)}") from exc

    # 4. Set appropriate TTL based on active cyclone count
    active_count = parsed_data.get("active_count", 0)
    ttl = TYPHOON_ACTIVE_CACHE_TTL_SECONDS if active_count > 0 else TYPHOON_EMPTY_CACHE_TTL_SECONDS

    _typhoon_cache["latest"] = {
        "data": parsed_data,
        "expires_at": now + ttl,
    }
    return parsed_data


class WeatherService:
    """Service class grouping weather domain operations."""

    list_regions = staticmethod(list_regions)
    get_forecast = staticmethod(get_forecast)
    get_map_data = staticmethod(get_map_data)
    get_short_term_forecast = staticmethod(get_short_term_forecast)
    clear_short_term_cache = staticmethod(clear_short_term_cache)
    get_observations = staticmethod(get_observations)
    clear_observation_cache = staticmethod(clear_observation_cache)
    get_radar_metadata = staticmethod(get_radar_metadata)
    clear_radar_cache = staticmethod(clear_radar_cache)
    get_typhoon_data = staticmethod(get_typhoon_data)
    clear_typhoon_cache = staticmethod(clear_typhoon_cache)
    refresh_forecasts = staticmethod(refresh_forecasts)
    to_taipei_isoformat = staticmethod(to_taipei_isoformat)
    sanitize_error = staticmethod(sanitize_error)

