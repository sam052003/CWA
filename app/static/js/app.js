/**
 * CWA Taiwan Weather Forecast — Client Application
 * Phase 8A: Light / Dark Theme, Map Workspace Controls, Chart.js Theme Sync
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
let taiwanDefaultBounds = null;
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
    mapPeriodSelect: document.getElementById("map-period-select"),
    detailLastUpdated: document.getElementById("detail-last-updated"),
    themeToggle: document.getElementById("theme-toggle"),
    mapResetView: document.getElementById("map-reset-view"),
    mapFullscreenToggle: document.getElementById("map-fullscreen-toggle"),
    detailPanel: document.getElementById("detail-panel"),
    detailPanelToggle: document.getElementById("detail-panel-toggle"),
    detailPanelSummaryLabel: document.getElementById("detail-panel-summary-label"),
    mapSection: document.querySelector(".map-section"),
    shortTermSection: document.getElementById("short-term-section"),
    shortTermRegionBadge: document.getElementById("short-term-region-badge"),
    shortTermLoading: document.getElementById("short-term-loading"),
    shortTermLoadingText: document.getElementById("short-term-loading-text"),
    shortTermError: document.getElementById("short-term-error"),
    shortTermErrorText: document.getElementById("short-term-error-text"),
    shortTermRetryBtn: document.getElementById("short-term-retry-btn"),
    shortTermEmpty: document.getElementById("short-term-empty"),
    shortTermCardsGrid: document.getElementById("short-term-cards-grid"),
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
// Theme Management & Chart.js Synchronization (Phase 8A)
// ---------------------------------------------------------------------------

/**
 * Return palette colors for Chart.js based on active data-theme.
 */
function getChartTheme() {
    const isDark = document.documentElement.dataset.theme === "dark";
    return {
        gridColor: isDark ? "#334155" : "#f1f5f9",
        tickColor: isDark ? "#94a3b8" : "#64748b",
        legendColor: isDark ? "#f8fafc" : "#334155",
        titleColor: isDark ? "#94a3b8" : "#64748b",
        tooltipBg: isDark ? "rgba(15, 23, 42, 0.95)" : "rgba(15, 23, 42, 0.9)",
        tooltipTitle: "#f8fafc",
        tooltipBody: "#f8fafc",
    };
}

/**
 * Dynamically synchronize Chart.js options with current theme without reloading data.
 */
function applyChartTheme() {
    if (!temperatureChartInstance) return;
    const theme = getChartTheme();

    if (temperatureChartInstance.options.scales && temperatureChartInstance.options.scales.x) {
        temperatureChartInstance.options.scales.x.grid.color = theme.gridColor;
        temperatureChartInstance.options.scales.x.ticks.color = theme.tickColor;
    }
    if (temperatureChartInstance.options.scales && temperatureChartInstance.options.scales.y) {
        temperatureChartInstance.options.scales.y.grid.color = theme.gridColor;
        temperatureChartInstance.options.scales.y.ticks.color = theme.tickColor;
        if (temperatureChartInstance.options.scales.y.title) {
            temperatureChartInstance.options.scales.y.title.color = theme.titleColor;
        }
    }
    if (
        temperatureChartInstance.options.plugins &&
        temperatureChartInstance.options.plugins.legend &&
        temperatureChartInstance.options.plugins.legend.labels
    ) {
        temperatureChartInstance.options.plugins.legend.labels.color = theme.legendColor;
    }
    if (
        temperatureChartInstance.options.plugins &&
        temperatureChartInstance.options.plugins.tooltip
    ) {
        temperatureChartInstance.options.plugins.tooltip.backgroundColor = theme.tooltipBg;
        temperatureChartInstance.options.plugins.tooltip.titleColor = theme.tooltipTitle;
        temperatureChartInstance.options.plugins.tooltip.bodyColor = theme.tooltipBody;
    }
    temperatureChartInstance.update();
}

/**
 * Update theme toggle button UI (aria attributes, title, label text).
 */
function updateThemeToggleUI(theme) {
    if (!elements.themeToggle) return;
    const isDark = theme === "dark";
    elements.themeToggle.setAttribute("aria-pressed", isDark ? "true" : "false");
    elements.themeToggle.setAttribute("aria-label", isDark ? "切換為淺色模式" : "切換為深色模式");
    elements.themeToggle.title = isDark ? "切換為淺色模式" : "切換為深色模式";
    const textSpan = elements.themeToggle.querySelector(".theme-toggle-text");
    if (textSpan) {
        textSpan.textContent = isDark ? "淺色模式" : "深色模式";
    }
}

/**
 * Switch and persist active theme.
 */
function setTheme(theme) {
    document.documentElement.dataset.theme = theme;
    try {
        localStorage.setItem("cwa_theme", theme);
    } catch (_) {}
    updateThemeToggleUI(theme);
    applyChartTheme();
}

/**
 * Initialize theme system, attach event listeners and system preference fallback.
 */
function initTheme() {
    let theme = document.documentElement.dataset.theme;
    if (!theme) {
        try {
            const stored = localStorage.getItem("cwa_theme");
            if (stored === "light" || stored === "dark") {
                theme = stored;
            }
        } catch (_) {}
        if (!theme) {
            theme = window.matchMedia &&
                window.matchMedia("(prefers-color-scheme: dark)").matches
                ? "dark"
                : "light";
        }
        document.documentElement.dataset.theme = theme;
    }

    updateThemeToggleUI(theme);

    // Follow OS preference only if user has not explicitly set preference
    if (window.matchMedia) {
        const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
        const handleChange = (e) => {
            let hasStored = false;
            try {
                const stored = localStorage.getItem("cwa_theme");
                if (stored === "light" || stored === "dark") {
                    hasStored = true;
                }
            } catch (_) {}
            if (!hasStored) {
                const sysTheme = e.matches ? "dark" : "light";
                document.documentElement.dataset.theme = sysTheme;
                updateThemeToggleUI(sysTheme);
                applyChartTheme();
            }
        };
        if (typeof mediaQuery.addEventListener === "function") {
            mediaQuery.addEventListener("change", handleChange);
        } else if (typeof mediaQuery.addListener === "function") {
            mediaQuery.addListener(handleChange);
        }
    }

    if (elements.themeToggle) {
        elements.themeToggle.addEventListener("click", () => {
            const currentTheme = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
            const newTheme = currentTheme === "dark" ? "light" : "dark";
            setTheme(newTheme);
        });
    }
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
 * If currentMapPeriod exists, only returns an exact start/end time match (no fallback to wrong period).
 */
function getForecastForCounty(countyName) {
    if (!mapDataCache || !mapDataCache.forecasts) return null;
    if (currentMapPeriod) {
        return (
            mapDataCache.forecasts.find(
                (f) =>
                    f.region_name === countyName &&
                    f.start_time === currentMapPeriod.start_time &&
                    f.end_time === currentMapPeriod.end_time
            ) || null
        );
    }
    return (
        mapDataCache.forecasts.find((f) => f.region_name === countyName) || null
    );
}

/**
 * Leaflet style function: Returns styling object based on county temperature.
 */
function getCountyStyle(feature) {
    const countyName = feature.properties.COUNTYNAME || feature.properties.name;
    const forecast = getForecastForCounty(countyName);
    const fillColor = forecast ? getTemperatureColor(forecast.max_temp) : "#cbd5e1";

    const isSelected = selectedCountyName && selectedCountyName === countyName;

    return {
        fillColor: fillColor,
        weight: isSelected ? 3.5 : 1.2,
        opacity: 1,
        color: isSelected ? "#1e3a8a" : "#ffffff",
        fillOpacity: isSelected ? 0.95 : 0.78,
    };
}

/**
 * Build rich HTML DOM element for county hover tooltip.
 */
function createTooltipElement(countyName) {
    const forecast = getForecastForCounty(countyName);

    const container = document.createElement("div");
    container.className = "county-tooltip";

    const titleEl = document.createElement("div");
    titleEl.className = "tooltip-county";
    titleEl.textContent = countyName;
    container.appendChild(titleEl);

    const weatherEl = document.createElement("div");
    weatherEl.className = "tooltip-weather";
    weatherEl.textContent = forecast ? (forecast.weather || "無資料") : "無預報資料";
    container.appendChild(weatherEl);

    const tempsEl = document.createElement("div");
    tempsEl.className = "tooltip-temps";

    const minSpan = document.createElement("span");
    minSpan.className = "temp-label-cold";
    minSpan.textContent = forecast && forecast.min_temp !== null ? `低 ${forecast.min_temp}°C` : "低 --";
    tempsEl.appendChild(minSpan);

    const maxSpan = document.createElement("span");
    maxSpan.className = "temp-label-warm";
    maxSpan.textContent = forecast && forecast.max_temp !== null ? `高 ${forecast.max_temp}°C` : "高 --";
    tempsEl.appendChild(maxSpan);

    container.appendChild(tempsEl);

    return container;
}

/**
 * Single Tooltip Manager: Closes currently active tooltip if one is open.
 */
function closeActiveTooltip() {
    if (activeTooltipLayer) {
        try {
            activeTooltipLayer.closeTooltip();
        } catch (_) {}
        activeTooltipLayer = null;
    }
}

/**
 * Reset style for a county layer, preserving selected-county highlight.
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
}

/**
 * Populate forecast period selector options from mapDataCache.periods.
 */
function populatePeriodSelector(periods) {
    if (!elements.mapPeriodSelect) return;
    elements.mapPeriodSelect.replaceChildren();

    if (!periods || periods.length === 0) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "暫無預報時段";
        elements.mapPeriodSelect.appendChild(opt);
        return;
    }

    periods.forEach((period) => {
        const opt = document.createElement("option");
        opt.value = `${period.start_time}_${period.end_time}`;
        opt.textContent = formatForecastPeriod(period.start_time, period.end_time);
        elements.mapPeriodSelect.appendChild(opt);
    });
}

/**
 * Canonical forecast period update pipeline for Phase 7B.
 * 1. Updates currentMapPeriod.
 * 2. Closes any active tooltip.
 * 3. Updates map period UI (select element and badge).
 * 4. Redraws all 22 county polygon styles (choropleth).
 * 5. Preserves selected county highlight outline.
 * 6. Updates selected county summary panel for the new period.
 * Does NOT reload Chart.js or Table, and does NOT fetch data.
 *
 * @param {Object|string} periodOrKey Period object with start_time & end_time, or period key string
 */
function setMapPeriod(periodOrKey) {
    if (!periodOrKey) return;
    let period = periodOrKey;
    if (typeof periodOrKey === "string" && mapDataCache && mapDataCache.periods) {
        period = mapDataCache.periods.find(
            (p) => `${p.start_time}_${p.end_time}` === periodOrKey
        ) || null;
    }
    if (!period) return;

    currentMapPeriod = period;

    // 1. Close any active tooltip
    closeActiveTooltip();

    // 2. Synchronize period selector and badge
    const periodKey = `${period.start_time}_${period.end_time}`;
    if (elements.mapPeriodSelect && elements.mapPeriodSelect.value !== periodKey) {
        elements.mapPeriodSelect.value = periodKey;
    }
    if (elements.mapPeriodBadge) {
        elements.mapPeriodBadge.textContent = formatForecastPeriod(
            period.start_time,
            period.end_time
        );
    }

    // 3. Redraw all county polygon styles using getCountyStyle
    if (geojsonLayer) {
        geojsonLayer.setStyle(getCountyStyle);
    }

    // 4. Preserve selected county polygon highlight
    if (selectedCountyName && countyLayersByName.has(selectedCountyName)) {
        const selectedLayer = countyLayersByName.get(selectedCountyName);
        selectedLayer.setStyle({
            weight: 3.5,
            color: "#1e3a8a",
            fillOpacity: 0.95,
        });
        selectedLayer.bringToFront();
    }

    // 5. Immediately update selected county summary panel for the new period
    if (selectedCountyName) {
        updateSummary(getForecastForCounty(selectedCountyName));
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

    // Update detail panel collapsed summary label if present
    if (elements.detailPanelSummaryLabel) {
        elements.detailPanelSummaryLabel.textContent = `📍 ${countyName}`;
    }

    // 6. Immediately update nearest-period summary using mapDataCache for currently displayed period
    const cachedForecast = getForecastForCounty(countyName);
    updateSummary(cachedForecast);

    // 7. Load detailed 7-day forecast for Chart and Table
    loadForecast(countyName);

    // 8. Load short-term 36-hour living forecast (F-C0032-001)
    loadShortTermForecast(countyName);
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
 * Capture-phase pointerdown handler on #taiwan-map container.
 * Bridges DOM pointer events on SVG polygon paths directly to county selection via countyLayersByName.
 */
function handleCountyPointerDown(event) {
    if (!event || !event.target) return;

    if (
        event.pointerType === "mouse" &&
        event.button !== 0
    ) {
        return;
    }

    const pathElement =
        typeof event.target.closest === "function"
            ? event.target.closest("path.leaflet-interactive")
            : null;

    if (!pathElement) return;

    let matchedCountyName = null;

    for (const [countyName, countyLayer] of countyLayersByName) {
        if (
            countyLayer &&
            typeof countyLayer.getElement === "function" &&
            countyLayer.getElement() === pathElement
        ) {
            matchedCountyName = countyName;
            break;
        }
        if (countyLayer && typeof countyLayer.eachLayer === "function") {
            let found = false;
            countyLayer.eachLayer((subLayer) => {
                if (
                    subLayer &&
                    typeof subLayer.getElement === "function" &&
                    subLayer.getElement() === pathElement
                ) {
                    found = true;
                }
            });
            if (found) {
                matchedCountyName = countyName;
                break;
            }
        }
    }

    if (!matchedCountyName) return;

    closeActiveTooltip();

    selectCounty(matchedCountyName, {
        panMap: false,
    });
}

/**
 * Enable scroll-wheel zoom for fine-pointer desktop devices, disable for mobile/touch.
 */
function syncMapWheelZoom() {
    if (!leafletMap) return;
    const isFinePointer = window.matchMedia && window.matchMedia("(pointer: fine)").matches;
    const isDesktopWidth = window.innerWidth > 960;
    if (isFinePointer && isDesktopWidth) {
        leafletMap.scrollWheelZoom.enable();
    } else {
        leafletMap.scrollWheelZoom.disable();
    }
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
        scrollWheelZoom: false, // Safely initialized, dynamically enabled via syncMapWheelZoom()
    });

    // Basemap: OpenStreetMap tiles with required attribution
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
        maxZoom: 18,
    }).addTo(leafletMap);

    // Apply wheel zoom synchronization
    syncMapWheelZoom();

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

    // DOM container mouseleave and pointerdown listeners
    if (elements.taiwanMap) {
        elements.taiwanMap.addEventListener("mouseleave", () => {
            closeActiveTooltip();
            if (hoveredCountyLayer) {
                resetCountyStyle(hoveredCountyLayer);
                hoveredCountyLayer = null;
            }
        });

        // ONE DOM pointerdown bridge on #taiwan-map container
        elements.taiwanMap.addEventListener(
            "pointerdown",
            handleCountyPointerDown,
            true
        );
    }
}

/**
 * Initialize map toolbar controls (Reset Taiwan View & Fullscreen) and Collapsible Panel.
 */
function initMapControls() {
    // 1. Reset Taiwan View (using GeoJSON getBounds() canonical bounds)
    if (elements.mapResetView) {
        elements.mapResetView.addEventListener("click", () => {
            if (leafletMap && taiwanDefaultBounds) {
                leafletMap.fitBounds(taiwanDefaultBounds, {
                    padding: [15, 15],
                    animate: true,
                });
            }
        });
    }

    // 2. Fullscreen Map Workspace
    if (elements.mapFullscreenToggle && elements.mapSection) {
        const isFullscreenSupported = !!(
            elements.mapSection.requestFullscreen ||
            elements.mapSection.webkitRequestFullscreen
        );

        if (!isFullscreenSupported) {
            elements.mapFullscreenToggle.disabled = true;
            elements.mapFullscreenToggle.title = "此瀏覽器不支援全螢幕模式";
            elements.mapFullscreenToggle.setAttribute("aria-disabled", "true");
        } else {
            elements.mapFullscreenToggle.addEventListener("click", () => {
                const isFull = !!(document.fullscreenElement || document.webkitFullscreenElement);
                if (!isFull) {
                    if (elements.mapSection.requestFullscreen) {
                        elements.mapSection.requestFullscreen().catch((err) => console.warn("Fullscreen request error:", err));
                    } else if (elements.mapSection.webkitRequestFullscreen) {
                        elements.mapSection.webkitRequestFullscreen();
                    }
                } else {
                    if (document.exitFullscreen) {
                        document.exitFullscreen().catch((err) => console.warn("Exit fullscreen error:", err));
                    } else if (document.webkitExitFullscreen) {
                        document.webkitExitFullscreen();
                    }
                }
            });

            const handleFullscreenChange = () => {
                const inFull = !!(document.fullscreenElement || document.webkitFullscreenElement);
                elements.mapFullscreenToggle.setAttribute("aria-label", inFull ? "退出全螢幕" : "全螢幕地圖");
                elements.mapFullscreenToggle.title = inFull ? "退出全螢幕" : "全螢幕地圖";
                const iconSpan = elements.mapFullscreenToggle.querySelector(".tool-icon");
                if (iconSpan) iconSpan.textContent = inFull ? "🗗" : "⛶";
                const labelSpan = elements.mapFullscreenToggle.querySelector(".tool-label");
                if (labelSpan) labelSpan.textContent = inFull ? "退出" : "全螢幕";

                elements.mapSection.classList.toggle("is-fullscreen", inFull);

                setTimeout(() => {
                    if (leafletMap) {
                        leafletMap.invalidateSize();
                    }
                }, 100);
            };

            document.addEventListener("fullscreenchange", handleFullscreenChange);
            document.addEventListener("webkitfullscreenchange", handleFullscreenChange);
        }
    }

    // 3. Collapsible Desktop Detail Panel
    if (elements.detailPanelToggle && elements.detailPanel) {
        elements.detailPanelToggle.addEventListener("click", () => {
            const isCollapsed = elements.detailPanel.classList.toggle("collapsed");
            elements.detailPanelToggle.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
            elements.detailPanelToggle.setAttribute("aria-label", isCollapsed ? "展開詳細資訊面板" : "收合詳細資訊面板");
            elements.detailPanelToggle.title = isCollapsed ? "展開面板" : "收合面板";
            const iconSpan = elements.detailPanelToggle.querySelector(".toggle-icon");
            if (iconSpan) iconSpan.textContent = isCollapsed ? "▶" : "◀";
            const textSpan = elements.detailPanelToggle.querySelector(".toggle-text");
            if (textSpan) textSpan.textContent = isCollapsed ? "展開" : "收合";
        });
    }

    // 4. Scroll-wheel zoom sync
    syncMapWheelZoom();
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

    elements.cardWeather.textContent = firstForecast.weather || "--";

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
    if (!elements.chartCanvas) return;

    // Destroy existing chart instance to prevent canvas reuse conflicts
    if (temperatureChartInstance) {
        temperatureChartInstance.destroy();
        temperatureChartInstance = null;
    }

    if (!forecasts || forecasts.length === 0) {
        return;
    }

    // Extract time labels and min/max temperatures chronologically
    const labels = forecasts.map((f) => formatShortDateTime(f.start_time));
    const maxTemps = forecasts.map((f) => f.max_temp);
    const minTemps = forecasts.map((f) => f.min_temp);

    const theme = getChartTheme();

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
                        color: theme.legendColor,
                    },
                },
                tooltip: {
                    backgroundColor: theme.tooltipBg,
                    titleColor: theme.tooltipTitle,
                    bodyColor: theme.tooltipBody,
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y !== null ? ctx.parsed.y + " °C" : "--"}`,
                    },
                },
            },
            scales: {
                x: {
                    grid: {
                        color: theme.gridColor,
                    },
                    ticks: {
                        font: { size: 12 },
                        color: theme.tickColor,
                        maxRotation: 45,
                        minRotation: 0,
                    },
                },
                y: {
                    title: {
                        display: true,
                        text: "溫度 (°C)",
                        color: theme.titleColor,
                        font: { size: 12, weight: "600" },
                    },
                    grid: {
                        color: theme.gridColor,
                    },
                    ticks: {
                        font: { size: 12 },
                        color: theme.tickColor,
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

        // Min Temp column
        const tdMin = document.createElement("td");
        tdMin.className = "num-col temp-cold";
        tdMin.textContent = f.min_temp !== null && f.min_temp !== undefined ? `${f.min_temp} °C` : "--";
        tr.appendChild(tdMin);

        // Max Temp column
        const tdMax = document.createElement("td");
        tdMax.className = "num-col temp-warm";
        tdMax.textContent = f.max_temp !== null && f.max_temp !== undefined ? `${f.max_temp} °C` : "--";
        tr.appendChild(tdMax);

        elements.tableBody.appendChild(tr);
    });
}

function updateMetadata(data) {
    if (!data) return;

    const timeStr = formatUpdatedTimestamp(data.updated_at);

    if (elements.lastUpdated) {
        elements.lastUpdated.textContent =
            `最後資料更新：${timeStr}`;
    }

    if (
        elements.detailLastUpdated &&
        (!mapDataCache || !mapDataCache.updated_at)
    ) {
        elements.detailLastUpdated.textContent = timeStr;
    }
}

// ---------------------------------------------------------------------------
// Phase 8B: Short-term 36h Living Forecast Functions (F-C0032-001)
// ---------------------------------------------------------------------------

let shortTermAbortController = null;

/**
 * Set loading UI for the 36-hour living forecast section independently.
 */
function setShortTermLoading(isLoading, message = "正在載入 36 小時預報...") {
    if (elements.shortTermLoading) {
        elements.shortTermLoading.style.display = isLoading ? "flex" : "none";
        if (elements.shortTermLoadingText) {
            elements.shortTermLoadingText.textContent = message;
        }
    }
    if (elements.shortTermCardsGrid && isLoading) {
        elements.shortTermCardsGrid.style.opacity = "0.5";
    } else if (elements.shortTermCardsGrid) {
        elements.shortTermCardsGrid.style.opacity = "1";
    }
}

/**
 * Set error UI for the 36-hour living forecast section independently.
 */
function setShortTermError(hasError, message = "暫時無法取得 36 小時生活預報") {
    if (elements.shortTermError) {
        elements.shortTermError.style.display = hasError ? "flex" : "none";
        if (elements.shortTermErrorText) {
            elements.shortTermErrorText.textContent = message;
        }
    }
}

/**
 * Map weather code or text to an emoji icon.
 */
function getWeatherIcon(weatherCode, weatherText) {
    const text = weatherText || "";
    if (text.includes("雷")) return "⛈️";
    if (text.includes("雨") || text.includes("陣雨")) return "🌧️";
    if (text.includes("陰")) return "☁️";
    if (text.includes("多雲")) return "⛅";
    if (text.includes("晴")) return "☀️";
    if (text.includes("雪")) return "❄️";
    if (text.includes("霧")) return "🌫️";
    return "🌤️";
}

/**
 * Determine a natural friendly title for the short-term forecast interval.
 */
function getShortTermPeriodTitle(startStr, endStr, index) {
    if (!startStr || !endStr) return `預報時段 ${index + 1}`;
    const startMatch = startStr.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
    if (!startMatch) return formatForecastPeriod(startStr, endStr);

    const sHour = parseInt(startMatch[4], 10);
    if (index === 0) {
        if (sHour >= 5 && sHour < 12) return "今天白天";
        if (sHour >= 12 && sHour < 18) return "今天下午至晚上";
        return "今天晚上 ～ 明天清晨";
    } else if (index === 1) {
        if (sHour >= 5 && sHour < 12) return "明天白天";
        if (sHour >= 12 && sHour < 18) return "明天下午至晚上";
        return "明天晚上 ～ 後天清晨";
    } else if (index === 2) {
        if (sHour >= 5 && sHour < 12) return "後天白天";
        if (sHour >= 12 && sHour < 18) return "後天下午至晚上";
        return "明天晚上 ～ 後天清晨";
    }
    return `生活預報時段 ${index + 1}`;
}

/**
 * Render 36-hour living forecast cards.
 */
function renderShortTermForecast(forecasts) {
    if (!elements.shortTermCardsGrid) return;
    elements.shortTermCardsGrid.innerHTML = "";

    if (!forecasts || forecasts.length === 0) {
        if (elements.shortTermEmpty) {
            elements.shortTermEmpty.style.display = "block";
        }
        return;
    }

    if (elements.shortTermEmpty) {
        elements.shortTermEmpty.style.display = "none";
    }

    forecasts.forEach((f, idx) => {
        const card = document.createElement("article");
        card.className = "short-term-card";

        const friendlyTitle = getShortTermPeriodTitle(f.start_time, f.end_time, idx);
        const periodTime = formatForecastPeriod(f.start_time, f.end_time);
        const icon = getWeatherIcon(f.weather_code, f.weather);
        const weatherDesc = f.weather || "--";

        let tempStr = "--";
        if (f.min_temp !== null && f.max_temp !== null) {
            tempStr = `${f.min_temp} ～ ${f.max_temp} °C`;
        } else if (f.min_temp !== null) {
            tempStr = `最低 ${f.min_temp} °C`;
        } else if (f.max_temp !== null) {
            tempStr = `最高 ${f.max_temp} °C`;
        }

        const popVal = f.pop !== null && f.pop !== undefined ? `${f.pop}%` : "--";
        const popPercent = f.pop !== null && f.pop !== undefined ? Math.min(100, Math.max(0, f.pop)) : 0;
        const ciVal = f.comfort_index || "--";

        card.innerHTML = `
            <div class="st-card-header">
                <span class="st-period-name">${friendlyTitle}</span>
                <span class="st-period-time">${periodTime}</span>
            </div>
            <div class="st-weather-row">
                <span class="st-weather-icon" aria-hidden="true">${icon}</span>
                <div class="st-weather-info">
                    <span class="st-weather-desc">${weatherDesc}</span>
                    <span class="st-temp-range">🌡️ ${tempStr}</span>
                </div>
            </div>
            <div class="st-metrics-group">
                <div class="st-metric-row">
                    <span class="st-metric-label">🌧️ 降雨機率</span>
                    <strong class="st-pop-value">${popVal}</strong>
                </div>
                <div class="st-pop-bar-bg" aria-hidden="true">
                    <div class="st-pop-bar-fill" style="width: ${popPercent}%;"></div>
                </div>
                <div class="st-metric-row st-ci-row">
                    <span class="st-metric-label">👕 舒適度</span>
                    <span class="st-ci-value">${ciVal}</span>
                </div>
            </div>
        `;

        elements.shortTermCardsGrid.appendChild(card);
    });
}

/**
 * Fetch and display 36-hour living forecast for the selected county (F-C0032-001).
 */
async function loadShortTermForecast(regionName) {
    if (!regionName) return;

    // Abort previous in-flight short-term request to prevent race conditions
    if (shortTermAbortController) {
        shortTermAbortController.abort();
    }
    shortTermAbortController = new AbortController();

    if (elements.shortTermRegionBadge) {
        elements.shortTermRegionBadge.textContent = regionName;
    }

    setShortTermLoading(true, `正在載入 ${regionName} 36 小時預報...`);
    setShortTermError(false);

    try {
        const url = `/api/forecast/short-term?region=${encodeURIComponent(regionName)}`;
        const response = await fetch(url, { signal: shortTermAbortController.signal });

        if (!response.ok) {
            throw new Error(`Short-term API error: ${response.status}`);
        }

        const data = await response.json();
        renderShortTermForecast(data.forecasts || []);
        setShortTermLoading(false);
    } catch (err) {
        if (err.name === "AbortError") {
            // Superseded by newer selection; exit silently
            return;
        }
        console.error("Short-term forecast fetch error:", err);
        setShortTermLoading(false);
        setShortTermError(true, "暫時無法取得 36 小時生活預報");
    }
}

// ---------------------------------------------------------------------------
// Data Fetching Functions
// ---------------------------------------------------------------------------

async function loadForecast(regionName) {
    if (!regionName) return;

    // Abort previous in-flight forecast request
    if (forecastAbortController) {
        forecastAbortController.abort();
    }
    forecastAbortController = new AbortController();

    setLoading(true, `正在載入 ${regionName} 天氣預報...`);

    try {
        const url = `/api/forecast?region=${encodeURIComponent(regionName)}`;
        const response = await fetch(url, { signal: forecastAbortController.signal });

        if (!response.ok) {
            throw new Error(`API responded with status: ${response.status}`);
        }

        const data = await response.json();

        // Update dashboard sections (Chart, Table, Metadata)
        const forecasts = data.forecasts || [];
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

        // Update detail panel and metadata bar with mapDataCache.updated_at
        if (mapDataCache.updated_at) {
            const timeStr = formatUpdatedTimestamp(mapDataCache.updated_at);
            if (elements.detailLastUpdated) {
                elements.detailLastUpdated.textContent = timeStr;
            }
            if (elements.lastUpdated) {
                elements.lastUpdated.textContent = `最後資料更新：${timeStr}`;
            }
        }

        // Populate period selector unconditionally from loaded periods
        populatePeriodSelector(mapDataCache.periods || []);

        // Initialize default active forecast period if available
        if (mapDataCache.periods && mapDataCache.periods.length > 0) {
            currentMapPeriod = mapDataCache.periods[0];
            const initialKey = `${currentMapPeriod.start_time}_${currentMapPeriod.end_time}`;
            if (elements.mapPeriodSelect) {
                elements.mapPeriodSelect.value = initialKey;
            }
            if (elements.mapPeriodBadge) {
                elements.mapPeriodBadge.textContent = formatForecastPeriod(
                    currentMapPeriod.start_time,
                    currentMapPeriod.end_time
                );
            }
        } else if (elements.mapPeriodBadge) {
            elements.mapPeriodBadge.textContent = "暫無預報時段";
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

            // Store canonical Taiwan bounds covering all GeoJSON counties and offshore islands
            taiwanDefaultBounds = geojsonLayer.getBounds();

            // Fit map bounds to Taiwan
            leafletMap.fitBounds(taiwanDefaultBounds, {
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
    // 0. Initialize theme system
    initTheme();

    // 1. Initialize Leaflet map
    initMap();

    // 2. Initialize map controls & toolbar (Reset View, Fullscreen, Collapsible Panel)
    initMapControls();

    // 3. Load Map Data and GeoJSON
    await loadMapDataAndGeoJSON();

    // 4. Load Regions and initial forecast
    await loadRegions();

    // 5. Attach change event listener to region selector
    if (elements.regionSelect) {
        elements.regionSelect.addEventListener("change", (event) => {
            const selectedRegion = event.target.value;
            selectCounty(selectedRegion, { panMap: true });
        });
    }

    // 5b. Attach click listener to short-term forecast retry button
    if (elements.shortTermRetryBtn) {
        elements.shortTermRetryBtn.addEventListener("click", () => {
            if (selectedCountyName) {
                loadShortTermForecast(selectedCountyName);
            }
        });
    }

    // 6. Attach change event listener to forecast period selector
    if (elements.mapPeriodSelect) {
        elements.mapPeriodSelect.addEventListener("change", (event) => {
            const selectedKey = event.target.value;
            const period = mapDataCache?.periods?.find(
                (p) => `${p.start_time}_${p.end_time}` === selectedKey
            );
            if (period) {
                setMapPeriod(period);
            }
        });
    }

    // 7. Invalidate map size and synchronize wheel zoom on window resize
    window.addEventListener("resize", () => {
        if (leafletMap) {
            leafletMap.invalidateSize();
            syncMapWheelZoom();
        }
    });
});
