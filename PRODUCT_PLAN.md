# FocusFlow V2 產品企劃與執行計畫

日期：2026-09-16｜定位：可長期自用、可展示工程能力的 Self-hosted Personal Digital Workspace。

## 一、理想體驗與目前落差

理想的一天：打開 Today → 記下待辦 → 放入專案／課程 → 開啟教材、筆記與行程 → 完成任務 → 回顧成果 → 可備份還原。

| 面向 | 已有 | 尚缺 |
|---|---|---|
| 工作核心 | Workspace/Project/Course、Task、Note、參考連結 | File/Event 正式關聯、課程題庫關聯、收件匣轉任務 |
| 日常操作 | Today、搜尋、專案編輯與封存 | Today 直接新增、完整數量與分頁、刷新／上一頁回到原專案 |
| 一致體驗 | 共用 CSS 與部分 HTTP/DOM helper | 所有舊面板的錯誤、空白、載入、手機及彈窗行為一致 |
| 信任與安全 | 權限測試、OAuth state、備份 migration、部分安全渲染 | Tasks/Money/Music 安全渲染、外部分頁、schema preflight、還原演練 |
| 工程展示 | 本機回歸測試與架構文件 | CI、可重現部署、固定示範資料、驗證過的操作影片／案例 |

不能用單一完成百分比代表成熟度；登入成功與測試通過不代表所有外部整合均可靠。

## 二、目標與範圍

- 首要使用者：本人日常學習、專案與生活管理；課程以 Project.kind=course 承載。
- 保留 FastAPI/Jinja2/SQLite/SQLAlchemy，採小批次交付；不重寫整站、不新增 AI/Redis 服務、不急著換資料庫。
- 支援工具 Money/Music 保持獨立，Google Tasks 與本機任務先明確分開。
- 使用可驗證的行為決定完成，而非單純頁面或功能數量。

## 三、本輪執行包：每天打開就能用

1. Today 可直接選專案建立任務，名稱／描述／到期日沿用現有驗證；無專案時引導先建立。
2. Today 每類回傳精確總數與分頁狀態；超過 100 筆可載入下一頁，避免內容被截斷。
3. 工作空間支援 URL query 狀態：專案／回收桶／Today；刷新與上一頁可回復。URL 不是授權依據，資料仍由 API 做 owner 驗證。
4. 唯讀 schema 檢查：migration head 與必要表／欄位不符，明確提示先備份並執行 migrate_db.py；不自動修改資料庫。
5. 加入 CI 設定：Python 3.11/3.12 回歸測試及 JS 語法檢查。不在 CI 放私人憑證；工作流程要 push 到遠端後才會實際運行。

## 四、後續里程碑與驗收

### M1 安全與資料可靠性（最高優先；本輪僅交付 preflight）
- Tasks/Money/Music 改安全 DOM；測試含 HTML／引號內容仍只顯示文字。
- HTTP 失敗不能假裝成功、不能清草稿；Google 列表分頁與日期契約補齊。
- 備份還原至新路徑，逐表核對後才切換；Money 精度改動先做副本驗證。
- 不在這些缺口完成前宣稱可公開多人部署。

### M2 日常工作流程（本輪主要交付）
- Today → 新增 → 專案 → 完成 → Today 數量更新。
- 瀏覽器刷新／上一頁保留定位；過期／其他帳號專案顯示可理解錯誤。
- 下一批：Keep 收件匣轉任務／筆記、可恢復草稿與搜尋分頁。

### M3 課程與資料關聯
- FileRef/EventRef 僅存來源與外部 ID；權限撤銷或外部刪除能顯示失效。
- QuizBank 選擇性掛課程；保留舊資料及原頁面。
- 驗收：同一課程能找到任務、筆記、教材與題庫；不預設雙向同步。

### M4 自架與作品集交付
- CI 實際運行、Docker 持久化及還原演練、範例資料不含私人內容。
- README、ERD、架構決策、已知限制、版本交付清單一致。
- 展示一個完整課程使用案例，以及測試／遷移／權限等工程取捨。

## 五、追蹤方式

- 每批列出實際檔案、測試結果與未驗證外部服務；不以「已寫程式」當作「已可用」。
- 每日使用一週後紀錄：哪些步驟需返回舊 Dashboard、儲存失敗次數、找不到內容的情境；本次沒有蒐集個人行為或新增遙測。
- 成功標準：可完成上述日常流程、沒有無聲儲存失敗、可回復資料、核心畫面在手機與桌面均能操作。

## 六、風險與控制

- 本機開發 reload 可能先載入半完成修改：避免本輪 schema 變更，對未來遷移先驗證副本再套用。
- 外部 API／授權／配額失敗：隔離測試與真實驗證分開，不因 mock 通過就宣稱連線成功。
- 範圍擴張：M3/M4 依驗收逐批交付，非本輪全部完成；現有安全待辦不因新增體驗功能而關閉。

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
