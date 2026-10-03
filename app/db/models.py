"""SQLAlchemy data models for PostgreSQL (Supabase).

Defined according to Section 7 of design.md:
- WeatherForecast (weather_forecasts table)
- FetchLog (fetch_logs table)

Will be finalized and migrated in Phase 3.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from app.db.database import Base


class WeatherForecast(Base):
    """Model representing 1-week weather forecast entries."""

    __tablename__ = "weather_forecasts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    dataset_id = Column(String(50), nullable=False)
    region_name = Column(String(50), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    weather = Column(String(100), nullable=True)
    min_temp = Column(Float, nullable=True)
    max_temp = Column(Float, nullable=True)
    fetched_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "dataset_id", "region_name", "start_time", "end_time",
            name="uq_weather_forecast"
        ),
        Index("idx_weather_region_start", "region_name", "start_time"),
    )


class FetchLog(Base):
    """Model for logging CWA API fetch operations and outcomes."""

    __tablename__ = "fetch_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    dataset_id = Column(String(50), nullable=False)
    fetched_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    status = Column(String(20), nullable=False)
    records_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
