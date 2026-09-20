# Sprint 3 Daily-use gate

2026-09-20；未進入 Sprint 4。

## Browser E2E

新增 tests/browser_core.py：headless Chromium + 真實 Uvicorn + 隔離 SQLite；測試 identity 使用 guest，禁止外站请求，不使用正式資料。Home → /projects → 新 Workspace → 新 Project → 新 Task → 完成 Task → 新 Note/閱讀 → archive/restore（內容仍在）→ reload URL 保留 Project → keyword search → logout 後 API 401，通過。

Google Login 並未在此 runner 自動化：Sprint 2 使用者已確認公開 HTTPS 登入成功，並有真實 refresh/provider 唯讀證據。不能將 guest E2E 宣稱 Google 全鏈自動測試。專案頁缺獨立 logout 入口，現行需回 Home；runner 用既有 logout route。Workspace switching、form failure、跨帳號由現有 API tests 覆蓋部分，尚未全部 browser E2E；mobile UI 本輪未重驗。

## Daily-use checklist

- [x] Home 可進入，Project UI 可新增/閱讀 Task/Note。
- [x] Task 可完成，archive/restore 不刪內容。
- [x] reload 保留 Project，Search 可找核心資料。
- [x] Today 有到期/未排程與未完成任務分組（既有 API regression）。
- [x] Workspace selector 與 Project sidebar 存在；管理動作保留 owner checks。
- [x] 登出後 session invalidated。
- [x] 正式 DB 備份/隔離還原；另有 populated row preservation test。
- [ ] Browser form error / 全部 empty states / multi-user / mobile 全流程尚未完全驗證。
- [ ] 異機加密備份與正式 restore cutover 尚未演練。
- [ ] Firebase 附件不可作為可靠 daily storage。

## Firebase decoupling

Firebase 是 Optional Attachment / Storage Integration。init_firebase 在未配置、檔案缺失/格式錯誤時不阻擋 Core；不再印出誤導的成功可用訊息。SDK 匯入仍是已安裝 dependency，本次不拆套件。Note/Keep 附件與下載失敗仍由路由固定錯誤處理，純文字 Notes/Core 繼續可用。新增 malformed key regression，Home/Workspace/Today/Search 通過。

## Security / data safety

Git tracked secrets 查詢未發現金鑰/DB，只有 .env.example；.gitignore/.dockerignore 包含 DB、.local、OAuth JSON exclusions。備份含 session secrets 必須 private，不稱無敏感內容。發現 Tasks/Calendar/Drive/Music 部分 provider errors 回傳 str(e)，本輪改固定錯誤文字。owner/archive preservation tests 保持通過；Workspace delete 只空白可刪，Project 只有可逆封存。

## Change list

services/firebase_service.py；routers/tasks.py、calendar.py、drive.py、music.py；scripts/backup_restore.py；tests/test_storage_optional.py、test_backup_restore.py、browser_core.py；docs/BACKUP_RESTORE.md、DAILY_USE_CHECKLIST.md、V2_ARCHITECTURE.md、ROADMAP.md。

無 schema/dependency change，revision 仍 0004；未 migration 或寫正式 domain 資料，未 commit/push。警告政策沿用 Sprint 2，本轮不清時間棄用警告。

## Readiness decision

有條件可開始單人、少量、可重建的文字型日常資料（Project/Task/Note）。尚未達成「唯一副本、不可遺失資料」或多人正式 production 的可靠度。附件不可用、同機備份、public access limits、完整 browser auth/form/mobile gaps 仍需處理。

Sprint 4 建議：異機加密備份與 restore cutover、完整 browser failure/multi-user coverage、附件 unavailable UX。沒有自行啟動。

## Final tests

59 passed / 304 warnings；原 57 tests 保持通過。Browser core runner exit 0。警告增加來自新增流程，未新增 schema。
