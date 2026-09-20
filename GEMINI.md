# FocusFlow OS - 開發進度與結構紀錄

> 歷史文件（2026-04-05）：保留原開發紀錄。模型已移至 models/，遷移已改用 Alembic，新增 /projects 與共用 CSS。最新入口請看 README.md 和 V2_IMPLEMENTATION_PLAN.md；原 Drive 資料夾樹、money_service 測試、多語系規劃已納入最新待辦。

這份檔案由 Gemini CLI 自動生成，用於紀錄專案結構、開發狀態及後續規劃。

## 🚀 專案概述
FocusFlow OS 是一個基於 FastAPI 的多功能儀表板系統，整合了 Google Drive、音樂、行事曆、筆記、任務管理及記帳功能。

---

## 📁 檔案結構 (Project Structure)

```text
C:\Users\urua0\Desktop\mydashborad-part2-cloud\
├── main.py                 # 專案入口點，負責 FastAPI 初始化與路由掛載
├── database.py             # SQLAlchemy 資料庫模型與工作階段管理
├── migrate_db.py           # 資料庫遷移腳本 (用於新增欄位)
├── requirements.txt        # 專案套件依賴 (包含 firebase-admin, fastapi 等)
├── .env                    # 環境變數設定 (包含 Google & Firebase 金鑰)
├── routers/                # 後端 API 路由
│   ├── drive.py            # Google Drive 檔案操作 (上傳、刪除、搬移)
│   ├── notes.py            # 筆記 API (支援 Firebase 圖片連結)
│   ├── money.py            # 記帳 API
│   └── ... (auth, calendar, etc.)
├── services/               # 業務邏輯抽離層
│   ├── firebase_service.py # Firebase 初始化與 Storage 上傳邏輯
│   └── money_service.py    # 記帳數據統計邏輯
├── static/                 # 前端靜態資源
│   ├── js/                 # 各功能的 JavaScript 邏輯 (drive.js, notes.js)
│   └── css/                # 各功能的樣式表
└── templates/              # Jinja2 模板
    ├── index.html          # 主頁面結構
    └── partials/           # 各功能的 HTML 片段
```

---

## ✅ 目前開發進度 (Current Status)

### 1. Google Drive 檔案管理
- [x] 檔案列表顯示與過濾。
- [x] 檔案上傳與刪除功能。
- [x] **[新增]** 檔案搬移功能 (`/api/drive/move`)，支援跨資料夾移動。
- [x] 前端實作 `move-modal` 彈窗。

### 2. 筆記系統 (Notes)
- [x] 基本筆記 CRUD。
- [x] **[整合]** Firebase Storage 圖片上傳。
- [x] 資料庫 `notes` 資料表新增 `image_url` 欄位。
- [x] 前端支援網格/清單模式下的圖片預覽。

### 3. 記帳系統 (Money)
- [x] **[優化]** 將統計邏輯從 Router 抽離至 `services/money_service.py`。
- [x] 支援分類預算超支提示 (Status: over)。

### 4. 系統修復
- [x] 修正 `index.html` 缺少的 `alert-modal` 結構，解決 `showAlert()` 報錯問題。

---

## ⚙️ 環境設定 (Environment Variables)

請確保 `.env` 檔案包含以下變數：
- `GOOGLE_TOKEN`: Google OAuth Token
- `GOOGLE_CREDENTIALS`: Google API 憑證
- `FIREBASE_KEY_FILE`: Firebase Admin SDK 金鑰 JSON 路徑
- `FIREBASE_STORAGE_BUCKET`: Firebase Storage 儲存桶名稱

---

## 📝 變更日誌 (Change Log - 2026-04-05)

- **Backend**:
  - `main.py`: 加入 Firebase 初始化。
  - `database.py`: `Note` 模型新增 `image_url`。
  - `routers/drive.py`: 新增 `/move` Post 接口。
  - `routers/notes.py`: 更新 `/add` 接口以處理 `UploadFile`。
- **Frontend**:
  - `static/js/drive.js`: 加入搬移檔案邏輯與選取狀態管理。
  - `templates/index.html`: 補強全域通知模態視窗 (`alert-modal`)。
  - `templates/partials/drive.html`: 加入搬移工具按鈕與 Modal 結構。

---

## 🎯 後續規劃 (Next Steps)
1. **Drive UI 優化**：將手動輸入資料夾 ID 改為資料夾樹狀選單。
2. **多語系支援**：將前端寫死的中文訊息整理成多語系檔。
3. **單元測試**：為 `money_service` 編寫測試案例。

---
*最後更新日期：2026-04-05*
