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
let currentMapMode = "temperature"; // "temperature" | "rainfall" | "observations"
let shortTermMapDataCache = null;
let currentRainfallMapPeriod = null;
let observationDataCache = null;
let selectedObservationStationId = null;
let stationObservationLayer = null;
let observationCanvasRenderer = null;

// Phase 8D: Radar Reflectivity Overlay (O-A0058-002)
let radarEnabled = false;
let radarOverlayLayer = null;
let radarMetadataCache = null;
let radarOpacity = 0.65;
let radarAutoRefreshTimer = null;

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
    mapLegend: document.getElementById("map-legend"),
    mapModeTemperature: document.getElementById("map-mode-temperature"),
    mapModeRainfall: document.getElementById("map-mode-rainfall"),
    mapModeObservations: document.getElementById("map-mode-observations"),
    rainfallLegend: document.getElementById("rainfall-legend"),
    observationLegend: document.getElementById("observation-legend"),
    rainfallSummaryGroup: document.getElementById("rainfall-summary-group"),
    temperatureSummaryGroup: document.getElementById("temperature-summary-group"),
    observationSummaryGroup: document.getElementById("observation-summary-group"),
    rainfallSummaryPeriod: document.getElementById("rainfall-summary-period"),
    observationSummaryPeriod: document.getElementById("observation-summary-period"),
    observationStationName: document.getElementById("observation-station-name"),
    observationCardWeather: document.getElementById("observation-card-weather"),
    observationCardTemp: document.getElementById("observation-card-temp"),
    observationCardHumidity: document.getElementById("observation-card-humidity"),
    observationCardWind: document.getElementById("observation-card-wind"),
    observationCardPressure: document.getElementById("observation-card-pressure"),
    observationCardPrecipitation: document.getElementById("observation-card-precipitation"),
    observationCardGust: document.getElementById("observation-card-gust"),
    observationDetailLastUpdated: document.getElementById("observation-detail-last-updated"),
    rainfallCardWeather: document.getElementById("rainfall-card-weather"),
    rainfallCardPoP: document.getElementById("rainfall-card-pop"),
    rainfallCardCI: document.getElementById("rainfall-card-ci"),
    rainfallDetailLastUpdated: document.getElementById("rainfall-detail-last-updated"),
    detailLastUpdated: document.getElementById("detail-last-updated"),
    themeToggle: document.getElementById("theme-toggle"),
    mapResetView: document.getElementById("map-reset-view"),
    mapFullscreenToggle: document.getElementById("map-fullscreen-toggle"),
    radarToggle: document.getElementById("radar-toggle"),
    radarOpacity: document.getElementById("radar-opacity"),
    radarRefresh: document.getElementById("radar-refresh"),
    radarStatus: document.getElementById("radar-status"),
    radarControlsWrapper: document.getElementById("radar-controls-wrapper"),
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
 * Format observation timestamp to 'HH:mm'.
 * @param {string} isoString e.g. "2026-10-07T18:00:00+08:00"
 * @returns {string} e.g. "18:00"
 */
function formatObservationTime(isoString) {
    if (!isoString || typeof isoString !== "string") return "--";
    const m = isoString.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
    if (!m) return isoString;
    return `${m[4]}:${m[5]}`;
}

/**
 * Format observation timestamp to 'YYYY/MM/DD HH:mm'.
 * @param {string} isoString e.g. "2026-10-07T18:00:00+08:00"
 * @returns {string} e.g. "2026/10/07 18:00"
 */
function formatFullObservationTime(isoString) {
    if (!isoString || typeof isoString !== "string") return "--";
    const m = isoString.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
    if (!m) return isoString;
    return `${m[1]}/${m[2]}/${m[3]} ${m[4]}:${m[5]}`;
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
    if (currentMapMode === "observations" && geojsonLayer) {
        geojsonLayer.setStyle(getCountyStyle);
    }
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
 * Map observed temperature to discrete palette colors (Phase 8C).
 * Dedicated observation temperature scale.
 * Discrete ranges: <20, 20-23, 24-27, 28-31, 32-35, >=36.
 * Missing / invalid: neutral slate gray.
 */
function getObservationTemperatureColor(temp) {
    if (temp === null || temp === undefined || isNaN(temp)) {
        return "#cbd5e1";
    }
    const val = Number(temp);
    if (val < 20) return "#60a5fa";
    if (val <= 23) return "#34d399";
    if (val <= 27) return "#facc15";
    if (val <= 31) return "#fb923c";
    if (val <= 35) return "#f87171";
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
 * Return color for rainfall probability choropleth (Phase 8B2).
 * Monotonic blue scale, readable in light and dark mode, neutral gray for missing/null.
 */
function getRainfallColor(pop) {
    if (pop === null || pop === undefined || isNaN(pop)) {
        return "#cbd5e1"; // Neutral gray for no data
    }
    const val = Number(pop);
    if (val <= 20) return "#dbeafe";
    if (val <= 40) return "#93c5fd";
    if (val <= 60) return "#60a5fa";
    if (val <= 80) return "#2563eb";
    return "#1e40af";
}

/**
 * Retrieve rainfall forecast item for a given county in the active short-term map period (Phase 8B2).
 * Matches region_name and exact start_time & end_time (does not fall back to wrong period).
 */
function getRainfallForecastForCounty(countyName) {
    if (!shortTermMapDataCache || !shortTermMapDataCache.forecasts) return null;
    if (currentRainfallMapPeriod) {
        return (
            shortTermMapDataCache.forecasts.find(
                (f) =>
                    f.region_name === countyName &&
                    f.start_time === currentRainfallMapPeriod.start_time &&
                    f.end_time === currentRainfallMapPeriod.end_time
            ) || null
        );
    }
    return (
        shortTermMapDataCache.forecasts.find((f) => f.region_name === countyName) || null
    );
}

/**
 * Leaflet style function: Returns styling object based on county temperature, rainfall, or observation mode (Phase 8C).
 */
function getCountyStyle(feature) {
    const countyName = feature.properties.COUNTYNAME || feature.properties.name;
    const isSelected = selectedCountyName && selectedCountyName === countyName;

    if (currentMapMode === "observations") {
        const isDark = document.documentElement.dataset.theme === "dark";
        return {
            fillColor: isDark ? "#334155" : "#f1f5f9",
            weight: isSelected ? 3.5 : 1.2,
            opacity: 1,
            color: isSelected ? "#1e3a8a" : (isDark ? "#475569" : "#cbd5e1"),
            fillOpacity: isSelected ? 0.65 : 0.35,
        };
    }

    if (currentMapMode === "rainfall") {
        const forecast = getRainfallForecastForCounty(countyName);
        const fillColor = forecast ? getRainfallColor(forecast.pop) : "#cbd5e1";
        return {
            fillColor: fillColor,
            weight: isSelected ? 3.5 : 1.2,
            opacity: 1,
            color: isSelected ? "#1e3a8a" : "#ffffff",
            fillOpacity: isSelected ? 0.95 : 0.78,
        };
    }

    const forecast = getForecastForCounty(countyName);
    const fillColor = forecast ? getTemperatureColor(forecast.max_temp) : "#cbd5e1";

    return {
        fillColor: fillColor,
        weight: isSelected ? 3.5 : 1.2,
        opacity: 1,
        color: isSelected ? "#1e3a8a" : "#ffffff",
        fillOpacity: isSelected ? 0.95 : 0.78,
    };
}

/**
 * Build rich HTML DOM element for county hover tooltip (Safe DOM manipulation).
 */
function createTooltipElement(countyName) {
    const container = document.createElement("div");
    container.className = "county-tooltip";

    const titleEl = document.createElement("div");
    titleEl.className = "tooltip-county";
    titleEl.textContent = countyName;
    container.appendChild(titleEl);

    if (currentMapMode === "observations") {
        const defaultStation = getDefaultStationForCounty(countyName);
        if (defaultStation) {
            const stationEl = document.createElement("div");
            stationEl.className = "tooltip-weather";
            const tempStr = defaultStation.temperature !== null ? `${defaultStation.temperature} °C` : "無氣溫資料";
            stationEl.textContent = `${defaultStation.station_name}測站 ${tempStr}`;
            container.appendChild(stationEl);

            if (defaultStation.observation_time) {
                const timeEl = document.createElement("div");
                timeEl.className = "tooltip-period";
                timeEl.textContent = `觀測時間 ${formatObservationTime(defaultStation.observation_time)}`;
                container.appendChild(timeEl);
            }
        } else {
            const noDataEl = document.createElement("div");
            noDataEl.className = "tooltip-weather";
            noDataEl.textContent = "目前無可用測站觀測資料";
            container.appendChild(noDataEl);
        }
        return container;
    }

    if (currentMapMode === "rainfall") {
        const rfForecast = getRainfallForecastForCounty(countyName);

        if (currentRainfallMapPeriod) {
            const periodEl = document.createElement("div");
            periodEl.className = "tooltip-period";
            periodEl.textContent = formatForecastPeriod(
                currentRainfallMapPeriod.start_time,
                currentRainfallMapPeriod.end_time
            );
            container.appendChild(periodEl);
        }

        const weatherEl = document.createElement("div");
        weatherEl.className = "tooltip-weather";
        weatherEl.textContent = rfForecast ? (rfForecast.weather || "無資料") : "無預報資料";
        container.appendChild(weatherEl);

        const popEl = document.createElement("div");
        popEl.className = "tooltip-pop";
        popEl.textContent = rfForecast && rfForecast.pop !== null && rfForecast.pop !== undefined
            ? `降雨機率 ${rfForecast.pop}%`
            : "降雨機率 --";
        container.appendChild(popEl);

        if (rfForecast && rfForecast.comfort_index) {
            const ciEl = document.createElement("div");
            ciEl.className = "tooltip-ci";
            ciEl.textContent = `舒適度 ${rfForecast.comfort_index}`;
            container.appendChild(ciEl);
        }

        if (rfForecast && (rfForecast.min_temp !== null || rfForecast.max_temp !== null)) {
            const tempsEl = document.createElement("div");
            tempsEl.className = "tooltip-temps";
            let tempStr = "--";
            if (rfForecast.min_temp !== null && rfForecast.max_temp !== null) {
                tempStr = `${rfForecast.min_temp} ～ ${rfForecast.max_temp} °C`;
            } else if (rfForecast.min_temp !== null) {
                tempStr = `最低 ${rfForecast.min_temp} °C`;
            } else if (rfForecast.max_temp !== null) {
                tempStr = `最高 ${rfForecast.max_temp} °C`;
            }
            tempsEl.textContent = tempStr;
            container.appendChild(tempsEl);
        }

        return container;
    }

    const forecast = getForecastForCounty(countyName);

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
 * Canonical forecast period update pipeline for Rainfall mode (Phase 8B2).
 * 1. Updates currentRainfallMapPeriod.
 * 2. Closes any active tooltip.
 * 3. Updates map period UI (select element and badge).
 * 4. Redraws all 22 county polygon styles (PoP choropleth).
 * 5. Preserves selected county highlight outline.
 * 6. Updates selected county rainfall summary panel for the new period.
 * Does NOT make any network fetch.
 *
 * @param {Object|string} periodOrKey Period object with start_time & end_time, or period key string
 */
function setRainfallMapPeriod(periodOrKey) {
    if (!periodOrKey) return;
    let period = periodOrKey;
    if (typeof periodOrKey === "string" && shortTermMapDataCache && shortTermMapDataCache.periods) {
        period = shortTermMapDataCache.periods.find(
            (p) => `${p.start_time}_${p.end_time}` === periodOrKey
        ) || null;
    }
    if (!period) return;

    currentRainfallMapPeriod = period;

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

    // 5. Immediately update selected county rainfall summary panel for the new period
    if (selectedCountyName) {
        updateRainfallSummary(getRainfallForecastForCounty(selectedCountyName));
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

    // 6. Immediately update nearest-period summary for currently displayed period
    if (currentMapMode === "observations" && observationDataCache) {
        const defaultSt = getDefaultStationForCounty(countyName);
        selectedObservationStationId = defaultSt ? defaultSt.station_id : null;
        updateObservationDetailPanel(defaultSt);
        updateStationMarkerEmphasis();
    } else if (currentMapMode === "rainfall" && shortTermMapDataCache) {
        updateRainfallSummary(getRainfallForecastForCounty(countyName));
    } else {
        const cachedForecast = getForecastForCounty(countyName);
        updateSummary(cachedForecast);
    }

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

    // Dedicated Leaflet radar pane (Phase 8D)
    if (!leafletMap.getPane("radarPane")) {
        leafletMap.createPane("radarPane");
        const rPane = leafletMap.getPane("radarPane");
        rPane.style.zIndex = 350;
        rPane.style.pointerEvents = "none";
    }

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

    // 5. Initialize Radar Overlay controls (Phase 8D)
    initRadarControls();
}

// ---------------------------------------------------------------------------
// Phase 8B2: Map Mode Controls & Short-Term Rainfall Map (F-C0032-001)
// ---------------------------------------------------------------------------

/**
 * Lazy-load F-C0032-001 all-county 36h map dataset once per session.
 */
async function loadShortTermMapData() {
    if (shortTermMapDataCache) return shortTermMapDataCache;

    if (elements.mapPeriodBadge) {
        elements.mapPeriodBadge.textContent = "正在載入降雨機率地圖...";
    }

    try {
        const response = await fetch("/api/map-data/short-term");
        if (!response.ok) {
            throw new Error(`Short-term map data fetch failed: ${response.status}`);
        }
        const data = await response.json();
        shortTermMapDataCache = data;
        return data;
    } catch (err) {
        console.error("Failed to load short-term map data:", err);
        return null;
    }
}

// ---------------------------------------------------------------------------
// Phase 8C: Current Weather Observations (O-A0001)
// ---------------------------------------------------------------------------

/**
 * Lazy-load O-A0001 observation dataset once per session.
 */
async function loadObservationData() {
    if (observationDataCache) return observationDataCache;

    if (elements.mapPeriodBadge) {
        elements.mapPeriodBadge.textContent = "正在載入目前觀測資料...";
    }

    try {
        const response = await fetch("/api/observations");
        if (!response.ok) {
            throw new Error(`Observation data fetch failed: ${response.status}`);
        }
        const data = await response.json();
        observationDataCache = data;
        return data;
    } catch (err) {
        console.error("Failed to load observation data:", err);
        return null;
    }
}

/**
 * Get or initialize station observation layer and canvas renderer.
 */
function getOrCreateStationLayer() {
    if (!stationObservationLayer) {
        stationObservationLayer = L.layerGroup();
    }
    if (!observationCanvasRenderer && typeof L !== "undefined" && L.canvas) {
        observationCanvasRenderer = L.canvas({ padding: 0.5 });
    }
    return stationObservationLayer;
}

/**
 * Build rich HTML DOM element for station hover tooltip (Safe DOM manipulation).
 */
function createStationTooltip(st) {
    const container = document.createElement("div");
    container.className = "station-tooltip";

    const nameEl = document.createElement("div");
    nameEl.className = "tooltip-station-name";
    nameEl.textContent = `${st.station_name || "未知"}測站`;
    container.appendChild(nameEl);

    const dataEl = document.createElement("div");
    dataEl.className = "tooltip-station-data";

    const tempSpan = document.createElement("span");
    tempSpan.textContent = st.temperature !== null && st.temperature !== undefined ? `${st.temperature} °C` : "--";
    dataEl.appendChild(tempSpan);

    if (st.relative_humidity !== null && st.relative_humidity !== undefined) {
        const rhSpan = document.createElement("span");
        rhSpan.textContent = `濕度 ${st.relative_humidity}%`;
        dataEl.appendChild(rhSpan);
    }
    container.appendChild(dataEl);

    if (st.observation_time) {
        const timeEl = document.createElement("div");
        timeEl.className = "tooltip-station-time";
        timeEl.textContent = `觀測 ${formatObservationTime(st.observation_time)}`;
        container.appendChild(timeEl);
    }

    return container;
}

/**
 * Build rich HTML DOM element for station click popup (Safe DOM manipulation, no innerHTML).
 */
function createStationPopup(st) {
    const container = document.createElement("div");
    container.className = "station-popup";

    const header = document.createElement("div");
    header.className = "station-popup-header";

    const title = document.createElement("div");
    title.className = "station-popup-title";
    const nameSpan = document.createElement("span");
    nameSpan.textContent = `${st.station_name || "未知"}測站`;
    const badgeSpan = document.createElement("span");
    badgeSpan.className = "obs-badge";
    badgeSpan.textContent = "目前觀測";
    title.appendChild(nameSpan);
    title.appendChild(badgeSpan);
    header.appendChild(title);

    const loc = document.createElement("div");
    loc.className = "station-popup-location";
    const locParts = [];
    if (st.county_name) locParts.push(st.county_name);
    if (st.town_name) locParts.push(st.town_name);
    loc.textContent = locParts.length > 0 ? locParts.join(" · ") : `測站編號 ${st.station_id}`;
    header.appendChild(loc);
    container.appendChild(header);

    const timeEl = document.createElement("div");
    timeEl.className = "station-popup-time";
    timeEl.textContent = `觀測時間：${formatFullObservationTime(st.observation_time)}`;
    container.appendChild(timeEl);

    const grid = document.createElement("div");
    grid.className = "station-popup-grid";

    function addItem(lbl, val) {
        const item = document.createElement("div");
        item.className = "station-popup-item";
        const l = document.createElement("span");
        l.className = "popup-lbl";
        l.textContent = lbl;
        const v = document.createElement("span");
        v.className = "popup-val";
        v.textContent = val;
        item.appendChild(l);
        item.appendChild(v);
        grid.appendChild(item);
    }

    addItem("天氣", st.weather || "--");
    addItem("氣溫", st.temperature !== null && st.temperature !== undefined ? `${st.temperature} °C` : "--");
    addItem("濕度", st.relative_humidity !== null && st.relative_humidity !== undefined ? `${st.relative_humidity}%` : "--");

    let windStr = "--";
    if (st.wind_direction_text) {
        windStr = st.wind_direction !== null && st.wind_direction >= 0 && st.wind_direction <= 360
            ? `${st.wind_direction_text} (${st.wind_direction}°)`
            : st.wind_direction_text;
    }
    addItem("風向", windStr);

    addItem("風速", st.wind_speed !== null && st.wind_speed !== undefined ? `${st.wind_speed} m/s` : "--");
    addItem("氣壓", st.air_pressure !== null && st.air_pressure !== undefined ? `${st.air_pressure} hPa` : "--");

    let precipStr = "--";
    if (st.precipitation_status === "trace") {
        precipStr = "雨跡";
    } else if (st.precipitation_status === "no_precipitation_6h") {
        precipStr = "無降雨 (6h)";
    } else if (st.precipitation_status === "instrument_error") {
        precipStr = "儀器異常";
    } else if (st.precipitation_status === "missing") {
        precipStr = "資料缺值";
    } else if (st.precipitation !== null && st.precipitation !== undefined) {
        precipStr = `${st.precipitation} mm`;
    }
    addItem("降水", precipStr);

    addItem("最大陣風", st.peak_gust_speed !== null && st.peak_gust_speed !== undefined ? `${st.peak_gust_speed} m/s` : "--");

    container.appendChild(grid);
    return container;
}

/**
 * Deterministically select a default representative station for a county.
 * Hierarchy:
 * 1. Station name matches county base name (e.g. 臺中市 -> 臺中)
 * 2. Station with the most complete observation fields
 * 3. Deterministic tie-break by station_id
 */
function getDefaultStationForCounty(countyName) {
    if (!observationDataCache || !observationDataCache.stations || !countyName) {
        return null;
    }
    const countyStations = observationDataCache.stations.filter(
        (st) => st.county_name === countyName
    );
    if (countyStations.length === 0) return null;

    const baseName = countyName.replace(/[市縣]$/, "");

    // 1. Exact match to base name or county name
    const exactNameMatch = countyStations.find(
        (st) => st.station_name === baseName || st.station_name === countyName
    );
    if (exactNameMatch) return exactNameMatch;

    // 2. Station with most complete fields
    const scoreStation = (st) => {
        let score = 0;
        if (st.temperature !== null) score += 2;
        if (st.weather !== null) score += 1;
        if (st.relative_humidity !== null) score += 1;
        if (st.wind_speed !== null) score += 1;
        if (st.air_pressure !== null) score += 1;
        if (st.precipitation !== null) score += 1;
        return score;
    };

    const sorted = [...countyStations].sort((a, b) => {
        const diff = scoreStation(b) - scoreStation(a);
        if (diff !== 0) return diff;
        return a.station_id.localeCompare(b.station_id);
    });

    return sorted[0];
}

/**
 * Update Observation summary group in the floating detail panel (Phase 8C).
 * Safe DOM manipulation with textContent.
 */
function updateObservationDetailPanel(station) {
    if (!elements.observationSummaryGroup) return;

    if (!station) {
        if (elements.observationStationName) {
            elements.observationStationName.textContent = "目前沒有可用的測站觀測資料";
        }
        if (elements.observationSummaryPeriod) {
            elements.observationSummaryPeriod.textContent = "--";
        }
        if (elements.observationCardWeather) elements.observationCardWeather.textContent = "--";
        if (elements.observationCardTemp) elements.observationCardTemp.textContent = "--";
        if (elements.observationCardHumidity) elements.observationCardHumidity.textContent = "--";
        if (elements.observationCardWind) elements.observationCardWind.textContent = "--";
        if (elements.observationCardPressure) elements.observationCardPressure.textContent = "--";
        if (elements.observationCardPrecipitation) elements.observationCardPrecipitation.textContent = "--";
        if (elements.observationCardGust) elements.observationCardGust.textContent = "--";
        if (elements.observationDetailLastUpdated) {
            elements.observationDetailLastUpdated.textContent = formatUpdatedTimestamp(
                observationDataCache?.updated_at
            );
        }
        return;
    }

    if (elements.observationStationName) {
        elements.observationStationName.textContent = `${station.station_name || "未知"}測站 (${station.station_id})`;
    }

    if (elements.observationSummaryPeriod) {
        elements.observationSummaryPeriod.textContent = `觀測時間 ${formatObservationTime(station.observation_time)}`;
    }

    if (elements.observationCardWeather) {
        elements.observationCardWeather.textContent = station.weather || "--";
    }

    if (elements.observationCardTemp) {
        elements.observationCardTemp.textContent =
            station.temperature !== null && station.temperature !== undefined
                ? `${station.temperature} °C`
                : "--";
    }

    if (elements.observationCardHumidity) {
        elements.observationCardHumidity.textContent =
            station.relative_humidity !== null && station.relative_humidity !== undefined
                ? `${station.relative_humidity}%`
                : "--";
    }

    if (elements.observationCardWind) {
        let windStr = "--";
        if (station.wind_direction_text) {
            windStr = station.wind_speed !== null && station.wind_speed !== undefined
                ? `${station.wind_direction_text} ${station.wind_speed} m/s`
                : station.wind_direction_text;
        } else if (station.wind_speed !== null && station.wind_speed !== undefined) {
            windStr = `${station.wind_speed} m/s`;
        }
        elements.observationCardWind.textContent = windStr;
    }

    if (elements.observationCardPressure) {
        elements.observationCardPressure.textContent =
            station.air_pressure !== null && station.air_pressure !== undefined
                ? `${station.air_pressure} hPa`
                : "--";
    }

    if (elements.observationCardPrecipitation) {
        let precipStr = "--";
        if (station.precipitation_status === "trace") {
            precipStr = "雨跡";
        } else if (station.precipitation_status === "no_precipitation_6h") {
            precipStr = "無降雨 (6h)";
        } else if (station.precipitation_status === "instrument_error") {
            precipStr = "儀器異常";
        } else if (station.precipitation_status === "missing") {
            precipStr = "資料缺值";
        } else if (station.precipitation !== null && station.precipitation !== undefined) {
            precipStr = `${station.precipitation} mm`;
        }
        elements.observationCardPrecipitation.textContent = precipStr;
    }

    if (elements.observationCardGust) {
        elements.observationCardGust.textContent =
            station.peak_gust_speed !== null && station.peak_gust_speed !== undefined
                ? `${station.peak_gust_speed} m/s`
                : "--";
    }

    if (elements.observationDetailLastUpdated) {
        elements.observationDetailLastUpdated.textContent = formatUpdatedTimestamp(
            observationDataCache?.updated_at
        );
    }
}

/**
 * Update visual emphasis of station circle markers based on selected station & county.
 */
function updateStationMarkerEmphasis() {
    if (!stationObservationLayer) return;
    stationObservationLayer.eachLayer((marker) => {
        if (!marker.stationData) return;
        const st = marker.stationData;
        const isSelected = selectedObservationStationId === st.station_id;
        const isCountyStation = selectedCountyName && st.county_name === selectedCountyName;

        marker.setStyle({
            radius: isSelected ? 8 : (isCountyStation ? 6 : 5),
            color: isSelected ? "#1e3a8a" : "#ffffff",
            weight: isSelected ? 3 : (isCountyStation ? 1.8 : 1.2),
            opacity: 1,
            fillOpacity: isSelected ? 1 : (isCountyStation ? 0.95 : 0.75),
        });

        if (isSelected && marker.bringToFront) {
            marker.bringToFront();
        }
    });
}

/**
 * Handle user clicking a station marker.
 * Synchronizes county and observation detail panel without refetching data.
 */
function selectObservationStation(st) {
    if (!st) return;
    selectedObservationStationId = st.station_id;

    // 1. Update observation detail panel
    updateObservationDetailPanel(st);

    // 2. Synchronize selected county if different
    if (st.county_name && st.county_name !== selectedCountyName) {
        selectedCountyName = st.county_name;
        if (elements.regionSelect && elements.regionSelect.value !== st.county_name) {
            elements.regionSelect.value = st.county_name;
        }
        if (elements.selectedRegionName) {
            elements.selectedRegionName.textContent = st.county_name;
        }
        if (elements.detailPanelSummaryLabel) {
            elements.detailPanelSummaryLabel.textContent = `📍 ${st.county_name}`;
        }
        if (geojsonLayer) {
            geojsonLayer.setStyle(getCountyStyle);
        }
        loadForecast(st.county_name);
        loadShortTermForecast(st.county_name);
    }

    // 3. Update marker visual highlights
    updateStationMarkerEmphasis();
}

/**
 * Render station circle markers onto Leaflet map using shared canvas renderer (Phase 8C).
 */
function renderStationMarkers(stations) {
    const layer = getOrCreateStationLayer();
    layer.clearLayers();

    if (!stations || !Array.isArray(stations)) return;

    stations.forEach((st) => {
        // Coordinate validation: latitude -90..90, longitude -180..180
        if (
            st.latitude === null ||
            st.longitude === null ||
            st.latitude === undefined ||
            st.longitude === undefined ||
            isNaN(st.latitude) ||
            isNaN(st.longitude) ||
            st.latitude < -90 ||
            st.latitude > 90 ||
            st.longitude < -180 ||
            st.longitude > 180
        ) {
            return; // Skip station with invalid or missing coordinates
        }

        const fillColor = getObservationTemperatureColor(st.temperature);
        const isSelected = selectedObservationStationId === st.station_id;
        const isCountyStation = selectedCountyName && st.county_name === selectedCountyName;

        const marker = L.circleMarker([st.latitude, st.longitude], {
            renderer: observationCanvasRenderer,
            radius: isSelected ? 8 : (isCountyStation ? 6 : 5),
            fillColor: fillColor,
            color: isSelected ? "#1e3a8a" : "#ffffff",
            weight: isSelected ? 3 : (isCountyStation ? 1.8 : 1.2),
            opacity: 1,
            fillOpacity: isSelected ? 1 : (isCountyStation ? 0.95 : 0.75),
        });

        marker.stationData = st;

        // Tooltip
        marker.bindTooltip(() => createStationTooltip(st), {
            sticky: true,
            direction: "top",
            className: "custom-leaflet-tooltip",
        });

        // Popup
        marker.bindPopup(() => createStationPopup(st), {
            className: "station-popup-wrapper",
            closeButton: true,
        });

        // Click interaction
        marker.on("click", () => {
            selectObservationStation(st);
        });

        layer.addLayer(marker);
    });
}

/**
 * Switch map mode between "temperature", "rainfall", and "observations" (Phase 8C).
 * Explicit 3-way branching, rejects unknown modes.
 *
 * @param {"temperature" | "rainfall" | "observations"} mode Desired map mode
 */
async function setMapMode(mode) {
    if (mode !== "temperature" && mode !== "rainfall" && mode !== "observations") {
        console.warn(`Unknown map mode requested: ${mode}`);
        return;
    }
    if (mode === currentMapMode) return;

    if (mode === "observations") {
        // Lazy-load observation dataset if not yet loaded
        if (!observationDataCache) {
            const data = await loadObservationData();
            if (!data || !data.stations || data.stations.length === 0) {
                if (elements.mapError) {
                    elements.mapError.textContent = "目前觀測資料暫時無法載入";
                    elements.mapError.classList.remove("hidden");
                    setTimeout(() => {
                        elements.mapError.classList.add("hidden");
                        elements.mapError.textContent = "地圖資料暫時無法載入";
                    }, 4000);
                }
                return;
            }
        }

        currentMapMode = "observations";

        // 1. Update mode toggle button attributes
        if (elements.mapModeTemperature) {
            elements.mapModeTemperature.classList.remove("active");
            elements.mapModeTemperature.setAttribute("aria-pressed", "false");
        }
        if (elements.mapModeRainfall) {
            elements.mapModeRainfall.classList.remove("active");
            elements.mapModeRainfall.setAttribute("aria-pressed", "false");
        }
        if (elements.mapModeObservations) {
            elements.mapModeObservations.classList.add("active");
            elements.mapModeObservations.setAttribute("aria-pressed", "true");
        }

        // 2. Toggle legends
        if (elements.mapLegend) elements.mapLegend.classList.add("hidden");
        if (elements.rainfallLegend) elements.rainfallLegend.classList.add("hidden");
        if (elements.observationLegend) elements.observationLegend.classList.remove("hidden");

        // 3. Toggle detail panel summary groups
        if (elements.temperatureSummaryGroup) elements.temperatureSummaryGroup.classList.add("hidden");
        if (elements.rainfallSummaryGroup) elements.rainfallSummaryGroup.classList.add("hidden");
        if (elements.observationSummaryGroup) elements.observationSummaryGroup.classList.remove("hidden");
        if (elements.summaryPeriod) elements.summaryPeriod.classList.add("hidden");
        if (elements.rainfallSummaryPeriod) elements.rainfallSummaryPeriod.classList.add("hidden");
        if (elements.observationSummaryPeriod) elements.observationSummaryPeriod.classList.remove("hidden");

        // 4. Hide / disable forecast period select in observation mode
        if (elements.mapPeriodSelect) {
            elements.mapPeriodSelect.classList.add("hidden");
            elements.mapPeriodSelect.disabled = true;
        }

        // 5. Update map period badge to observation time
        if (elements.mapPeriodBadge) {
            elements.mapPeriodBadge.textContent = `最新觀測 ${formatUpdatedTimestamp(observationDataCache?.updated_at)}`;
        }

        // 6. Redraw county polygons with neutral styling
        if (geojsonLayer) {
            geojsonLayer.setStyle(getCountyStyle);
        }

        // 7. Add station observation layer to map & render markers
        const layer = getOrCreateStationLayer();
        if (leafletMap && !leafletMap.hasLayer(layer)) {
            layer.addTo(leafletMap);
        }
        renderStationMarkers(observationDataCache.stations);

        // 8. Update detail panel with default county station or selected station
        if (selectedObservationStationId) {
            const st = observationDataCache.stations.find((s) => s.station_id === selectedObservationStationId);
            if (st) {
                updateObservationDetailPanel(st);
            } else if (selectedCountyName) {
                const defaultSt = getDefaultStationForCounty(selectedCountyName);
                selectedObservationStationId = defaultSt ? defaultSt.station_id : null;
                updateObservationDetailPanel(defaultSt);
            } else {
                selectedObservationStationId = null;
                updateObservationDetailPanel(null);
            }
        } else if (selectedCountyName) {
            const defaultSt = getDefaultStationForCounty(selectedCountyName);
            selectedObservationStationId = defaultSt ? defaultSt.station_id : null;
            updateObservationDetailPanel(defaultSt);
        } else {
            selectedObservationStationId = null;
            updateObservationDetailPanel(null);
        }
        updateStationMarkerEmphasis();

    } else if (mode === "rainfall") {
        // Lazy-load short-term all-county map data if not yet loaded
        if (!shortTermMapDataCache) {
            const data = await loadShortTermMapData();
            if (!data || !data.periods || data.periods.length === 0) {
                if (elements.mapError) {
                    elements.mapError.textContent = "降雨機率地圖暫時無法載入";
                    elements.mapError.classList.remove("hidden");
                    setTimeout(() => {
                        elements.mapError.classList.add("hidden");
                        elements.mapError.textContent = "地圖資料暫時無法載入";
                    }, 4000);
                }
                return;
            }
        }

        currentMapMode = "rainfall";

        // Remove station observation layer if present
        if (stationObservationLayer && leafletMap && leafletMap.hasLayer(stationObservationLayer)) {
            leafletMap.removeLayer(stationObservationLayer);
        }

        // 1. Update mode toggle button attributes
        if (elements.mapModeTemperature) {
            elements.mapModeTemperature.classList.remove("active");
            elements.mapModeTemperature.setAttribute("aria-pressed", "false");
        }
        if (elements.mapModeRainfall) {
            elements.mapModeRainfall.classList.add("active");
            elements.mapModeRainfall.setAttribute("aria-pressed", "true");
        }
        if (elements.mapModeObservations) {
            elements.mapModeObservations.classList.remove("active");
            elements.mapModeObservations.setAttribute("aria-pressed", "false");
        }

        // 2. Toggle legends
        if (elements.mapLegend) elements.mapLegend.classList.add("hidden");
        if (elements.rainfallLegend) elements.rainfallLegend.classList.remove("hidden");
        if (elements.observationLegend) elements.observationLegend.classList.add("hidden");

        // 3. Toggle detail panel summary groups
        if (elements.temperatureSummaryGroup) elements.temperatureSummaryGroup.classList.add("hidden");
        if (elements.rainfallSummaryGroup) elements.rainfallSummaryGroup.classList.remove("hidden");
        if (elements.observationSummaryGroup) elements.observationSummaryGroup.classList.add("hidden");
        if (elements.summaryPeriod) elements.summaryPeriod.classList.add("hidden");
        if (elements.rainfallSummaryPeriod) elements.rainfallSummaryPeriod.classList.remove("hidden");
        if (elements.observationSummaryPeriod) elements.observationSummaryPeriod.classList.add("hidden");

        // 4. Restore forecast period select
        if (elements.mapPeriodSelect) {
            elements.mapPeriodSelect.classList.remove("hidden");
            elements.mapPeriodSelect.disabled = false;
        }

        // 5. Set or restore currentRainfallMapPeriod
        if (!currentRainfallMapPeriod && shortTermMapDataCache.periods.length > 0) {
            currentRainfallMapPeriod = shortTermMapDataCache.periods[0];
        }

        // 6. Populate period selector options from shortTermMapDataCache.periods
        populatePeriodSelector(shortTermMapDataCache.periods);

        // 7. Apply active rainfall period
        if (currentRainfallMapPeriod) {
            setRainfallMapPeriod(currentRainfallMapPeriod);
        }

    } else if (mode === "temperature") {
        currentMapMode = "temperature";

        // Remove station observation layer if present
        if (stationObservationLayer && leafletMap && leafletMap.hasLayer(stationObservationLayer)) {
            leafletMap.removeLayer(stationObservationLayer);
        }

        // 1. Update mode toggle button attributes
        if (elements.mapModeTemperature) {
            elements.mapModeTemperature.classList.add("active");
            elements.mapModeTemperature.setAttribute("aria-pressed", "true");
        }
        if (elements.mapModeRainfall) {
            elements.mapModeRainfall.classList.remove("active");
            elements.mapModeRainfall.setAttribute("aria-pressed", "false");
        }
        if (elements.mapModeObservations) {
            elements.mapModeObservations.classList.remove("active");
            elements.mapModeObservations.setAttribute("aria-pressed", "false");
        }

        // 2. Toggle legends
        if (elements.mapLegend) elements.mapLegend.classList.remove("hidden");
        if (elements.rainfallLegend) elements.rainfallLegend.classList.add("hidden");
        if (elements.observationLegend) elements.observationLegend.classList.add("hidden");

        // 3. Toggle detail panel summary groups
        if (elements.temperatureSummaryGroup) elements.temperatureSummaryGroup.classList.remove("hidden");
        if (elements.rainfallSummaryGroup) elements.rainfallSummaryGroup.classList.add("hidden");
        if (elements.observationSummaryGroup) elements.observationSummaryGroup.classList.add("hidden");
        if (elements.summaryPeriod) elements.summaryPeriod.classList.remove("hidden");
        if (elements.rainfallSummaryPeriod) elements.rainfallSummaryPeriod.classList.add("hidden");
        if (elements.observationSummaryPeriod) elements.observationSummaryPeriod.classList.add("hidden");

        // 4. Restore forecast period select
        if (elements.mapPeriodSelect) {
            elements.mapPeriodSelect.classList.remove("hidden");
            elements.mapPeriodSelect.disabled = false;
        }

        // 5. Restore period selector options from mapDataCache.periods
        if (mapDataCache && mapDataCache.periods) {
            populatePeriodSelector(mapDataCache.periods);
            if (currentMapPeriod) {
                setMapPeriod(currentMapPeriod);
            }
        }
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

/**
 * Update rainfall summary card group in detail panel (Phase 8B2).
 * Secure DOM manipulation with textContent.
 */
function updateRainfallSummary(forecast) {
    if (!elements.rainfallSummaryGroup) return;

    if (!forecast) {
        if (elements.rainfallSummaryPeriod) elements.rainfallSummaryPeriod.textContent = "--";
        if (elements.rainfallCardWeather) elements.rainfallCardWeather.textContent = "--";
        if (elements.rainfallCardPoP) elements.rainfallCardPoP.textContent = "--";
        if (elements.rainfallCardCI) elements.rainfallCardCI.textContent = "--";
        if (elements.rainfallDetailLastUpdated) {
            elements.rainfallDetailLastUpdated.textContent = formatUpdatedTimestamp(
                shortTermMapDataCache?.updated_at
            );
        }
        return;
    }

    if (elements.rainfallSummaryPeriod) {
        elements.rainfallSummaryPeriod.textContent = formatForecastPeriod(
            forecast.start_time,
            forecast.end_time
        );
    }

    if (elements.rainfallCardWeather) {
        elements.rainfallCardWeather.textContent = forecast.weather || "--";
    }

    if (elements.rainfallCardPoP) {
        elements.rainfallCardPoP.textContent =
            forecast.pop !== null && forecast.pop !== undefined
                ? `${forecast.pop}%`
                : "--";
    }

    if (elements.rainfallCardCI) {
        elements.rainfallCardCI.textContent = forecast.comfort_index || "--";
    }

    if (elements.rainfallDetailLastUpdated) {
        elements.rainfallDetailLastUpdated.textContent = formatUpdatedTimestamp(
            shortTermMapDataCache?.updated_at
        );
    }
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
 * Determine a natural friendly title for the short-term forecast interval
 * derived directly from actual start_time and end_time.
 * Avoids browser timezone conversion by parsing ISO components directly.
 * Does NOT rely on array index as calendar truth.
 *
 * Examples:
 *   "2026-10-07T06:00:00+08:00" ~ "2026-10-07T18:00:00+08:00" -> "10/07 白天"
 *   "2026-10-07T18:00:00+08:00" ~ "2026-10-08T06:00:00+08:00" -> "10/07 晚上 ～ 10/08 清晨"
 *   "2026-10-08T06:00:00+08:00" ~ "2026-10-08T18:00:00+08:00" -> "10/08 白天"
 */
function getShortTermPeriodTitle(startStr, endStr, index) {
    if (!startStr) return "生活預報";
    const startMatch = String(startStr).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
    if (!startMatch) {
        return endStr ? formatForecastPeriod(startStr, endStr) : "生活預報";
    }

    const sMonth = startMatch[2];
    const sDay = startMatch[3];
    const sHour = parseInt(startMatch[4], 10);
    const sDate = `${sMonth}/${sDay}`;

    const endMatch = endStr ? String(endStr).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/) : null;
    const eDate = endMatch ? `${endMatch[2]}/${endMatch[3]}` : "";

    if (sHour >= 5 && sHour < 12) {
        return `${sDate} 白天`;
    } else if (sHour >= 12 && sHour < 18) {
        return `${sDate} 下午至晚上`;
    } else if (sHour >= 18) {
        if (eDate && eDate !== sDate) {
            return `${sDate} 晚上 ～ ${eDate} 清晨`;
        }
        return `${sDate} 晚上`;
    } else {
        // sHour < 5 (e.g. 00:00 - 06:00 凌晨至清晨)
        return `${sDate} 凌晨至清晨`;
    }
}

/**
 * Render 36-hour living forecast cards safely without innerHTML interpolation.
 */
function renderShortTermForecast(forecasts) {
    if (!elements.shortTermCardsGrid) return;
    elements.shortTermCardsGrid.replaceChildren();

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
        const weatherDesc = (f.weather !== null && f.weather !== undefined && String(f.weather).trim() !== "")
            ? String(f.weather).trim()
            : "--";

        let tempStr = "--";
        if (f.min_temp !== null && f.min_temp !== undefined && f.max_temp !== null && f.max_temp !== undefined) {
            tempStr = `${f.min_temp} ～ ${f.max_temp} °C`;
        } else if (f.min_temp !== null && f.min_temp !== undefined) {
            tempStr = `最低 ${f.min_temp} °C`;
        } else if (f.max_temp !== null && f.max_temp !== undefined) {
            tempStr = `最高 ${f.max_temp} °C`;
        }

        const popVal = (f.pop !== null && f.pop !== undefined) ? `${f.pop}%` : "--";

        let popPercent = 0;
        if (typeof f.pop === "number" && !isNaN(f.pop)) {
            popPercent = Math.min(100, Math.max(0, f.pop));
        } else if (typeof f.pop === "string" && f.pop.trim() !== "") {
            const parsedNum = parseFloat(f.pop);
            if (!isNaN(parsedNum)) {
                popPercent = Math.min(100, Math.max(0, parsedNum));
            }
        }

        const ciVal = (f.comfort_index !== null && f.comfort_index !== undefined && String(f.comfort_index).trim() !== "")
            ? String(f.comfort_index).trim()
            : "--";

        // 1. Header: Friendly Period Title & Exact Timestamp
        const headerDiv = document.createElement("div");
        headerDiv.className = "st-card-header";

        const periodNameSpan = document.createElement("span");
        periodNameSpan.className = "st-period-name";
        periodNameSpan.textContent = friendlyTitle;

        const periodTimeSpan = document.createElement("span");
        periodTimeSpan.className = "st-period-time";
        periodTimeSpan.textContent = periodTime;

        headerDiv.appendChild(periodNameSpan);
        headerDiv.appendChild(periodTimeSpan);

        // 2. Weather Row: Icon, Description, Temperature Range
        const weatherRow = document.createElement("div");
        weatherRow.className = "st-weather-row";

        const iconSpan = document.createElement("span");
        iconSpan.className = "st-weather-icon";
        iconSpan.setAttribute("aria-hidden", "true");
        iconSpan.textContent = icon;

        const weatherInfo = document.createElement("div");
        weatherInfo.className = "st-weather-info";

        const descSpan = document.createElement("span");
        descSpan.className = "st-weather-desc";
        descSpan.textContent = weatherDesc;

        const tempSpan = document.createElement("span");
        tempSpan.className = "st-temp-range";
        tempSpan.textContent = `🌡️ ${tempStr}`;

        weatherInfo.appendChild(descSpan);
        weatherInfo.appendChild(tempSpan);

        weatherRow.appendChild(iconSpan);
        weatherRow.appendChild(weatherInfo);

        // 3. Metrics Group: Precipitation Probability (PoP) & Comfort Index (CI)
        const metricsGroup = document.createElement("div");
        metricsGroup.className = "st-metrics-group";

        const popRow = document.createElement("div");
        popRow.className = "st-metric-row";

        const popLabel = document.createElement("span");
        popLabel.className = "st-metric-label";
        popLabel.textContent = "🌧️ 降雨機率";

        const popValue = document.createElement("strong");
        popValue.className = "st-pop-value";
        popValue.textContent = popVal;

        popRow.appendChild(popLabel);
        popRow.appendChild(popValue);

        const popBarBg = document.createElement("div");
        popBarBg.className = "st-pop-bar-bg";
        popBarBg.setAttribute("aria-hidden", "true");

        const popBarFill = document.createElement("div");
        popBarFill.className = "st-pop-bar-fill";
        popBarFill.style.width = `${popPercent}%`;

        popBarBg.appendChild(popBarFill);

        const ciRow = document.createElement("div");
        ciRow.className = "st-metric-row st-ci-row";

        const ciLabel = document.createElement("span");
        ciLabel.className = "st-metric-label";
        ciLabel.textContent = "👕 舒適度";

        const ciValue = document.createElement("span");
        ciValue.className = "st-ci-value";
        ciValue.textContent = ciVal;

        ciRow.appendChild(ciLabel);
        ciRow.appendChild(ciValue);

        metricsGroup.appendChild(popRow);
        metricsGroup.appendChild(popBarBg);
        metricsGroup.appendChild(ciRow);

        // Assemble Card
        card.appendChild(headerDiv);
        card.appendChild(weatherRow);
        card.appendChild(metricsGroup);

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
// Phase 8D: Radar Reflectivity Overlay (O-A0058-002)
// ---------------------------------------------------------------------------

/**
 * Format timestamp into MM/DD HH:mm for radar status badge.
 */
function formatRadarTimestamp(timeStr) {
    if (!timeStr) return "";
    try {
        const d = new Date(timeStr);
        if (isNaN(d.getTime())) return timeStr;
        const month = String(d.getMonth() + 1).padStart(2, "0");
        const day = String(d.getDate()).padStart(2, "0");
        const hours = String(d.getHours()).padStart(2, "0");
        const minutes = String(d.getMinutes()).padStart(2, "0");
        return `${month}/${day} ${hours}:${minutes}`;
    } catch (e) {
        return timeStr;
    }
}

/**
 * Update radar status badge with truthful timestamp labeling.
 */
function updateRadarStatusBadge(metadata) {
    if (!elements.radarStatus) return;
    if (!metadata) {
        elements.radarStatus.textContent = "最新雷達影像";
        return;
    }
    if (metadata.time_source === "radar_datetime" && metadata.radar_time) {
        const formatted = formatRadarTimestamp(metadata.radar_time);
        elements.radarStatus.textContent = `雷達時間：${formatted}`;
    } else if (metadata.time_source === "last_modified" && metadata.updated_at) {
        const formatted = formatRadarTimestamp(metadata.updated_at);
        elements.radarStatus.textContent = `影像更新：${formatted}`;
    } else {
        elements.radarStatus.textContent = "最新雷達影像";
    }
}

/**
 * Append harmless cache-busting version parameter to official ProductURL without modifying base URL.
 */
function getRadarImageUrlWithVersion(metadata) {
    if (!metadata || !metadata.image_url) return "";
    const versionVal = metadata.radar_time || metadata.updated_at || Date.now().toString();
    const sep = metadata.image_url.includes("?") ? "&" : "?";
    return `${metadata.image_url}${sep}v=${encodeURIComponent(versionVal)}`;
}

/**
 * Lazy-load radar metadata from /api/radar.
 */
async function loadRadarMetadata(forceRefresh = false) {
    if (radarMetadataCache && !forceRefresh) {
        return radarMetadataCache;
    }
    const url = forceRefresh ? `/api/radar?_t=${Date.now()}` : "/api/radar";
    try {
        const res = await fetch(url);
        if (!res.ok) {
            throw new Error(`Radar API returned status ${res.status}`);
        }
        const data = await res.json();
        radarMetadataCache = data;
        return data;
    } catch (err) {
        console.error("Failed to load radar metadata:", err);
        return null;
    }
}

/**
 * Apply or refresh Leaflet image overlay for radar reflectivity.
 */
async function applyRadarOverlay(forceRefresh = false) {
    if (!elements.radarStatus) return;
    elements.radarStatus.textContent = "正在載入雷達回波...";
    elements.radarStatus.classList.remove("hidden");

    const metadata = await loadRadarMetadata(forceRefresh);
    if (!metadata || !metadata.image_url) {
        if (elements.radarStatus) {
            elements.radarStatus.textContent = "雷達影像暫時無法載入";
        }
        if (radarOverlayLayer && leafletMap && leafletMap.hasLayer(radarOverlayLayer)) {
            leafletMap.removeLayer(radarOverlayLayer);
        }
        return;
    }

    const bounds = metadata.bounds
        ? [[metadata.bounds.south, metadata.bounds.west], [metadata.bounds.north, metadata.bounds.east]]
        : [[17.75, 115.00], [29.25, 126.50]];

    const versionedUrl = getRadarImageUrlWithVersion(metadata);

    // If overlay already exists on map, remove to recreate safely without recreating whole map
    if (radarOverlayLayer && leafletMap && leafletMap.hasLayer(radarOverlayLayer)) {
        leafletMap.removeLayer(radarOverlayLayer);
    }

    radarOverlayLayer = L.imageOverlay(versionedUrl, bounds, {
        opacity: radarOpacity,
        interactive: false,
        pane: "radarPane",
    });

    radarOverlayLayer.on("load", () => {
        updateRadarStatusBadge(metadata);
    });

    radarOverlayLayer.on("error", () => {
        if (leafletMap && leafletMap.hasLayer(radarOverlayLayer)) {
            leafletMap.removeLayer(radarOverlayLayer);
        }
        if (elements.radarStatus) {
            elements.radarStatus.textContent = "雷達影像暫時無法載入";
        }
    });

    if (radarEnabled && leafletMap) {
        radarOverlayLayer.addTo(leafletMap);
    }
}

/**
 * Start 10-minute non-blocking auto-refresh timer while radar is active.
 */
function startRadarAutoRefresh() {
    stopRadarAutoRefresh();
    radarAutoRefreshTimer = setInterval(async () => {
        if (radarEnabled) {
            try {
                await applyRadarOverlay(true);
            } catch (e) {
                console.warn("Non-blocking radar auto-refresh failed:", e);
            }
        }
    }, 600000); // 10 minutes (600,000 ms)
}

/**
 * Stop auto-refresh timer.
 */
function stopRadarAutoRefresh() {
    if (radarAutoRefreshTimer) {
        clearInterval(radarAutoRefreshTimer);
        radarAutoRefreshTimer = null;
    }
}

/**
 * Toggle radar reflectivity overlay on/off.
 */
async function toggleRadar() {
    if (radarEnabled) {
        radarEnabled = false;
        if (elements.radarToggle) {
            elements.radarToggle.setAttribute("aria-pressed", "false");
            elements.radarToggle.classList.remove("active");
        }
        if (elements.radarOpacity) {
            elements.radarOpacity.disabled = true;
        }
        if (elements.radarRefresh) {
            elements.radarRefresh.disabled = true;
        }
        if (elements.radarStatus) {
            elements.radarStatus.classList.add("hidden");
        }
        if (elements.radarControlsWrapper) {
            elements.radarControlsWrapper.classList.add("disabled");
        }
        if (radarOverlayLayer && leafletMap && leafletMap.hasLayer(radarOverlayLayer)) {
            leafletMap.removeLayer(radarOverlayLayer);
        }
        stopRadarAutoRefresh();
    } else {
        radarEnabled = true;
        if (elements.radarToggle) {
            elements.radarToggle.setAttribute("aria-pressed", "true");
            elements.radarToggle.classList.add("active");
        }
        if (elements.radarOpacity) {
            elements.radarOpacity.disabled = false;
        }
        if (elements.radarRefresh) {
            elements.radarRefresh.disabled = false;
        }
        if (elements.radarControlsWrapper) {
            elements.radarControlsWrapper.classList.remove("disabled");
        }
        await applyRadarOverlay(false);
        startRadarAutoRefresh();
    }
}

/**
 * Initialize event listeners for radar overlay controls.
 */
function initRadarControls() {
    if (elements.radarToggle) {
        elements.radarToggle.addEventListener("click", () => {
            toggleRadar();
        });
    }

    if (elements.radarOpacity) {
        elements.radarOpacity.addEventListener("input", (e) => {
            const val = parseFloat(e.target.value);
            if (!isNaN(val)) {
                radarOpacity = val;
                elements.radarOpacity.setAttribute("aria-valuenow", val.toString());
                const percentEl = document.getElementById("radar-opacity-val");
                if (percentEl) {
                    percentEl.textContent = `${Math.round(val * 100)}%`;
                }
                if (radarOverlayLayer) {
                    radarOverlayLayer.setOpacity(radarOpacity);
                }
            }
        });
    }

    if (elements.radarRefresh) {
        elements.radarRefresh.addEventListener("click", async () => {
            if (radarEnabled) {
                await applyRadarOverlay(true);
            }
        });
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

    // 5c. Attach click listeners to map mode buttons (Phase 8B2, Phase 8C)
    if (elements.mapModeTemperature) {
        elements.mapModeTemperature.addEventListener("click", () => {
            setMapMode("temperature");
        });
    }
    if (elements.mapModeRainfall) {
        elements.mapModeRainfall.addEventListener("click", () => {
            setMapMode("rainfall");
        });
    }
    if (elements.mapModeObservations) {
        elements.mapModeObservations.addEventListener("click", () => {
            setMapMode("observations");
        });
    }

    // 6. Attach change event listener to forecast period selector
    if (elements.mapPeriodSelect) {
        elements.mapPeriodSelect.addEventListener("change", (event) => {
            const selectedKey = event.target.value;
            if (currentMapMode === "rainfall") {
                const period = shortTermMapDataCache?.periods?.find(
                    (p) => `${p.start_time}_${p.end_time}` === selectedKey
                );
                if (period) {
                    setRainfallMapPeriod(period);
                }
            } else {
                const period = mapDataCache?.periods?.find(
                    (p) => `${p.start_time}_${p.end_time}` === selectedKey
                );
                if (period) {
                    setMapPeriod(period);
                }
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
