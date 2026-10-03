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
