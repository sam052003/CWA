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

後續可改成：

- Vercel Cron
- GitHub Actions
- secured internal endpoint

定時更新。

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
│  ├─ core/
│  │  ├─ __init__.py
│  │  └─ config.py
│  │
│  ├─ api/
│  │  └─ routes.py
│  │
│  ├─ services/
│  │  └─ weather_service.py
│  │
│  ├─ repositories/
│  │  └─ weather_repository.py
│  │
│  ├─ clients/
│  │  └─ cwa_client.py
│  │
│  ├─ parsers/
│  │  └─ cwa_parser.py
│  │
│  ├─ db/
│  │  ├─ database.py
│  │  └─ models.py
│  │
│  ├─ templates/
│  │  └─ index.html
│  │
│  └─ static/
│     ├─ css/
│     │  └─ style.css
│     └─ js/
│        └─ app.js
│
├─ scripts/
│  ├─ init_db.py
│  └─ fetch_weather.py
│
├─ tests/
│  ├─ test_api.py
│  ├─ test_config.py
│  ├─ test_parser.py
│  └─ test_repository.py
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

第一版可先設定約每 **6 小時**更新一次；實際頻率之後依使用的 CWA dataset 發布時程調整。

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

- [ ] GET `/api/regions`
- [ ] GET `/api/forecast`
- [ ] refresh service
- [ ] error handling

### Phase 5 — Frontend

- [ ] Layout
- [ ] Region dropdown
- [ ] Summary cards
- [ ] Chart.js line chart
- [ ] Forecast table
- [ ] loading/error state
- [ ] responsive layout

### Phase 6 — Deployment

- [ ] GitHub
- [ ] Vercel Project
- [ ] `CWA_API_KEY` Environment Variable
- [ ] `DATABASE_URL` Environment Variable
- [ ] Supabase production connection
- [ ] Build test
- [ ] Production smoke test

### Phase 7 — Advanced

- [ ] Taiwan map
- [ ] Township forecast
- [ ] PoP
- [ ] humidity
- [ ] wind
- [ ] UV
- [ ] weather alert
- [ ] AI summary

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
- [ ] 網站可以切換縣市
- [ ] 可以顯示一週天氣資料表
- [ ] 可以顯示最高／最低溫折線圖
- [ ] CWA API Key 未出現在 GitHub
- [ ] Database credentials 未出現在 GitHub
- [ ] GitHub repository 有完整原始碼
- [ ] Vercel deployment 可正常瀏覽

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
        │
        │ JSON
        ▼
Python / FastAPI
        │
        ├── CWA Client
        ├── JSON Parser
        ├── Weather Service
        └── Repository
                │
                │ SQL
                ▼
        Supabase PostgreSQL
                │
                ▼
          FastAPI API
                │
                ▼
    HTML / CSS / JavaScript
                │
                ▼
             Chart.js

GitHub → Vercel Deployment
```

這個版本不再依賴 SQLite，本機與正式部署環境都採 PostgreSQL，避免 Vercel 本機檔案持久化問題，也讓整個專案架構更接近一般正式 Web Application。
