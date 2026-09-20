# FocusFlow V2 architecture

日期：2026-09-20。定位：Self-hosted Personal Cloud & Productivity Platform，daily use 優先。

## 現況與決策

維持 FastAPI/Jinja2/SQLite/SQLAlchemy modular monolith；不為符合 app/core 範例搬移全部目錄。

Browser → templates/static → routers → services → models/SQLite 或 Google/Firebase。

Core 邊界：auth/config/database 是共用基礎；workspaces + project_content + overview 是 Core domain API；legacy App routers 逐步抽出服務。新 API 延用 require_user 與 owner-scoped helpers，不繞過 Workspace ownership。

Session email → Workspace → Project(kind project/course) → Task、optional Note、ProjectLink。

ProjectLink 是 HTTP(S) 參考網址，不等於 File metadata、Calendar event 或 GitHub 同步。Identity 未有 User table；將來導入 stable user ID 必須先建立 email mapping/guest merge/session migration，不現在替換外鍵。

## API 與生命週期

/api/workspaces：create/list；/{workspace_id}：read/rename；/{workspace_id}/projects：create/list；/{workspace_id}/projects/{project_id}：read/rename；/archive：archive/restore。

Core detail GET 也經 ownership 與 workspace/project 配對檢查；他人資源回 404，無登入回 401。Project archive 是可逆流程，尚未承諾 hard delete；Workspace deletion 需先定義子項歸屬。

Notes 舊資料保持 project_id=NULL；Google Tasks 繼續獨立，不偷偷建立本地副本。後續先設計 FileRef/EventRef/provider identity 與 owner semantics，再新增 migration。

## 部署與邊界

常駐用 serve.py 單 worker，HTTPS 可經 Funnel；本機/公開登入 URL 不可混用，Secure cookie 保持啟用。健康檢查區分 app/DB 與 provider availability。secret JSON 不進 Git 或 image，runtime 注入。SQLite 必須有持久化路徑與可還原備份。

## 保留的未來方向

Home/App shell、Global Search 擴充、GitHub integration、AI shared capability、Dev/CLI 分期加入。AdaptiveCode 維持獨立產品；Homelab 是 infrastructure project。沒有本期 PostgreSQL、Redis 新服務、微服務或 AI 工作。


## Sprint 2 更新

見 [Sprint 2 實作與 ADR](SPRINT_2.md)：Workspace 只刪空白項目，Project 保留 archive/restore；Task 選 Local source of truth，Google sync 延後。57 tests passed。


## Sprint 3

Firebase = Optional Attachment / Storage Integration；見 [Daily-use gate](DAILY_USE_CHECKLIST.md) 及 [Backup/Restore](BACKUP_RESTORE.md)。同機快照不等於災難復原。
