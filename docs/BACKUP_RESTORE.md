# SQLite Backup / Restore

2026-09-20，適用 revision 0004_daily_workspace。工具 scripts/backup_restore.py 不覆寫任何既有目的檔；只使用 SQLite backup API，不直接複製執行中的 DB/WAL。

## Backup procedure

在 repository 執行（目的檔每次使用新名稱）：

```powershell
python scripts/backup_restore.py focusflow.db .local/backups/manual-YYYYMMDD-HHMM.db
```

來源以 mode=ro 開啟。snapshot 可在程式運作時建立一致 DB 快照；維護時間停止寫入更容易比較。失敗目的檔會清除，不修改來源。

## Restore procedure

先還原到新隔離路徑，絕不直接覆蓋正式 DB：

```powershell
python scripts/backup_restore.py .local/backups/manual-YYYYMMDD-HHMM.db .local/restore-drill/new-restored.db
```

驗證後才安排停機，把 DATABASE_URL 指到已驗證檔案，再用 serve.py；保留舊 DB 與設定，失敗時停機切回。正式切換未在本 Sprint 執行。恢復舊快照會撤回快照後寫入，必须事先確認恢復點。

## Verification / 本次 drill

正式 focusflow.db → .local/backups/sprint3-snapshot.db → .local/restore-drill/sprint3-restored.db。兩次 integrity=ok、FK 無違規、revision=0004；Workspace/Project/Note/Task 均為 0（正式目前空資料）。另有 populated 隔離測試，各 1 筆；逐欄比對四表、封存欄/關聯與原內容保留，拒絕覆寫來源。

## Failure scenarios

目的檔存在：停止，改新檔名；來源不存在：不建立空來源；錯 revision、integrity/FK 失敗：不接受備份。磁碟不足/權限錯誤應先修復後重跑。不要手動 stamp 掩蓋 schema drift。revision 將來改變時需同步更新驗證工具。

## Limitations / 敏感資料

DB 備份包含 session token 與私人資料；不是 sanitized export。放 .local 下且 *.db 被 Git/Docker 排除。不可提交或貼出 DB；限制檔案 ACL，另備加密異機副本。此 Sprint 只建立同機副本，不能抵抗硬碟故障/勒索軟體。OAuth JSON/.env 與雲端附件不包含於 DB 備份，須另行安全保管；Firebase 歷史物件無法用 DB 還原。
