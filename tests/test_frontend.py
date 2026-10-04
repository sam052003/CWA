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


def test_dom_pointerdown_bridge_county_selection():
    """Verify DOM pointerdown bridge on #taiwan-map container handles county polygon selection via countyLayersByName."""
    response = client.get("/static/js/app.js")
    assert response.status_code == 200
    js = response.text

    # 1. handleCountyPointerDown exists
    assert "function handleCountyPointerDown(event)" in js

    # 2. taiwanMap has ONE pointerdown capture listener attached
    assert "handleCountyPointerDown" in js
    assert 'elements.taiwanMap.addEventListener(' in js
    assert '"pointerdown"' in js or "'pointerdown'" in js
    assert "handleCountyPointerDown, true" in js or "handleCountyPointerDown,\n            true" in js

    # 3. Handler matches "path.leaflet-interactive"
    assert 'path.leaflet-interactive' in js
    assert 'event.target.closest("path.leaflet-interactive")' in js

    # 4. Handler iterates countyLayersByName
    assert "countyLayersByName" in js
    assert "for (const [countyName, countyLayer] of countyLayersByName)" in js

    # 5. Handler compares countyLayer.getElement() === pathElement
    assert "countyLayer.getElement() === pathElement" in js

    # 6. Handler calls selectCounty(matchedCountyName, { panMap: false })
    assert "selectCounty(matchedCountyName, {" in js
    assert "panMap: false" in js

    # 7. Dropdown still uses selectCounty(selectedRegion, { panMap: true })
    assert "selectCounty(selectedRegion" in js
    assert "panMap: true" in js

    # 8. Leaflet mousedown county-selection handler is removed
    assert "mousedown: (e) =>" not in js
    assert "mousedown:(e)=>" not in js

    # 9. No data-county-name or dataset.countyName
    assert "data-county-name" not in js
    assert "dataset.countyName" not in js

    # 10. Hover mouseover and mouseout remain
    assert "mouseover: (e) =>" in js
    assert "mouseout: (e) =>" in js
    assert "closeActiveTooltip()" in js


def test_forecast_period_map_phase_7b():
    """Verify Phase 7B Forecast Period Map selector, shared update function, and semantics."""
    html_resp = client.get("/")
    assert html_resp.status_code == 200
    html = html_resp.text

    # A. HTML:
    # - map-period-select exists
    # - associated accessible label exists
    assert 'id="map-period-select"' in html
    assert 'for="map-period-select"' in html
    assert "預報時段" in html

    js_resp = client.get("/static/js/app.js")
    assert js_resp.status_code == 200
    js = js_resp.text

    # B. JavaScript:
    # - periods are populated from mapDataCache.periods
    assert "populatePeriodSelector" in js
    assert "elements.mapPeriodSelect" in js

    # - currentMapPeriod changes through shared function setMapPeriod
    assert "function setMapPeriod(" in js
    assert "currentMapPeriod = period" in js

    # - selector displays formatted forecast periods
    assert "formatForecastPeriod(period.start_time, period.end_time)" in js

    # - period switch redraws GeoJSON styles
    assert "geojsonLayer.setStyle(getCountyStyle)" in js

    # - selected county summary updates from getForecastForCounty()
    assert "updateSummary(getForecastForCounty(selectedCountyName))" in js

    # - selected polygon styling is preserved
    assert "selectedLayer.setStyle({" in js
    assert "selectedLayer.bringToFront()" in js

    # - no loadForecast() or fetch() inside period-switch function
    set_period_idx = js.find("function setMapPeriod(")
    assert set_period_idx != -1
    set_period_end = js.find("function selectCounty(", set_period_idx)
    set_period_body = (
        js[set_period_idx:set_period_end]
        if set_period_end != -1
        else js[set_period_idx:set_period_idx + 1500]
    )
    assert "fetch(" not in set_period_body
    assert "loadForecast(" not in set_period_body

    # C. getForecastForCounty:
    # - exact current period match is used
    # - current period missing county data returns null
    # - must NOT fall back to wrong period
    forecast_fn_idx = js.find("function getForecastForCounty(")
    assert forecast_fn_idx != -1
    forecast_fn_end = js.find("function getCountyStyle(", forecast_fn_idx)
    forecast_fn_body = js[forecast_fn_idx:forecast_fn_end]
    assert "f.start_time === currentMapPeriod.start_time" in forecast_fn_body
    assert "f.end_time === currentMapPeriod.end_time" in forecast_fn_body
    assert "|| null" in forecast_fn_body

    # loadForecast must not overwrite summary with forecasts[0]
    load_forecast_idx = js.find("async function loadForecast(")
    assert load_forecast_idx != -1
    load_forecast_end = js.find("async function loadMapDataAndGeoJSON(", load_forecast_idx)
    load_forecast_body = js[load_forecast_idx:load_forecast_end]
    assert "updateSummary(forecasts[0])" not in load_forecast_body
    assert "updateSummary(forecasts.length > 0 ? forecasts[0] : null)" not in load_forecast_body

    # D. Regression:
    # - handleCountyPointerDown still exists
    assert "function handleCountyPointerDown(event)" in js
    # - county pointer selection still routes to selectCounty()
    assert "selectCounty(matchedCountyName, {" in js
    # - dropdown selection still works
    assert "selectCounty(selectedRegion" in js
    # - mouseover/mouseout tooltip remains
    assert "mouseover: (e) =>" in js
    assert "mouseout: (e) =>" in js
    # - Chart/Table functions remain
    assert "updateChart" in js
    assert "updateTable" in js


