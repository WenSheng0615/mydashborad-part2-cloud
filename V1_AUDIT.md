# FocusFlow V1 audit — 2026-09-15

> 歷史基線：以下描述 2026-09-15 起始盤點，並非目前狀態。最新狀態見 V2_IMPLEMENTATION_PLAN.md；逐頁問題見 PAGE_ARCHITECTURE_REVIEW.md。OAuth、models、migration、部分上傳與安全渲染後來已修復。

## 實際基線

- 本機：Desktop/mydashborad-part2-cloud；master 領先 origin/master 1 commit。
- 開始時已有 17 個 tracked 修改與 2 個 untracked 檔案（Google auth service、quiz.js）；本輪保留原內容與 Git 歷史，不自動 commit。
- FastAPI 0.122、Jinja2 3.1.6、SQLAlchemy 2.0.44、SQLite。9 routers：auth / drive / music / calendar / notes / tasks / money / chat / quiz。
- 原先沒有 Alembic、tests、CI、README、dockerignore。database.py 定義 11 models，import 時 create_all 及 ALTER；migrate_db.py 以 cwd 尋找 DB 手動加 notes.image_url。
- services：money 統計、Firebase 上傳、尚未追蹤的 Google token refresh/service 建構。大量同步 DB/API 呼叫位於 async routers。
- templates/index.html + 9 partials；static CSS/JS、manifest、service worker。主頁外部依賴 Font Awesome CDN / YouTube iframe API；未做完整瀏覽器視覺 QA。

## 功能及驗證範圍

| 模組 | 實作現況 | 驗證界線 |
|---|---|---|
| Auth | Google OAuth、訪客、session 到期、訪客合併、裝置連結 | 可做本機訪客與 session 測試；真實 Google OAuth 未驗證 |
| Notes | SQLite 新增/列出/刪除，圖片 Firebase | 本機文字流程可驗證；原刪除缺 owner 驗證，本輪修正 |
| Money | SQLite 記帳、分類、預算與統計 | 本機流程可驗證；Float 金額及分類名稱關聯是技術債 |
| Quiz | 自訂題库、匯入、練習、測驗、歷史 | 本機流程可驗證；尚無 Project/Course 關聯 |
| Keep/chat | SQLite 儲存文字、連結、檔案；Redis 廣播 | CRUD 不依賴 Redis；即時同步與 Firebase 上傳未連線驗證 |
| Tasks | Google Tasks API，notes 標記模擬 doing | 沒有本機 Task model；Google 外部操作未驗證 |
| Drive | Google Drive 列出/上傳/刪除/移動 | 外部操作未驗證；查詢字串跳脫與分頁待改善 |
| Calendar | Google Calendar 列出/新增/刪除 | 外部操作未驗證；月份 UTC 與 Taipei 邊界待改善 |
| Music | YouTube API、yt-dlp、SQLite 播放歷史 | 外部播放未驗證；匿名 stream endpoint 缺配額保護 |

## 資料盤點（唯讀；不輸出帳號、token 或內容）

11 張表：sessions 6、notes 0、transactions 0、categories 0、keep_items 0、music_history 42、exam_sessions 11、exam_answers 122、quiz_banks 2、quiz_questions 468、quiz_options 1872。
現有 image_url / tag / expires_at 均已存在；無 alembic_version。舊模型多以 user_email 隔離，既有 quiz 關聯未宣告 FK。不得直接重建/清空 DB。

## 環境、secrets 與部署

- 本機存在 .env、OAuth credentials、Firebase key、SQLite session token；只查看設定鍵名與 schema/count，未輸出值。
- 當前 Git tracked 路徑不含真實 .env、DB、credentials；.env.example 已做本機私鑰/OAuth token/JSON credential 格式掃描，未命中。不是完整 Git 歷史 secret audit。
- main.py 原先在 routers import 後才 load_dotenv，導致 auth / Redis 提前讀取錯誤設定；本輪提前載入。
- Dockerfile 使用 Python 3.11-slim、ffmpeg，還裝了未使用的 MySQL build dependencies；沒有 compose/volume/healthcheck。COPY . . 原先可能將本機 secrets/DB 打入 image；本輪加 .dockerignore。
- Redis 已在舊版使用，本輪不新增 Redis 依賴。原初始化 log 會打印可能含密碼的 URL，本輪去除。
- 啟動會依環境內容寫出 credentials 檔；只在隔離、停用 dotenv/清空 credential env 的 smoke test 執行。

## 優先技術債

1. 本輪：移除隱式 DDL、導入可備份驗證的 migration、拆 models、Notes 刪除 owner 檢查。
2. 下一輪：OAuth state 儲存/驗證（目前產生後未比對）、舊 routes session 清理及例外 rollback、上傳容量/名稱驗證、前端 innerHTML 的輸出跳脫逐一稽核。
3. 後續：Google 分頁/錯誤契約、money 精度/分類識別、quiz FK、同步 I/O、離線資源與部署持久化。

最終可執行測試結果見 V2_IMPLEMENTATION_PLAN.md；外部授權服務、真實音樂播放、Docker build 不列為已通過。


第二批更新：OAuth state 已補驗證；Task/Note Project 關聯已實作，實際 DB 升級到 0003。上傳與前端 escaping 仍列後續。詳見 V2_IMPLEMENTATION_PLAN.md。
