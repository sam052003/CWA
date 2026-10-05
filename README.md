# CWA Taiwan Weather Forecast (中央氣象署一週天氣預報)

以**中央氣象署（CWA）Open Data API** 為資料來源的臺灣天氣預報網站，支援 22 縣市一週預報、最高/最低溫折線圖與預報資料表。

> **專案規格與主要設計原則**：請參閱 [`MyPlan/design.md`](MyPlan/design.md)。

---

## Live Demo

- **Production URL**: [https://cwa-9cyxfmmd2-cwa-weather-project.vercel.app/](https://cwa-9cyxfmmd2-cwa-weather-project.vercel.app/)

> **說明**：本網址為目前專案正式上線之 Vercel Production 站台，已完整串接 Supabase PostgreSQL 資料庫與每日定時 Vercel Cron 排程自動更新。

### 專案階段狀態摘要

- Phase 1 ✅ Environment
- Phase 2 ✅ CWA API & Parser
- Phase 3 ✅ Supabase PostgreSQL
- Phase 4 ✅ FastAPI Web API
- Phase 5 ✅ Frontend Dashboard
- Phase 6 ✅ Vercel Production Deployment & Scheduled Refresh
- Phase 7A ✅ Taiwan County Forecast Map
- Phase 7B ✅ Forecast Period Map
- Phase 7C ✅ Complete Taiwan Weather Dashboard
- Phase 8A 📋 App Experience & Map Workspace (實作完成，待正式環境手動驗收)

---

## 技術架構

- **後端 Web 框架**：FastAPI
- **資料庫**：PostgreSQL (Supabase)，使用 SQLAlchemy + psycopg driver（不使用 SQLite）
- **前端介面**：HTML + CSS + JavaScript + Chart.js
- **部署平台**：Vercel (Serverless)
- **版本控制**：Git + GitHub

---

## 專案目錄結構

```text
CWA/
├─ MyPlan/
│  └─ design.md              # 系統主要設計規格文件
├─ app/
│  ├─ main.py                # FastAPI 應用程式主入口
│  ├─ core/
│  │  ├─ __init__.py
│  │  └─ config.py           # 集中環境變數管理 (pydantic-settings)
│  ├─ api/
│  │  └─ routes.py           # API 路由與 Health Check
│  ├─ services/
│  │  └─ weather_service.py  # 業務邏輯服務層 (Phase 4)
│  ├─ repositories/
│  │  └─ weather_repository.py # 資料庫存取層 (Phase 3)
│  ├─ clients/
│  │  └─ cwa_client.py       # CWA API 連線 Client (Phase 2)
│  ├─ parsers/
│  │  └─ cwa_parser.py       # JSON 解析與正規化 (Phase 2)
│  ├─ db/
│  │  ├─ database.py         # PostgreSQL 連線設定 (Supabase)
│  │  └─ models.py           # SQLAlchemy Data Models
│  ├─ templates/
│  │  └─ index.html          # 前端 HTML 模板 (Phase 5)
│  └─ static/
│     ├─ css/style.css       # 樣式表 (Phase 5)
│     └─ js/app.js           # 前端互動邏輯 (Phase 5)
├─ scripts/
│  ├─ init_db.py             # 資料庫初始化腳本
│  └─ fetch_weather.py       # 天氣資料更新腳本
├─ tests/
│  ├─ test_api.py            # API 端點測試
│  ├─ test_config.py         # 設定與環境變數測試
│  ├─ test_cwa_client.py     # CWA 連線 Client 測試 (Phase 2)
│  ├─ test_deployment.py     # 部署準備與受保護 Cron 測試 (Phase 6)
│  ├─ test_frontend.py       # 前端模板與靜態資源測試 (Phase 5)
│  ├─ test_parser.py         # JSON Parser 測試 (Phase 2)
│  ├─ test_repository.py     # Repository 測試 (Phase 3)
│  └─ test_weather_service.py# 業務服務層測試 (Phase 4)
├─ .env.example              # 環境變數範本 (集中管理 APP_NAME, ENVIRONMENT, PORT, CWA_API_KEY, DATABASE_URL)
├─ .gitignore                # 排除敏感檔案與虛擬環境
├─ requirements.txt          # Python 依賴套件清單
├─ vercel.json               # Vercel 部署設定
├─ README.md                 # 專案說明與啟動指南
└─ .python-version           # Python 版本聲明
```

---

## 本機快速啟動指南

### 1. 建立並啟用 Python 虛擬環境

**Windows (PowerShell)**:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 安裝依賴套件

```bash
pip install -r requirements.txt
```

### 3. 設定環境變數

複製範本檔案 `.env.example` 為 `.env`：

**Windows (PowerShell)**:
```powershell
Copy-Item .env.example .env
```

**macOS / Linux**:
```bash
cp .env.example .env
```

編輯 `.env` 檔案並填入相應的金鑰與資料庫連線資訊：
```env
APP_NAME=CWA Taiwan Weather Forecast
ENVIRONMENT=development
PORT=8000
CWA_API_KEY=your_cwa_api_key_here
DATABASE_URL=postgresql+psycopg://postgres.<PROJECT_REF>:<PASSWORD>@<POOLER_HOST>:6543/postgres
```

> **重要安全須知**：
> - `.env` 檔案已被 `.gitignore` 排除，**切勿將真實的 API Key 或密碼 commit 到 GitHub**。
> - Production 部署時，請在 Vercel 後台 Project Settings → Environment Variables 中設定。

### 4. 啟動本機開發伺服器

使用 `uvicorn` 啟動：
```bash
uvicorn app.main:app --reload --port 8000
```
或直接執行：
```bash
python -m app.main
```

### 5. 檢視與測試端點

啟動後，瀏覽器或 API 測試工具可訪問：
- **氣象預報儀表板首頁**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **系統健康檢查 (Health Check)**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- **API 健康檢查**: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- **FastAPI 自動化 Swagger API 文件**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **縣市列表 API**: [http://127.0.0.1:8000/api/regions](http://127.0.0.1:8000/api/regions)
- **指定縣市天氣預報 API**: [http://127.0.0.1:8000/api/forecast?region=臺中市](http://127.0.0.1:8000/api/forecast?region=臺中市)
- **全臺縣市地圖預報資料 API**: [http://127.0.0.1:8000/api/map-data](http://127.0.0.1:8000/api/map-data)
- **臺灣縣市邊界 GeoJSON**: [http://127.0.0.1:8000/static/data/taiwan_counties.geojson](http://127.0.0.1:8000/static/data/taiwan_counties.geojson)
- **手動更新預報 API (POST, 開發環境)**: `http://127.0.0.1:8000/api/refresh`
- **ReDoc 文件**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### 6. 執行自動化測試

```bash
pytest
```

---

## Vercel 雲端正式部署指南 (Phase 6 準備)

本專案支援 **Vercel Zero-Config FastAPI** 原生辨識部署，無需自訂 legacy builds 或 catch-all rewrites。

### 1. 建立 Vercel 專案

1. 登入 [Vercel Dashboard](https://vercel.com/)。
2. 點擊 **Add New...** → **Project**。
3. 匯入 GitHub 專案 `sam052003/CWA`。
4. Framework Preset 選擇 **Other**（Vercel 將自動辨識 `app/main.py` 的 FastAPI 實例）。

### 2. 設定 Vercel 環境變數

在 Vercel 專案設定頁面 (**Settings** → **Environment Variables**) 加入以下變數：

#### 應用程式一般設定 (Config)
```text
APP_NAME=CWA Taiwan Weather Forecast
ENVIRONMENT=production
```

> **注意**：Vercel Serverless Function 環境無需設定 `PORT`。

#### 機敏金鑰 (Secrets)
| 變數名稱 | 說明 | 範例 / 格式 |
|---|---|---|
| `CWA_API_KEY` | 中央氣象署 Open Data API Key | `CWA-XXXXXXXX-XXXX-...` |
| `DATABASE_URL` | Supabase Transaction Pooler (port 6543) | `postgresql+psycopg://postgres.<REF>:<PWD>@<POOLER_HOST>:6543/postgres` |
| `CRON_SECRET` | Vercel Cron 受保護端點驗證金鑰 | 由安全指令產生的 32+ 字元隨機字串 |

#### 安全產生 `CRON_SECRET` 指令
請在本機終端機執行下列指令產生隨機金鑰，直接貼至 Vercel 後台（**切勿將真實金鑰提交至版本庫**）：
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Vercel Cron 定時資料更新排程

本專案於 `vercel.json` 配置每日 UTC 00:00 透過受保護端點 `GET /api/cron/refresh` 自動觸發氣象資料更新：

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "crons": [
    {
      "path": "/api/cron/refresh",
      "schedule": "0 0 * * *"
    }
  ]
}
```

> **Production 排程與方案說明**：
> - **Cron expression 使用 UTC**：`0 0 * * *` 代表每日一次（UTC 00:00）。
> - **Hobby 方案執行時間**：Vercel Hobby（免費方案）之定時工作會排入該小時的佇列中執行，因此臺灣時間大約於 **08:00～08:59** 觸發更新。
> - **更新管道**：
>   ```text
>   Vercel Cron → protected GET /api/cron/refresh → CWA → Supabase
>   ```
> - **升級至 Pro**：若未來升級至 Vercel Pro 方案，可將 schedule 修改為 `0 */6 * * *` 實現約每 6 小時自動更新。

---

## 正式上線系統架構 (Production Architecture)

```text
CWA Open Data API
        ↓
    CWA Client
        ↓
Parser / Normalizer
        ↓
  Weather Service
        ↓
Supabase PostgreSQL
        ↓
    FastAPI API
        ↓
 HTML / JavaScript
        ↓
Chart.js / Forecast Table
        ↓
 Vercel Production

Scheduled Update：

Vercel Cron
    ↓
GET /api/cron/refresh
    ↓
CRON_SECRET authentication
    ↓
Weather Service
    ↓
CWA Open Data API
    ↓
Supabase PostgreSQL
```

---

## 目前開發進度

- [x] **Phase 1: 環境與基礎架構**
  - 專案目錄結構建立
  - FastAPI 基礎架構與 Health Check / Hello World 端點
  - `requirements.txt`、`.gitignore`、`.env.example`
  - 安全保護機制（預留 `CWA_API_KEY` 與 `DATABASE_URL`，確保 Secrets 不外洩）
  - 本機啟動與測試流程建立
- [x] **Phase 2: CWA API 資料串接與解析**
  - CWA Client 實作（Timeout、例外處理、Datastore 404 至 File API fallback）
  - 取得真實 CWA 一週預報 Sample JSON Fixture（無 Secret）
  - CWA JSON Parser（以 `(startTime, endTime)` 對齊 Wx, MinT, MaxT，具備完整異常處理）
  - 完整 Mock 單元測試與 Fixture 結構測試
- [x] **Phase 3: Supabase PostgreSQL 資料庫串接與 Repository**
  - Supabase PostgreSQL connection（採用 Transaction Pooler + NullPool 連線策略，停用 prepared statements）
  - `weather_forecasts` 與 `fetch_logs` 資料表結構
  - PostgreSQL UPSERT（以 `(dataset_id, region_name, start_time, end_time)` 為鍵避免重複累積）
  - Repository query（縣市列表去重排序與指定縣市依時間排序預報）
  - Transaction handling（全成功 commit，失敗自動 rollback 並記錄 failure log）
  - `--save-db` 指令列旗標支援真實資料寫入與安全摘要輸出
- [x] **Phase 4: Web API 端點 (`/api/regions`, `/api/forecast`, `/api/refresh`)**
  - `GET /api/regions`：取得資料庫中現有 22 縣市清單
  - `GET /api/forecast?region={region_name}`：查詢指定縣市最新未過期預報（依 `start_time ASC` 排序，時間為 `Asia/Taipei (+08:00)`）
  - `POST /api/refresh`：觸發從 CWA API 更新並寫入資料庫（開發環境可用，production 環境回傳 403）
  - 完整業務邏輯與驗證封裝於 Weather Service 層，提供統一例外處理與安全機敏字串過濾
- [x] **Phase 5: 前端視覺化 (HTML, CSS, JavaScript, Chart.js)**
  - 首頁 `GET /` 整合 Jinja2 模板動態提供天氣儀表板
  - 22 縣市下拉選單（預設臺中市，非同步動態載入無刷新切換）
  - 近期預報時段摘要資訊卡（天氣現象、預測最低溫與最高溫）
  - Chart.js 折線圖（呈現未來一週最高溫與最低溫趨勢，切換地區自動銷毀重建避免重疊）
  - 完整時段預報詳細資料表（保留 CWA 約 12 小時真實區間，支援行動版水平捲動與響應式排版）
  - 載入中（Loading）與錯誤處理（Error Banner）狀態提示，XSS 安全過濾與無障礙設計 (a11y)
- [x] **Phase 6: Vercel 雲端正式部署與定時更新 (正式完成)**
  - [x] Vercel Zero-Config 設定（`vercel.json` 移除 catch-all rewrites）
  - [x] Vercel Project 建立並連結 GitHub
  - [x] Production Environment Variables 已設定 (`APP_NAME`, `ENVIRONMENT`, `CWA_API_KEY`, `DATABASE_URL`, `CRON_SECRET`)
  - [x] Supabase production connection 驗證正常
  - [x] Vercel Build & Deployment 成功部署
  - [x] Production smoke test 驗收通過
  - [x] Protected Cron endpoint 部署完成 (`GET /api/cron/refresh`)
  - [x] Supabase fetch_logs success verified（成功寫入 success 更新日誌）
- [x] **Phase 7A: 臺灣縣市預報地圖 (Leaflet 互動地圖視覺化)**
  - [x] 整合 Leaflet 1.9.4 與 OpenStreetMap 底圖（保留官方圖資版權與署名）
  - [x] 新增 `GET /api/map-data`：套用 Latest Batch Rule，依最新批次與非過期時段回傳 22 縣市預報資料
  - [x] 資料一致性修正：同步將 Latest Batch Rule 套用至 `GET /api/forecast`，排除歷史重複批次之干擾
  - [x] 臺灣 22 縣市行政邊界 GeoJSON（`app/static/data/taiwan_counties.geojson`）
  - [x] 縣市分級面量圖（Choropleth）：依最近預報時段之預測最高溫分級著色，搭配「預測最高溫 °C」圖例
  - [x] 懸浮互動提示（Tooltip）：即時呈現縣市名稱、天氣現象、預測最低／最高溫
  - [x] 地圖點擊與縣市選單雙向同步（點擊多邊形立即更新摘要卡、Chart.js 折線圖與詳細預報清單）
  - [x] 專業氣象 GIS 儀表板排版（桌面版地圖 65–70% + 摘要面板 30–35%）與跨裝置響應式支援
- [x] **Phase 7B: 預報時段切換控制 (選擇日期／預報時段顯示地圖 — 生產環境已驗收完成)**
  - [x] forecast periods available（有效預報時段可用）
  - [x] period selector（時段下拉選單）
  - [x] switching period updates all counties（切換時段即時更新全縣市多邊形與摘要）
  - [x] no page reload（零頁面重整）
  - [x] no 22 API requests（零額外網路請求，不發送 22 次 API）
- [x] **Phase 7C: 完整成果展示 Taiwan Weather Dashboard (對應課程第 19 項 — 已完成並通過生產環境驗收)**
  - [x] map-first dashboard layout（地圖優先氣象儀表板整體整合）
  - [x] selected county detail panel（選定縣市即時摘要面板，含資料更新時間）
  - [x] existing Chart.js integrated（既有 Chart.js 一週溫度趨勢折線圖整合）
  - [x] existing forecast table integrated（既有預報詳細時段資料表整合）
  - [x] responsive desktop/mobile（桌面／平板／手機跨裝置響應式排版）
- [ ] **Phase 8: Advanced Weather Platform**
  - [ ] **8A**: App Experience & Map Workspace（實作完成，待正式環境手動驗收 — 深淺模式、OSM 濾鏡適配、地圖擴展為 600–680px 主工作台、桌面浮動面板、重設視角、全螢幕地圖）
  - [ ] **8B**: Rich County Forecast（串接 `F-C0032-001` 今明 36 小時預報，新增降雨機率 `PoP` 與舒適度指數 `CI`）
  - [ ] **8C**: Current Weather Observations（串接 `O-A0001` 全臺自動氣象站即時觀測，UI 嚴格區隔「目前觀測」與「未來預報」）
  - [ ] **8D**: Radar Layer（串接 `O-A0058-002` 雷達回波合成圖，支援 ImageOverlay、透明度調整與時間戳記，零二進位寫庫）
  - [ ] **8E**: Typhoon Center（串接 `W-C0034-005` 颱風分析與預報、路徑線段、暴風圈半徑多邊形、西北太平洋廣域視角與正常空狀態）
  - [ ] **8F**: Township Detailed Forecast（串接 `F-D0047-093` 鄉鎮市區細緻預報，伺服器端過濾分級查詢，防禦巨量資料傳輸）
  - [ ] **8G**: Application Polish / Future Features（最愛縣市、分享網址狀態、PWA 支援、警特報橫幅與全方位無障礙適配）

> **完整系統設計規格**：請參閱 [`MyPlan/design.md#phase-8--advanced-weather-platform`](MyPlan/design.md#phase-8--advanced-weather-platform)。

---

## 地圖圖資與 GeoJSON 資料來源說明

| 項目 | 說明 |
|---|---|
| **資料集名稱** | 臺灣直轄市、縣市界線（twCounty2010.geo.json） |
| **直接來源** | g0v/twgeojson（[https://github.com/g0v/twgeojson](https://github.com/g0v/twgeojson)） |
| **圖資授權** | CC0 1.0 Universal |
| **座標系統** | WGS84 (EPSG:4326) 經緯度 |
| **圖資處理** | 進行適度幾何簡化以縮減靜態資源傳輸大小（約 636 KB），並將縣市名稱標準化（例如將「台」統一為「臺」、「桃園縣」更新為「桃園市」），確保 22 縣市名稱與中央氣象署 CWA `region_name` 100% 精準對齊。 |
| **底圖來源** | OpenStreetMap Tiles（&copy; OpenStreetMap contributors） |



