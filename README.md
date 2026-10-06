# FocusFlow

最新架構與 Sprint（2026-09-20）：[Audit](docs/V1_AUDIT.md) · [Architecture](docs/V2_ARCHITECTURE.md) · [Roadmap](docs/ROADMAP.md)。根目錄舊報告保留為歷史。

FastAPI + Jinja2 + SQLite personal workspace. V1 modules remain available; V2 includes a Workspace / Project UI and API core.

## HomeCloud Production Status

As of 2026-10-05, FocusFlow is running on the private HomeCloud environment using Docker Compose, persistent SQLite, Redis, nginx, Tailscale private HTTPS, scheduled backup, health monitoring, Discord alerts, and a Windows VM-external backup copy.

This is a private self-hosted deployment, not a public Internet production service.

See:

- `docs/HOMECLOUD_DEPLOYMENT.md`
- `docs/HOMECLOUD_OPERATIONS.md`
- `docs/BACKUP_RESTORE.md`


## Local development (PowerShell)

Use Python 3.11+ (this run tested Python 3.12). From this repository:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Existing `.env` and credentials stay private. For a clean offline development database, run:

```powershell
$env:PYTHON_DOTENV_DISABLED = '1'
$env:DATABASE_URL = 'sqlite:///./development.db'
.\.venv\Scripts\python.exe migrate_db.py
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

`PYTHON_DOTENV_DISABLED` only skips `.env`; it does not erase variables inherited from your shell. Use a clean shell for testing without credentials. Google/Firebase features need actual configuration; basic guest Notes/Money/Quiz/Workspace work without them. Redis is an existing optional Keep broadcast integration; without a Redis server, Keep writes persist but broadcast attempts may wait for a timeout.

Visit `/api/auth/guest`, then `/docs` to exercise Workspace endpoints using the same browser session. Visit `/` for the legacy dashboard or `/projects` for Today, workspaces, projects/courses, tasks, notes, search and trash.

## Upgrade an existing SQLite database

The local `focusflow.db` was backed up and upgraded to **0004_daily_workspace on 2026-09-16**. The following steps apply to other databases and future upgrades. Stop the running app and any other database writers before upgrading. The CLI loads `.env` and defaults to `focusflow.db` beside `config.py`; `DATABASE_URL` overrides this. Prefer an absolute URL for deployment.

```powershell
# In a new shell, with the app stopped, from the repository:
.\.venv\Scripts\python.exe migrate_db.py
if ($LASTEXITCODE -ne 0) { throw 'Migration failed; inspect before starting app' }
.\.venv\Scripts\python.exe -m alembic check
if ($LASTEXITCODE -ne 0) { throw 'Schema drift detected' }
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

For an existing database the CLI first uses SQLite online backup and verifies integrity. The backup is stored in `.local/backups/` beside the database, with a timestamp. Backups contain private user data and tokens; keep them local. Migration 0001 adopts V1 without dropping tables and only repairs known missing columns / indexes. Migration 0002 adds workspaces and projects; 0003 adds local tasks and note links; 0004 adds project archiving, note trash and reference links. Unexpected V1 column/key differences stop the migration for review. Do not use `alembic stamp head` to bypass validation. Direct `alembic upgrade` bypasses the backup helper.

Automatic downgrade is intentionally disabled because it could delete user data. To roll back: stop writers, retain the failed database for diagnosis, restore the verified backup to the configured database location, then run the matching old application version. Do not overwrite a live database or copy a WAL database with ordinary file copying. A failed SQLite DDL migration may leave partial schema changes; restore the backup before retrying after resolving the cause.

## Core API

All requests require the existing `session_id` cookie. JSON payloads:

| Method | Path | Body / result |
|---|---|---|
| GET | `/api/workspaces` | list; `limit` 1–200, `offset` >= 0 |
| POST | `/api/workspaces` | `{"name":"Learning"}` |
| PATCH | `/api/workspaces/{id}` | `{"name":"School"}` |
| GET | `/api/workspaces/{id}/projects` | list with pagination |
| POST | `/api/workspaces/{id}/projects` | `{"name":"Database","kind":"course"}`; kind defaults to project |
| PATCH | `/api/workspaces/{id}/projects/{project_id}` | `{"name":"Database II"}` |

Names are trimmed, 1–120 characters. Owner comes from the authenticated session; client-provided owner fields are rejected. Projects inherit owner through their workspace. Unknown / other users' objects return 404; invalid or expired sessions return 401. Guest-to-Google merge transfers workspace ownership and preserves projects. No destructive core endpoints are introduced.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Tests always use temporary DBs and disable real credentials before importing the app. Keep publish is mocked; external service connectivity is not certified. Alembic `check` compares the configured database with model metadata.

## Docker

FocusFlow is currently deployed on HomeCloud using Docker Compose. The application uses a persistent `/data` mount with `DATABASE_URL=sqlite:////data/focusflow.db`, while credentials are supplied only at runtime and are not stored in the image. Redis runs as an internal Docker service without a published host port. The application port is bound to `127.0.0.1:8000` and is reached through nginx and Tailscale Serve.

Before database migration or other destructive operations, create and verify a backup first. See `docs/HOMECLOUD_DEPLOYMENT.md` and `docs/HOMECLOUD_OPERATIONS.md` for the current production procedure.

See V1_AUDIT.md and V2_IMPLEMENTATION_PLAN.md for findings, scope and deferred work.


## Project tasks and notes

Under `/api/workspaces/{workspace_id}/projects/{project_id}`:

| Method | Suffix | Body / behavior |
|---|---|---|
| GET | `/tasks` | list, limit/offset |
| POST | `/tasks` | `{"title":"Read","description":"Chapter 1","due_date":"2026-10-01"}` |
| PATCH | `/tasks/{task_id}` | any title/description/status/due_date fields; null due_date clears it |
| GET | `/notes` | owner's project notes, limit/offset |
| PUT | `/notes/{note_id}` | attach own existing note; can move it from another own project |
| DELETE | `/notes/{note_id}` | unlink from this project; does not delete note |

Local tasks use `todo`, `doing`, `done`; remain separate from existing Google Tasks. Notes created with V1 start unassigned. All operations validate the workspace/project chain and session owner. New routes are available in `/docs`; the project UI is available at `/projects`.

OAuth login now uses expiring, single-use server-side state and a browser-binding cookie. Run one Uvicorn worker for now; a process restart discards pending login attempts. No new secret or Redis dependency is needed.

## Current behavior and limits (2026-09-16)

- Calendar add/update validates dates and uses APP_TIMEZONE (Asia/Taipei by default). All-day end dates are exclusive; choose the next day for a one-day event. Failed saves keep the form open.
- Drive delete moves files to Google Drive trash; restore them in Google Drive. Uploads are limited to 20 MB.
- Quiz JSON import: at most 20 MB, 1000 questions, 20 options per question; content validation occurs before writes.
- Notes/Keep and now Calendar/Drive use safe DOM rendering for dynamic content. Other legacy modules still need the remaining fixes listed in PAGE_ARCHITECTURE_REVIEW.md.
- Core JSON export is not a full backup and does not include cloud file bytes or all legacy modules.
- Shared styling: theme.css (palette), components.css (controls), dashboard.css (shell), feature CSS (layout).

## Documentation map

- README.md: current setup and operating instructions.
- V2_IMPLEMENTATION_PLAN.md: current state, ordered backlog, dated historical work.
- PAGE_ARCHITECTURE_REVIEW.md: page/API/model mapping and findings, with current resolution status.
- V1_AUDIT.md / GEMINI.md: historical baselines; not authoritative current feature lists.

## Daily workflow and preflight

- Open `/projects` → quick-add a task to a project/course. Today shows exact totals and loads additional pages.
- Project and trash views retain their URL on refresh and browser Back/Forward.
- `python main.py` checks schema before launching. When starting Uvicorn directly, first run `.\.venv\Scripts\python.exe check_database.py` and stop if it fails. This check is read-only and does not run migrations; use the documented backup/migration procedure separately.
- CI configuration is in `.github/workflows/checks.yml`; it has not yet run remotely.
- Product milestones, acceptance criteria and executed scope: PRODUCT_PLAN.md.


## 2026-09-17 修復更新

本次實測發現的 Tasks/Money/Music HTML 注入、Tasks 500 清草稿、undefined 欄位已修復；Music 返回歌單已補、未完成的歌單寫入按鈕已明確停用。新增 serve.py、health/live、health/ready、Docker preflight 及瀏覽器 CI 回歸。詳細驗證與限制見 FIXES_2026_09_17.md。正式啟動使用 `python serve.py`，先依既有步驟備份及完成 migration；不能當作已完成公網部署。
