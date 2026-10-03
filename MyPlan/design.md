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

#### Phase 7 驗收標準 (Acceptance Criteria — 待實作，全數保持未勾選)

##### Phase 7A — 驗收標準
- [ ] Taiwan map renders
- [ ] 22 counties render
- [ ] temperature choropleth
- [ ] hover tooltip
- [ ] click selection
- [ ] map/dropdown sync

##### Phase 7B — 驗收標準
- [ ] forecast periods available
- [ ] period selector
- [ ] switching period updates all counties
- [ ] no page reload
- [ ] no 22 API requests

##### Phase 7C — 驗收標準
- [ ] map-first dashboard layout
- [ ] selected county detail panel
- [ ] existing Chart.js integrated
- [ ] existing forecast table integrated
- [ ] responsive desktop/mobile
- [ ] Production deployment

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
