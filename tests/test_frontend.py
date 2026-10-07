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

    # - selectCounty always calls updateSummary(cachedForecast), including null
    select_county_idx = js.find("function selectCounty(")
    assert select_county_idx != -1
    select_county_end = js.find("function onEachCountyFeature(", select_county_idx)
    select_county_body = js[select_county_idx:select_county_end]
    assert "const cachedForecast = getForecastForCounty(countyName);" in select_county_body
    assert "updateSummary(cachedForecast);" in select_county_body
    assert "if (cachedForecast)" not in select_county_body

    # - empty periods invoke populatePeriodSelector unconditionally
    load_map_idx = js.find("async function loadMapDataAndGeoJSON(")
    assert load_map_idx != -1
    load_map_end = js.find("async function loadRegions(", load_map_idx)
    load_map_body = js[load_map_idx:load_map_end]
    assert "populatePeriodSelector(mapDataCache.periods || []);" in load_map_body

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


def test_taiwan_weather_dashboard_phase_7c():
    """Verify Phase 7C Taiwan Weather Dashboard final integration and presentation hierarchy."""
    html_resp = client.get("/")
    assert html_resp.status_code == 200
    html = html_resp.text

    css_resp = client.get("/static/css/style.css")
    assert css_resp.status_code == 200
    css = css_resp.text

    js_resp = client.get("/static/js/app.js")
    assert js_resp.status_code == 200
    js = js_resp.text

    # 1. Map remains first major dashboard section in DOM hierarchy
    map_idx = html.find('id="taiwan-map"')
    chart_idx = html.find('id="temperature-chart"')
    table_idx = html.find('id="forecast-table-body"')
    assert map_idx != -1 and chart_idx != -1 and table_idx != -1
    assert map_idx < chart_idx < table_idx

    # 2. Selected county detail panel elements exist
    assert 'id="selected-region-name"' in html
    assert 'id="summary-period"' in html
    assert 'id="card-weather"' in html
    assert 'id="card-min-temp"' in html
    assert 'id="card-max-temp"' in html

    # 3. Last updated value exists in detail panel and uses existing mapDataCache.updated_at
    assert 'id="detail-last-updated"' in html
    assert "elements.detailLastUpdated" in js
    assert "mapDataCache.updated_at" in js
    assert "formatUpdatedTimestamp(mapDataCache.updated_at)" in js

    # 4. Region selector and forecast period selector remain accessible
    assert 'id="region-select"' in html
    assert 'for="region-select"' in html
    assert 'id="map-period-select"' in html
    assert 'for="map-period-select"' in html

    # 5. Chart.js canvas and forecast table remain
    assert '<canvas id="temperature-chart"' in html
    assert '<table class="forecast-table"' in html
    assert "updateChart" in js
    assert "updateTable" in js

    # 6. Regressions: handleCountyPointerDown and setMapPeriod remain
    assert "function handleCountyPointerDown(event)" in js
    assert "function setMapPeriod(" in js
    assert "currentMapPeriod = period" in js
    assert "selectCounty(matchedCountyName, {" in js

    # 7. loadForecast does not overwrite current-period summary
    load_forecast_idx = js.find("async function loadForecast(")
    assert load_forecast_idx != -1
    load_forecast_end = js.find("async function loadMapDataAndGeoJSON(", load_forecast_idx)
    load_forecast_body = js[load_forecast_idx:load_forecast_end]
    assert "updateSummary(forecasts[0])" not in load_forecast_body

    # 8. Period switching contains no fetch()
    set_period_idx = js.find("function setMapPeriod(")
    assert set_period_idx != -1
    set_period_end = js.find("function selectCounty(", set_period_idx)
    set_period_body = js[set_period_idx:set_period_end]
    assert "fetch(" not in set_period_body

    # 9. Responsive CSS contains mobile and tablet rules with map height 320-380px
    assert "@media (max-width: 960px)" in css
    assert "@media (max-width: 600px)" in css
    assert "360px" in css


def test_phase_8a_app_experience_and_map_workspace():
    """Verify Phase 8A App Experience & Map Workspace elements, scripts, controls, and regressions."""
    html_resp = client.get("/")
    assert html_resp.status_code == 200
    html = html_resp.text

    css_resp = client.get("/static/css/style.css")
    assert css_resp.status_code == 200
    css = css_resp.text

    js_resp = client.get("/static/js/app.js")
    assert js_resp.status_code == 200
    js = js_resp.text

    # 1. HTML Controls & Hierarchy
    assert 'id="theme-toggle"' in html
    assert 'id="detail-panel-toggle"' in html
    assert 'id="map-reset-view"' in html
    assert 'id="map-fullscreen-toggle"' in html
    assert 'id="region-select"' in html
    assert 'id="map-period-select"' in html

    # Canvas & Forecast table remain below map workspace in DOM hierarchy
    map_idx = html.find('id="taiwan-map"')
    chart_idx = html.find('id="temperature-chart"')
    table_idx = html.find('id="forecast-table-body"')
    assert map_idx != -1 and chart_idx != -1 and table_idx != -1
    assert map_idx < chart_idx < table_idx

    # Anti-flash theme initialization script in head before stylesheet
    theme_script_idx = html.find('localStorage.getItem("cwa_theme")')
    stylesheet_idx = html.find('href="/static/css/style.css"')
    assert theme_script_idx != -1 and stylesheet_idx != -1
    assert theme_script_idx < stylesheet_idx

    # 2. JavaScript Theme & Map Workspace Logic
    assert "cwa_theme" in js
    assert "dataset.theme" in js
    assert "prefers-color-scheme" in js
    assert "getChartTheme" in js
    assert "applyChartTheme" in js
    assert "temperatureChartInstance.update()" in js
    assert "taiwanDefaultBounds" in js
    assert "geojsonLayer.getBounds()" in js
    assert "leafletMap.fitBounds(taiwanDefaultBounds" in js
    # Verify no hardcoded bounding box in JS
    assert "[[21.8, 119.3], [25.4, 122.2]]" not in js

    # Fullscreen API & resize invalidation
    assert "requestFullscreen" in js
    assert "exitFullscreen" in js
    assert "fullscreenchange" in js
    assert "leafletMap.invalidateSize()" in js

    # Scroll wheel zoom sync
    assert "syncMapWheelZoom" in js
    assert "scrollWheelZoom" in js

    # 3. Regressions: County pointer down, period switch, and chart/table integrity
    assert "function handleCountyPointerDown(event)" in js
    assert "path.leaflet-interactive" in js
    assert "selectCounty(matchedCountyName, {" in js
    assert "function setMapPeriod(" in js

    # Period switch contains no fetch()
    set_period_idx = js.find("function setMapPeriod(")
    assert set_period_idx != -1
    set_period_end = js.find("function selectCounty(", set_period_idx)
    set_period_body = js[set_period_idx:set_period_end]
    assert "fetch(" not in set_period_body
    assert "loadForecast(" not in set_period_body

    # loadForecast does not overwrite period summary
    load_forecast_idx = js.find("async function loadForecast(")
    assert load_forecast_idx != -1
    load_forecast_end = js.find("async function loadMapDataAndGeoJSON(", load_forecast_idx)
    load_forecast_body = js[load_forecast_idx:load_forecast_end]
    assert "updateSummary(forecasts[0])" not in load_forecast_body

    # 4. CSS Dark Theme & Workspace Rules
    assert '[data-theme="dark"]' in css
    assert "--map-tile-filter" in css
    assert ".leaflet-tile-pane" in css
    assert "600px" in css  # desktop map height >= 600px
    assert "@media (max-width: 960px)" in css
    assert "position: static" in css  # detail panel becomes static on tablet/mobile
    assert "360px" in css  # mobile map height


def test_phase_8a_refinements_and_corrections():
    """Verify Phase 8A focused corrections: detail panel updated_at ownership, Chart.js live tooltip theme sync,
    fullscreen fallback, floating summary stacked layout overrides, and interaction regressions."""
    js_resp = client.get("/static/js/app.js")
    assert js_resp.status_code == 200
    js = js_resp.text

    css_resp = client.get("/static/css/style.css")
    assert css_resp.status_code == 200
    css = css_resp.text

    # 1. Detail panel updated_at ownership:
    # updateMetadata does NOT overwrite detailLastUpdated when mapDataCache.updated_at exists
    update_meta_idx = js.find("function updateMetadata(")
    assert update_meta_idx != -1
    update_meta_end = js.find("async function loadForecast(", update_meta_idx)
    update_meta_body = js[update_meta_idx:update_meta_end]

    assert "!mapDataCache || !mapDataCache.updated_at" in update_meta_body
    assert "elements.detailLastUpdated.textContent = timeStr" in update_meta_body

    # loadMapDataAndGeoJSON owns mapDataCache.updated_at detail display
    load_map_idx = js.find("async function loadMapDataAndGeoJSON(")
    assert load_map_idx != -1
    load_map_body = js[load_map_idx:load_map_idx + 1200]
    assert "if (mapDataCache.updated_at)" in load_map_body
    assert "elements.detailLastUpdated.textContent = timeStr" in load_map_body

    # 2. Complete Chart.js live theme synchronization:
    # applyChartTheme updates tooltip backgroundColor, titleColor, bodyColor safely without reload
    apply_theme_idx = js.find("function applyChartTheme(")
    assert apply_theme_idx != -1
    apply_theme_end = js.find("function updateThemeToggleUI(", apply_theme_idx)
    apply_theme_body = js[apply_theme_idx:apply_theme_end]

    assert "temperatureChartInstance.options.plugins.tooltip.backgroundColor = theme.tooltipBg" in apply_theme_body
    assert "temperatureChartInstance.options.plugins.tooltip.titleColor = theme.tooltipTitle" in apply_theme_body
    assert "temperatureChartInstance.options.plugins.tooltip.bodyColor = theme.tooltipBody" in apply_theme_body
    assert "temperatureChartInstance.update()" in apply_theme_body

    # 3. Fullscreen unsupported state handling:
    # initMapControls detects requestFullscreen or webkitRequestFullscreen; disables button with explanatory title if neither supported
    assert "const isFullscreenSupported = !!" in js
    assert "elements.mapSection.requestFullscreen ||" in js
    assert "elements.mapSection.webkitRequestFullscreen" in js
    assert "elements.mapFullscreenToggle.disabled = true" in js
    assert "此瀏覽器不支援全螢幕模式" in js

    # 4. Detail summary card overflow / layout bug fix:
    # Final CSS contains .cards-grid.vertical-cards-grid selector
    assert ".cards-grid.vertical-cards-grid" in css

    # Placed after generic .cards-grid to guarantee higher specificity override
    cards_grid_idx = css.find(".cards-grid {")
    vertical_override_idx = css.find(".cards-grid.vertical-cards-grid {")
    assert cards_grid_idx != -1
    assert vertical_override_idx != -1
    assert vertical_override_idx > cards_grid_idx

    # Selector uses flex-direction: column and grid-template-columns: none
    assert "grid-template-columns: none" in css
    # Individual summary cards remain horizontal rows
    assert ".cards-grid.vertical-cards-grid .card {" in css
    assert "flex-direction: row" in css
    assert "overflow-wrap: anywhere" in css

    # 5. Preserved interaction regressions:
    # Pointerdown bridge with path.leaflet-interactive
    assert "function handleCountyPointerDown(event)" in js
    assert "path.leaflet-interactive" in js
    assert "countyLayersByName" in js

    # Period switching contains no fetch()
    set_period_idx = js.find("function setMapPeriod(")
    assert set_period_idx != -1
    set_period_end = js.find("function selectCounty(", set_period_idx)
    set_period_body = js[set_period_idx:set_period_end]
    assert "fetch(" not in set_period_body

    # Chart and Table behavior remains intact
    assert "updateChart(forecasts)" in js
    assert "updateTable(forecasts)" in js


def test_phase_8b_short_term_forecast_frontend():
    """Verify Phase 8B 36-hour living forecast frontend elements, placement, JS logic, and responsive CSS."""
    html_resp = client.get("/")
    assert html_resp.status_code == 200
    html = html_resp.text

    css_resp = client.get("/static/css/style.css")
    assert css_resp.status_code == 200
    css = css_resp.text

    js_resp = client.get("/static/js/app.js")
    assert js_resp.status_code == 200
    js = js_resp.text

    # 1. HTML Section Hierarchy: below map workspace, before one-week chart
    map_idx = html.find('id="taiwan-map"')
    short_term_idx = html.find('id="short-term-section"')
    chart_idx = html.find('id="temperature-chart"')
    table_idx = html.find('id="forecast-table-body"')

    assert map_idx != -1 and short_term_idx != -1 and chart_idx != -1 and table_idx != -1
    assert map_idx < short_term_idx < chart_idx < table_idx

    # Section elements
    assert "今明 36 小時生活預報" in html
    assert 'id="short-term-region-badge"' in html
    assert 'id="short-term-loading"' in html
    assert 'id="short-term-error"' in html
    assert 'id="short-term-retry-btn"' in html
    assert 'id="short-term-empty"' in html
    assert 'id="short-term-cards-grid"' in html

    # 2. JavaScript logic
    assert "shortTermAbortController" in js
    assert "loadShortTermForecast(" in js
    assert "renderShortTermForecast(" in js
    assert "setShortTermLoading(" in js
    assert "setShortTermError(" in js
    assert "getWeatherIcon(" in js
    assert "/api/forecast/short-term?region=" in js

    # Dedicated abort controller cancels in-flight requests on county switch
    load_st_idx = js.find("async function loadShortTermForecast(")
    assert load_st_idx != -1
    load_st_end = js.find("async function loadForecast(", load_st_idx)
    load_st_body = js[load_st_idx:load_st_end]
    assert "shortTermAbortController.abort()" in load_st_body
    assert "shortTermAbortController = new AbortController()" in load_st_body

    # PoP and CI rendering
    assert "st-pop-value" in js
    assert "st-pop-bar-fill" in js
    assert "st-ci-value" in js

    # selectCounty triggers both 7-day and 36h short-term load
    select_county_idx = js.find("function selectCounty(")
    assert select_county_idx != -1
    select_county_end = js.find("function onEachCountyFeature(", select_county_idx)
    select_county_body = js[select_county_idx:select_county_end]
    assert "loadForecast(countyName)" in select_county_body
    assert "loadShortTermForecast(countyName)" in select_county_body

    # Period selector semantics unchanged: setMapPeriod does NOT trigger short-term forecast
    set_period_idx = js.find("function setMapPeriod(")
    assert set_period_idx != -1
    set_period_end = js.find("function selectCounty(", set_period_idx)
    set_period_body = js[set_period_idx:set_period_end]
    assert "loadShortTermForecast" not in set_period_body
    assert "fetch(" not in set_period_body

    # 3. CSS & Responsive Rules
    assert ".short-term-section" in css
    assert ".short-term-cards-grid" in css
    assert ".short-term-card" in css
    assert ".st-pop-bar-fill" in css
    assert ".st-ci-value" in css
    assert "@media (max-width: 960px)" in css
    assert "@media (max-width: 600px)" in css


def test_phase_8b_short_term_safe_dom_and_period_labels():
    """Verify renderShortTermForecast uses safe DOM construction without innerHTML interpolation,
    clamps PoP bar width, and derives friendly labels from actual timestamps instead of array index.
    """
    js_resp = client.get("/static/js/app.js")
    assert js_resp.status_code == 200
    js = js_resp.text

    # 1. Locate renderShortTermForecast function body
    render_st_idx = js.find("function renderShortTermForecast(")
    assert render_st_idx != -1
    render_st_end = js.find("async function loadShortTermForecast(", render_st_idx)
    render_st_body = js[render_st_idx:render_st_end]

    # Safe DOM construction: uses createElement, textContent, appendChild, replaceChildren
    assert "document.createElement(" in render_st_body
    assert "textContent" in render_st_body
    assert "appendChild(" in render_st_body
    assert "replaceChildren(" in render_st_body

    # No innerHTML in renderShortTermForecast
    assert "innerHTML" not in render_st_body

    # Dynamic values safely assigned via textContent
    assert "periodNameSpan.textContent = friendlyTitle" in render_st_body
    assert "periodTimeSpan.textContent = periodTime" in render_st_body
    assert "descSpan.textContent = weatherDesc" in render_st_body
    assert "tempSpan.textContent = `🌡️ ${tempStr}`" in render_st_body
    assert "popValue.textContent = popVal" in render_st_body
    assert "ciValue.textContent = ciVal" in render_st_body

    # PoP width is clamped 0-100 before assigning to style.width
    assert "Math.min(100, Math.max(0," in render_st_body
    assert "popBarFill.style.width = `${popPercent}%`" in render_st_body

    # 2. Friendly period labels derived from actual timestamps, not array index
    title_fn_idx = js.find("function getShortTermPeriodTitle(")
    assert title_fn_idx != -1
    title_fn_end = js.find("function renderShortTermForecast(", title_fn_idx)
    title_fn_body = js[title_fn_idx:title_fn_end]

    # Parses ISO components directly without browser timezone shift
    assert "match(/^(\\d{4})-(\\d{2})-(\\d{2})[T ](\\d{2}):(\\d{2})/" in title_fn_body
    # Does NOT use index === 0, index === 1, index === 2 for calendar truth
    assert "index === 0" not in title_fn_body
    assert "index === 1" not in title_fn_body
    assert "index === 2" not in title_fn_body
    # Derives friendly period based on start / end hours and dates
    assert "白天" in title_fn_body
    assert "晚上" in title_fn_body
    assert "清晨" in title_fn_body

    # 3. Phase 7 pointer bridge and map regressions remain intact
    assert "function handleCountyPointerDown(event)" in js
    assert "function setMapPeriod(" in js
    assert "function selectCounty(" in js


def test_phase_8b2_rainfall_map_mode_html():
    """Verify HTML markup contains required map mode controls, legends, and summary elements for Phase 8B2."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # Map mode controls
    assert 'class="map-mode-control"' in html
    assert 'id="map-mode-temperature"' in html
    assert 'id="map-mode-rainfall"' in html
    assert 'aria-label="地圖顯示模式"' in html

    # Legends: both temperature and rainfall legends exist
    assert 'id="map-legend"' in html
    assert 'id="rainfall-legend"' in html
    assert "降雨機率 %" in html
    assert "無資料" in html

    # Detail panel: temperature and rainfall summary groups exist
    assert 'id="temperature-summary-group"' in html
    assert 'id="rainfall-summary-group"' in html
    assert 'id="rainfall-summary-period"' in html
    assert 'id="rainfall-card-weather"' in html
    assert 'id="rainfall-card-pop"' in html
    assert 'id="rainfall-card-ci"' in html
    assert 'id="rainfall-detail-last-updated"' in html
    assert 'id="detail-last-updated"' in html


def test_phase_8b2_rainfall_map_mode_js():
    """Verify JS contains independent state variables, safe tooltip rendering,
    color scale, and separate period setters for Phase 8B2.
    """
    response = client.get("/static/js/app.js")
    assert response.status_code == 200
    js = response.text

    # 1. State variables
    assert 'currentMapMode = "temperature"' in js
    assert "shortTermMapDataCache = null" in js
    assert "currentRainfallMapPeriod = null" in js

    # 2. Key functions
    assert "function getRainfallColor(" in js
    assert "function getRainfallForecastForCounty(" in js
    assert "function setRainfallMapPeriod(" in js
    assert "function loadShortTermMapData(" in js
    assert "function setMapMode(" in js
    assert "function updateRainfallSummary(" in js

    # 3. Dedicated endpoint lazy fetch
    assert '"/api/map-data/short-term"' in js

    # 4. Period switching does NOT make network fetches
    rf_period_idx = js.find("function setRainfallMapPeriod(")
    assert rf_period_idx != -1
    rf_period_end = js.find("function selectCounty(", rf_period_idx)
    rf_period_body = js[rf_period_idx:rf_period_end]
    assert "fetch(" not in rf_period_body

    temp_period_idx = js.find("function setMapPeriod(")
    assert temp_period_idx != -1
    temp_period_end = js.find("function setRainfallMapPeriod(", temp_period_idx)
    temp_period_body = js[temp_period_idx:temp_period_end]
    assert "fetch(" not in temp_period_body

    # 5. Safe DOM tooltip rendering (no innerHTML with untrusted strings)
    tt_idx = js.find("function createTooltipElement(")
    assert tt_idx != -1
    tt_end = js.find("function closeActiveTooltip(", tt_idx)
    tt_body = js[tt_idx:tt_end]
    assert "document.createElement(" in tt_body
    assert "textContent" in tt_body
    assert "innerHTML" not in tt_body

    # 6. Selected county outline re-applied on period switch and mode switch
    assert "geojsonLayer.setStyle(getCountyStyle)" in rf_period_body
    assert "selectedLayer.bringToFront()" in rf_period_body
    assert "geojsonLayer.setStyle(getCountyStyle)" in temp_period_body
    assert "selectedLayer.bringToFront()" in temp_period_body

    # 7. Pointer bridge unchanged
    assert "function handleCountyPointerDown(event)" in js
    assert "countyLayersByName" in js


# ==============================================================================
# Phase 8C: Observation Mode Frontend Tests
# ==============================================================================

def test_phase_8c_observation_html():
    """Verify HTML markup contains all Phase 8C observation mode buttons, legends, and summary cards."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # 1. Mode Button
    assert 'id="map-mode-observations"' in html
    assert "即時觀測" in html
    assert 'aria-pressed="false"' in html

    # 2. Observation Legend
    assert 'id="observation-legend"' in html
    assert "目前氣溫 °C" in html

    # 3. Floating Detail Panel Observation Group
    assert 'id="observation-summary-group"' in html
    assert 'id="observation-summary-period"' in html
    assert 'id="observation-station-name"' in html
    assert 'id="observation-card-weather"' in html
    assert 'id="observation-card-temp"' in html
    assert 'id="observation-card-humidity"' in html
    assert 'id="observation-card-wind"' in html
    assert 'id="observation-card-pressure"' in html
    assert 'id="observation-card-precipitation"' in html
    assert 'id="observation-card-gust"' in html
    assert 'id="observation-detail-last-updated"' in html
    assert "目前觀測" in html
    assert "測站資料不代表全縣市平均" in html


def test_phase_8c_observation_js():
    """Verify JS contains observation state, safe DOM rendering, layer lifecycle, and explicit 3-way mode switching."""
    response = client.get("/static/js/app.js")
    assert response.status_code == 200
    js = response.text

    # 1. Observation State variables
    assert "observationDataCache = null" in js
    assert "selectedObservationStationId = null" in js
    assert "stationObservationLayer = null" in js
    assert "observationCanvasRenderer = null" in js

    # 2. Key observation functions
    assert "function getObservationTemperatureColor(" in js
    assert "function loadObservationData(" in js
    assert "function getOrCreateStationLayer(" in js
    assert "function renderStationMarkers(" in js
    assert "function createStationTooltip(" in js
    assert "function createStationPopup(" in js
    assert "function getDefaultStationForCounty(" in js
    assert "function updateObservationDetailPanel(" in js
    assert "function updateStationMarkerEmphasis(" in js
    assert "function selectObservationStation(" in js

    # 3. Lazy-fetch from dedicated API endpoint
    assert '"/api/observations"' in js

    # 4. Safe DOM popup construction (no innerHTML with untrusted data)
    popup_idx = js.find("function createStationPopup(")
    assert popup_idx != -1
    popup_end = js.find("function getDefaultStationForCounty(", popup_idx)
    popup_body = js[popup_idx:popup_end]
    assert "document.createElement(" in popup_body
    assert "textContent" in popup_body
    assert "innerHTML" not in popup_body

    # 5. Explicit 3-way branching in setMapMode
    set_mode_idx = js.find("async function setMapMode(mode)")
    assert set_mode_idx != -1
    set_mode_end = js.find("function updateSummary(", set_mode_idx)
    set_mode_body = js[set_mode_idx:set_mode_end]

    assert 'mode === "observations"' in set_mode_body
    assert 'mode === "rainfall"' in set_mode_body
    assert 'mode === "temperature"' in set_mode_body
    assert 'Unknown map mode requested' in set_mode_body

    # 6. Preserved Phase 7 pointer bridge
    assert "function handleCountyPointerDown(event)" in js
    assert "countyLayersByName" in js

    # 7. Clearing stale selected station when county has no station (Phase 8C correctness)
    assert "selectedObservationStationId = defaultSt ? defaultSt.station_id : null;" in js
    select_county_idx = js.find("function selectCounty(countyName, options = {})")
    assert select_county_idx != -1
    select_county_end = js.find("function resetCountyStyle(", select_county_idx)
    select_county_body = js[select_county_idx:select_county_end]

    assert "const defaultSt = getDefaultStationForCounty(countyName);" in select_county_body
    assert "selectedObservationStationId = defaultSt ? defaultSt.station_id : null;" in select_county_body
    assert "updateObservationDetailPanel(defaultSt);" in select_county_body
    assert "updateStationMarkerEmphasis();" in select_county_body


def test_phase_8c_stale_station_selection_clearing():
    """Verify that when a county has no station, selectedObservationStationId is explicitly set to null and markers update."""
    response = client.get("/static/js/app.js")
    assert response.status_code == 200
    js = response.text

    # Verify both in selectCounty and in setMapMode that null fallback is explicit
    assert "selectedObservationStationId = defaultSt ? defaultSt.station_id : null;" in js
    assert "selectedObservationStationId = null;" in js
    assert "updateStationMarkerEmphasis();" in js









