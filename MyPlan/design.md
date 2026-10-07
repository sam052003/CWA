# CWA Taiwan Weather Forecast — System Design

> 專案：CWA 天氣預報網站  
> Repository：`sam052003/CWA`  
> 文件目的：定義資料來源、資料流程、PostgreSQL schema、網站功能與 Vercel 部署方式，再依此逐步實作。

---

## 1. 專案目標

建立一個以 **中央氣象署（CWA）Open Data API** 為資料來源的臺灣天氣預報網站，完成以下完整流程：

1. 從 CWA Open Data API 取得 JSON 天氣資料。
2. 使用 Python 解析與整理 JSON。
3. 將整理後的預報資料存入 PostgreSQL。
4. 透過 SQL 查詢地區與日期資料。
5. 建立 Web App，讓使用者選擇縣市並查看一週天氣預報。
6. 使用折線圖與資料表呈現最高／最低溫。
7. 將專案版本控制於 GitHub。
8. 最終部署至 Vercel。

整體流程：

`CWA API → JSON → Python → Data Processing → PostgreSQL → SQL Query → Web App → Chart/Table → GitHub → Vercel`

---

## 2. MVP 功能範圍

第一版先完成「可以穩定展示與部署」的核心功能，不一開始加入過多功能。

### 必做功能

- CWA API 資料取得
- 臺灣 22 縣市一週天氣預報
- 縣市下拉選單
- 顯示：
  - 日期
  - 天氣現象
  - 最低溫
  - 最高溫
- 一週最高／最低溫折線圖
- 一週預報資料表
- PostgreSQL 儲存
- SQL 查詢
- 手機／桌面基本響應式介面
- GitHub 版本控制
- Vercel 部署

### 第二階段再加入

- 臺灣地圖視覺化
- 鄉鎮市區預報
- 降雨機率
- 體感溫度
- 相對濕度
- 風速／風向
- UV
- 歷史查詢或資料分析
- 天氣提醒／AI 摘要

---

## 3. CWA 資料來源

### 3.1 第一版資料集

MVP 優先使用：

`F-C0032-005` — **一般天氣預報－1 週縣市天氣預報**

核心欄位：

- `Wx`：天氣現象
- `MinT`：最低溫度
- `MaxT`：最高溫度

API 端點與呼叫說明：

- Datastore API Base URL：
  ```text
  https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-005
  ```
- File API Base URL（實際資料端點）：
  ```text
  https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/F-C0032-005?format=JSON
  ```

> **API 呼叫說明**：在氣象署平台實際取得 `F-C0032-005` 資料時，Datastore endpoint 會回傳 HTTP 404 (`Resource not found`)。目前 CWA Client 會自動 fallback 到 CWA File API (`fileapi/v1/opendataapi/F-C0032-005?format=JSON`) 取得完整預報 JSON。

### 3.2 進階資料集

若之後需要「鄉鎮市區」與更多氣象元素，可再加入：

`F-D0047-093`

可用於第二階段的地圖、鄉鎮選擇、降雨機率、濕度、風速等功能。

### 3.3 環境變數與 API Key 管理

**CWA API Key 與 Database Credentials 不得寫入 GitHub 原始碼。**

專案所有環境變數由 `app/core/config.py` 的 `Settings` class 集中管理：

- 使用 `pydantic-settings` 搭配 `BaseSettings` 與 `SettingsConfigDict`。
- 本機開發自動讀取根目錄 `.env`（由 `.env.example` 複製建立）。
- 部署至 Vercel 時由平台 `Project Settings → Environment Variables` 注入。
- 所有 application modules 不直接呼叫 `os.getenv()` 或 `load_dotenv()`。
- 透過 `get_settings()` 取得 cached `Settings` singleton instance。

`.env` 範例內容：

```env
APP_NAME=CWA Taiwan Weather Forecast
ENVIRONMENT=development
PORT=8000
CWA_API_KEY=your_cwa_api_key_here
DATABASE_URL=postgresql+psycopg://postgres.<PROJECT_REF>:<PASSWORD>@<POOLER_HOST>:6543/postgres
```

程式取得設定方式：

```python
from app.core.config import get_settings

settings = get_settings()
api_key = settings.cwa_api_key
```

前端 JavaScript **不能直接取得 API Key 或 Database URL**；所有外部 API 請求與資料庫操作必須由 server-side Python 執行。

---

## 4. 技術選型

| 項目 | 技術 |
|---|---|
| Language | Python 3.12 |
| Settings / Config | pydantic-settings |
| CWA API Request | requests / httpx |
| Web Backend | FastAPI |
| HTML Template | Jinja2 |
| Frontend | HTML + CSS + JavaScript |
| Chart | Chart.js |
| Database | PostgreSQL |
| Managed Database | Supabase |
| ORM / DB Layer | SQLAlchemy |
| PostgreSQL Driver | psycopg |
| Version Control | Git + GitHub |
| Deployment | Vercel |
| Testing | pytest |

### 為什麼使用 PostgreSQL + Supabase？

老師提供的 SQLite 流程很適合教學與單機練習，但本專案預計最終部署到 **Vercel**。

PostgreSQL + Supabase 的優點：

- 保留完整 SQL 學習內容。
- 適合真正的 Web App。
- 資料不會因 Vercel Serverless Instance 重啟而消失。
- 本機與正式環境可以共用相同資料庫架構。
- Supabase 提供網頁介面，可直接查看 Table 與資料。
- 未來若增加使用者、收藏地區、歷史資料等功能也容易擴充。

---

## 5. 系統架構

```text
CWA Open Data API
        ↓
Python CWA Client
        ↓
JSON Parser / Normalizer
        ↓
Weather Service
        ↓
Supabase PostgreSQL
        ↓
Repository / SQL Query
        ↓
FastAPI
        ↓
HTML + JavaScript
        ↓
Chart.js + Forecast Table
        ↓
Vercel
```

### 分層原則

#### API Client

只負責：

- 呼叫 CWA API
- Timeout
- HTTP status
- JSON response
- API error handling

#### Parser

只負責：

- 找出 CWA JSON 中需要的資料
- `Wx / MinT / MaxT`
- 將不同 weatherElement 的時間資料整併成統一格式

#### Service

負責：

- refresh forecast
- 驗證資料
- 呼叫 parser
- 寫入 database
- 查詢最新資料

#### Repository

所有 SQL / Database Access 集中在 repository，不將 SQL 散落在 route 與 UI。

#### Web

FastAPI route 只處理：

- request
- parameter validation
- service call
- response

---

## 6. 資料流程

### Step 1 — 取得 CWA JSON

Python server 使用環境變數中的 Authorization Key 呼叫 CWA API。

概念：

```python
headers = {
    "Authorization": CWA_API_KEY
}

response = requests.get(
    CWA_API_URL,
    headers=headers,
    timeout=15
)
```

### Step 2 — JSON Parser 與實際資料結構

根據實際取得的 sample JSON（`tests/fixtures/cwa_f_c0032_005_sample.json`），`F-C0032-005` 的實際樹狀層級為：

```text
cwaopendata
└─ dataset
   └─ location[]
      ├─ locationName
      └─ weatherElement[]
         ├─ elementName
         └─ time[]
            ├─ startTime
            ├─ endTime
            └─ parameter
```

各氣象元素資料細節：

- **Wx**：
  - `parameter.parameterName` = 天氣文字（例如 `"晴時多雲"`）
  - `parameter.parameterValue` = 天氣代碼（例如 `"2"`）
- **MaxT**：
  - `parameter.parameterName` = 溫度數值（字串，例如 `"27"`，需轉為數值）
  - `parameter.parameterUnit` = `C`
- **MinT**：
  - `parameter.parameterName` = 溫度數值（字串，例如 `"25"`，需轉為數值）
  - `parameter.parameterUnit` = `C`

目前實際 sample 規格：
- **22 locations**：涵蓋臺灣全部 22 個縣市
- **weather elements**：固定包含 `Wx`, `MaxT`, `MinT`
- **12 小時區間**：每個 element 包含 15 個時間區間（每 12 小時一個區間資料）

Parser 需要依據各縣市與時間區間（以 `startTime` 與 `endTime` 為鍵）將 `Wx`、`MinT`、`MaxT` 整併對齊。

標準化後：

```json
{
  "region_name": "臺中市",
  "start_time": "2026-10-03T18:00:00+08:00",
  "end_time": "2026-10-04T06:00:00+08:00",
  "weather": "多雲",
  "min_temp": 24,
  "max_temp": 30
}
```

### Step 3 — 寫入 PostgreSQL

採 UPSERT，避免每次更新產生重複資料。

### Step 4 — SQL Query

使用者選擇縣市後：

```sql
SELECT
    region_name,
    start_time,
    end_time,
    weather,
    min_temp,
    max_temp
FROM weather_forecasts
WHERE region_name = :region_name
ORDER BY start_time ASC;
```

### Step 5 — Website

FastAPI 將資料傳給前端：

- Chart.js 畫折線圖
- HTML table 顯示預報
- Selector 切換縣市

---

## 7. PostgreSQL Database Design

Database 使用：

**Supabase PostgreSQL**

### 7.1 weather_forecasts

```sql
CREATE TABLE IF NOT EXISTS weather_forecasts (
    id BIGSERIAL PRIMARY KEY,
    dataset_id VARCHAR(50) NOT NULL,
    region_name VARCHAR(50) NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    weather VARCHAR(100),
    min_temp REAL,
    max_temp REAL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_weather_forecast
        UNIQUE (dataset_id, region_name, start_time, end_time)
);
```

### Index

```sql
CREATE INDEX IF NOT EXISTS idx_weather_region_start
ON weather_forecasts(region_name, start_time);
```

### 7.2 fetch_logs

記錄資料更新是否成功。

```sql
CREATE TABLE IF NOT EXISTS fetch_logs (
    id BIGSERIAL PRIMARY KEY,
    dataset_id VARCHAR(50) NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL,
    records_count INTEGER DEFAULT 0,
    error_message TEXT
);
```

用途：

- 確認最近更新時間
- CWA API 異常時除錯
- 網站顯示「最後更新時間」

---

## 8. Supabase Database Connection

### 8.1 本機開發

`.env`

```env
APP_NAME=CWA Taiwan Weather Forecast
ENVIRONMENT=development
PORT=8000
CWA_API_KEY=your_cwa_api_key_here
DATABASE_URL=postgresql+psycopg://postgres.<PROJECT_REF>:<PASSWORD>@<POOLER_HOST>:6543/postgres
```

Python 端（透過集中設定存取）：

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    poolclass=NullPool,
    pool_pre_ping=True,
    connect_args={"prepare_threshold": None},
)
```

> **連線機制說明**：目前專案採用 **Supabase Transaction Pooler (port 6543) + psycopg 3**。因為 Transaction Pooler (PgBouncer) 不支援 prepared statements，故設定 `connect_args={"prepare_threshold": None}` 停用 prepared statements，並搭配 `NullPool` 避免 client 端維持大型閒置連線池。


### 8.2 Vercel

Vercel Environment Variables 設定：

```text
CWA_API_KEY
DATABASE_URL
```

Production 不把密碼、API Key 或 connection string commit 到 GitHub。

### 8.3 連線管理

Vercel 採 Serverless 架構，因此資料庫連線必須注意：

- 不要每個 function 無限制建立大量 connection。
- 使用 Supabase 提供的適合 serverless 的連線方式 / pooler。
- SQLAlchemy connection 使用完後必須正常釋放。
- 不把 database connection 長期存在 global transaction 中。

---

## 9. Website UI Design

### 9.1 Header

顯示：

**Taiwan Weather Forecast**  
中央氣象署一週天氣預報

副標題：

`Data Source: Central Weather Administration (CWA)`

---

### 9.2 Region Selector

```text
選擇地區
[ 臺中市 ▼ ]
```

第一版使用 22 縣市。

切換縣市後：

- 不 reload 整個網站
- 前端呼叫 `/api/forecast?region=臺中市`
- 重新繪製圖表與 table

---

### 9.3 Summary Cards

顯示目前選擇地區近期預報：

```text
┌────────────┐
│ 天氣       │
│ 多雲       │
└────────────┘

┌────────────┐
│ 最低溫     │
│ 24 °C      │
└────────────┘

┌────────────┐
│ 最高溫     │
│ 30 °C      │
└────────────┘
```

---

### 9.4 Temperature Chart

Chart.js Line Chart：

- X axis：日期
- Y axis：溫度 °C
- Line 1：MaxT
- Line 2：MinT

標題：

**未來一週最高／最低溫**

---

### 9.5 Forecast Table

| 日期 | 天氣 | 最低溫 | 最高溫 |
|---|---|---:|---:|
| 10/03 | 多雲 | 24°C | 30°C |
| 10/04 | 多雲時晴 | 24°C | 31°C |
| ... | ... | ... | ... |

---

### 9.6 Footer

顯示：

- 資料來源：中央氣象署 Open Data
- Dataset ID
- 最後資料更新時間
- GitHub Repository

---

## 10. Backend API Design

### GET /api/regions

取得可選縣市。

Response：

```json
{
  "regions": [
    "臺北市",
    "新北市",
    "臺中市"
  ]
}
```

### GET /api/forecast

Request：

```text
/api/forecast?region=臺中市
```

Response：

```json
{
  "region": "臺中市",
  "updated_at": "2026-10-03T16:00:00+08:00",
  "forecasts": [
    {
      "start_time": "...",
      "end_time": "...",
      "weather": "多雲",
      "min_temp": 24,
      "max_temp": 30
    }
  ]
}
```

### POST /api/refresh

開發階段可手動刷新 CWA 資料。

Production 不對一般使用者公開，避免：

- 任意大量呼叫 CWA API
- API quota 浪費
- 惡意 refresh

### GET /api/cron/refresh

專為 Vercel Cron 設計的受保護定時更新端點（HTTP GET）。

**安全性機制**：
- 必須攜帶 Header：`Authorization: Bearer <CRON_SECRET>`
- 使用 `hmac.compare_digest` 進行常數時間比對防範 Timing Attacks
- 若伺服器未設定 `CRON_SECRET`，預設採取 **Fail-Closed** 原則拒絕連線 (HTTP 401)
- 權限無效回傳 HTTP 401，不對外洩露任何機敏字串與錯誤堆疊

**排程規格**：
- Vercel Hobby（免費方案）：每日一次（`0 0 * * *`，UTC 00:00，約臺灣時間 08:00）
- Vercel Pro：可設定為每 6 小時一次（`0 */6 * * *`）

### GET /api/map-data (Phase 7 預先設計)

為全台 22 縣市地圖視覺化與多時段切換所規劃的高效匯總端點（Phase 7 規劃，本階段僅定義架構，不進行程式碼實作）。

**設計概念**：
- 前端地圖需要同時呈現全台 22 縣市的預報數值以繪製面量圖（Choropleth）。
- 若前端針對 22 縣市發送 22 次 HTTP 請求，會造成不必要的網路開銷、瀏覽器連線排隊與資料庫負擔。
- 因此由後端單一查詢打包「最新單一批次」之 22 縣市全部有效時段預報，一次性傳送給前端，由前端在本地記憶體中即時切換時段。

**Response Schema Concept**：
```json
{
  "dataset_id": "F-C0032-005",
  "updated_at": "2026-10-04T00:30:00+08:00",
  "periods": [
    {
      "start_time": "2026-10-04T06:00:00+08:00",
      "end_time": "2026-10-04T18:00:00+08:00"
    },
    {
      "start_time": "2026-10-04T18:00:00+08:00",
      "end_time": "2026-10-05T06:00:00+08:00"
    }
  ],
  "forecasts": [
    {
      "region_name": "臺中市",
      "start_time": "2026-10-04T06:00:00+08:00",
      "end_time": "2026-10-04T18:00:00+08:00",
      "weather": "多雲",
      "min_temp": 24.0,
      "max_temp": 31.0
    }
  ]
}
```

**架構與效能要求**：
- **最新批次規則 (Latest Batch Rule)**：
  - 由於 `weather_forecasts` 表保留歷史資料，舊批次與新批次可能存在重疊未過期的時段。
  - 後端查詢必須先定位該資料集最新的 `fetched_at` batch（例如透過子查詢 `SELECT MAX(fetched_at) FROM weather_forecasts WHERE dataset_id = :dataset_id`），僅選取該 batch 之紀錄，杜絕新舊資料混雜。
  - 再以 `end_time > CURRENT_TIMESTAMP` 過濾掉過期時段。
  - 不得刪除歷史資料，確保資料庫維持稽核與追溯歷史之能力。
- **穩定排序 (Deterministic Ordering)**：
  - 結果統一以 `start_time ASC, region_name ASC` 排序，方便前端建構時段陣列與索引映射。
- **資料量輕量**：
  - 22 縣市 × 約 15 個預報區間 ≈ 330 筆紀錄，未壓縮 JSON 大小約 25～35 KB（啟用 Gzip/Brotli 僅約 4～6 KB），可由前端一次取得並暫存。
- **嚴格分層設計**：
  - Repository (`WeatherRepository.get_latest_map_forecasts`) → Service (`WeatherService.get_map_data`) → Route (`GET /api/map-data`)。

---

## 11. 預計目錄結構

```text
CWA/
├─ MyPlan/
│  └─ design.md
│
├─ app/
│  ├─ main.py
│  │
├─ core/
│  ├─ __init__.py
│  └─ config.py
│
├─ api/
│  ├─ routes.py
│  └─ schemas.py
│
├─ services/
│  └─ weather_service.py
│
├─ repositories/
│  └─ weather_repository.py
│
├─ clients/
│  └─ cwa_client.py
│
├─ parsers/
│  └─ cwa_parser.py
│
├─ db/
│  ├─ database.py
│  └─ models.py
│
├─ templates/
│  └─ index.html
│
└─ static/
   ├─ css/
   │  └─ style.css
   ├─ js/
   │  └─ app.js
   └─ data/
      └─ taiwan_counties.geojson  # Phase 7: 22 縣市界線 GeoJSON
│
├─ scripts/
│  ├─ init_db.py
│  └─ fetch_weather.py
│
├─ tests/
│  ├─ test_api.py
│  ├─ test_config.py
│  ├─ test_cwa_client.py
│  ├─ test_deployment.py
│  ├─ test_frontend.py
│  ├─ test_parser.py
│  ├─ test_repository.py
│  └─ test_weather_service.py
│
├─ .env.example
├─ .gitignore
├─ requirements.txt
├─ vercel.json
├─ README.md
└─ .python-version
```

---

## 12. .gitignore 規劃

```gitignore
.env
.env.*
!.env.example

__pycache__/
*.py[cod]
.pytest_cache/
.venv/
venv/

.vercel/
.DS_Store
```

Database 本身位於 Supabase，不會有 `.db` 檔案需要 commit。

---

## 13. requirements.txt 初步規劃

```text
fastapi
uvicorn
jinja2
requests
sqlalchemy
psycopg[binary]
python-dotenv
pydantic-settings
pytest
httpx
```

實際開發時再固定版本。

---

## 14. Error Handling

### CWA API

需要處理：

- Timeout
- 401 / Authorization failure
- 404 dataset error
- 429 rate limit
- 5xx server error
- CWA response `success = false`

### JSON

需要處理：

- records 不存在
- location 不存在
- weatherElement 缺欄位
- 某日期沒有 MinT / MaxT / Wx

### PostgreSQL

需要處理：

- Connection failure
- Query failure
- Duplicate data
- Transaction rollback
- Supabase 暫時無法連線

### UI

資料讀取失敗時顯示：

```text
目前無法取得天氣資料，請稍後再試。
```

不要直接把 Python traceback、Database URL 或 Secret 顯示給使用者。

---

## 15. Data Refresh Strategy

CWA 預報資料會定期更新，因此不需要每次開網頁都直接打 CWA API。

建議：

```text
Scheduled Refresh
       ↓
CWA API
       ↓
Parser
       ↓
Supabase PostgreSQL
       ↓
FastAPI Query
       ↓
Website
```

優點：

- 網站載入快
- 減少 CWA API request
- 避免多人瀏覽重複呼叫
- 即使 CWA API 暫時異常，仍可顯示最近成功取得的預報

### Production 現況與排程說明

- **Vercel Hobby Cron**：
  - Schedule: `0 0 * * *`
  - 代表每日一次（UTC 00:00）。
  - 在 Vercel Hobby 方案下執行時間可能落在該小時內，因此臺灣時間約為上午 **08:00～08:59**。
- **資料更新流程**：
  ```text
  Vercel Cron
      ↓
  protected GET /api/cron/refresh (Bearer CRON_SECRET)
      ↓
  CWA Open Data API (F-C0032-005)
      ↓
  Supabase PostgreSQL (UPSERT)
  ```
- **升級擴充**：
  - 若未來升級至 Vercel Pro，可調整排程為 `0 */6 * * *` 實現約每 6 小時自動更新。

---

## 16. 開發階段

### Phase 1 — Environment

- [x] 建立 Python environment
- [x] requirements.txt
- [x] `.env`
- [x] `.env.example`
- [x] `.gitignore`
- [x] FastAPI Hello World

### Phase 2 — CWA API

- [x] CWA API request
- [x] 驗證 API Key
- [x] 取得 sample JSON
- [x] 分析 JSON hierarchy
- [x] 建立 parser

### Phase 3 — Supabase PostgreSQL

- [x] 建立 Supabase Project
- [x] 取得 PostgreSQL connection information
- [x] 建立 `weather_forecasts`
- [x] 建立 `fetch_logs`
- [x] Python 成功連線
- [x] insert / upsert
- [x] SELECT region
- [x] SELECT forecast

### Phase 4 — Web API

- [x] GET `/api/regions`
- [x] GET `/api/forecast`
- [x] refresh service
- [x] error handling

### Phase 5 — Frontend

- [x] Layout
- [x] Region dropdown
- [x] Summary cards
- [x] Chart.js line chart
- [x] Forecast table
- [x] loading/error state
- [x] responsive layout

### Phase 6 — Deployment (Completed & Verified)

- [x] GitHub Repository
- [x] Vercel Project
- [x] Environment Variables
- [x] Supabase production connection
- [x] Build & Deploy
- [x] Production smoke test
- [x] Vercel Cron auto refresh
- [x] CRON_SECRET protection verified

**Production URL**:
https://cwa-9cyxfmmd2-cwa-weather-project.vercel.app/

**Cron Production 驗證狀態**:
- `GET /api/cron/refresh` 已部署
- 無 Authorization header → HTTP 401 已驗證
- 正確 Vercel Cron authentication → HTTP 200 已驗證
- refresh 成功後 Supabase `fetch_logs` 產生 success 紀錄
- Production scheduled refresh pipeline 已驗證可正常運作

### Phase 7 — Interactive Taiwan Weather Dashboard (規劃中)

對應原課程流程：
- **Phase 7A**：對應原課程第 17 項（台灣地圖視覺化）
- **Phase 7B**：對應原課程第 18 項（選擇日期／預報時段顯示地圖）
- **Phase 7C**：對應原課程第 19 項（完整 Taiwan Weather Dashboard）

---

#### 7A. 台灣縣市天氣地圖 (Taiwan County Weather Map — 對應第 17 項)

將純文字與下拉選單擴充為直覺的互動式地理空間 GIS 視覺化：

- **Leaflet 互動式地圖**：輕量、高效能開源地圖核心，支援向量圖層與平滑縮放拖曳。
- **台灣 22 縣市 GeoJSON 幾何界線**：
  - 本地靜態檔案：`app/static/data/taiwan_counties.geojson`
  - 規格：GeoJSON `FeatureCollection`、WGS84 座標系統（EPSG:4326）。
  - 屬性包含縣市名稱，精準對齊 CWA `region_name`（如「臺中市」、「臺北市」、「新北市」等）。
  - 資料來源優先採用內政部或政府開放資料之官方邊界圖資，實作時於 README 記載來源與授權。
  - 打包為靜態資源（static asset），前端載入首頁時本地讀取，不依賴不可靠的第三方外鏈 geometry API。
- **面量圖多邊形渲染 (Polygon Choropleth)**：
  - 依各縣市預報最高溫或天氣數值映射至漸層色彩階梯（Color Scale）。
- **懸停提示 (Hover Tooltip)**：
  - 滑鼠游標移動至各縣市時，即時彈出顯示縣市名稱、天氣現象與預測最高/最低溫。
- **點擊選取 (Click Selection)**：
  - 點擊特定縣市時高亮（Highlight）該多邊形邊框，並將選取地區傳遞至系統狀態。
- **地圖與下拉選單雙向同步 (Bidirectional Synchronization)**：
  - 既有地區下拉選單保留作為備用/輔助控制項。
  - 點選地圖縣市 → 同步更新下拉選單的值。
  - 切換下拉選單 → 地圖自動高亮對應多邊形並聚焦。
- **核心數值定義規則**：
  - 地圖呈現的是 **預報（Forecast）**，而非即時觀測（Current Observation）。
  - UI 必須明確標註「最近預報時段」、「預測最高溫」、「預測最低溫」，嚴禁標示為「即時溫度」或「現在溫度」。

---

#### 7B. 預報時段地圖切換 (Forecast Period Map — 對應第 18 項)

中央氣象署 F-C0032-005 為時段型預報（約 12 小時一筆，跨越未來一週約 15 個時段），非單純 date-only 結構：

- **時段選擇器 (Forecast Period Selector)**：
  - 於地圖上方或控制列提供時段選擇控制項（按鈕群組或滑桿/下拉），顯示格式如：`MM/DD HH:mm ～ MM/DD HH:mm`。
- **全島多邊形即時連動**：
  - 切換不同預報時段時，全台 22 縣市地圖的：
    - 天氣現象 (weather)
    - 預測最低溫 (min_temp)
    - 預測最高溫 (max_temp)
    - 多邊形塗色 (polygon colors)
    一併即時同步重新渲染。
- **高效零額外請求架構**：
  - 前端於載入時透過 `GET /api/map-data` 一次取得全台 22 縣市於所有有效時段的資料。
  - 切換時段由瀏覽器本機記憶體直接過濾渲染，無需重整網頁，亦絕不重複向後端發送 22 次 HTTP 請求。

---

#### 7C. 完整天氣儀表板整合 (Complete Taiwan Weather Dashboard — 對應第 19 項)

整合地圖、卡片、折線圖與表格，建立具備 GIS 特色的專業氣象儀表板：

- **最終桌面版面配置 (Desktop Layout)**：
  ```text
  Header (Taiwan Weather Forecast / 中央氣象署一週天氣預報)

  Map Dashboard Section (地圖儀表板核心區)
  ├─ Taiwan interactive weather map (約佔寬度 65–70%)
  └─ Selected region detail panel (約佔寬度 30–35%)

  Detailed Section (時段深度分析區)
  ├─ Existing Chart.js temperature chart (未來一週最高/最低溫折線圖)
  └─ Existing forecast table (一週時段預報清單，支援水平滑動)

  Footer (資料來源與 GitHub 連結)
  ```
- **以地圖為核心的視覺層級 (Map-First Information Hierarchy)**：
  - 地圖為使用者造訪首頁的第一主要視覺焦點。
  - 右側選取縣市資訊面板（Detail Panel）顯示：
    - 選取縣市名稱 (selected region)
    - 天氣現象與圖示 (weather)
    - 預報時段區間 (forecast period)
    - 預測最低溫 (min_temp)
    - 預測最高溫 (max_temp)
    - 最後資料更新時間 (updated_at)
- **聯動更新管線**：
  - 點擊地圖縣市：
    1. 地圖多邊形高亮選取。
    2. 下拉選單同步切換至該縣市。
    3. 更新右側 Detail Panel 內容。
    4. 既有 Chart.js 銷毀重建更新該縣市未來一週溫標走勢。
    5. 既有 Forecast Table 更新該縣市完整 15 個預報時段。
  - 切換下拉選單：
    1. 地圖選取多邊形同步高亮切換。
    2. 更新 Detail Panel、Chart.js 與 Forecast Table。
- **視覺風格規範 (Visual Style Guidelines)**：
  - **定位**：專業氣象地理資訊儀表板（Professional Weather GIS Dashboard）。
  - **參考概念**：參考氣象署 GIS 空間佈局與現代環境監測站（如 AirBox）之空間視覺化直覺感。
  - **智慧財產與合規保護**：嚴禁複製任何第三方網站之商標、Logo、特定品牌元素、精確排版或具版權之視覺資產。
  - **色彩與質感**：
    - 淺中性底圖（Light neutral map）：簡潔乾淨之底圖或向量圖層，避免花俏雜亂。
    - 氣象系統主色（Navy / Sky Blue accents）：使用深藍、天藍與冷暖色溫作重點點綴。
    - 白色資訊面板（White info panels）：乾淨白底帶細緻 1px 邊框與柔和陰影。
    - 清晰溫度圖例（Clear temperature legend）：標示最高溫階層色盤與數值範圍。
    - 收斂裝飾元素：減少過度圓角與雜亂卡片，強調清晰閱讀性與地圖主體性。
- **響應式排版 (Responsive Breakpoints)**：
  - **Desktop (大螢幕)**：左側地圖 (約 65~70%) + 右側縣市細節面板 (約 30~35%) 雙欄並排。
  - **Tablet (平板)**：地圖置頂保持主視覺，右側面板適度縮窄或流暢折至地圖下方。
  - **Mobile (手機)**：垂直單欄依序堆疊：
    `Map (保持 320～380px 高度以維持流暢觸控) → Region Details → Temperature Chart → Forecast Table`。

---

#### Phase 7 驗收標準 (Acceptance Criteria — 已驗收完成)

##### Phase 7A — 驗收標準
- [x] Taiwan map renders
- [x] 22 counties render
- [x] temperature choropleth
- [x] hover tooltip
- [x] click selection
- [x] map/dropdown sync

##### Phase 7B — 驗收標準
- [x] forecast periods available
- [x] period selector
- [x] switching period updates all counties
- [x] no page reload
- [x] no 22 API requests

##### Phase 7C — 驗收標準
- [x] map-first dashboard layout
- [x] selected county detail panel
- [x] existing Chart.js integrated
- [x] existing forecast table integrated
- [x] responsive desktop/mobile
- [x] Production deployment

---

## 17. Testing Strategy

### Parser Test

使用固定 JSON fixture 測試：

- 正常資料
- 少 Wx
- 少 MinT
- 少 MaxT
- 時間欄位不一致

### Repository Test

測試：

- insert
- duplicate upsert
- region filter
- chronological sorting

### API Test

測試：

- 正常縣市
- 不存在的縣市
- Database 沒有資料
- service error

### Security Test

確認：

- GitHub 沒有 CWA API Key
- GitHub 沒有 Supabase password / DATABASE_URL
- HTML source 沒有 secret
- API response 沒有 secret
- log 沒有印出 secret

---

## 18. Definition of Done

MVP 完成條件：

- [x] 可以從 CWA 成功取得真實資料
- [x] 可以解析 22 縣市資料
- [x] 可以寫入 Supabase PostgreSQL
- [x] 相同預報重複 refresh 不會一直新增 duplicate rows
- [x] 可以用 SQL 查詢指定縣市
- [x] 網站可以切換縣市
- [x] 可以顯示一週天氣資料表
- [x] 可以顯示最高／最低溫折線圖
- [x] GitHub repository 有完整原始碼
- [x] Vercel deployment 可正常瀏覽
- [x] Production Cron 可自動更新資料
- [x] Current tracked source files 不含真實 CWA API credentials
- [x] Current tracked source files 不含真實 database credentials
- [x] Current tracked source files 不含真實 CRON_SECRET
- [x] Phase 7A: 臺灣 22 縣市分級面量圖視覺化與點擊互動
- [x] Phase 7B: 預報時段切換控制（生產環境已驗收完成）
- [x] Phase 7C: Complete Taiwan Weather Dashboard（已完成並通過生產環境驗收）

---

## 19. 第一版實作原則

先完成：

```text
CWA
 ↓
F-C0032-005
 ↓
Wx + MinT + MaxT
 ↓
Python Parser
 ↓
Supabase PostgreSQL
 ↓
SQL Query
 ↓
FastAPI
 ↓
Region Dropdown
 ↓
7-day Chart + Table
 ↓
Vercel
```

等這條 pipeline 完整跑通後，再加入地圖、鄉鎮、降雨機率等功能。

---

## 20. 最終第一版技術架構

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

這個版本不再依賴 SQLite，本機與正式部署環境都採 PostgreSQL，避免 Vercel 本機檔案持久化問題，也讓整個專案架構更接近一般正式 Web Application。

---

## 21. Phase 7: 地圖儀表板與成果展示 (Taiwan Weather Dashboard)

### 21.1 Phase 7A: 臺灣縣市預報地圖 (已完成)
- Leaflet 1.9.4 底圖與 22 縣市 GeoJSON 多邊形圖層。
- 依最近時段最高溫分級面量圖（Choropleth）。
- 懸浮 Tooltip 即時顯示天氣與溫度。
- 地圖縣市點擊與縣市選單雙向同步。

### 21.2 Phase 7B: 預報時段切換控制 (已完成，生產環境已驗收)
- 對應課程第 18 項「選擇日期／預報時段顯示地圖」。
- [x] forecast periods available（有效預報時段可用）
- [x] period selector（時段下拉選單）
- [x] switching period updates all counties（切換時段即時更新全縣市多邊形與摘要）
- [x] no page reload（零頁面重整）
- [x] no 22 API requests（零額外網路請求，不發送 22 次 API）

### 21.3 Phase 7C: 完整成果展示 Taiwan Weather Dashboard (已完成並通過生產環境驗收)
- 對應課程第 19 項「完整成果展示 Taiwan Weather Dashboard」。
- [x] map-first dashboard layout（地圖優先氣象儀表板整體整合）
- [x] selected county detail panel（選定縣市即時摘要面板，含資料更新時間）
- [x] existing Chart.js integrated（既有 Chart.js 一週溫度趨勢折線圖整合）
- [x] existing forecast table integrated（既有預報詳細時段資料表整合）
- [x] responsive desktop/mobile（桌面／平板／手機跨裝置響應式排版）
- [x] Production deployment（正式環境部署與完整成果驗收）

---

## 22. 未來擴充規劃演進 (Future Extensions Evolution)

前期於 Phase 7 保留之延伸規劃項目，已於下節正式提升並整合為完整的 **Phase 8 — Advanced Weather Platform** 系統設計架構藍圖。

---

## Phase 8 — Advanced Weather Platform

> **階段願景**：將現有已通過生產環境驗收的中央氣象署天氣預報儀表板（Phase 1–7C），進一步演進為全方位、現代化且具備專業氣象工作台體驗的「進階氣象平台（Advanced Weather Platform）」，在無縫保留 Phase 7 所有既有驗收規格的前提下，擴展即時觀測、短中期降雨機率預報、雷達回波疊加、颱風動態中心與鄉鎮細緻預報。

```text
+---------------------------------------------------------------------------------------------------+
|                                CWA Advanced Weather Platform (Phase 8)                            |
+---------------------------------------------------------------------------------------------------+
|  [Header] Brand Title | Theme Toggle (Light/Dark) | Map Modes: [氣溫] [降雨] [觀測] | Overlay: [☁️雷達] |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  +---------------------------------------------------------------+  +--------------------------+  |
|  |                   Map Workspace (Leaflet)                     |  |  Floating / Collapsible  |  |
|  |                                                               |  |  County Summary Panel    |  |
|  |   - Single Leaflet Map Instance                               |  |                          |  |
|  |   - Height: 600–680px (~65–70vh)                              |  |  - Region Selector       |  |
|  |   - Independent Layers:                                       |  |  - Selected County Name  |  |
|  |       * countyForecastLayer (Choropleth GeoJSON)              |  |  - Selected Forecast     |  |
|  |       * stationObservationLayer (Weather Stations)            |  |    Period                |  |
|  |       * radarOverlayLayer (CWA Radar ImageOverlay)            |  |  - Weather Phenomenon    |  |
|  |       * typhoonTrackLayer (Past/Forecast Tracks)              |  |  - Predicted Min/Max     |  |
|  |       * typhoonRadiusLayer (7/10-Level Wind Radii)            |  |    Temperature           |  |
|  |   - Interactive Controls: Reset View (GeoJSON getBounds),     |  |  - updated_at            |  |
|  |     Fullscreen, Map Toolbar, Opacity Slider                   |  |                          |  |
|  |                                                               |  |  (Desktop: Floating Card |  |
|  |                                                               |  |   Mobile: Stacked Below) |  |
|  +---------------------------------------------------------------+  +--------------------------+  |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
|  [Detailed Sections Below Map Workspace]                                                          |
|  +---------------------------------------------------------------------------------------------+  |
|  |  7-Day Temperature Trend Chart (Chart.js - Full-width section below map)                    |  |
|  +---------------------------------------------------------------------------------------------+  |
|  |  Detailed Period Forecast Table (Full-width responsive table below map)                     |  |
|  +---------------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
```

---

### 1. 總體設計原則與架構規範 (Guiding Principles)

1. **嚴格保持 Phase 7 既有規格 (Preserve Verified Phase 7 Behavior)**：
   - 既有縣市一週預報（`F-C0032-005`）、縣市下拉選單、7 日高低溫折線圖、詳細時段預報表、GeoJSON 分級面量圖、時段切換選單（Phase 7B）、指標點擊雙向連動與 Vercel Cron 排程皆為系統核心基石，任何 Phase 8 的擴充均不得破壞既有通過驗收之行為與資料一致性。
2. **單一地圖實例原則 (ONE Leaflet Map Instance)**：
   - 全應用程式維持唯一一個 `L.map` 實例，不因切換不同氣象模式或圖層而銷毀重建地圖，防止記憶體洩漏與底圖重複請求。
3. **資料領域分離 (Domain Separation)**：
   - 嚴禁將所有異質氣象資料全部混入 `weather_forecasts` 表。縣市預報、即時觀測、雷達中繼、颱風路徑與鄉鎮預報皆劃分專屬資料模型與獨立儲存結構。
4. **觀測與預報嚴格區隔 (Strict Observation vs Forecast Separation)**：
   - 「目前觀測（Current Observations）」代表既有過去發生之量測真值；「未來預報（Future Forecasts）」代表數值模式預測值。UI、API 及資料庫欄位必須徹底隔離，絕不相互指涉或混淆。
5. **高效快取與零冗餘下載 (Smart Caching & Selective Download)**：
   - 針對高頻更新與巨量資料集（如雷達回波、全臺自動觀測站、368 鄉鎮細緻預報），採用後端過濾與伺服器快取架構，避免前端下載數十 MB 無用封包或過度頻繁衝擊 CWA API。

---

### 2. 8A — App Experience & Map Workspace (使用者體驗與地圖工作台)

#### 2.1 系統級 Light / Dark 主題體系
- **主題切換互動 (Theme Toggle in Header)**：
  - 於 Header 右側設置主題切換按鈕，支援流暢的 Sun/Moon 圖示翻轉過渡動效。
  - 首度造訪時優先遵循瀏覽器或作業系統設定：`window.matchMedia('(prefers-color-scheme: dark)')`。
  - 使用者手動切換後，設定值持久化於 `localStorage.getItem('cwa_theme')`（值域為 `'light'` 或 `'dark'`）。
  - HTML 根節點以屬性 `data-theme="dark"` 即時響應，避免切換時出現畫面白閃（Flash of Unstyled Theme, FOUT）。
- **CSS Custom Properties 設計代幣體系 (Design Tokens)**：
  ```css
  /* 基礎語意代幣體系 */
  :root {
    --bg-app: #f8fafc;
    --bg-surface: #ffffff;
    --bg-surface-elevated: #ffffff;
    --bg-panel: rgba(255, 255, 255, 0.92);
    --border-color: #e2e8f0;
    --border-subtle: #edf2f7;
    --text-primary: #1e293b;
    --text-secondary: #475569;
    --text-muted: #94a3b8;
    --accent-primary: #2563eb;
    --accent-hover: #1d4ed8;
    --shadow-card: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
    --shadow-float: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
    --map-tile-filter: none;
  }

  [data-theme="dark"] {
    --bg-app: #0f172a;
    --bg-surface: #1e293b;
    --bg-surface-elevated: #334155;
    --bg-panel: rgba(30, 41, 59, 0.92);
    --border-color: #334155;
    --border-subtle: #1e293b;
    --text-primary: #f8fafc;
    --text-secondary: #cbd5e1;
    --text-muted: #64748b;
    --accent-primary: #3b82f6;
    --accent-hover: #60a5fa;
    --shadow-card: 0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -2px rgba(0, 0, 0, 0.2);
    --shadow-float: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.4);
    /* OSM 底圖優化深色濾鏡，避免刺眼白底同時保留道路與地名 */
    --map-tile-filter: brightness(0.82) contrast(1.12) invert(0.92) hue-rotate(185deg) saturate(0.65);
  }
  ```
- **Chart.js 佈景主題動態同步**：
  - 監聽主題變更事件，動態更新 Chart.js 全域或實例屬性：
    - `scales.x.grid.color`: 淺色 `#e2e8f0` / 深色 `#334155`
    - `scales.y.grid.color`: 淺色 `#e2e8f0` / 深色 `#334155`
    - `scales.x.ticks.color` & `scales.y.ticks.color`: 淺色 `#475569` / 深色 `#cbd5e1`
    - `plugins.legend.labels.color`: 淺色 `#1e293b` / 深色 `#f8fafc`
    - `plugins.tooltip`: 背景更換為深灰/深藍，文字維持高對比反白。
  - 切換時調用 `chartInstance.update()` 觸發平滑過渡。
- **Leaflet 控制項與圖例暗色適配**：
  - 縮放按鈕 (`.leaflet-bar a`)、圖層控制器與自訂工具箱適配 `var(--bg-surface)` 與 `var(--border-color)`。
  - 縣市懸浮 Tooltip (`.cwa-county-tooltip`) 及面量圖圖例 (`.cwa-choropleth-legend`) 採用深色毛玻璃背景與清晰文字，確保符合 WCAG 對比度規範。
  - **底圖保留政策**：初階段**不引進第三方深色圖磚服務**（避免第三方 API Key 依賴、計費限制或服務中斷），繼續保留現有標準 OpenStreetMap 底圖及 `&copy; OpenStreetMap contributors` 版權署名。深色模式下僅對 Leaflet 圖磚容器 `.leaflet-tile-pane` 套用 CSS 濾鏡，向量多邊形、標記與文字標註層則保持原始清晰色彩。

#### 2.2 地圖工作台 UX (Map Workspace UX)
- **桌面版大工作區設計**：
  - 桌面視窗下將地圖高度由原本約 450px 擴大至 **600–680px（或約 65–70vh）**，使地圖真正成為探索氣象空間資料的主核心工作台。
- **桌面浮動／收合面板範圍修正 (Desktop Floating/Collapsible Panel Scope)**：
  - **桌面端 (Desktop)**：浮動面板僅承載縣市焦點控制與即時摘要，**絕對不把 Chart.js 圖表與完整預報時段資料表塞入浮動面板**：
    - 浮動面板內容**僅包含**：
      1. 縣市下拉選單（Region Selector）
      2. 選定縣市名稱（Selected County Name）
      3. 當前選擇之預報時段標籤（Selected Forecast Period）
      4. 天氣現象描述與圖示（Weather Phenomenon）
      5. 預測最低溫與最高溫（Predicted Min/Max Temperature）
      6. 資料最後更新時間（updated_at）
    - **Chart.js 折線圖與詳細預報資料表（Forecast Table）**：始終維持在「地圖工作台下方」作為全寬詳情展示區塊，防止遮擋地圖工作視野並確保長型資料維持最佳閱讀體驗。
    - 提供「收合／展開（Collapse / Expand）」切換鈕（`id="detail-panel-toggle"`），收合時縮為輕量縣市摘要膠囊標籤，釋放 100% 完整寬幅地圖。
  - **行動端 (Mobile)**：維持 Phase 7C 驗收良好之垂直響應式排版，在 `<= 960px` 視窗下浮動面板自動切換為正常靜態文件流（`position: static`，寬度 100%），固定於地圖下方垂直堆疊展開，收合按鈕可隱藏，防止行動小螢幕被懸浮圖層遮擋。
- **地圖互動手勢與輔助控制**：
  - 桌面版啟用滾輪縮放（`scrollWheelZoom: true`），配合 GIS 操作習慣。
  - 行動端完整保留單指拖曳、雙指捏合縮放（Pinch-to-zoom）與觸控雙擊縮放。
  - **重設臺灣視角邊界修正 (Reset to Taiwan View Bounds)**：
    - 新增專屬控制按鈕（`id="map-reset-view"`，Accessible label: `重設臺灣視角`）。
    - **嚴禁硬編碼邊界座標**（如 `[[21.8, 119.3], [25.4, 122.2]]`，會造成金門、連江等離島被裁切排除）。
    - 實作規範：於 GeoJSON 圖層載入後，直接透過 `geojsonLayer.getBounds()` 取得官方完整圖資邊界並儲存為正規臺灣邊界（`taiwanDefaultBounds`），重設時以 `leafletMap.fitBounds(taiwanDefaultBounds, { padding: [15, 15], animate: true })` 準確還原全臺全境（含所有外島）。
  - **全螢幕工作模式控制按鈕 (Fullscreen Control)**：
    - 新增 `id="map-fullscreen-toggle"` 控制鈕，使用標準 HTML5 Fullscreen API（`requestFullscreen` / `exitFullscreen`）將地圖工作區放大為沉浸式全螢幕，並在 `fullscreenchange` 事件中調用 `leafletMap.invalidateSize()` 確保地圖圖磚自動補齊。

---

### 3. 8B — Rich County Forecast (富縣市短中期預報)

#### 3.1 資料來源與氣象要素定義
- **資料集代號**：`F-C0032-001` (一般天氣預報－今明 36 小時天氣預報 / 縣市天氣預報)
- **核心候選欄位**：
  - `Wx`：天氣現象名稱及天氣代碼（01–42，可對應圖示）
  - `MinT`：預測最低溫度 (°C)
  - `MaxT`：預測最高溫度 (°C)
  - `PoP`：降雨機率（Probability of Precipitation, %）
  - `CI`：舒適度指數（Comfort Index，如「舒適」、「悶熱」、「稍有寒意」等）
- **與既有 F-C0032-005 預報之清晰職責區隔**：
  - `F-C0032-001`（36 小時）：分為「今晚明晨」、「明日白天」、「明日晚上」等三個具體生活時段，提供民眾出門防雨與穿衣之高精度短時指引（含 `PoP` 與 `CI`）。
  - `F-C0032-005`（7 天預報）：提供跨一週之長週期氣溫走勢圖（折線圖與 7 日趨勢）。
  - **批次與資料集隔離準則**：兩者透過 `dataset_id` 嚴密隔離，資料庫查詢、快取鍵與 API 路由絕對獨立，不混用預報批次時間與時段資料。

#### 3.2 後端與快取架構設計（Phase 8B 架構修正）
- **架構保護原則**：
  - Phase 8B **不修改 PostgreSQL schema**，不在 `weather_forecasts` 表新增欄位，亦不建立新資料表。既有一週預報（`F-C0032-005`）與每日排程維持絕對穩定。
  - 資料流：`Browser → FastAPI (/api/forecast/short-term) → WeatherService → in-memory TTL 快取 → CWAClient → CWA F-C0032-001`。
- **CWAClient (`app/clients/cwa_client.py`)**：
  - 定義 `DATASET_FORECAST_36H = "F-C0032-001"`。
  - 新增 `fetch_forecast_36h(region_name: Optional[str] = None)`，以 `locationName` 伺服器端過濾。嚴格不對前端暴露 `CWA_API_KEY`。
  - 嚴格啟用 HTTPS TLS 憑證驗證，嚴禁任何 `verify=False`；若發生 `requests.exceptions.SSLError` 則立即安全 Fail-Closed 並封裝為 `CWAConnectionError`，不外洩憑證內部細節、金鑰或標頭。
- **CWAParser (`app/parsers/cwa_parser.py`)**：
  - 新增 `parse_short_term_forecast(data, dataset_id="F-C0032-001")`。
  - 核心要素：`Wx`、`MinT`、`MaxT`、`PoP`、`CI`，以 `(start_time, end_time)` 複合鍵嚴格對齊（不依賴陣列索引）。
  - 數值安全轉換：`PoP` 限制為 0~100 整數，無效值或遺漏時安全轉為 `null`，不因缺漏特定指標而丟棄整筆時段。
- **WeatherService 與行程內快取 (`app/services/weather_service.py`)**：
  - 新增 `get_short_term_forecast(region_name: str)`（不需 DB Session）。
  - 內建行程級最佳努力（best-effort）TTL 快取（10~30 分鐘），冷啟動安全容錯，不干擾既有排程。
- **API 端點設計**：
  - `GET /api/forecast/short-term?region={region_name}`：回傳該縣市 36 小時三時段之生活預報資料。
- **前端安全與時段標籤 (`app/static/js/app.js`)**：
  - 卡片渲染全面採用安全 DOM 操作（`createElement`, `textContent`, `appendChild`, `replaceChildren`），嚴禁將 API 字串內插至 `innerHTML`。
  - 時段標題依據實際 `start_time` 與 `end_time` 之時間戳記解析判定（如 `10/07 白天`、`10/07 晚上 ～ 10/08 清晨`），不以陣列索引猜測日曆真相。既有精確時段時間戳記維持清晰顯示。
  - 降雨機率條寬度經 0~100 數值驗證與限制後以 `style.width` 安全賦值。
- **Phase 8B2 — Rainfall Map Mode (已完成並通過生產環境驗收)**：
  - 降雨機率地圖面量圖切換使用專屬端點 `GET /api/map-data/short-term`，不破壞既有 `/api/map-data` 契約。單一 Leaflet 地圖實例支援 [🌡️ 溫度] 與 [🌧️ 降雨機率] 雙模式切換。既有溫度地圖維持氣溫面量圖不變。

---

### 4. 8C — Current Weather Observations (現在即時氣象觀測)

#### 4.1 資料來源與觀測資料結構
- **資料集代號**：`O-A0001` (自動氣象站觀測資料－自動氣象站觀測資料 / 現在天氣觀測資料)
- **核心候選欄位**：
  - `StationId` / `StationName`：測站代碼與中文名稱（如 `467490` 臺中）
  - `CountyName` / `TownshipName`：所屬縣市與鄉鎮
  - `GeoPosition`：經度 (`Longitude`)、緯度 (`Latitude`)、測站高度 (`Altitude`)
  - `AirTemperature`：即時測得大氣溫度 (°C)
  - `RelativeHumidity`：相對濕度 (%)
  - `WindDirection`：風向 (角度 0–360° 與十六方位描述)
  - `WindSpeed`：平均風速 (m/s 或 蒲福風級)
  - `PeakGustSpeed`：最大陣風風速 (m/s)
  - `AirPressure`：測站大氣壓力 (hPa)
  - `Precipitation`：累積雨量 (過去 1 小時 / 過去 24 小時累積雨量 mm)
  - `ObservationTime`：實際觀測取樣時間（ISO 8601 時間戳記）

#### 4.2 介面黃金原則：目前觀測 vs 未來預報嚴格區隔
- **UI 視覺分離準則**：
  - 介面採用高對比雙軌徽章與分區：
    - **【目前觀測 (Current Observations)】**：採用「翠綠色/青色」專屬實心標籤，標註 `[即時觀測] 測站：臺中站 (14:00 觀測)`。顯示項為真實量測之氣溫、濕度、風速、氣壓、時雨量。
    - **【未來預報 (Future Forecasts)】**：採用「晴空藍/靛藍」專屬標籤，標註 `[未來預報] 2026/10/05 晚上~明日清晨`。顯示項為預測天氣現象、預測高低溫、預測降雨機率。
  - **嚴格禁令**：在系統任何一處，絕不允許將預報數值冠以「目前/即時」名稱，也絕不允許將觀測值標註為預報。

#### 4.3 Leaflet 測站標記圖層與選取縣市摘要
- **`stationObservationLayer` (測站標記圖層)**：
  - 在既有單一 Leaflet 地圖實例上，使用 `L.layerGroup()` 搭配 `L.circleMarker` 呈現全臺氣象站點位。
  - **高效共享 Canvas 渲染器 (Shared Canvas Renderer)**：採用 `L.canvas({ padding: 0.5 })` 渲染全數測站標記，避免大量 SVG/DOM 節點產生效能負擔，確保 60fps 平滑縮放與平移，零第三方外掛依賴（不引進 MarkerCluster）。
  - 標記點顏色依據實測氣溫漸層著色（`getObservationTemperatureColor`）；點擊標記彈出氣象站詳細資訊卡（氣溫、相對濕度、氣壓、風向風速、降水量、實際觀測時間）。
  - **未來聚合評估**：點聚合（Clustering）僅作為未來若實測效能確有不足時之評估項目，目前版本不採用也不包含聚合外掛。
- **選定縣市即時觀測摘要 (Selected County Observation Summary)**：
  - 當使用者點選特定縣市時，詳細面板頂部自動載入該縣市基準代表測站之「目前觀測數據卡片群」，讓使用者一目了然「現在正在下雨嗎？現在氣溫多少？」，下方緊接著「未來幾天一週趨勢」。

---

### 5. 8D — Radar Layer (雷達整合回波圖層疊加)

#### 5.1 資料來源與地理空間幾何
- **資料集代號 (Active Product)**：`O-A0058-001` (雷達整合回波圖－臺灣（較大範圍）_無地形)
  - **選用決策說明**：Phase 8D 最初曾評估有地形版本 `O-A0058-002`，但在生產視覺實測中發現，在既有 OpenStreetMap 底圖與 GeoJSON 邊界之上再次疊加內建地形與海岸線之圖層會產生明顯之雙重地圖對齊視覺瑕疵。因此正式啟用之雷達疊加圖資全面切換為 `O-A0058-001`（較大範圍_無地形），純回波圖層更適合與 Web 地圖底圖無縫疊合。（`O-A0058-002` 僅保留作為獨立靜態圖資參考，非主動疊加圖層）。
- **官方中繼規格 (Official Metadata)**：
  - **更新頻率**：約每 10 分鐘產製一次
  - **經度涵蓋範圍 (Longitude Range)**：`115.00 – 126.50`（西界 115.00, 東界 126.50）
  - **緯度涵蓋範圍 (Latitude Range)**：`17.75 – 29.25`（南界 17.75, 北界 29.25）
  - **影像解析度尺寸 (Image Dimension)**：`3600 × 3600` 像素
  - **官方最新圖檔 ProductURL**：`https://cwaopendata.s3.ap-northeast-1.amazonaws.com/Observation/O-A0058-001.png`
- **地理範圍邊界與前端顯示校準 (Geographic Bounds & Display Calibration)**：
  - 後端 API 端點 `GET /api/radar` 始終保持回傳 CWA 官方原始幾何範圍（南界 17.75、西界 115.00、北界 29.25、東界 126.50），絕不竄改或偽造官方中繼資料。
  - **前端顯示校準結構 (Display Calibration Layer)**：保留集中式校準常數 `RADAR_DISPLAY_BOUND_ADJUST` 與專屬轉換函式 `getRadarDisplayBounds()`，現階段各項偏移量均維持中性 `0.0`，不隨意加入未經測量之魔法數值。啟用無地形圖檔 `O-A0058-001` 為當前解決視覺對齊之根本架構方案。

#### 5.2 Leaflet 架構定位與 ImageOverlay 圖層控制
- **關鍵架構原則：獨立圖層疊加 (Overlay)，絕非第 4 種地圖模式 (Map Mode)**：
  - 既有 `currentMapMode` 保持 3 種模式（`temperature` 溫度、`rainfall` 降雨機率、`observations` 即時觀測）不變。
  - 雷達狀態由獨立變數管控（`radarEnabled`, `radarOverlayLayer`, `radarPendingOverlayLayer`, `radarMetadataCache`, `radarOpacity`），可與三種模式任意疊加共存。
- **專屬 Leaflet Pane (`radarPane`) 與層次堆疊**：
  - 建立專屬 pane：`leafletMap.createPane("radarPane")`。
  - z-index 設定為 `350`（高於底圖 OSM tilePane 200，但低於縣市多邊形與測站標記 overlayPane 400）。
  - 設定 `pointer-events: none`：確保雷達圖層完全透通所有指標事件，絕不干擾縣市多邊形點擊橋接器 (`handleCountyPointerDown`)、測站 hover/click、以及地圖拖曳縮放。
- **`radarOverlayLayer` 實作與生命週期硬化**：
  - 使用 `L.imageOverlay(radarImageUrl, calibratedBounds, { opacity: radarOpacity, interactive: false, pane: "radarPane" })`。
  - 圖片載入附帶防快取版本參數（`?v=<encoded timestamp>`，強制重整時使用 `Date.now()` 直接向圖檔 CDN 請求最新圖檔）。
  - 生命週期防護：採用 `radarPendingOverlayLayer` 候選圖層追蹤，重整失敗或圖檔載入失敗時保留前一張有效圖層；雷達關閉時同步卸載候選與啟用中圖層，杜絕延遲載入圖檔在關閉後竄出。
- **聚焦渲染與底圖自動淡化 (Focused Radar Rendering & Basemap Fading)**：
  - **Radar ON**：當有效雷達圖層成功載入後，`O-A0058-001` 成為主視覺氣象渲染核心，OpenStreetMap 底圖自動淡化至 `0.08`（`baseTileLayer.setOpacity(0.08)`），徹底消除底圖細節與雷達圖資之間的相互干擾與雙重底圖視覺衝突。
  - **Radar OFF**：雷達關閉時，OpenStreetMap 底圖立即恢復正常清晰度（`baseTileLayer.setOpacity(1.0)`）。
  - **非干擾性與模式獨立保證**：底圖淡化僅作用於 `baseTileLayer`，縣市邊界 GeoJSON（`geojsonLayer`）、測站標記（`stationObservationLayer`）與選定縣市邊框維持 100% 原始清晰可見；於不同地圖模式（溫度、降雨、觀測）切換時底圖淡化狀態維持不變。
  - **生命週期與錯誤防護**：初次載入失敗時底圖不淡化並自動同步重設按鈕狀態；更新失敗且有既有雷達圖層時維持淡化與上一張影像；延遲圖檔在關閉後不竄出且不淡化底圖。
- **圖層控制與工具條**：
  - **雷達開關按鈕 (Radar Toggle)**：`#radar-toggle`，一鍵開啟／隱藏雷達回波，aria-pressed 支援無障礙。
  - **透明度滑桿 (Opacity Slider)**：`#radar-opacity`，支援 0.1–1.0（step 0.05，預設 0.65），本地 `setOpacity()` 即時調整，零額外網路請求。
  - **觀測時間戳記展示**：`#radar-status`（aria-live="polite"），若為官方觀測時間標示「雷達時間：MM/DD HH:mm」，若為 HEAD Last-Modified 標示「影像更新：MM/DD HH:mm」，嚴格不偽造氣象觀測時間。
  - **手動重新整理與自動更新**：`#radar-refresh` 按鈕手動重取中繼並更新圖層；雷達開啟時每 10 分鐘自動進行單一非阻塞計時更新，雷達關閉時自動清除計時器。
  - **載入與非阻塞錯誤狀態**：載入中顯示「正在載入雷達回波...」；若圖檔載入失敗顯示「雷達更新失敗，顯示上一張影像」（初次載入顯示「雷達影像暫時無法載入」），維持既有底圖與天氣功能正常可用。

#### 5.3 儲存與快取架構
- **二進位儲存禁令 (NO Large Binary in PostgreSQL)**：
  - 嚴格禁止將數 MB 的雷達 PNG 圖片二進位資料存入 PostgreSQL 資料庫。
  - 後端僅提供專屬輕量中繼端點 `GET /api/radar`，具備 5 分鐘伺服器行程內快取。
  - 支援 CWA File API XML 第一優先解析，並在 XML 不可用時安全平降至官方標準常數與 S3 HEAD `Last-Modified` 檢查，絕不洩漏 API Key。

---

### 6. 8E — Typhoon Center (颱風動態中心與路徑預報 — 最後規劃功能 / FINAL Planned Feature)

#### 6.1 資料來源與氣象要素
- **資料集代號**：`W-C0034-005` (熱帶氣旋分析與預報－警報與路徑預報資料)
- **支援氣象要素**：
  - 活動熱帶氣旋清單：颱風年份、編號、中文名稱、英文名稱、目前分級（輕度、中度、強烈颱風）。
  - 過去分析路徑（Past Analyzed Track）：歷史各時段節點經緯度、強度、中心氣壓。
  - 當前颱風中心（Current Cyclone Center）：即時定位經緯度、中心氣壓 (`CenterPressure` hPa)、近中心最大風速 (`MaxWindSpeed` m/s / 級)、最大陣風 (`PeakGust` m/s / 級)、移動方向與速度 (`Movement` km/h)。
  - 未來預報路徑（Future Forecast Track）：未來 24h、48h、72h、96h、120h 預估中心位置。
  - 暴風半徑與機率圓：
    - 7 級風暴風半徑（15 m/s，暴風圈半徑 km）。
    - 10 級風暴風半徑（25 m/s，十級風暴風半徑 km）。
    - 四象限不對稱半徑（若官方提供東南、東北、西南、西北四象限差異，繪製非對稱風圈多邊形）。
    - 70% 預報機率半徑圓（Forecast Probability Circle）。

#### 6.2 Leaflet 颱風雙圖層架構
- **`typhoonTrackLayer` (路徑圖層)**：
  - 歷史分析路徑：以實線與實心圓點繪製過去節點，節點顏色反映當時強度。
  - 當前颱風中心：旋轉颱風圖示標記，點擊彈出當前強度卡片。
  - 未來預報路徑：以虛線連接未來預報節點，標示預計抵達時間與預估氣壓。
- **`typhoonRadiusLayer` (暴風半徑圖層)**：
  - 以半透明橘紅色面绘制 7 級風暴風圈；以深紅色面绘制 10 級風暴風圈。
  - 以天藍色虛線圓繪製未來 70% 機率圓。

#### 6.3 廣域視角與正常空狀態 (WNP View & Normal Empty State)
- **西北太平洋廣域視角 (Western North Pacific View)**：
  - 進入颱風模式時，地圖自動展開為西北太平洋廣域視野（緯度 `10°N–35°N`，經度 `110°E–150°E`），若有活動颱風則透過 `map.fitBounds(typhoonBounds.pad(0.2))` 自動框選颱風全路徑與臺灣全境，不鎖死在臺灣本島狹隘視角。
- **正常空狀態處理 (Normal Empty State)**：
  - 當目前西北太平洋無活動熱帶氣旋時，面板明確提示：
    `「目前無活動熱帶氣旋 (No Active Tropical Cyclones)」`
  - **核心規範**：無颱風為氣候正常狀態，**絕非系統錯誤或 API 故障**，UI 呈現乾淨寧靜之空狀態卡片，不彈出錯誤告警。

---

### 7. 8F — Township Detailed Forecast (鄉鎮市區細緻預報 — 延後規劃 / 專案當前範圍外 / Deferred / Future Work / Out of Scope)

#### 7.1 資料來源與氣象要素
- **資料集代號**：`F-D0047-093` (臺灣各鄉鎮市區未來 1 週天氣預報) 或分縣市鄉鎮資料集
- **候選氣象要素**：
  - `T`：平均溫度 (°C)
  - `Td`：露點溫度 (°C)
  - `RH`：相對濕度 (%)
  - `Wind`：風向與蒲福風級 / 風速 (m/s)
  - `AT`：體感溫度 (°C)
  - `CI`：舒適度指數描述
  - `Wx`：天氣現象描述與圖示代碼
  - `PoP`：3 小時 / 12 小時降雨機率 (%)
  - `MaxT` / `MinT`：預測最高／最低溫

#### 7.2 巨量資料防禦與伺服器端過濾機制 (Data Volume Strategy)
- **痛點評估**：全臺共有 368 個鄉鎮市區，若將一週內每 3 小時之細緻資料一次性傳送至前端瀏覽器，JSON 體積往往達 15–30 MB，將造成行動端瀏覽器崩潰與巨大延遲。
- **伺服器端過濾與漸進式 API**：
  - **禁令**：嚴禁前端一次性下載全臺鄉鎮預報資料集！
  - 採伺服器端分段解構與漸進加載（Progressive Query）：
    1. `GET /api/townships?county={county_name}`：回傳該縣市轄下鄉鎮清單（名稱、代碼，傳輸量 < 3 KB）。
    2. `GET /api/forecast/township?county={county_name}&township={township_name}`：僅查詢並回傳特定單一鄉鎮之時序預報（傳輸量 < 25 KB）。
- **快取與資料庫儲存策略**：
  - 建立專屬 `township_forecasts` 表或以最新批次 JSON 結構化儲存，建立 `(county_name, township_name, start_time)` 複合索引。
  - 後端服務對鄉鎮查詢實施記憶體快取（TTL: 1–2 小時），大幅減輕資料庫查詢壓力。
- **階層式選擇器流程 (Hierarchical Selector Flow)**：
  - `選取縣市 (County Selector)` → `自動連動載入鄉鎮選單 (Township Selector)` → `呈現該鄉鎮 3 小時逐時天氣卡與體感溫度走勢`。

---

### 8. 8G — Application Polish / Future Features (平台精緻化與延伸特性 — 延後規劃 / 專案當前範圍外 / Deferred / Future Work / Out of Scope)

以下功能已完成架構規劃，保留為後續延伸實作項目：
1. **喜愛縣市/鄉鎮收藏 (Saved Favorites)**：
   - 支援將常用縣市/鄉鎮釘選為最愛，存於 `localStorage`；於介面頂端提供快速切換晶片籤（Quick Chips）。
2. **可分享的網址狀態 (Shareable URL State)**：
   - 透過 HTML5 History API (`pushState` / `replaceState`) 雙向同步網址參數，如 `/?region=臺中市&mode=observations` 或 `/?mode=typhoon`。
   - 使用者複製連結即可精確重現相同的地圖位置與模式。
3. **PWA 與可安裝應用程式 (Progressive Web App)**：
   - 配置 `manifest.json` 與 Service Worker，支援手機「加入主畫面」獨立運行，並離線快取靜態資源。
4. **氣象警特報整合 (Weather Warnings & Advisories)**：
   - 串接 CWA 警特報資料集（大雨特報、低溫特報、陸上強風特報），於地圖相關縣市外框疊加動態警示光暈，並在頂部展示警特報公告橫幅。
5. **地圖圖層偏好記憶 (Map Layer Preferences)**：
   - 記住使用者偏好的預設模式、雷達透明度與面板折疊狀態，重訪時自動恢復。
6. **全方位無障礙體驗 (Accessibility Polish)**：
   - 完整支援鍵盤 Focus 操作、Tab 循環切換與跳過導覽鏈結。
   - 資料非同步更新區域全面配置 `aria-live="polite"` 與語意化 ARIA 標籤。

---

### 9. 地圖整體架構設計 (Map Architecture)

```text
+-----------------------------------------------------------------------+
|                       Single L.map Instance                           |
+-----------------------------------------------------------------------+
|  Base Layer:                                                          |
|    - OpenStreetMap TileLayer (© OpenStreetMap contributors)           |
|      (Dark Mode: CSS filter applied strictly to .leaflet-tile-pane)   |
+-----------------------------------------------------------------------+
|  Independent Overlay Layers:                                          |
|    - radarOverlayLayer       -> ImageOverlay (Bounds, Opacity Slider, |
|                                 radarPane z-index:350, independent)   |
|    - countyForecastLayer     -> GeoJSON Choropleth (Overlay, z:400)   |
|    - stationObservationLayer -> Station Markers (Canvas, z:400)       |
|    - typhoonTrackLayer       -> Future Tracks / Center Markers        |
|    - typhoonRadiusLayer      -> Future 7/10-Level Wind Radii          |
+-----------------------------------------------------------------------+
|  Map Mode Controller (Segmented Bar):                                 |
|    [ 🌡️ 氣溫 (Temperature) ] [ 🌧️ 降雨 (Rainfall) ] [ 📍 觀測 (Observation) ] |
|    - Single Leaflet instance never destroyed                          |
|    - Switch mutually-exclusive core visualization modes cleanly       |
|    - Preserve county pointer selection & highlight sync               |
|                                                                       |
|  Independent Overlay Controls:                                        |
|    [ ☁️ 雷達回波 (Radar ON/OFF) ] (Independent overlay, NOT a mode)    |
|      - Dedicated radarPane (z-index: 350, pointer-events: none)       |
|      - Coexists simultaneously with all 3 map modes                   |
|      - Independent opacity slider, status badge, manual/auto refresh  |
|    (Future typhoon layers / controls)                                 |
+-----------------------------------------------------------------------+
```

1. **單一實例永續運行 (Single Leaflet Instance)**：
   - 確保全站僅有一處 `L.map('map', ...)`。在模式切換（氣溫、降雨、即時觀測）時，僅切換對應視覺化與圖層，絕對不呼叫 `map.remove()` 重建實例。
2. **圖層階層與獨立疊加架構 (Layer Hierarchy & Overlays)**：
   - `countyForecastLayer`：縣市多邊形面量圖（氣溫面量圖 / 降雨機率面量圖，overlayPane z-index: 400）。
   - `stationObservationLayer`：自動氣象站即時觀測 Canvas 標記圖層（overlayPane z-index: 400）。
   - `radarOverlayLayer`：雷達整合回波圖層（專屬 `radarPane` z-index: 350，`pointer-events: none`，獨立疊加於底圖之上且置於縣市邊界與測站標記之下）。
   - `typhoonTrackLayer` / `typhoonRadiusLayer`：未來颱風路徑折線與暴風圈多邊形。
3. **地圖模式控制器與獨立圖層開關 (Map Mode Controller vs Independent Overlays)**：
   - **地圖模式控制器 (Map Mode Controller)** 嚴格限定為 3 種互斥模式：
     - `[🌡️ 氣溫預報 (Temperature)]`
     - `[🌧️ 降雨機率 (Rainfall)]`
     - `[📍 即時觀測 (Observations)]`
   - **獨立疊加圖層 (Independent Overlays)**：
     - `[☁️ 雷達回波 (Radar ON/OFF)]`：**雷達絕非第 4 種地圖模式**，而是可與氣溫、降雨、即時觀測三種模式並存之獨立 Leaflet 疊加層（Overlay）。
     - 切換地圖模式時絕不影響雷達圖層的開啟狀態或生命週期。
4. **完整保留既有縣市指標選取架構 (Preserve Proven County Selection)**：
   - Phase 7 驗證通過之 GeoJSON 多邊形點擊、高亮邊框（Highlight）、懸浮 Tooltip 與下拉選單雙向聯動機制 100% 保留。在切換至觀測或疊加雷達圖層時，使用者仍可點選縣市並切換聚焦目標，雷達圖層設有 `pointer-events: none` 絕不攔截縣市點擊橋接器。

---

### 10. 資料與 API 架構設計 (Data / API Architecture)

#### 10.1 領域模型與資料庫表結構分工 (Domain Models & Tables)
**絕對不將所有異質氣象資料混入同一張 `weather_forecasts` 表！**

> **架構重要說明（Phase 8C / 8D 現行實作）**：  
> 目前已實作之 Phase 8C（氣象測站即時觀測）與 Phase 8D（雷達回波疊加中繼）採用「伺服器端即時向 CWA 抓取 + 行程內最佳努力 (process-local) TTL 快取」機制，**未在 Supabase 資料庫建立或寫入額外資料表**（零 DB 綱要異動、零 PNG 二進位寫庫）。在 Vercel Serverless 無狀態環境下，行程內快取為最佳努力機制（冷啟動自癒抓取），不依賴或保證跨執行個體共享快取。資料庫持久化儲存保留為未來擴充架構選項。

```text
+-----------------------+     +--------------------------+
|   weather_forecasts   |     | (Future: observations)   |
+-----------------------+     +--------------------------+
| id (BigInt, PK)       |     | station_id (VARCHAR)     |
| dataset_id (VARCHAR)  |     | station_name (VARCHAR)   |
| region_name (VARCHAR) |     | county_name (VARCHAR)    |
| start_time (TIMESTAMPTZ)    | latitude / longitude     |
| end_time (TIMESTAMPTZ)|     | observation_time (TS)    |
| weather (VARCHAR)     |     | temperature / humidity   |
| min_temp / max_temp   |     | wind_speed / direction   |
| pop (INT, nullable)   |     | pressure / rain_1h       |
| comfort_index (VAR)   |     | fetched_at (TS)          |
| fetched_at (TS)       |     | [現行: 行程內 TTL 快取]  |
+-----------------------+     +--------------------------+

+-----------------------+     +--------------------------+
| (Future: typhoon)     |     | (Future: radar_meta)     |
+-----------------------+     +--------------------------+
| typhoon_id (VARCHAR)  |     | dataset_id (VARCHAR)     |
| cwa_id / name_zh/en   |     | observation_time (TS)    |
| intensity (VARCHAR)   |     | image_url (TEXT)         |
| is_active (BOOLEAN)   |     | bounds_geojson (TEXT)    |
| latest_track_json     |     | [現行: 行程內 5分快取]    |
+-----------------------+     +--------------------------+
```

1. `weather_forecasts`：縣市級預報（包含 `F-C0032-005` 一週預報與 `F-C0032-001` 短期預報，透過 `dataset_id` 嚴格區隔，持久化存儲於 Supabase PostgreSQL）。
2. `weather_observations`：`O-A0001` 自動氣象站真實量測數據（現行：伺服器端 live CWA 查詢 + 行程內 10 分鐘 TTL 快取）。
3. `typhoon_events` & `typhoon_tracks`：`W-C0034-005` 颱風中繼、歷史與預報路徑座標（未來擴充規劃）。
4. `radar_metadata`：`O-A0058-001` 雷達圖片時間戳與中繼 URL（現行：伺服器端 File API/S3 查詢 + 行程內 5 分鐘 TTL 快取，零圖片二進位入庫）。
5. `township_forecasts`：`F-D0047-093` 鄉鎮市區層級預報（未來擴充規劃）。

#### 10.2 嚴謹分層軟體架構 (Strict Layered Architecture)
維持高內聚低耦合之設計準則：
```text
CWA Open Data API
       ↓
  CWA Client       (app/clients/cwa_client.py)
       ↓
  CWA Parser       (app/parsers/cwa_parser.py)
       ↓
 Weather Repository (app/repositories/weather_repository.py - 預報持久化)
       ↓
 Weather Service   (app/services/weather_service.py - 行程內 TTL 快取與聚合)
       ↓
  FastAPI Routes   (app/api/routes.py)
       ↓
 Frontend Client   (app/static/js/app.js)
```

#### 10.3 智慧快取策略 (Smart Caching Strategy)
為防止高流量訪問對 CWA API 造成配額耗盡與頻寬浪費，設計基於資料更新特性的分級快取機制：
- **雷達回波 (`O-A0058-001`)**：CWA 約 10 分鐘產製一次 → 伺服器端行程內最佳努力快取 TTL: 5 分鐘（零圖片二進位寫入資料庫）。
- **現在觀測 (`O-A0001`)**：氣象站約 10–15 分鐘取樣一次 → 伺服器端行程內最佳努力快取 TTL: 10 分鐘（零 DB 綱要異動）。
- **颱風資訊 (`W-C0034-005`)**：平時無颱風快取 1 小時；警報發布期間快取 TTL: 15–30 分鐘（未來擴充規劃）。
- **短時預報 (`F-C0032-001`)**：每日發布約 4 次（約 05:00、11:00、17:00、23:00 四次常態更新，並視氣象情勢調整更新） → 伺服器端行程內快取 TTL: 10–30 分鐘。
- **鄉鎮預報 (`F-D0047-093`)**：每日更新 2–4 次 → 伺服器快取 TTL: 60–120 分鐘（未來擴充規劃）。
- **快取架構說明**：目前 Phase 8C 與 Phase 8D 架構為「伺服器端即時 CWA 抓取 + 行程內最佳努力（process-local）TTL 快取」。在 Vercel Serverless 無狀態環境下，各執行個體維護自身記憶體快取，冷啟動時安全自癒抓取，不依賴或承諾跨執行個體共享快取保證（不保證跨實例 < 50ms 命中）；持久化儲存（如 Supabase 資料庫或共享快取）保留為未來大規模擴充之架構選項。

---

### 11. 實作規劃路線圖 (Phase 8 Implementation Roadmap)

- [x] **Phase 8A — App Experience & Map Workspace** (已完成並通過生產環境驗收 / Completed and Production Verified)：
  - [x] 深淺色主題切換（Header 鈕、Sun/Moon 圖示、localStorage 持久化、prefers-color-scheme 零閃爍初始化）
  - [x] Chart.js 網格、標籤、Tooltip 主題動態同步更新（不破壞現有資料）
  - [x] Leaflet 控制項、Tooltip、圖例暗色適配與 OSM 底圖輕量 CSS 濾鏡
  - [x] 桌面版地圖擴展為主工作台（高度 600–680px，最大寬度 1440–1520px）
  - [x] 桌面浮動/收合縣市摘要面板（Chart.js 與預報資料表保留於地圖下方作為全寬詳情區塊）
  - [x] 桌面滾輪縮放（細指標裝置）與行動端手勢完整保留
  - [x] 重設臺灣視角控制按鈕（採用 GeoJSON `getBounds()` 動態計算，涵蓋本島與外島全境）
  - [x] 全螢幕地圖工作區控制按鈕（HTML5 Fullscreen API，支援尺寸動態重新計算）
  - [x] 跨裝置響應式支援（行動端 <= 960px 面板回歸靜態堆疊排版）
- [x] **Phase 8B — Rich County Forecast** (已完成並通過生產環境驗收 / Completed and Production Verified)：
  - [x] CWA `F-C0032-001` 今明 36 小時預報客戶端與安全過濾
  - [x] 專屬短天期解析器（`(start_time, end_time)` 嚴格複合鍵對齊，PoP/CI 容錯與數值安全轉換）
  - [x] 行程內最佳努力（best-effort）TTL 快取（10~30 分鐘，冷啟動自癒容錯，零 DB 結構變更）
  - [x] `GET /api/forecast/short-term` 專屬 API 端點與錯誤遮罩
  - [x] 前端今明 36 小時生活預報卡片（3 時段卡片、PoP 機率條、CI 舒適度文字標籤、獨立載入/錯誤狀態、防競態 AbortController）
- [x] **Phase 8B2 — Rainfall Probability Map Mode** (已完成並通過生產環境驗收 / Completed and Production Verified)：
  - [x] 獨立端點 `GET /api/map-data/short-term`（不破壞既有 `/api/map-data` 契約）
  - [x] 後端單次請求獲取全臺 22 縣市 F-C0032-001 完整資料（無 N+1 請求）
  - [x] 獨立全縣市地圖行程內快取（TTL: 15 分鐘，不與單一縣市快取共用）
  - [x] 單一 Leaflet 地圖實例支援 [🌡️ 溫度] 與 [🌧️ 降雨機率] 雙模式切換
  - [x] 降雨機率面量圖（藍色系漸層 0–20%, 21–40%, 41–60%, 61–80%, 81–100%, 無資料灰色）
  - [x] 降雨機率專屬圖例與安全 DOM Tooltip（呈現 PoP% 與舒適度文字）
  - [x] 浮動面板模式連動（降雨模式切換為短時預報摘要卡片群與獨立更新時間）
  - [x] 降雨資料延遲載入（首次點擊才抓取，後續切換時段無額外網路請求）
  - [x] 完整保留縣市選取、外框高亮、重設視角、全螢幕與深淺色主題
- [x] **Phase 8C — Current Weather Observations** (已完成並通過生產環境驗收 / Completed and production verified)：
  - [x] CWA `O-A0001` 全臺氣象測站即時觀測客戶端與連線重試 (`DATASET_OBSERVATION = "O-A0001"`)
  - [x] 專屬觀測資料解析器（嚴格選用 WGS84 座標系統，濾除 -99/X 等缺值，正規化雨跡 T 與 -98 無降雨狀態）
  - [x] 獨立行程內最佳努力 TTL 快取（10 分鐘，冷啟動自癒容錯，零 DB 結構變更）
  - [x] 專屬 API 端點 `GET /api/observations` 與安全錯誤遮罩
  - [x] 單一 Leaflet 地圖三模式控制項 `[🌡️ 溫度] [🌧️ 降雨機率] [📍 即時觀測]`
  - [x] 測站 Canvas CircleMarker 標記圖層（依據實測氣溫顏色漸層渲染，零第三方程式庫依賴）
  - [x] 縣市多邊形維持中性底色並保留實體點擊橋接器，支援選定縣市自動對焦代表測站
  - [x] 浮動面板切換至測站即時觀測摘要群組（明確標示「目前觀測 某某測站」與實際觀測時間，註明測站不代表全縣市平均）
  - [x] 測站 Hover 安全 Tooltip 與 Click 詳情 Popup（DOM 安全構建，無 innerHTML 插值）
  - [x] 觀測資料延遲載入（首次切換才抓取），切換縣市或測站重用客戶端快取
- [ ] **Phase 8D — Radar Layer** (實作完成，待正式環境手動驗收 / Implemented, pending production manual acceptance)：
  - [x] 採用無地形標準圖資 `O-A0058-001`（雷達整合回波圖－臺灣（較大範圍）_無地形，經度 115.00–126.50、緯度 17.75–29.25、解析度 3600×3600、更新頻率約 10 分鐘，消除底圖地形重複渲染誤差）
  - [x] CWA File API XML 伺服器端中繼資料解析（`ProductURL`, `DateTime`, `LongitudeRange`, `LatitudeRange`, `ImageDimension`）與 XML 命名空間韌性解析
  - [x] S3 HEAD `Last-Modified` 安全平降備援機制與語義明確時間來源標註（`radar_datetime` vs `last_modified`）
  - [x] 獨立行程內最佳努力 5 分鐘 TTL 快取（零 PNG 二進位寫入資料庫、零 DB 變更）
  - [x] 專屬 API 端點 `GET /api/radar` 與安全金鑰防護（零機密洩漏）
  - [x] Leaflet 獨立圖層架構（雷達為 Overlay 疊加層，絕非第 4 種地圖模式；與溫度、降雨、即時觀測三模式無縫共存）
  - [x] 專屬 Leaflet Pane (`radarPane`，z-index: 350，`pointer-events: none`)，保證絕不干擾縣市多邊形點擊橋接器、測站標記與地圖拖曳
  - [x] 聚焦渲染與底圖自動淡化（雷達開啟時 O-A0058-001 成為主視覺焦點並自動淡化 OSM 底圖至 0.08，關閉時立即恢復 1.0，縣市邊界與測站標記維持清晰）
  - [x] 地圖工具列雷達控制群組（開關 `#radar-toggle`、透明度滑桿 `#radar-opacity` 0.1–1.0、時間戳記 `#radar-status` 與重新整理 `#radar-refresh`）
  - [x] 圖片延遲載入（首次開啟才獲取）、防快取版本參數 (`?v=...`)、非阻塞錯誤處理與開啟時 10 分鐘自動背景更新
- [ ] **Phase 8E — Typhoon Center**（最後規劃功能 / FINAL planned feature）：`W-C0034-005` 颱風中心與路徑（歷史/預報路徑、暴風圈多邊形、西北太平洋廣域視角、無颱風正常空狀態）。
- [ ] **Phase 8F — Township Detailed Forecast**（延後規劃 / 專案當前範圍外 / Deferred / Future Work / Out of current project scope）：`F-D0047-093` 鄉鎮市區細緻預報（伺服器端解構過濾、focused API 漸進查詢、縣市→鄉鎮二階選單）。
- [ ] **Phase 8G — Application Polish / Future Features**（延後規劃 / 專案當前範圍外 / Deferred / Future Work / Out of current project scope）：喜愛縣市收藏、可分享網址狀態、PWA 離線支援、警特報橫幅與全方位無障礙適配。


