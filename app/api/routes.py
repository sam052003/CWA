import hmac
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    ErrorResponse,
    ForecastResponse,
    MapDataResponse,
    RefreshResponse,
    RegionsResponse,
    ShortTermForecastResponse,
    ShortTermMapDataResponse,
    ObservationResponse,
)
from app.clients.cwa_client import CWAClientError
from app.core.config import get_settings
from app.db.database import get_db
from app.services import weather_service
from app.services.weather_service import (
    ForecastNotFoundError,
    RegionNotFoundError,
    WeatherDatabaseError,
    WeatherRefreshError,
)

router = APIRouter(prefix="/api", tags=["Weather"])


@router.get("/health", summary="Health check")
def health_check():
    """Health check endpoint to verify backend service status."""
    return {
        "status": "healthy",
        "service": "CWA Taiwan Weather Forecast API",
        "version": "0.1.0",
    }


@router.get(
    "/regions",
    response_model=RegionsResponse,
    summary="List available regions",
    responses={
        503: {"model": ErrorResponse, "description": "Database service unavailable"},
    },
)
def get_regions_endpoint(session: Session = Depends(get_db)):
    """Retrieve distinct list of available regions in Taiwan."""
    try:
        regions = weather_service.list_regions(session)
        return RegionsResponse(regions=regions)
    except WeatherDatabaseError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable",
        )


@router.get(
    "/forecast",
    response_model=ForecastResponse,
    summary="Get active weather forecast for a region",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid region parameter"},
        404: {"model": ErrorResponse, "description": "Region not found or no active forecast"},
        503: {"model": ErrorResponse, "description": "Database service unavailable"},
    },
)
def get_forecast_endpoint(
    region: str = Query(..., description="Target region name, e.g. 臺中市"),
    session: Session = Depends(get_db),
):
    """Retrieve chronological active weather forecasts for the requested region."""
    if not region or not region.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Region query parameter must not be empty",
        )

    clean_region = region.strip()

    try:
        data = weather_service.get_forecast(session=session, region_name=clean_region)
        return ForecastResponse(**data)
    except RegionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region '{clean_region}' not found",
        )
    except ForecastNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active forecast found for region '{clean_region}'",
        )
    except WeatherDatabaseError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving forecast",
        )


@router.get(
    "/forecast/short-term",
    response_model=ShortTermForecastResponse,
    summary="Get 36-hour living weather forecast for a region",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid region parameter"},
        404: {"model": ErrorResponse, "description": "Region not found or no forecast"},
        502: {"model": ErrorResponse, "description": "Upstream CWA service unavailable"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def get_short_term_forecast_endpoint(
    region: str = Query(..., description="Target region name, e.g. 臺中市"),
):
    """Retrieve 36-hour rich living weather forecast (F-C0032-001) for the requested region."""
    if not region or not region.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Region query parameter must not be empty",
        )

    clean_region = region.strip()

    try:
        data = weather_service.get_short_term_forecast(region_name=clean_region)
        return ShortTermForecastResponse(**data)
    except RegionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region '{clean_region}' not found",
        )
    except ForecastNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active short-term forecast found for region '{clean_region}'",
        )
    except CWAClientError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream weather data service unavailable",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving short-term forecast",
        )


@router.get(
    "/map-data/short-term",
    response_model=ShortTermMapDataResponse,
    summary="Get active 36-hour living forecast data for Taiwan county rainfall map",
    responses={
        404: {"model": ErrorResponse, "description": "No active short-term map forecasts found"},
        502: {"model": ErrorResponse, "description": "CWA API request failed"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def get_short_term_map_data_endpoint():
    """Retrieve 36-hour rich forecasts (F-C0032-001) across all Taiwan regions for rainfall probability map."""
    try:
        data = weather_service.get_short_term_map_data()
        return ShortTermMapDataResponse(**data)
    except ForecastNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active short-term map forecasts found",
        )
    except CWAClientError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream weather data service unavailable",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving short-term map data",
        )


# ==============================================================================
# Phase 8C: Current Weather Observations Endpoint (O-A0001)
# ==============================================================================

@router.get(
    "/observations",
    response_model=ObservationResponse,
    summary="Get current weather station observations for Taiwan",
    responses={
        404: {"model": ErrorResponse, "description": "No active weather observation records found"},
        502: {"model": ErrorResponse, "description": "Upstream weather data service unavailable"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def get_observations_endpoint():
    """Retrieve current weather station observations (O-A0001) across all stations."""
    try:
        data = weather_service.get_observations()
        return ObservationResponse(**data)
    except ForecastNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active weather observation records found",
        )
    except CWAClientError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream weather data service unavailable",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving weather observations",
        )


@router.get(
    "/map-data",
    response_model=MapDataResponse,
    summary="Get active weather forecast data for Taiwan county map",
    responses={
        503: {"model": ErrorResponse, "description": "Database service unavailable"},
    },
)
def get_map_data_endpoint(session: Session = Depends(get_db)):
    """Retrieve active weather forecasts across all Taiwan regions from the latest batch."""
    try:
        data = weather_service.get_map_data(session=session)
        return MapDataResponse(**data)
    except WeatherDatabaseError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable",
        )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Refresh weather forecast data from CWA Open Data API",
    responses={
        403: {"model": ErrorResponse, "description": "Disabled in production environment"},
        502: {"model": ErrorResponse, "description": "CWA API request failed"},
        503: {"model": ErrorResponse, "description": "Database service unavailable"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def refresh_forecast_endpoint(session: Session = Depends(get_db)):
    """Trigger on-demand data refresh from CWA API and persist to PostgreSQL via UPSERT.

    Disabled in production environment (Phase 4 development only).
    """
    settings = get_settings()
    if settings.ENVIRONMENT.lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Refresh endpoint is disabled in production environment",
        )

    try:
        summary = weather_service.refresh_forecasts(session=session)
        return RefreshResponse(**summary)
    except WeatherRefreshError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch data from Central Weather Administration API",
        )
    except WeatherDatabaseError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable during refresh",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred during refresh",
        )


@router.get(
    "/cron/refresh",
    response_model=RefreshResponse,
    summary="Protected cron endpoint for scheduled forecast refresh",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        502: {"model": ErrorResponse, "description": "CWA API request failed"},
        503: {"model": ErrorResponse, "description": "Database service unavailable"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def cron_refresh_endpoint(
    authorization: Optional[str] = Header(None),
    session: Session = Depends(get_db),
):
    """Protected endpoint triggered by Vercel Cron to refresh weather forecasts.

    Requires Bearer token authentication matching the configured CRON_SECRET.
    """
    settings = get_settings()
    configured_secret = settings.CRON_SECRET

    # Fail closed: reject if CRON_SECRET is not configured or blank
    if not configured_secret or not configured_secret.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    # Validate Authorization header
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    provided_token = authorization[7:].strip()
    if not hmac.compare_digest(provided_token, configured_secret.strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    try:
        summary = weather_service.refresh_forecasts(session=session)
        return RefreshResponse(**summary)
    except WeatherRefreshError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch data from Central Weather Administration API",
        )
    except WeatherDatabaseError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable during refresh",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred during refresh",
        )

