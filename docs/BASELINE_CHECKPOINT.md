# V2 development baseline checkpoint

三個提交前 blocker 已修復：SQLite backup/verify connection 使用 closing，失敗 revision 不殘留目的檔（含 Windows regression）；CI 加入獨立 DB、動態 port、禁用外站的 browser_core；Quiz EOF whitespace 清理。

Windows browser runner 另外修正 venv 子程序結束：關閉整個測試程序樹，避免 server.log 持續被鎖。Linux 使用 terminate/wait。不透過忽略 cleanup error 掩蓋問題。

驗證：61 pytest passed / 304 warnings；browser_core exit 0；browser_security 的 desktop/mobile、injection 與錯誤保留輸入 checks 通過；全部 JS syntax、pip check、正式 DB read-only preflight、git diff --check 通過。遠端 GitHub Actions 未觸發（沒有 push）；不是宣稱 Linux matrix 已遠端執行。

原有累積修改包含 Sprint 之前內容。按依賴合併為設定、資料層、應用整合、備份、測試部署、文件六組，不偽造逐 Sprint 的歷史。沒有變更正式 DB schema、secret、外部服務，也未開始 Sprint 4。

候選檔案與每次 staged blob 均檢查敏感路徑/常見 key 格式/本機實際 key 比對；無命中。這不是保證任意編碼密鑰都能偵測，也不是完整 Git 歷史內容稽核。Ignored 本機 DB/secret/backups 仍保留，不是待提交項目。

建議 checkpoint 名稱 v0.2.0-baseline；需另行確認才建立 tag。本輪只建立 local commits，不 push。
