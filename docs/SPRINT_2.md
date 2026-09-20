# Sprint 2 — Core Completion & Real-world Validation

日期：2026-09-20。只執行本 Sprint；未進入 Sprint 3。

## Core 最終能力與資料安全

Workspace：create/list/get/rename + delete empty；有任何 Project（包括 archived）回 409。Project：create/list/get/rename/archive/restore，不 hard delete。Workspace 不提供 cascade 或整批 archive；需要更完整收納能力時再設計 migration。DB RESTRICT 外鍵是第二層保護，併發插入與刪除極端競態仍可能回通用 DB error，資料不會級聯刪除。

Project archive 語意維持「從預設列表及 Today 隱藏」，不是 read-only/freeze。owner 可整理內容；Notes/Tasks 關聯保留；restore 恢復列表。匿名 401、跨 owner 或錯 workspace/project 404。這是 owner-only，沒有協作角色。

## Project Context

沿用 /projects：Workspace selector → Project → metadata/type/archive state + tasks + notes。新增 metadata 中 workspace 名稱/建立日期；新增 Workspace rename 與只在空白時顯示 delete（使用確認框，後端再次檢查）。既有 Notes 掛載/解除與 Task 建立/編輯不重做；不加 File/Calendar/GitHub。

## Authentication 真實證據

本 Sprint 檢查到新 web OAuth client 已有授權 session；refresh token 向 Google 更新成功。oauth2 userinfo、Tasks tasklists、Drive files、Calendar calendarList、YouTube channels 的唯讀請求全部成功。公開 /health/ready、/api/auth/login = 200。這證明已有真實 callback/session 授權結果，但並非本次自動重演整個瀏覽器同意畫面；logout 用隔離測試驗證，未登出使用者。Google 寫入與所有 UI 場景未測。

nonce/PKCE/state、cookie 與 callback 路徑保留。移除 /auth/user 與共用 provider error 的原始 exception detail，避免 token/provider payload 洩漏。session token 仍明文存 DB；public access limits 未完成。

### 開發 / production 設定

Development：獨立 shell/DB，RENDER_EXTERNAL_URL=http://127.0.0.1:8000、OAUTH_REDIRECT_URI=http://127.0.0.1:8000/api/auth/callback、COOKIE_SECURE=false。Google client 必須登記 exact callback。Production：RENDER_EXTERNAL_URL=實際公開 HTTPS origin、OAUTH_REDIRECT_URI=該 origin + /api/auth/callback、COOKIE_SECURE=true，serve.py 單 worker。沿用現有變數避免破壞部署；無新增硬編碼網址。不要在同一 shell/DB 同時跑開發與排程。修改/reload 會清除 pending OAuth state，重新開始登入。

## Firebase decision：Refactor（optional legacy integration）

仍被 Note 圖片與 Keep 附件 upload、受 owner 保護的 download 使用；不是 Workspace/Project/純文字 Notes/Local Task 的必要 dependency。

前次 key 有效但 bucket list 空及 configured bucket 404；本 Sprint 已變為 credential refresh 失敗（RefreshError），故不能宣稱 bucket 已恢復，也無法確定失敗根因。需帳戶端確認 key 是否撤銷、服務帳戶是否停用。沒有建立 bucket、增加費用或刪除附件紀錄。

建議後續把 storage adapter 明確設為 optional，未配置時附件功能顯示 unavailable；自架 local storage 要另行設計 owner/path traversal/backup，不在本 Sprint 重建。既有 initialize 訊息不等於服務可用；pure Core 可繼續使用。

## Task ADR：選 A

| 策略 | 複雜度 | offline/self-host、ownership | 衝突 / 未來整合 |
|---|---|---|---|
| A Local source of truth + Google sync | Core 簡單，sync 後續較複雜 | 自有資料、離線優先 | 明確 canonical ID；需版本/刪除標記/衝突政策，易擴其他 provider |
| B Google source of truth | 初期較低，Core 耦合 provider | 仰賴網路/授權，資料控制較弱 | 受 Google 欄位/API 限制，其他整合不易 |
| C 同時 Local/Google provider abstraction | 現在最高 | 能離線但語意分裂 | 多 canonical records、能力差異、去重衝突較多 |

決定：A 符合 Personal Cloud；此時 Google Tasks 與 Local Tasks 仍獨立，明確標示來源，不假裝同步。未來 mapping(local_task_id/provider/external_id)、sync revision/tombstone/retry/授權範圍須先 ADR 與測試，再選單向輸出起步；不在此 Sprint 建表或實作雙向 sync。

## Deprecation 分類

- Python：datetime.utcnow() 是主要來源，包括 DB session、models、舊 routers 與 tests；將來移除會 breaking。全面改 aware datetime 會影響舊 SQLite naive timestamps，本次不做。
- SQLAlchemy：部分警告從 default callable wrapper 冒出，實際根源仍是 Python utcnow，不能誤判 ORM API 被移除。
- FastAPI/Starlette：TemplateResponse 舊參數順序已低風險修為 request-first keyword。
- Project archive：改 datetime.now(timezone.utc).replace(tzinfo=None)，保留既有 naive UTC 儲存格式。
- Third-party：google_auth_oauthlib utcfromtimestamp 警告，後續透過相容套件升級處理。
- Pydantic：本次未觀察到獨立 deprecation；不代表未來無風險。

## Tests / migration / changed files

原 54 tests 保持通過，新增 3 tests：workspace delete/ownership + project archive/restore/tasks/notes workflow；provider secret error redaction；logout invalidates session。總計 57 passed / 298 warnings（新增流程增加警告觸發次數，不是新增 21 種警告）。

修改：services/workspace_service.py、routers/workspaces.py、routers/auth.py、services/google_auth_service.py、main.py、templates/projects.html、static/js/projects.js、tests/test_core.py、tests/test_oauth.py、docs/V2_ARCHITECTURE.md、docs/ROADMAP.md、本報告。無 dependency/schema change、無 production migration/DB 寫入；唯讀 Google probes 不修改雲端內容。未 commit/push。UI 新互動尚未完成瀏覽器 E2E，不能用 API tests 代替。

## Sprint 3 建議（未開始）

優先 backup/restore 演練、Project workflow browser E2E、optional storage unavailable UX 與憑證問題釐清；再評估 Workspace archive。不要先加新 domain 或 AI。

使用者最終確認：本 Sprint 公開 HTTPS Google 登入成功回到首頁；完整互動由使用者完成。
