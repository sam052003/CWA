"""Weather repository layer - handles SQL queries and database operations for forecasts and logs.

Provides PostgreSQL UPSERT for forecast records, query methods by region,
and execution logging for CWA data fetching pipeline.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import FetchLog, WeatherForecast


def to_timezone_aware_datetime(val: Union[str, datetime]) -> datetime:
    """Convert an ISO 8601 string or existing datetime to a timezone-aware datetime.

    Preserves timezone information (e.g. +08:00) and never drops it.
    Raises:
        ValueError: If the datetime is naive (missing timezone information).
        TypeError: If the input is not a string or datetime.
    """
    if isinstance(val, datetime):
        if val.tzinfo is None:
            raise ValueError(f"Datetime '{val}' is naive; timezone information is required.")
        return val
    elif isinstance(val, str):
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            raise ValueError(f"Datetime string '{val}' is naive; timezone information is required.")
        return dt
    else:
        raise TypeError(f"Expected str or datetime, got {type(val).__name__}")


def prepare_forecast_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform parser records into database-ready dictionaries with timezone-aware datetimes."""
    now_utc = datetime.now(timezone.utc)
    prepared: List[Dict[str, Any]] = []

    for r in records:
        prepared.append({
            "dataset_id": str(r["dataset_id"]),
            "region_name": str(r["region_name"]),
            "start_time": to_timezone_aware_datetime(r["start_time"]),
            "end_time": to_timezone_aware_datetime(r["end_time"]),
            "weather": r.get("weather"),
            "min_temp": float(r["min_temp"]) if r.get("min_temp") is not None else None,
            "max_temp": float(r["max_temp"]) if r.get("max_temp") is not None else None,
            "fetched_at": r.get("fetched_at") if r.get("fetched_at") is not None else now_utc,
        })

    return prepared


def upsert_forecasts(session: Session, records: List[Dict[str, Any]]) -> int:
    """Upsert forecast records into weather_forecasts table using PostgreSQL ON CONFLICT.

    Conflict target:
        (dataset_id, region_name, start_time, end_time)

    Updates on conflict:
        - weather
        - min_temp
        - max_temp
        - fetched_at

    Ensures that re-running the fetch pipeline updates existing intervals rather than
    creating duplicate rows.

    Args:
        session: Active SQLAlchemy database session.
        records: List of forecast dictionaries from CWAParser.

    Returns:
        The count of records processed.
    """
    if not records:
        return 0

    prepared_records = prepare_forecast_records(records)

    stmt = pg_insert(WeatherForecast).values(prepared_records)
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=["dataset_id", "region_name", "start_time", "end_time"],
        set_={
            "weather": stmt.excluded.weather,
            "min_temp": stmt.excluded.min_temp,
            "max_temp": stmt.excluded.max_temp,
            "fetched_at": stmt.excluded.fetched_at,
        },
    )
    session.execute(upsert_stmt)
    return len(prepared_records)


def get_regions(session: Session) -> List[str]:
    """Retrieve distinct list of region names sorted in ascending order."""
    stmt = (
        select(WeatherForecast.region_name)
        .distinct()
        .order_by(WeatherForecast.region_name.asc())
    )
    result = session.execute(stmt).scalars().all()
    return list(result)


def get_forecasts_by_region(
    session: Session,
    region_name: str,
    active_only: bool = False,
    current_time: Optional[datetime] = None,
) -> List[WeatherForecast]:
    """Retrieve forecasts for a specific region, ordered chronologically by start_time.

    Args:
        session: Active SQLAlchemy session.
        region_name: Target region name (e.g. '臺中市').
        active_only: If True, filters out expired intervals (end_time > current_time).
                     If False (default for backwards compatibility), returns all intervals.
        current_time: Reference timestamp for expiration check (defaults to current UTC time).

    Returns:
        List of WeatherForecast records ordered by start_time ascending.
    """
    stmt = select(WeatherForecast).where(WeatherForecast.region_name == region_name)
    if active_only:
        ref_time = current_time or datetime.now(timezone.utc)
        stmt = stmt.where(WeatherForecast.end_time > ref_time)
    stmt = stmt.order_by(WeatherForecast.start_time.asc())
    result = session.execute(stmt).scalars().all()
    return list(result)


def get_latest_batch_forecasts(
    session: Session,
    dataset_id: str = "F-C0032-005",
    region_name: Optional[str] = None,
    active_only: bool = True,
    current_time: Optional[datetime] = None,
) -> List[WeatherForecast]:
    """Retrieve forecast records belonging to the latest batch for a dataset.

    Applies the Latest Batch Rule:
    1. Filters by dataset_id.
    2. Identifies latest batch fetched_at via scalar subquery.
    3. Selects only rows where fetched_at matches the latest batch.
    4. If active_only is True, filters end_time > current_time (defaults to now UTC).
    5. If region_name is provided, filters for that region.
    6. Deterministic ordering:
       - If region_name: start_time ASC
       - Otherwise: start_time ASC, region_name ASC
    """
    latest_batch_subquery = (
        select(func.max(WeatherForecast.fetched_at))
        .where(WeatherForecast.dataset_id == dataset_id)
        .scalar_subquery()
    )

    stmt = select(WeatherForecast).where(
        WeatherForecast.dataset_id == dataset_id,
        WeatherForecast.fetched_at == latest_batch_subquery,
    )

    if region_name:
        stmt = stmt.where(WeatherForecast.region_name == region_name)

    if active_only:
        ref_time = current_time or datetime.now(timezone.utc)
        stmt = stmt.where(WeatherForecast.end_time > ref_time)

    if region_name:
        stmt = stmt.order_by(WeatherForecast.start_time.asc())
    else:
        stmt = stmt.order_by(WeatherForecast.start_time.asc(), WeatherForecast.region_name.asc())

    result = session.execute(stmt).scalars().all()
    return list(result)


def get_active_forecasts_by_region(
    session: Session,
    region_name: str,
    current_time: Optional[datetime] = None,
    dataset_id: str = "F-C0032-005",
) -> List[WeatherForecast]:
    """Retrieve non-expired forecasts for a region from the latest batch only."""
    return get_latest_batch_forecasts(
        session=session,
        dataset_id=dataset_id,
        region_name=region_name,
        active_only=True,
        current_time=current_time,
    )


def get_map_forecasts(
    session: Session,
    dataset_id: str = "F-C0032-005",
    current_time: Optional[datetime] = None,
) -> List[WeatherForecast]:
    """Retrieve active forecast records across all regions from the latest batch only."""
    return get_latest_batch_forecasts(
        session=session,
        dataset_id=dataset_id,
        region_name=None,
        active_only=True,
        current_time=current_time,
    )


def create_fetch_log(
    session: Session,
    dataset_id: str,
    status: str,
    records_count: int = 0,
    error_message: Optional[str] = None,
) -> FetchLog:
    """Create and persist a fetch log entry in the database.

    Args:
        session: Active SQLAlchemy session.
        dataset_id: Dataset identifier (e.g. 'F-C0032-005').
        status: Operation outcome status ('success' or 'failure').
        records_count: Count of records parsed and upserted.
        error_message: Sanitized error description if failed.

    Returns:
        The created FetchLog instance.
    """
    log_entry = FetchLog(
        dataset_id=dataset_id,
        status=status,
        records_count=records_count,
        error_message=error_message,
        fetched_at=datetime.now(timezone.utc),
    )
    session.add(log_entry)
    session.flush()
    return log_entry


def get_latest_fetch_log(
    session: Session,
    dataset_id: Optional[str] = None,
    status: Optional[str] = None,
) -> Optional[FetchLog]:
    """Retrieve the most recent fetch log entry, optionally filtered by dataset_id and status."""
    stmt = select(FetchLog)
    if dataset_id:
        stmt = stmt.where(FetchLog.dataset_id == dataset_id)
    if status:
        stmt = stmt.where(FetchLog.status == status)
    stmt = stmt.order_by(FetchLog.fetched_at.desc(), FetchLog.id.desc()).limit(1)
    return session.execute(stmt).scalars().first()


class WeatherRepository:
    """Repository class grouping weather query and persistence operations."""

    to_timezone_aware_datetime = staticmethod(to_timezone_aware_datetime)
    prepare_forecast_records = staticmethod(prepare_forecast_records)
    upsert_forecasts = staticmethod(upsert_forecasts)
    get_regions = staticmethod(get_regions)
    get_forecasts_by_region = staticmethod(get_forecasts_by_region)
    get_latest_batch_forecasts = staticmethod(get_latest_batch_forecasts)
    get_active_forecasts_by_region = staticmethod(get_active_forecasts_by_region)
    get_map_forecasts = staticmethod(get_map_forecasts)
    create_fetch_log = staticmethod(create_fetch_log)
    get_latest_fetch_log = staticmethod(get_latest_fetch_log)
