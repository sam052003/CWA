"""Tests for frontend dashboard templates, static assets, and accessibility."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_html():
    """Verify GET / returns 200 OK with text/html content type."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_root_html_structure_and_components():
    """Verify GET / HTML contains all required dashboard sections and IDs."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # Header
    assert "Taiwan Weather Forecast" in html
    assert "中央氣象署一週天氣預報" in html
    assert "Data Source: Central Weather Administration (CWA)" in html

    # Region Selector & Accessibility Label
    assert 'id="region-select"' in html
    assert 'for="region-select"' in html
    assert "選擇地區" in html

    # Loading & Error Banners
    assert 'id="loading-state"' in html
    assert 'id="error-state"' in html

    # Summary Cards
    assert 'id="summary-period"' in html
    assert 'id="card-weather"' in html
    assert 'id="card-min-temp"' in html
    assert 'id="card-max-temp"' in html

    # Chart Canvas
    assert 'id="temperature-chart"' in html
    assert "<canvas" in html

    # Forecast Table
    assert "<table" in html
    assert "<thead" in html
    assert "<tbody" in html
    assert 'id="forecast-table-body"' in html
    assert "預報時間" in html
    assert "天氣現象" in html
    assert "最低溫" in html
    assert "最高溫" in html

    # Metadata & Footer
    assert 'id="last-updated"' in html
    assert "F-C0032-005" in html
    assert "https://github.com/sam052003/CWA" in html


def test_static_css_asset():
    """Verify static stylesheet is served with 200 OK and valid CSS content."""
    response = client.get("/static/css/style.css")
    assert response.status_code == 200
    assert "text/css" in response.headers.get("content-type", "") or "stylesheet" in response.text or "--primary" in response.text
    assert "--primary" in response.text
    assert ".app-container" in response.text
    assert ".chart-container" in response.text


def test_static_js_asset():
    """Verify static client script is served with 200 OK and valid JS content."""
    response = client.get("/static/js/app.js")
    assert response.status_code == 200
    assert "loadRegions" in response.text
    assert "loadForecast" in response.text
    assert "updateSummary" in response.text
    assert "updateChart" in response.text
    assert "updateTable" in response.text
    assert "encodeURIComponent" in response.text
    assert "temperatureChartInstance.destroy()" in response.text


def test_frontend_does_not_contain_secrets():
    """Verify HTML and JS do not leak sensitive credentials or internal keys."""
    html_resp = client.get("/")
    js_resp = client.get("/static/js/app.js")

    forbidden_patterns = [
        "CWA_API_KEY",
        "DATABASE_URL",
        "postgresql://",
        "postgresql+psycopg://",
        "supabase.co",
        "password",
    ]

    for pattern in forbidden_patterns:
        assert pattern not in html_resp.text
        assert pattern not in js_resp.text
