# FocusFlow repository audit

日期：2026-09-20。依目前 working tree，不代表已提交版本。branch：master；起始已有大量 tracked 修改與 untracked 模組，本 Sprint 保留它們，未 commit/push。

## 實際架構與模組

FastAPI modular-monolith 雛形。main.py 匯入 config、還原憑證、註冊 routers、掛載 Jinja2/static。python main.py 是 reload 開發入口；serve.py 是單 worker、無 reload 的常駐入口。兩者先檢查 schema；直接 uvicorn main:app 可繞過 preflight。

- routers：auth、notes、tasks（Google）、calendar、drive、music、money、chat、quiz、workspaces、project_content、overview、files、health。
- services：workspace/project_content、Google token refresh、credential restore、Firebase、upload bounds、money summary、access-log redaction。
- 前端：index.html + 九個 partial 面板；projects.html 提供 Today/Workspace/Project/Core Tasks/Notes/Links/Search。theme/components 共用樣式已存在，仍有 App CSS/JS 與 inline handlers，尚非完整獨立 App shell。
- tests：core、content、daily workflow、OAuth、credential、legacy smoke、migration、deployment、priority fixes；另有 mocked browser_security.py。

## Database / migration

SQLite + SQLAlchemy；實體 DB 唯讀檢查：0004_daily_workspace，integrity_check=ok，foreign_key_check=0。

15 張 domain/legacy 表：sessions、notes、transactions、categories、music_history、quiz_banks、quiz_questions、quiz_options、exam_sessions、exam_answers、keep_items、workspaces、projects、tasks、project_links；另有 alembic_version。

models/base.py 共用 Base；legacy.py 保留舊模型；workspace/task/project_link 分檔。database.py 提供相容匯出、session factory、session/guest merge。

0001 frozen legacy adoption → 0002 Workspace/Project → 0003 Task/nullable Note.project_id → 0004 archive/trash/links。migrate_db.py 先 SQLite online backup + integrity check，再 upgrade head；不是啟動時自動 ALTER。不要直接 stamp 不明舊 DB。

## 與 brief 的差異

- Workspace/Project 已有 create/list/rename，Project archive/restore；本 Sprint 補 detail GET。並非完整 CRUD：Workspace delete、Project hard delete/跨 workspace move 未實作。
- User 不是獨立 identity 表：session email 為 owner，Workspace.user_email，Project 經 workspace 查 owner。
- Course 已是 Project.kind=course，尚無獨立 Course domain。
- Core Task 必須屬於 Project；Note.project_id 可空。Google Tasks 與本機 Task 是兩套資料，沒有同步。
- Today、keyword search（Project/Task/Note）、core export 已先實作；不是完整 Global Search 或全系統備份。
- Redis dependency/broadcast code 已存在，可降級；本輪不新加 Redis。
- File/Event metadata、integration registry、tags/activity/notification、GitHub、AI、Dev/CLI 尚未建立。

## 功能證據與外部整合

本次離線 regression：54 passed（基線 52）；覆蓋本機 core/legacy smoke 和 mocked OAuth，不能宣稱真實 Google 寫入成功。

Google 登入/Tasks/Drive/Calendar/YouTube 用 mydashborad2 新 web OAuth。Firebase 用 mydashborad-cloud 服務帳戶。2026-09-20 前次實測：Firebase key 有效，但 bucket 清單空、configured bucket 404；新 OAuth authorized session 未找到。這些是外部服務阻礙，不阻擋離線 Core Sprint。

Tailscale Funnel + Windows 工作排程器提供 HTTPS；手動 main.py 與排程競爭 8000 埠曾失敗。健康 ready 只檢查 DB，不代表 Firebase/Google 可用。

## 技術債、安全與 dead code

- OAuth state/PKCE/nonce 為程序記憶體：reload/重啟會失效，維持一 worker。HTTPS 下從 localhost 登入會丟 cookie；本 Sprint 在登入入口回覆明確錯誤並提供 canonical URL。
- session token_json 明文儲存於 DB；本機檔案/備份與主機帳戶必須保護。無完整角色/分享/配額/登入限流，公開多人 production 尚未完成。
- GOOGLE_TOKEN → token.json 是殘留恢復路徑：實際 Google APIs 讀 sessions.token_json；暫保留相容，後續再移除，不刪使用者憑證。
- .gitignore 排除所有 JSON，可能誤忽略未來測試 fixture；Docker 原未排除下載的 client_secret JSON，本 Sprint 修補。
- legacy routers 混有 DB/provider 邏輯；部分 async handlers 使用同步 SDK；外部列表分頁、錯誤分類與 timeout 尚不一致。
- Money 使用 Float；datetime.utcnow/Jinja2 舊介面產生 deprecation warnings。未在本輪改金額或時間語意。
- Docker 還有 MySQL build dependencies，但 runtime 僅 SQLite；未做 image build/供應鏈漏洞掃描。pip check 僅驗證 dependency 相容。
- Music playlist 寫入未完成，UI 已停用；stream 仰賴外部影音來源；不是已驗證長期可用。

## Migration / rollback 風險與缺測

本 Sprint 不改 model/schema、不執行 production migration、不改原資料列。未做真實備份還原演練、多人併發、所有 App E2E、Docker build、遠端 CI、Google/Firebase 寫入測試。未證實的功能不得標為 ready。

變更 rollback：逐項撤回本 Sprint 的新增 routes/guard/ignore/docs，保留起始 dirty tree；不可 git reset --hard。未來 migration 在 DB 副本演練，停寫並確認備份可還原，再套用正式資料；不把 downgrade 當作資料備份。
