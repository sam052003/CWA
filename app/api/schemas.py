"""Pydantic schemas for API request and response models."""

from typing import List, Optional
from pydantic import BaseModel, Field


class RegionsResponse(BaseModel):
    """Response model for /api/regions endpoint."""

    regions: List[str] = Field(..., description="List of available regions in Taiwan")


class ForecastItem(BaseModel):
    """Single forecast period data item."""

    start_time: str = Field(..., description="Forecast period start time in ISO 8601 (Asia/Taipei)")
    end_time: str = Field(..., description="Forecast period end time in ISO 8601 (Asia/Taipei)")
    weather: Optional[str] = Field(None, description="Weather description, e.g. 晴時多雲")
    min_temp: Optional[float] = Field(None, description="Minimum temperature in Celsius")
    max_temp: Optional[float] = Field(None, description="Maximum temperature in Celsius")


class ForecastResponse(BaseModel):
    """Response model for /api/forecast endpoint."""

    region: str = Field(..., description="Region name, e.g. 臺中市")
    dataset_id: str = Field(..., description="CWA Dataset ID, e.g. F-C0032-005")
    updated_at: str = Field(..., description="Last data update time in ISO 8601 (Asia/Taipei)")
    forecasts: List[ForecastItem] = Field(..., description="Chronological active forecast records")


class ShortTermForecastItem(BaseModel):
    """Single short-term 36h forecast period data item (F-C0032-001)."""

    start_time: str = Field(..., description="Forecast period start time in ISO 8601 (Asia/Taipei)")
    end_time: str = Field(..., description="Forecast period end time in ISO 8601 (Asia/Taipei)")
    weather: Optional[str] = Field(None, description="Weather description, e.g. 多雲短暫陣雨")
    weather_code: Optional[str] = Field(None, description="Weather code, e.g. 08")
    min_temp: Optional[float] = Field(None, description="Minimum temperature in Celsius")
    max_temp: Optional[float] = Field(None, description="Maximum temperature in Celsius")
    pop: Optional[int] = Field(None, description="Probability of precipitation (0-100)")
    comfort_index: Optional[str] = Field(None, description="Comfort index description, e.g. 舒適至悶熱")


class ShortTermForecastResponse(BaseModel):
    """Response model for /api/forecast/short-term endpoint."""

    region: str = Field(..., description="Region name, e.g. 臺中市")
    dataset_id: str = Field("F-C0032-001", description="CWA Dataset ID, e.g. F-C0032-001")
    updated_at: Optional[str] = Field(None, description="Data update timestamp in ISO 8601 (Asia/Taipei)")
    forecasts: List[ShortTermForecastItem] = Field(..., description="Chronological short-term forecast records")


class MapPeriodItem(BaseModel):
    """Single forecast period interval for map visualization."""

    start_time: str = Field(..., description="Forecast period start time in ISO 8601 (Asia/Taipei)")
    end_time: str = Field(..., description="Forecast period end time in ISO 8601 (Asia/Taipei)")


class MapForecastItem(BaseModel):
    """Forecast item for county map."""

    region_name: str = Field(..., description="County/City name, e.g. 臺中市")
    start_time: str = Field(..., description="Forecast period start time in ISO 8601 (Asia/Taipei)")
    end_time: str = Field(..., description="Forecast period end time in ISO 8601 (Asia/Taipei)")
    weather: Optional[str] = Field(None, description="Weather description, e.g. 多雲")
    min_temp: Optional[float] = Field(None, description="Minimum temperature in Celsius")
    max_temp: Optional[float] = Field(None, description="Maximum temperature in Celsius")


class MapDataResponse(BaseModel):
    """Response model for /api/map-data endpoint."""

    dataset_id: str = Field(..., description="CWA Dataset ID, e.g. F-C0032-005")
    updated_at: str = Field(..., description="Data update timestamp in ISO 8601 (Asia/Taipei)")
    periods: List[MapPeriodItem] = Field(..., description="Unique active forecast periods sorted chronologically")
    forecasts: List[MapForecastItem] = Field(..., description="Active forecasts across all regions sorted by start_time ASC, region_name ASC")



class RefreshResponse(BaseModel):
    """Response model for /api/refresh endpoint."""

    status: str = Field(..., description="Execution status, e.g. success")
    dataset_id: str = Field(..., description="CWA Dataset ID")
    records_count: int = Field(..., description="Number of upserted forecast records")
    regions_count: int = Field(..., description="Number of regions updated")
    updated_at: str = Field(..., description="Update timestamp in ISO 8601 (Asia/Taipei)")


class ErrorResponse(BaseModel):
    """Generic error response model."""

    detail: str = Field(..., description="Error description message")
