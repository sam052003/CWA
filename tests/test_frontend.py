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
    """Verify GET / HTML contains all required dashboard sections, Leaflet assets, and map elements."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # Header
    assert "Taiwan Weather Forecast" in html
    assert "中央氣象署一週天氣預報" in html
    assert "Data Source: Central Weather Administration (CWA)" in html

    # Leaflet and Chart.js External Libraries
    assert "leaflet.css" in html
    assert "leaflet.js" in html
    assert "chart.umd.min.js" in html

    # Map Container and Legend
    assert 'id="map-container"' in html
    assert 'id="taiwan-map"' in html
    assert 'id="map-legend"' in html
    assert "預測最高溫 °C" in html
    assert 'id="map-period-badge"' in html

    # Region Selector & Selected Region Heading
    assert 'id="region-select"' in html
    assert 'for="region-select"' in html
    assert "選擇地區" in html
    assert 'id="selected-region-name"' in html

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
    """Verify static stylesheet is served with 200 OK and valid GIS dashboard CSS rules."""
    response = client.get("/static/css/style.css")
    assert response.status_code == 200
    css = response.text
    assert ".dashboard-main-grid" in css
    assert ".map-container" in css
    assert ".taiwan-map" in css
    assert ".map-legend" in css
    assert ".county-tooltip" in css


def test_static_js_asset():
    """Verify static client script contains Leaflet map, GeoJSON, and sync logic."""
    response = client.get("/static/js/app.js")
    assert response.status_code == 200
    js = response.text
    assert "loadRegions" in js
    assert "loadForecast" in js
    assert "/api/map-data" in js
    assert "/static/data/taiwan_counties.geojson" in js
    assert "initMap" in js
    assert "getTemperatureColor" in js
    assert "selectCounty" in js
    assert "updateSummary" in js
    assert "updateChart" in js
    assert "updateTable" in js
    assert "temperatureChartInstance.destroy()" in js
    assert "leafletMap.invalidateSize()" in js


def test_static_geojson_asset_served():
    """Verify local taiwan_counties.geojson is served directly via static files."""
    response = client.get("/static/data/taiwan_counties.geojson")
    assert response.status_code == 200
    data = response.json()
    assert data.get("type") == "FeatureCollection"
    assert len(data.get("features", [])) == 22


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


def test_county_selection_and_tooltip_lifecycle_js():
    """Verify JS client contains explicit tooltip lifecycle, single tooltip manager, and unified county selection."""
    response = client.get("/static/js/app.js")
    assert response.status_code == 200
    js = response.text

    # 1. Explicit tooltip close behavior and single active tooltip management
    assert "closeActiveTooltip" in js
    assert "activeTooltipLayer" in js
    assert "currentLayer.closeTooltip()" in js
    assert "createTooltipElement" in js

    # 2. Secure DOM manipulation for tooltips (document.createElement & textContent)
    assert "document.createElement" in js
    assert "textContent" in js

    # 3. Selected region heading element and update
    assert "selectedRegionName" in js
    assert "elements.selectedRegionName.textContent = countyName" in js

    # 4. Map click routes through shared county-selection function
    assert "selectCounty(countyName" in js

    # 5. Dropdown routes through the same county-selection flow
    assert "selectCounty(selectedRegion" in js

    # 6. mapDataCache is used for immediate selected-region summary
    assert "getForecastForCounty(countyName)" in js
    assert "updateSummary(cachedForecast)" in js

    # 7. Existing loadForecast is still used for detailed Chart/Table
    assert "loadForecast(countyName)" in js
    assert "updateChart" in js
    assert "updateTable" in js


def test_delegated_county_polygon_click_selection():
    """Verify delegated event listener on #taiwan-map container handles county polygon selection."""
    response = client.get("/static/js/app.js")
    assert response.status_code == 200
    js = response.text

    # 1. data-county-name assignment on rendered GeoJSON paths
    assert "dataset.countyName = countyName" in js
    assert "dataset.countyName" in js

    # 2. One delegated click handler on taiwan-map container
    assert "handleMapCountyClick" in js
    assert 'elements.taiwanMap.addEventListener("click", handleMapCountyClick, true)' in js

    # 3. Event target / closest polygon detection
    assert "path.leaflet-interactive[data-county-name]" in js
    assert "event.target.closest" in js
    assert "pathElement.dataset" in js

    # 4. Click routes to selectCounty(countyName, { panMap: false })
    assert "selectCounty(countyName, {" in js
    assert "panMap: false" in js

    # 5. Existing hover mouseover/mouseout behavior remains in layer.on
    assert "mouseover: (e) =>" in js
    assert "mouseout: (e) =>" in js
    assert "closeActiveTooltip()" in js

    # 6. Dropdown still calls shared selectCounty()
    assert "selectCounty(selectedRegion" in js

    # 7. Verify old unreliable per-path code is removed
    assert "attachPathClickHandler" not in js
    assert 'layer.on("add"' not in js
    assert 'L.DomEvent.on(pathElement, "click"' not in js
    assert "click: (e) =>" not in js
    assert "click:(e)=>" not in js


