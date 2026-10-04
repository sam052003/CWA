/**
 * CWA Taiwan Weather Forecast — Client Application
 * Phase 7A: Taiwan County Weather Map (Leaflet GIS Dashboard)
 */

// Global state holders
let temperatureChartInstance = null;
let forecastAbortController = null;
let leafletMap = null;
let geojsonLayer = null;
let mapDataCache = null;
let currentMapPeriod = null;
let selectedCountyName = null;
let activeTooltipLayer = null;
let hoveredCountyLayer = null;
const countyLayersByName = new Map();

// DOM Element References
const elements = {
    regionSelect: document.getElementById("region-select"),
    selectedRegionName: document.getElementById("selected-region-name"),
    loadingState: document.getElementById("loading-state"),
    loadingText: document.getElementById("loading-text"),
    errorState: document.getElementById("error-state"),
    errorText: document.getElementById("error-text"),
    weatherContent: document.getElementById("weather-content"),
    summaryPeriod: document.getElementById("summary-period"),
    cardWeather: document.getElementById("card-weather"),
    cardMinTemp: document.getElementById("card-min-temp"),
    cardMaxTemp: document.getElementById("card-max-temp"),
    chartCanvas: document.getElementById("temperature-chart"),
    tableBody: document.getElementById("forecast-table-body"),
    lastUpdated: document.getElementById("last-updated"),
    taiwanMap: document.getElementById("taiwan-map"),
    mapError: document.getElementById("map-error"),
    mapPeriodBadge: document.getElementById("map-period-badge"),
};

// ---------------------------------------------------------------------------
// Helpers: Date & Time Formatting (Pure string extraction preserves +08:00)
// ---------------------------------------------------------------------------

/**
 * Format ISO 8601 string to 'MM/DD HH:mm'.
 * Avoids browser timezone shift by parsing ISO components directly.
 * @param {string} isoString e.g. "2026-10-04T06:00:00+08:00"
 * @returns {string} e.g. "10/04 06:00"
 */
function formatShortDateTime(isoString) {
    if (!isoString || typeof isoString !== "string") return "--";
    const m = isoString.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
    if (!m) return isoString;
    return `${m[2]}/${m[3]} ${m[4]}:${m[5]}`;
}

/**
 * Format forecast interval to readable string.
 * @param {string} startStr e.g. "2026-10-04T06:00:00+08:00"
 * @param {string} endStr e.g. "2026-10-04T18:00:00+08:00"
 * @returns {string} e.g. "10/04 06:00 ～ 10/04 18:00"
 */
function formatForecastPeriod(startStr, endStr) {
    const startFormatted = formatShortDateTime(startStr);
    const endFormatted = formatShortDateTime(endStr);
    return `${startFormatted} ～ ${endFormatted}`;
}

/**
 * Format updated_at timestamp to 'YYYY/MM/DD HH:mm'.
 * @param {string} isoString e.g. "2026-10-04T00:30:00+08:00"
 * @returns {string} e.g. "2026/10/04 00:30"
 */
function formatUpdatedTimestamp(isoString) {
    if (!isoString || typeof isoString !== "string") return "--";
    const m = isoString.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
    if (!m) return isoString;
    return `${m[1]}/${m[2]}/${m[3]} ${m[4]}:${m[5]}`;
}

// ---------------------------------------------------------------------------
// UI State Management (Loading & Error Handling)
// ---------------------------------------------------------------------------

function setLoading(isLoading, message = "正在載入天氣資料...") {
    if (isLoading) {
        elements.loadingText.textContent = message;
        elements.loadingState.classList.remove("hidden");
        clearError();
    } else {
        elements.loadingState.classList.add("hidden");
    }
}

function showError(message = "目前無法取得天氣資料，請稍後再試。") {
    elements.errorText.textContent = message;
    elements.errorState.classList.remove("hidden");
    setLoading(false);
}

function clearError() {
    elements.errorState.classList.add("hidden");
    elements.errorText.textContent = "";
}

function showMapError(message = "地圖資料暫時無法載入") {
    if (elements.mapError) {
        elements.mapError.textContent = message;
        elements.mapError.classList.remove("hidden");
    }
}

// ---------------------------------------------------------------------------
// Map & Choropleth Logic (Leaflet 1.9.4 + Taiwan Counties GeoJSON)
// ---------------------------------------------------------------------------

/**
 * Map forecast max_temp to discrete palette colors.
 * Discrete ranges: <20, 20-23, 24-27, 28-31, 32-35, >=36.
 * Missing / invalid: neutral slate gray.
 */
function getTemperatureColor(temp) {
    if (temp === null || temp === undefined || isNaN(temp)) {
        return "#cbd5e1";
    }
    if (temp < 20) return "#60a5fa";
    if (temp <= 23) return "#34d399";
    if (temp <= 27) return "#facc15";
    if (temp <= 31) return "#fb923c";
    if (temp <= 35) return "#f87171";
    return "#dc2626";
}

/**
 * Retrieve forecast item for a given county in the active map period.
 */
function getForecastForCounty(countyName) {
    if (!mapDataCache || !mapDataCache.forecasts) return null;
    if (currentMapPeriod) {
        const matched = mapDataCache.forecasts.find(
            (f) =>
                f.region_name === countyName &&
                f.start_time === currentMapPeriod.start_time &&
                f.end_time === currentMapPeriod.end_time
        );
        if (matched) return matched;
    }
    return mapDataCache.forecasts.find((f) => f.region_name === countyName) || null;
}

/**
 * Determine polygon style based on county forecast and selected state.
 */
function getCountyStyle(feature) {
    const countyName = feature.properties.COUNTYNAME || feature.properties.name;
    const forecast = getForecastForCounty(countyName);
    const maxTemp = forecast ? forecast.max_temp : null;
    const isSelected = selectedCountyName && selectedCountyName === countyName;

    return {
        interactive: true,
        fillColor: getTemperatureColor(maxTemp),
        weight: isSelected ? 3.5 : 1.2,
        opacity: 1,
        color: isSelected ? "#1e3a8a" : "#475569",
        dashArray: "",
        fillOpacity: isSelected ? 0.92 : 0.78,
    };
}

/**
 * Generate secure DOM element for hover tooltip using document.createElement & textContent.
 * Prevents HTML injection of weather strings while cleanly styling weather info.
 */
function createTooltipElement(countyName) {
    const container = document.createElement("div");
    container.className = "county-tooltip";

    const countyDiv = document.createElement("div");
    countyDiv.className = "tooltip-county";
    countyDiv.textContent = countyName;
    container.appendChild(countyDiv);

    const forecast = getForecastForCounty(countyName);
    if (!forecast) {
        const noDataDiv = document.createElement("div");
        noDataDiv.className = "tooltip-weather";
        noDataDiv.textContent = "暫無預報資料";
        container.appendChild(noDataDiv);
        return container;
    }

    const weatherDiv = document.createElement("div");
    weatherDiv.className = "tooltip-weather";
    weatherDiv.textContent = forecast.weather || "未知";
    container.appendChild(weatherDiv);

    const tempsDiv = document.createElement("div");
    tempsDiv.className = "tooltip-temps";

    const minSpan = document.createElement("span");
    minSpan.className = "temp-label-cold";
    const minStr = forecast.min_temp !== null && forecast.min_temp !== undefined ? `${forecast.min_temp}°C` : "--";
    minSpan.textContent = `預測最低 ${minStr}`;
    tempsDiv.appendChild(minSpan);

    const maxSpan = document.createElement("span");
    maxSpan.className = "temp-label-warm";
    const maxStr = forecast.max_temp !== null && forecast.max_temp !== undefined ? `${forecast.max_temp}°C` : "--";
    maxSpan.textContent = `預測最高 ${maxStr}`;
    tempsDiv.appendChild(maxSpan);

    container.appendChild(tempsDiv);
    return container;
}

/**
 * Explicitly close any active county tooltip across all layers.
 * Enforces requirement that at most ONE county tooltip is visible at a time.
 */
function closeActiveTooltip() {
    if (activeTooltipLayer) {
        try {
            activeTooltipLayer.closeTooltip();
        } catch (e) {
            // ignore
        }
        activeTooltipLayer = null;
    }
    countyLayersByName.forEach((layer) => {
        if (layer && typeof layer.closeTooltip === "function") {
            try {
                if (layer.isTooltipOpen && layer.isTooltipOpen()) {
                    layer.closeTooltip();
                }
            } catch (e) {
                // ignore
            }
        }
    });
}

/**
 * Restore polygon style for a county layer.
 * If the layer is currently selected, preserves its selected highlight.
 */
function resetCountyStyle(layer) {
    if (!layer || !geojsonLayer) return;
    const countyName = layer.feature && layer.feature.properties
        ? (layer.feature.properties.COUNTYNAME || layer.feature.properties.name)
        : null;
    const isSelected = selectedCountyName && selectedCountyName === countyName;

    geojsonLayer.resetStyle(layer);

    if (isSelected) {
        layer.setStyle({
            weight: 3.5,
            color: "#1e3a8a",
            fillOpacity: 0.95,
        });
        layer.bringToFront();
    }

    const pathElement = typeof layer.getElement === "function" ? layer.getElement() : null;
    if (pathElement && countyName) {
        pathElement.dataset.countyName = countyName;
    }
}

/**
 * Shared county-selection function for both map clicks and dropdown changes.
 * 1. Closes any active tooltip.
 * 2. Updates selected county state and manages visual polygon highlights.
 * 3. Synchronizes dropdown selection.
 * 4. Immediately updates selected-region-name heading.
 * 5. Immediately updates nearest-period summary from mapDataCache.
 * 6. Loads detailed 7-day forecast via API for Chart and Table.
 *
 * @param {string} countyName Name of the county to select (e.g. "臺中市")
 * @param {Object} options Configuration options
 * @param {boolean} options.panMap Whether to gently pan the map to the selected county (default: false)
 */
function selectCounty(countyName, options = {}) {
    if (!countyName) return;

    // 1. Close any active tooltip
    closeActiveTooltip();

    const prevCounty = selectedCountyName;
    selectedCountyName = countyName;

    // 2. Remove previous selected polygon highlight
    if (prevCounty && prevCounty !== countyName && countyLayersByName.has(prevCounty) && geojsonLayer) {
        const prevLayer = countyLayersByName.get(prevCounty);
        geojsonLayer.resetStyle(prevLayer);
    }

    // 3. Highlight selected county polygon
    if (countyLayersByName.has(countyName)) {
        const targetLayer = countyLayersByName.get(countyName);
        targetLayer.setStyle({
            weight: 3.5,
            color: "#1e3a8a",
            fillOpacity: 0.95,
        });
        targetLayer.bringToFront();

        const targetPath = typeof targetLayer.getElement === "function" ? targetLayer.getElement() : null;
        if (targetPath) {
            targetPath.dataset.countyName = countyName;
        }

        // Optional gentle pan for dropdown selection without excessive zooming
        if (options.panMap && leafletMap && targetLayer.getBounds) {
            const bounds = targetLayer.getBounds();
            leafletMap.panTo(bounds.getCenter(), { animate: true });
        }
    }

    // 4. Synchronize dropdown
    if (elements.regionSelect && elements.regionSelect.value !== countyName) {
        elements.regionSelect.value = countyName;
    }

    // 5. Immediately update selected-region-name heading
    if (elements.selectedRegionName) {
        elements.selectedRegionName.textContent = countyName;
    }

    // 6. Immediately update nearest-period summary using mapDataCache for currently displayed period
    const cachedForecast = getForecastForCounty(countyName);
    if (cachedForecast) {
        updateSummary(cachedForecast);
    }

    // 7. Load detailed 7-day forecast for Chart and Table
    loadForecast(countyName);
}

/**
 * Configure hover and click interactions for each county feature.
 */
function onEachCountyFeature(feature, layer) {
    const countyName = feature.properties.COUNTYNAME || feature.properties.name;
    countyLayersByName.set(countyName, layer);

    // Bind tooltip with dynamic content
    layer.bindTooltip(() => createTooltipElement(countyName), {
        sticky: true,
        direction: "auto",
        className: "custom-leaflet-tooltip",
    });

    layer.on({
        mouseover: (e) => {
            const currentLayer = e.target;

            // 1. Close any previously opened tooltip
            closeActiveTooltip();

            // 2. Open current county tooltip
            currentLayer.setTooltipContent(createTooltipElement(countyName));
            currentLayer.openTooltip(e.latlng);
            activeTooltipLayer = currentLayer;

            // Clean up previous hover layer style if mouseout was missed during rapid movement
            if (hoveredCountyLayer && hoveredCountyLayer !== currentLayer) {
                resetCountyStyle(hoveredCountyLayer);
            }
            hoveredCountyLayer = currentLayer;

            // 3. Apply hover polygon style
            const isSelected = selectedCountyName && selectedCountyName === countyName;
            currentLayer.setStyle({
                weight: isSelected ? 3.5 : 2.5,
                color: isSelected ? "#1e3a8a" : "#0f172a",
                fillOpacity: 0.92,
            });
            currentLayer.bringToFront();

            // Maintain selected layer prominence
            if (selectedCountyName && selectedCountyName !== countyName && countyLayersByName.has(selectedCountyName)) {
                countyLayersByName.get(selectedCountyName).bringToFront();
            }
        },
        mouseout: (e) => {
            const currentLayer = e.target;

            // Explicitly close that county tooltip
            currentLayer.closeTooltip();
            if (activeTooltipLayer === currentLayer) {
                activeTooltipLayer = null;
            }

            // Restore polygon style, preserving selected-county highlight
            resetCountyStyle(currentLayer);
            if (hoveredCountyLayer === currentLayer) {
                hoveredCountyLayer = null;
            }
        },
    });
}

/**
 * Delegated pointerdown handler on stable map container #taiwan-map.
 * Intercepts user pointer interaction directly on rendered SVG county polygon paths.
 */
function handleMapCountyPointerDown(event) {
    if (!event || !event.target) return;

    // Only primary mouse button. Touch/pen pointer events remain supported.
    if (event.pointerType === "mouse" && event.button !== 0) {
        return;
    }

    const pathElement = typeof event.target.closest === "function"
        ? event.target.closest("path.leaflet-interactive[data-county-name]")
        : null;

    if (!pathElement) return;

    const countyName = pathElement.dataset?.countyName;
    if (!countyName) return;

    closeActiveTooltip();

    selectCounty(countyName, {
        panMap: false,
    });
}

/**
 * Initialize Leaflet Map with neutral OpenStreetMap basemap.
 */
function initMap() {
    if (leafletMap || !elements.taiwanMap || typeof L === "undefined") return;

    leafletMap = L.map("taiwan-map", {
        center: [23.7, 120.95],
        zoom: 7.2,
        minZoom: 6,
        maxZoom: 12,
        zoomSnap: 0.25,
        scrollWheelZoom: false, // Prevent unintentional zooming on page scroll
    });

    // Basemap: OpenStreetMap tiles with required attribution
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
        maxZoom: 18,
    }).addTo(leafletMap);

    // Map-level click and mouseout cleanup
    leafletMap.on("click", () => {
        closeActiveTooltip();
    });
    leafletMap.on("mouseout", () => {
        closeActiveTooltip();
        if (hoveredCountyLayer) {
            resetCountyStyle(hoveredCountyLayer);
            hoveredCountyLayer = null;
        }
    });

    // DOM container mouseleave and delegated pointerdown listener
    if (elements.taiwanMap) {
        elements.taiwanMap.addEventListener("mouseleave", () => {
            closeActiveTooltip();
            if (hoveredCountyLayer) {
                resetCountyStyle(hoveredCountyLayer);
                hoveredCountyLayer = null;
            }
        });

        // ONE delegated pointerdown listener on stable #taiwan-map container
        elements.taiwanMap.addEventListener("pointerdown", handleMapCountyPointerDown, true);
    }
}

// ---------------------------------------------------------------------------
// Render Functions (Secure DOM manipulation with textContent & createElement)
// ---------------------------------------------------------------------------

function updateSummary(firstForecast) {
    if (!firstForecast) {
        elements.summaryPeriod.textContent = "--";
        elements.cardWeather.textContent = "--";
        elements.cardMinTemp.textContent = "--";
        elements.cardMaxTemp.textContent = "--";
        return;
    }

    elements.summaryPeriod.textContent = formatForecastPeriod(
        firstForecast.start_time,
        firstForecast.end_time
    );
    elements.cardWeather.textContent = firstForecast.weather || "未知";
    elements.cardMinTemp.textContent =
        firstForecast.min_temp !== null && firstForecast.min_temp !== undefined
            ? `${firstForecast.min_temp} °C`
            : "--";
    elements.cardMaxTemp.textContent =
        firstForecast.max_temp !== null && firstForecast.max_temp !== undefined
            ? `${firstForecast.max_temp} °C`
            : "--";
}

function updateChart(forecasts) {
    if (!elements.chartCanvas || typeof Chart === "undefined") return;

    // Destroy existing Chart instance if present to avoid overlay duplication
    if (temperatureChartInstance) {
        temperatureChartInstance.destroy();
        temperatureChartInstance = null;
    }

    if (!forecasts || forecasts.length === 0) return;

    const labels = forecasts.map((f) => formatShortDateTime(f.start_time));
    const maxTemps = forecasts.map((f) => f.max_temp);
    const minTemps = forecasts.map((f) => f.min_temp);

    const ctx = elements.chartCanvas.getContext("2d");
    temperatureChartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "最高溫 (°C)",
                    data: maxTemps,
                    borderColor: "#ea580c",
                    backgroundColor: "rgba(234, 88, 12, 0.08)",
                    borderWidth: 2.5,
                    pointBackgroundColor: "#ea580c",
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    tension: 0.3,
                    fill: false,
                },
                {
                    label: "最低溫 (°C)",
                    data: minTemps,
                    borderColor: "#0284c7",
                    backgroundColor: "rgba(2, 132, 199, 0.08)",
                    borderWidth: 2.5,
                    pointBackgroundColor: "#0284c7",
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    tension: 0.3,
                    fill: false,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: "index",
                intersect: false,
            },
            plugins: {
                legend: {
                    position: "top",
                    labels: {
                        boxWidth: 16,
                        usePointStyle: true,
                        pointStyle: "circle",
                        font: { size: 13, weight: "600" },
                        color: "#334155",
                    },
                },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y !== null ? ctx.parsed.y + " °C" : "--"}`,
                    },
                },
            },
            scales: {
                x: {
                    grid: {
                        color: "#f1f5f9",
                    },
                    ticks: {
                        font: { size: 12 },
                        color: "#64748b",
                        maxRotation: 45,
                        minRotation: 0,
                    },
                },
                y: {
                    title: {
                        display: true,
                        text: "溫度 (°C)",
                        color: "#64748b",
                        font: { size: 12, weight: "600" },
                    },
                    grid: {
                        color: "#e2e8f0",
                    },
                    ticks: {
                        font: { size: 12 },
                        color: "#64748b",
                        stepSize: 2,
                    },
                },
            },
        },
    });
}

function updateTable(forecasts) {
    if (!elements.tableBody) return;

    // Clear existing rows
    elements.tableBody.replaceChildren();

    if (!forecasts || forecasts.length === 0) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = 4;
        td.className = "empty-table-cell";
        td.textContent = "目前無可用預報資料";
        tr.appendChild(td);
        elements.tableBody.appendChild(tr);
        return;
    }

    forecasts.forEach((f) => {
        const tr = document.createElement("tr");

        // Period column
        const tdPeriod = document.createElement("td");
        tdPeriod.textContent = formatForecastPeriod(f.start_time, f.end_time);
        tr.appendChild(tdPeriod);

        // Weather column
        const tdWeather = document.createElement("td");
        tdWeather.textContent = f.weather || "--";
        tr.appendChild(tdWeather);

        // Min temp column
        const tdMin = document.createElement("td");
        tdMin.className = "num-col temp-cold";
        tdMin.textContent = f.min_temp !== null && f.min_temp !== undefined ? `${f.min_temp}°C` : "--";
        tr.appendChild(tdMin);

        // Max temp column
        const tdMax = document.createElement("td");
        tdMax.className = "num-col temp-warm";
        tdMax.textContent = f.max_temp !== null && f.max_temp !== undefined ? `${f.max_temp}°C` : "--";
        tr.appendChild(tdMax);

        elements.tableBody.appendChild(tr);
    });
}

function updateMetadata(data) {
    if (elements.lastUpdated) {
        const timeStr = formatUpdatedTimestamp(data.updated_at);
        elements.lastUpdated.textContent = `最後資料更新：${timeStr}`;
    }
}

// ---------------------------------------------------------------------------
// Data Fetching: API Calls (GET /api/forecast, /api/map-data, /api/regions)
// ---------------------------------------------------------------------------

async function loadForecast(regionName) {
    if (!regionName) return;

    // Abort previous in-flight forecast request to prevent race conditions on rapid switching
    if (forecastAbortController) {
        forecastAbortController.abort();
    }
    forecastAbortController = new AbortController();
    const signal = forecastAbortController.signal;

    setLoading(true, `正在載入 ${regionName} 天氣預報...`);

    try {
        const encodedRegion = encodeURIComponent(regionName);
        const response = await fetch(`/api/forecast?region=${encodedRegion}`, { signal });

        if (!response.ok) {
            throw new Error(`API responded with status: ${response.status}`);
        }

        const data = await response.json();

        // Update dashboard sections
        const forecasts = data.forecasts || [];
        updateSummary(forecasts.length > 0 ? forecasts[0] : null);
        updateChart(forecasts);
        updateTable(forecasts);
        updateMetadata(data);

        setLoading(false);
    } catch (err) {
        if (err.name === "AbortError") {
            // Request was superseded by a newer selection; cancel silently without error banner
            return;
        }
        console.error("Forecast fetch error:", err);
        setLoading(false);
        showError("目前無法取得詳細天氣資料，請稍後再試。");
        // Maintain county selection state, highlight, and dropdown sync, but clear chart/table
        updateChart([]);
        updateTable([]);
    }
}

async function loadMapDataAndGeoJSON() {
    try {
        // Fetch map data and GeoJSON in parallel
        const [mapDataRes, geojsonRes] = await Promise.all([
            fetch("/api/map-data"),
            fetch("/static/data/taiwan_counties.geojson"),
        ]);

        if (!mapDataRes.ok) {
            throw new Error(`Map data failed: ${mapDataRes.status}`);
        }
        if (!geojsonRes.ok) {
            throw new Error(`GeoJSON failed: ${geojsonRes.status}`);
        }

        mapDataCache = await mapDataRes.json();
        const geojsonData = await geojsonRes.json();

        // Use the earliest / nearest active forecast period for Phase 7A default
        if (mapDataCache.periods && mapDataCache.periods.length > 0) {
            currentMapPeriod = mapDataCache.periods[0];
            if (elements.mapPeriodBadge) {
                elements.mapPeriodBadge.textContent = formatForecastPeriod(
                    currentMapPeriod.start_time,
                    currentMapPeriod.end_time
                );
            }
        }

        // Render GeoJSON choropleth layer on Leaflet map
        if (leafletMap && geojsonData) {
            if (geojsonLayer) {
                leafletMap.removeLayer(geojsonLayer);
            }

            geojsonLayer = L.geoJSON(geojsonData, {
                interactive: true,
                style: getCountyStyle,
                onEachFeature: onEachCountyFeature,
            }).addTo(leafletMap);

            // Assign data-county-name attribute to all rendered county SVG paths
            geojsonLayer.eachLayer((layer) => {
                const countyName =
                    layer.feature?.properties?.COUNTYNAME ||
                    layer.feature?.properties?.name;

                const assignElementData = (target) => {
                    const pathElement = typeof target.getElement === "function" ? target.getElement() : null;
                    if (pathElement && countyName) {
                        pathElement.dataset.countyName = countyName;
                    }
                };

                if (typeof layer.eachLayer === "function") {
                    layer.eachLayer(assignElementData);
                } else {
                    assignElementData(layer);
                }
            });

            // Fit map bounds to Taiwan
            leafletMap.fitBounds(geojsonLayer.getBounds(), {
                padding: [15, 15],
            });

            // Ensure selected county is highlighted if already chosen
            if (selectedCountyName && countyLayersByName.has(selectedCountyName)) {
                const targetLayer = countyLayersByName.get(selectedCountyName);
                targetLayer.setStyle({
                    weight: 3.5,
                    color: "#1e3a8a",
                    fillOpacity: 0.95,
                });
                targetLayer.bringToFront();
            }
        }
    } catch (err) {
        console.error("Map initialization error:", err);
        showMapError("地圖資料暫時無法載入，請查看詳細預報。");
    }
}

async function loadRegions() {
    setLoading(true, "正在載入臺灣各縣市清單...");

    try {
        const response = await fetch("/api/regions");
        if (!response.ok) {
            throw new Error(`Failed to load regions: ${response.status}`);
        }

        const data = await response.json();
        const regions = data.regions || [];

        if (regions.length === 0) {
            throw new Error("No regions available");
        }

        // Populate region select options securely
        elements.regionSelect.replaceChildren();
        regions.forEach((region) => {
            const opt = document.createElement("option");
            opt.value = region;
            opt.textContent = region;
            elements.regionSelect.appendChild(opt);
        });

        elements.regionSelect.disabled = false;

        // Default selection: If user has already made a selection, keep it; otherwise default to '臺中市'
        const initialRegion = selectedCountyName || (regions.includes("臺中市") ? "臺中市" : regions[0]);
        elements.regionSelect.value = initialRegion;

        // Trigger initial selection if not already selected
        if (!selectedCountyName) {
            selectCounty(initialRegion, { panMap: false });
        }
    } catch (err) {
        console.error("Regions load error:", err);
        elements.regionSelect.disabled = true;
        showError("無法載入縣市清單，請確認網路連線或稍後再試。");
    }
}

// ---------------------------------------------------------------------------
// Initialization on DOMContentLoaded
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", async () => {
    // 1. Initialize Leaflet map
    initMap();

    // 2. Load Map Data and GeoJSON
    await loadMapDataAndGeoJSON();

    // 3. Load Regions and initial forecast
    await loadRegions();

    // 4. Attach change event listener to region selector
    if (elements.regionSelect) {
        elements.regionSelect.addEventListener("change", (event) => {
            const selectedRegion = event.target.value;
            selectCounty(selectedRegion, { panMap: true });
        });
    }

    // 5. Invalidate map size on window resize
    window.addEventListener("resize", () => {
        if (leafletMap) {
            leafletMap.invalidateSize();
        }
    });
});
