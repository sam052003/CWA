/**
 * CWA Taiwan Weather Forecast — Client Application
 * Phase 5: Modular, accessible, and secure weather dashboard logic.
 */

// Global Chart.js instance holder
let temperatureChartInstance = null;

// DOM Element References
const elements = {
    regionSelect: document.getElementById("region-select"),
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
    if (!elements.chartCanvas) return;

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
                        font: {
                            family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                            size: 13,
                            weight: "600",
                        },
                        color: "#0f172a",
                    },
                },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            return `${context.dataset.label}: ${context.parsed.y} °C`;
                        },
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
// Data Fetching: API Calls (GET /api/regions and GET /api/forecast)
// ---------------------------------------------------------------------------

async function loadForecast(regionName) {
    if (!regionName) return;

    setLoading(true, `正在載入 ${regionName} 天氣預報...`);

    try {
        const encodedRegion = encodeURIComponent(regionName);
        const response = await fetch(`/api/forecast?region=${encodedRegion}`);

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
        console.error("Forecast fetch error:", err);
        showError("目前無法取得天氣資料，請稍後再試。");
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

        // Default selection: Prefer '臺中市', otherwise first region
        const defaultRegion = regions.includes("臺中市") ? "臺中市" : regions[0];
        elements.regionSelect.value = defaultRegion;

        // Automatically trigger forecast load for default region
        await loadForecast(defaultRegion);
    } catch (err) {
        console.error("Regions load error:", err);
        elements.regionSelect.disabled = true;
        showError("無法載入縣市清單，請確認網路連線或稍後再試。");
    }
}

// ---------------------------------------------------------------------------
// Initialization on DOMContentLoaded
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
    // Attach change event listener to region selector
    if (elements.regionSelect) {
        elements.regionSelect.addEventListener("change", (event) => {
            const selectedRegion = event.target.value;
            loadForecast(selectedRegion);
        });
    }

    // Initial load
    loadRegions();
});
