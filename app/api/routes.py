"""API routes for CWA Taiwan Weather Forecast."""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["Weather"])


@router.get("/health", summary="Health check")
def health_check():
    """Health check endpoint to verify backend service status."""
    return {
        "status": "healthy",
        "service": "CWA Taiwan Weather Forecast API",
        "version": "0.1.0",
    }


# Note: Endpoints below are reserved for Phase 4 according to design.md
# GET  /api/regions   - List available regions (Phase 4)
# GET  /api/forecast  - Query forecast by region (Phase 4)
# POST /api/refresh   - Trigger forecast update (Phase 4)
