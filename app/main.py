"""Main application entrypoint for CWA Taiwan Weather Forecast."""

import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router

# Load environment variables from .env file if it exists
load_dotenv()

app = FastAPI(
    title="CWA Taiwan Weather Forecast",
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
        "message": "Welcome to CWA Taiwan Weather Forecast API",
        "status": "online",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", summary="Service health check")
def health_check():
    """Root-level health check endpoint."""
    return {
        "status": "healthy",
        "service": "CWA Taiwan Weather Forecast",
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
