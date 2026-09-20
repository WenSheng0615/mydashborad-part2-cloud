# Roadmap & Sprint 1

日期：2026-09-20。以現有 0004 Core 為起點；本次只做 Sprint 1，共五個 Issues。

## S1-01 Repository audit / architecture（完成）
- Goal：建立可信現況與 phase 對照。
- Reason：brief 假設多項尚未實作，但現況已有 Core/Today/Search。
- Files：docs/V1_AUDIT.md、V2_ARCHITECTURE.md、ROADMAP.md、README.md。
- Approach：核對 entrypoint、router/service/model、migration、tests、部署歷史，區分 mocked/真實證據。
- Acceptance：包含差異、未驗證能力、rollback 與後續工作。
- Risk：文件過期；以 dated evidence 更新，不覆寫歷史。

## S1-02 Secret packaging baseline（完成）
- Goal：Docker build context 不帶入下載的 OAuth JSON。
- Reason：Git ignore 不控制 Docker COPY。
- Files：.dockerignore。
- Approach：新增 client_secret_*.json，保留原 exclusions。
- Acceptance：規則覆蓋現有下載檔；不刪除金鑰；Docker build 本次未驗證。
- Risk：未來其他命名金鑰仍需檢查。

## S1-03 Canonical OAuth login diagnostics（完成）
- Goal：避免 localhost 起始、公網 callback 才失敗。
- Reason：nonce cookie 無法跨 hostname；已觀察到 400。
- Files：routers/auth.py、main.py、tests/test_oauth.py。
- Approach：Secure 模式下入口 origin 與 APP_URL 不一致，回 400/oauth_origin_mismatch/login_url；啟動訊息顯示 APP_URL。
- Acceptance：錯誤 origin 不建立 state/不呼叫 provider，正確 HTTPS 繼續；不降低 Cookie/PKCE 安全。
- Risk：reverse proxy 必須正確傳遞 scheme/host；完整使用者授權仍需真實登入。

## S1-04 Core detail reads（完成）
- Goal：補 Workspace/Project 單筆 GET 契約。
- Reason：既有 create/list/rename/archive 並非完整 CRUD，先補最低風險 read。
- Files：routers/workspaces.py、tests/test_core.py。
- Approach：重用 owned_workspace/owned_project，不搬移模型。
- Acceptance：owner 可讀，匿名 401，他人/錯 workspace/不存在 404。
- Risk：不解決 delete/move；不得宣稱完整 CRUD。

## S1-05 Baseline & migration verification（完成）
- Goal：證明小改動不破壞既有 Core。
- Reason：working tree 已有大量累積修改。
- Files：既有 tests、check_database.py、migrations（只執行，不修改）。
- Approach：baseline pytest、targeted pytest、完整 regression、pip check、原 DB 唯讀 schema/integrity/FK 檢查。
- Acceptance：52 baseline → 54 passed；targeted 17 passed；pip check 通過；0004/integrity ok/FK 0。
- Risk：277 deprecation warnings；離線測試不保證雲端整合。

## 下一個建議 Issue（未執行）

Canonical HTTPS 完整登入與 provider readiness：在新 OAuth client 完成使用者授權後測試 Tasks/Drive/Calendar/YouTube；確認 Firebase bucket 或另行決定本機儲存方案。不要把 initialize 成功當作 bucket 可用，也不要擅自開付費服務。

## 後續順序（不屬於本 Sprint）

1. 備份還原演練、Workspace/Project lifecycle 與 public access 邊界。
2. FileRef/EventRef 可選關聯設計及向後相容 migration；不強迫舊資料選 Project。
3. Daily driver 與 Home/App shell 小步改良。
4. 擴充 keyword search；之後才 GitHub。
5. 真實需求出現才 AI/semantic search、Dev/CLI。
6. Production backup/monitoring/CI 逐步驗證；是否換 DB 由需求決定。

## 執行結果與限制

本 Sprint 無 schema migration、無正式資料修改、無依賴新增、未 commit/push。完整 pytest 54 passed / 277 warnings；原 DB 唯讀檢查通過。git diff --check 發現起始既有 templates/partials/quiz.html 尾端空白問題，未為此修改無關檔案。Docker build、遠端 CI、完整 UI E2E/雲端寫入未執行。回退只撤回本 Sprint hunks，不還原整個 dirty tree。


## Sprint 2 更新

見 [Sprint 2 實作與 ADR](SPRINT_2.md)：Workspace 只刪空白項目，Project 保留 archive/restore；Task 選 Local source of truth，Google sync 延後。57 tests passed。


## Sprint 3

Firebase = Optional Attachment / Storage Integration；見 [Daily-use gate](DAILY_USE_CHECKLIST.md) 及 [Backup/Restore](BACKUP_RESTORE.md)。同機快照不等於災難復原。
