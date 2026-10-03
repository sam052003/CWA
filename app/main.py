"""Main application entrypoint for CWA Taiwan Weather Forecast."""

from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router as api_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="Taiwan Weather Forecast web application powered by Central Weather Administration (CWA) Open Data API.",
    version="0.1.0",
)

BASE_DIR = Path(__file__).resolve().parent

# Templates setup
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Static directory setup
STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include API router
app.include_router(api_router)


@app.get("/", response_class=HTMLResponse, summary="Weather Forecast Dashboard")
def read_root(request: Request):
    """Serve the weather forecast HTML dashboard."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_name": settings.APP_NAME},
    )


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
