# FocusFlow V2 第一階段

## 目前狀態（2026-09-16）

最新產品企劃見 PRODUCT_PLAN.md：Today 快速新增／精確數量分頁、URL 定位、啟動前 schema 檢查、CI 設定已交付；49 tests passed。遠端 CI 未執行。

本節為最新狀態；後續標示「歷史」的紀錄代表當時狀態，不應當作目前待辦。

- 技術仍為 FastAPI、Jinja2、SQLite、SQLAlchemy；保留舊功能。
- 資料庫已升級至 `0004_daily_workspace`：專案封存、筆記回收欄位、參考連結。先前備份與原有資料逐筆比對已完成；本批不修改 schema 或使用者資料。
- `/` 是九個功能面板的 Dashboard；`/projects` 已有工作空間、專案／課程、Today、本機任務、筆記掛載、參考連結、搜尋及回收桶。
- 本機 Task 與 Google Tasks 各自獨立。File／Event domain、雙向同步尚未實作。
- Google OAuth 已由使用者確認登入成功；不等於全部 Google/Firebase/YouTube 操作均驗證。
- 共用 theme/components 已建立，兩個頁面外殼完成桌面／手機、明暗模式檢查；全部功能彈窗的 QA 仍待補。
- 本批修正 Calendar 編輯 API 與日期範圍驗證、Drive 回收桶與 20 MB 上傳上限、Quiz 20 MB／1000 題／20 選項上限及預先驗證、Calendar/Drive 安全 DOM 與失敗保留輸入。
- 匯出僅包含 core 內容與參考連結，不能替代全系統備份。

### 下一批順序

1. Tasks／Money／Music 的動態 HTML、安全事件綁定與 HTTP 錯誤處理；Google Tasks 欄位契約。
2. 外部服務分頁、Drive 查詢跳脫、Calendar 前端時區與全天結束日說明；所有頁面互動 QA。
3. 啟動 schema 檢查、備份還原演練、CI；逐頁抽取共用版型與依賴。
4. Drive 資料夾選擇器、money_service 測試、FileRef／EventRef、Course–QuizBank。
5. 多語系在功能與文字穩定後進行；AI、資料庫替換不在當前範圍。

## 歷史分批紀錄

方向：Self-hosted Personal Digital Workspace；Workspace → Project/Course → Task、Note、File、Event。

## 本輪分批交付

1. **開發基線及資料層**：保留既有修改；requirements-dev、隔離環境、config 預先載入、models/base + legacy、database 相容匯出；Alembic 0001 採納 V1，先檢查 schema，只補已知三欄/缺表/index，不改既有資料列。CLI 自動 SQLite backup + integrity check。
2. **Workspace / Project Core**：新增兩張表；Workspace 以 user_email 擁有；Project 透過 workspace 繼承 owner，kind=project/course；FK、名稱檢查。提供有 session 與 owner 驗證的列出/建立/重新命名 API。第一批不提供刪除及跨 workspace 移動，以避免級聯刪除和歸屬問題。
3. **驗證與使用說明**：migration 全新/舊 schema/重複執行/異常拒絕、原資料庫副本逐列比對、跨帳號隔離與訪客合併、舊本機 API 與首頁 smoke。

## 第一批當時的後續規劃（歷史）

- 先明確定義本機 Task 與 Google Tasks 的同步責任，再加 nullable Project 關聯於 Note；不強制分配旧資料。
- File / Event 初期以外部識別與連結方式設計；避免現在複製 Google 資料。
- Core 使用穩定後再新增 Jinja2 專案頁；保留 V1 前端。
- OAuth state、資源上限與前端 escaping 列下一批修復；再評估搜尋、GitHub、CI/CD；AI、換 DB 不在本輪。

## 第一批執行結果（歷史）

- Python 3.12 隔離環境：20 tests passed（migration、API、權限、訪客合併、V1 本機 smoke）。
- 第一批：全新 DB 升級及 Alembic check 通過；第二批：新增 core 後重新驗證通過。
- 既有 SQLite 的 online backup 副本升級到 0002；11 張舊表逐列雜湊/筆數均一致；完整性及 Alembic check 通過。
- 發現 notes.image_url 實際是 TEXT，model 與 frozen baseline 已對齊；無須改寫實際舊欄位。
- 原始 focusflow.db 的 SHA-256 與起始完全一致；未升級原始 DB。使用 core 前依 README 停機並執行 migrate_db.py。
- 真實 Uvicorn 子程序以獨立 DB 啟動，HTTP / = 200、OpenAPI 包含 Workspace；檢查後已停止。
- pip check、全部 static/js 與 sw.js 的 Node 語法檢查、本輪 tracked 檔案 diff whitespace 檢查通過。
- 剩餘 69 個 deprecation warnings 來自舊版 datetime.utcnow / TemplateResponse 使用方式；本輪不改既有日期儲存語意。
- 未做：Docker build、瀏覽器完整互動/外觀 QA、真實 OAuth / Firebase / Redis / Google API / YouTube 播放驗證。
- 未 commit/push；保留起始 17 個 tracked 修改與 2 個 untracked 檔案。

Migration 參考：[Alembic 官方 tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)。


## 第二批：OAuth 與 Project 內容（2026-09-15）

- OAuth：10 分鐘一次性 state、獨立瀏覽器 nonce 綁定、server-side PKCE verifier、回呼使用後移除；缺少/錯誤/過期 state 不交換 token；失敗訊息不洩漏 provider token。pending attempts 上限 1000。
- OAuth 暫存採單一程序記憶體，符合目前單 worker 部署；重啟或同時在多頁發起登入時需重新登入。多 worker 前要改用共用短期 store；本輪不引入新服務。
- SQLite Task 屬於 Project，提供建立/分頁列出/更新（todo/doing/done、描述、日期可清除）。Google Tasks 的 `/api/tasks` 保持獨立，不自動同步或複製。
- Note 新增 nullable project_id；提供掛載、分頁列出、解除關聯 API。解除只清除關聯，原筆記內容與 V1 API 保留；不強制分配舊筆記。
- 0003 migration 只新增 tasks 與 notes.project_id/index；SQLite 直接新增可空 FK 欄位，不重建舊 notes 表。Project 有關聯內容時 DB 會阻擋直接刪除；API 尚無 Project 刪除。
- 現有 project DB 已先備份再升級到 0003_project_content；所有原有欄位/資料列逐表雜湊完全一致，integrity_check / foreign_key_check / alembic check 通過。
- 備份：`.local/backups/focusflow.db.20260915T121151394868Z.db`。此備份含私人資料，未輸出內容。
- 32 tests passed；Uvicorn 真實 HTTP 啟動確認通過；測試服務已停止。
- Windows 前後測試帳號的 Temp/.pytest_cache ACL 不同，這次測試用新的 workspace basetemp 並停用 cache provider。137 個既有日期/TemplateResponse deprecation warnings 保留。
- 尚未實測 Google OAuth/Firebase/Redis/YouTube；新增安全測試使用 fake provider，不宣稱真實授權已完成。

下一批：上傳容量/檔名處理、前端 escaping，接著小範圍 Jinja2 專案頁。沒有新增 File/Event、自動同步、AI 或更換前端框架。本輪未 commit/push。


## 2026-09-16 OAuth 登入修復

- login 500：非 JSON 的 GOOGLE_CREDENTIALS 在啟動時覆寫 credentials.json。新增驗證及原子寫入，無效設定保留現有檔案。
- callback 500：使用者回報診斷碼 oauth_token_exchange_InvalidClientError。舊專案憑證 client ID 與 4 筆 session 一致，但 secret 全部不一致；改以 4 筆 session 一致的 secret 恢復，舊檔已備份於忽略追蹤的 .local/backups。
- Google token endpoint 預檢使用刻意無效的測試授權碼，恢復後回傳 invalid_grant，未再回覆 invalid_client；使用者已於 2026-09-16 確認完整瀏覽器登入成功。
- 新增安全錯誤階段碼（不含例外文字、token 或授權碼），以及真實 OAuth SDK + 模擬 token HTTP 回應的完整 callback 測試。
- /service-worker.js 相容路由已補；40 tests passed。沒有更動使用者資料或公開 secrets。

## 本批驗證結果（2026-09-16）

- pytest：46 passed，148 warnings（既有日期／API deprecated 用法等仍待整理）。測試使用隔離 DB；Google provider 為 mock。
- 新測試涵蓋 Calendar patch／日期拒絕／錯誤不洩漏、Drive 移回收桶／超限拒絕與暫存清理、Quiz 匯入驗證失敗不寫入。
- Playwright：Calendar／Drive 的 HTML 測試字串不生成標籤、不執行事件；危險連結停用；Calendar 模擬 502 保留表單與內容。
- calendar.js、drive.js 的 Node 語法檢查通過。
- 無資料庫 migration、沒有操作真實 Google 雲端檔案或行程；未 commit/push。

## 本輪執行結果（2026-09-16）

已完成：
- Today 快速新增本機任務，選擇未封存專案／課程；沿用既有 owner 與資料驗證。
- Today 提供 counts/has_more、limit/offset；UI 精確總數及「載入更多」。offset 分頁期間若其他裝置新增／完成任務，建議重新整理，尚非快照或 cursor 分頁。
- `/projects?project=...` 與 `?view=trash` 支援重新整理、上一頁／下一頁；未知專案回 Today 並提示。
- `check_database.py` 唯讀比對 Alembic head 與 models 的必要表／欄位；`python main.py` 啟動前執行。直接 uvicorn 啟動須先手動執行檢查；reload 期間的新 schema 變更不受此一次性檢查保護。不是完整 schema/type/index/integrity audit。
- `.github/workflows/checks.yml` 已新增 Python 3.11/3.12 pytest 及 Node JS 語法檢查設定；尚未 push，因此遠端 CI 尚未執行。

驗證：49 tests passed，263 warnings；包含 101 筆任務分頁、不跨 owner、不顯示封存／已完成項目，以及 preflight 不建立缺失 DB、不改動舊版 DB、偵測缺欄位。
Playwright 使用模擬 API 完成快速新增、專案刷新／上一頁、回收桶刷新、390px 手機無橫向溢出。沒有新增使用者真實任務，也未操作外部 Google API。
本機原資料庫唯讀 preflight 通過；沒有 migration、未 commit/push。M1 其餘安全修復、M3/M4 仍待逐批交付。


## 2026-09-17 修復更新

本次實測發現的 Tasks/Money/Music HTML 注入、Tasks 500 清草稿、undefined 欄位已修復；Music 返回歌單已補、未完成的歌單寫入按鈕已明確停用。新增 serve.py、health/live、health/ready、Docker preflight 及瀏覽器 CI 回歸。詳細驗證與限制見 FIXES_2026_09_17.md。正式啟動使用 `python serve.py`，先依既有步驟備份及完成 migration；不能當作已完成公網部署。
