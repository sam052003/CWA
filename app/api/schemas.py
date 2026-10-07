from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


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


# Phase 8B2: 36-Hour Short-Term Map Data Schemas (F-C0032-001)


class ShortTermMapPeriodItem(BaseModel):
    """Single forecast period interval for short-term rainfall map visualization."""

    start_time: str = Field(..., description="Forecast period start time in ISO 8601 (Asia/Taipei)")
    end_time: str = Field(..., description="Forecast period end time in ISO 8601 (Asia/Taipei)")


class ShortTermMapForecastItem(BaseModel):
    """Forecast item for county short-term map (F-C0032-001) including PoP and CI."""

    region_name: str = Field(..., description="County/City name, e.g. 臺中市")
    start_time: str = Field(..., description="Forecast period start time in ISO 8601 (Asia/Taipei)")
    end_time: str = Field(..., description="Forecast period end time in ISO 8601 (Asia/Taipei)")
    weather: Optional[str] = Field(None, description="Weather description, e.g. 多雲短暫陣雨")
    weather_code: Optional[str] = Field(None, description="Weather code, e.g. 08")
    min_temp: Optional[float] = Field(None, description="Minimum temperature in Celsius")
    max_temp: Optional[float] = Field(None, description="Maximum temperature in Celsius")
    pop: Optional[int] = Field(None, description="Probability of precipitation (0-100)")
    comfort_index: Optional[str] = Field(None, description="Comfort index description, e.g. 舒適至悶熱")


class ShortTermMapDataResponse(BaseModel):
    """Response model for /api/map-data/short-term endpoint."""

    dataset_id: str = Field("F-C0032-001", description="CWA Dataset ID, e.g. F-C0032-001")
    updated_at: str = Field(..., description="Data update timestamp in ISO 8601 (Asia/Taipei)")
    periods: List[ShortTermMapPeriodItem] = Field(..., description="Unique active forecast periods sorted chronologically")
    forecasts: List[ShortTermMapForecastItem] = Field(..., description="Active short-term forecasts across all regions sorted by start_time ASC, region_name ASC")


# ==============================================================================
# Phase 8C: Current Weather Observations Schemas (O-A0001)
# ==============================================================================

class ObservationStationItem(BaseModel):
    """Normalized observation station data model for O-A0001."""

    station_id: str = Field(..., description="Station identifier, e.g. 467490")
    station_name: str = Field(..., description="Station Chinese name, e.g. 臺中")
    observation_time: Optional[str] = Field(None, description="Observation timestamp in ISO 8601 (Asia/Taipei)")
    county_name: Optional[str] = Field(None, description="County name, e.g. 臺中市")
    town_name: Optional[str] = Field(None, description="Township name, e.g. 北區")
    latitude: Optional[float] = Field(None, description="WGS84 latitude coordinate")
    longitude: Optional[float] = Field(None, description="WGS84 longitude coordinate")
    altitude: Optional[float] = Field(None, description="Station altitude in meters")
    weather: Optional[str] = Field(None, description="Observed weather condition description")
    temperature: Optional[float] = Field(None, description="Measured air temperature in Celsius")
    relative_humidity: Optional[float] = Field(None, description="Measured relative humidity percentage (0-100)")
    wind_direction: Optional[float] = Field(None, description="Wind direction in degrees (0-360)")
    wind_direction_text: Optional[str] = Field(None, description="Traditional compass wind direction description, e.g. 西南風")
    wind_speed: Optional[float] = Field(None, description="Wind speed in meters per second (m/s)")
    air_pressure: Optional[float] = Field(None, description="Atmospheric air pressure in hPa")
    precipitation: Optional[float] = Field(None, description="Measured precipitation in mm (or null for non-numeric/sentinel)")
    precipitation_status: Optional[str] = Field(None, description="Precipitation semantic state: trace, instrument_error, no_precipitation_6h, missing, or null")
    peak_gust_speed: Optional[float] = Field(None, description="Peak gust wind speed in m/s")


class ObservationResponse(BaseModel):
    """Response model for GET /api/observations endpoint."""

    dataset_id: str = Field("O-A0001", description="CWA Dataset ID")
    updated_at: str = Field(..., description="Observation snapshot update timestamp in ISO 8601 (Asia/Taipei)")
    stations: List[ObservationStationItem] = Field(..., description="Sorted list of weather station observations")


# ==============================================================================
# Phase 8D: Radar Reflectivity Overlay Schemas (O-A0058-001)
# ==============================================================================

class RadarBounds(BaseModel):
    """Geographical bounding box for Leaflet radar image overlay."""

    south: float = Field(..., description="Southern latitude boundary (WGS84)")
    west: float = Field(..., description="Western longitude boundary (WGS84)")
    north: float = Field(..., description="Northern latitude boundary (WGS84)")
    east: float = Field(..., description="Eastern longitude boundary (WGS84)")

    @model_validator(mode="after")
    def validate_bounds(self) -> "RadarBounds":
        if self.south >= self.north:
            raise ValueError(f"south ({self.south}) must be less than north ({self.north})")
        if self.west >= self.east:
            raise ValueError(f"west ({self.west}) must be less than east ({self.east})")
        return self


class RadarMetadataResponse(BaseModel):
    """Response model for GET /api/radar endpoint."""

    dataset_id: str = Field("O-A0058-001", description="CWA Dataset ID")
    image_url: str = Field(..., description="Direct URL of the latest radar reflectivity PNG image")
    radar_time: Optional[str] = Field(None, description="Official radar observation timestamp in ISO 8601 (Asia/Taipei)")
    time_source: str = Field(..., description="Source of timestamp: radar_datetime, last_modified, or fallback")
    bounds: RadarBounds = Field(..., description="Geographical bounding box for Leaflet overlay")
    image_width: int = Field(3600, description="Image pixel width")
    image_height: int = Field(3600, description="Image pixel height")
    updated_at: Optional[str] = Field(None, description="Metadata or file update timestamp in ISO 8601 (Asia/Taipei)")


# ==============================================================================
# Phase 8E: Typhoon Center / Tropical Cyclone Track Schemas (W-C0034-005)
# ==============================================================================

class TyphoonAnalysisPoint(BaseModel):
    """Analysis data point along the past/current track of a tropical cyclone."""

    time: Optional[str] = Field(None, description="Observation / fix timestamp in ISO 8601")
    latitude: float = Field(..., description="Latitude (WGS84, -90 to 90)")
    longitude: float = Field(..., description="Longitude (WGS84, -180 to 180)")
    max_wind_speed: Optional[float] = Field(None, description="Maximum sustained wind speed in m/s")
    max_gust_speed: Optional[float] = Field(None, description="Maximum peak gust speed in m/s")
    pressure: Optional[float] = Field(None, description="Central atmospheric pressure in hPa")
    radius_15ms: Optional[float] = Field(None, description="Radius of 15 m/s (7-level) wind circle in km")
    radius_25ms: Optional[float] = Field(None, description="Radius of 25 m/s (10-level) wind circle in km")
    quadrant_15ms: Optional[Dict[str, Optional[float]]] = Field(None, description="Quadrant radii for 15 m/s wind in km")
    quadrant_25ms: Optional[Dict[str, Optional[float]]] = Field(None, description="Quadrant radii for 25 m/s wind in km")
    movement_speed: Optional[float] = Field(None, description="Movement speed in km/h")
    movement_direction: Optional[str] = Field(None, description="Movement direction (e.g. W, WNW, NW)")
    movement_prediction: Optional[str] = Field(None, description="Movement prediction text description")


class TyphoonForecastPoint(BaseModel):
    """Forecast data point along the future track of a tropical cyclone."""

    init_time: Optional[str] = Field(None, description="Forecast base initialization time in ISO 8601")
    tau: Optional[int] = Field(None, description="Forecast lead time in hours (e.g. 6, 12, 24, 48, 72, 96, 120)")
    valid_time: Optional[str] = Field(None, description="Derived forecast valid timestamp in ISO 8601")
    latitude: float = Field(..., description="Forecast latitude (WGS84, -90 to 90)")
    longitude: float = Field(..., description="Forecast longitude (WGS84, -180 to 180)")
    max_wind_speed: Optional[float] = Field(None, description="Forecast maximum sustained wind speed in m/s")
    max_gust_speed: Optional[float] = Field(None, description="Forecast maximum peak gust speed in m/s")
    pressure: Optional[float] = Field(None, description="Forecast central pressure in hPa")
    radius_15ms: Optional[float] = Field(None, description="Forecast radius of 15 m/s wind circle in km")
    radius_25ms: Optional[float] = Field(None, description="Forecast radius of 25 m/s wind circle in km")
    probability_70_radius: Optional[float] = Field(None, description="70% probability circle radius in km")
    state_transfer: Optional[str] = Field(None, description="State transition (e.g. Extratropical, Dissipated)")


class TyphoonItem(BaseModel):
    """Normalized active tropical cyclone data item."""

    id: str = Field(..., description="Unique tropical cyclone identifier")
    year: Optional[int] = Field(None, description="Cyclone year")
    name_en: Optional[str] = Field(None, description="International English name")
    name_zh: Optional[str] = Field(None, description="CWA official Chinese name")
    cwa_td_no: Optional[str] = Field(None, description="CWA Tropical Depression number")
    cwa_ty_no: Optional[str] = Field(None, description="CWA Typhoon number")
    analysis_points: List[TyphoonAnalysisPoint] = Field(default_factory=list, description="Historical analysis track points")
    current: Optional[TyphoonAnalysisPoint] = Field(None, description="Latest analyzed cyclone center point")
    forecast_points: List[TyphoonForecastPoint] = Field(default_factory=list, description="Future forecast track points")


class TyphoonResponse(BaseModel):
    """Response model for GET /api/typhoons endpoint."""

    dataset_id: str = Field("W-C0034-005", description="CWA Dataset ID")
    updated_at: Optional[str] = Field(None, description="Dataset update timestamp in ISO 8601 (Asia/Taipei)")
    active_count: int = Field(..., description="Number of currently active tropical cyclones")
    cyclones: List[TyphoonItem] = Field(default_factory=list, description="List of active tropical cyclones")


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
