"""Main application entrypoint for CWA Taiwan Weather Forecast."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="Taiwan Weather Forecast web application powered by Central Weather Administration (CWA) Open Data API.",
    version="0.1.0",
)

# Static directory setup
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include API router
app.include_router(api_router)


@app.get("/", summary="Root / Hello World")
def read_root():
    """Root endpoint returning welcome message and basic service information."""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "environment": settings.ENVIRONMENT,
        "status": "online",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", summary="Service health check")
def health_check():
    """Root-level health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
