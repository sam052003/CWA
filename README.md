# CWA Taiwan Weather Forecast (中央氣象署一週天氣預報)

以**中央氣象署（CWA）Open Data API** 為資料來源的臺灣天氣預報網站，支援 22 縣市一週預報、最高/最低溫折線圖與預報資料表。

> **專案規格與主要設計原則**：請參閱 [`MyPlan/design.md`](MyPlan/design.md)。

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
│  ├─ test_parser.py         # JSON Parser 測試 (Phase 2)
│  └─ test_repository.py     # Repository 測試 (Phase 3)
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
DATABASE_URL=postgresql+psycopg://postgres:your_password@db.your_project.supabase.co:5432/postgres
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
- **歡迎頁面 (Hello World)**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **系統健康檢查 (Health Check)**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- **API 健康檢查**: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- **FastAPI 自動化 Swagger API 文件**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc 文件**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### 6. 執行自動化測試

```bash
pytest
```

---

## 目前開發進度

- [x] **Phase 1: 環境與基礎架構** (當前完成)
  - 專案目錄結構建立
  - FastAPI 基礎架構與 Health Check / Hello World 端點
  - `requirements.txt`、`.gitignore`、`.env.example`
  - 安全保護機制（預留 `CWA_API_KEY` 與 `DATABASE_URL`，確保 Secrets 不外洩）
  - 本機啟動與測試流程建立
- [ ] **Phase 2: CWA API 資料串接與解析**
- [ ] **Phase 3: Supabase PostgreSQL 資料庫串接與 Repository**
- [ ] **Phase 4: Web API 端點 (`/api/regions`, `/api/forecast`, `/api/refresh`)**
- [ ] **Phase 5: 前端視覺化 (HTML, CSS, JavaScript, Chart.js)**
- [ ] **Phase 6: Vercel 雲端正式部署**
