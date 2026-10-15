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

---

## 2026-10 Production Update

Sprint 3 時本文件只涵蓋 repository 內的 manual backup / restore drill。

截至 2026-10-05，
HomeCloud 已新增實際 production backup chain：

- Ubuntu 每日 03:00 使用 systemd timer 建立 SQLite backup。
- Backup 使用 SQLite Backup API。
- Backup 完成後執行 `PRAGMA quick_check` 與 table count 驗證。
- HomeCloud 端保留 14 天。
- Windows host 每日 03:15 透過 Tailscale SSH / SCP 取得最新 backup。
- Windows 端保留 30 天。
- 已執行隔離 restore drill，驗證 quick_check、tables 與 application schema preflight。

目前 Windows copy 屬於 VM-external second copy，
不是 encrypted geographic off-site backup。

Production backup 操作、排程與 monitoring 詳情請參考：

- `docs/HOMECLOUD_OPERATIONS.md`
- `docs/HOMECLOUD_DEPLOYMENT.md`

原本 Sprint 3 的 manual backup / restore 流程仍保留，
作為開發環境與 isolated restore drill 的參考。


## Verified maintenance update — 2026-10-15

The host timer still invokes `/home/wensheng/scripts/backup-focusflow.sh`, now sourced from repository `scripts/backup-focusflow.sh`. It uses a lock, private staging directory and mode 0600 files; it calls the existing SQLite snapshot/verify tool and only publishes a final filename after integrity, FK and revision validation. Publication refuses an existing destination. Failure removes staging output. No scheduled retention deletion is performed by this revised wrapper; old snapshots are currently tiny and retained pending an explicit retention review.

One pre-existing zero-byte snapshot dated 2026-10-15 was found. The historical journal reported success without sufficient detail to establish why it was empty. The invalid file was retained; selectors and monitoring now ignore invalid snapshots. Windows helper `scripts/backup-homecloud.ps1` selects a verified remote snapshot, checks SSH/SCP exit codes, downloads to a unique partial file, checks SQLite and SHA256, and only then moves it to a final filename. It fails rather than trusting an already-existing invalid copy. Interrupted partial downloads are cleaned up. The script uses the project venv Python and therefore depends on the saved project path.

Manual schedule-equivalent run, failure drill and isolated restore all passed. The restored snapshot matched all 16 SQLite tables; domain counts: Workspace=2, Project=0, Note=2, Task=0. Empty Project/Task tables are not evidence of real populated production coverage; populated regression tests remain separate. Windows second copy was checked successfully. Neither production DB nor schema was replaced.

Next scheduled execution must still be observed. A Windows copy is not geographic off-site storage or host-disaster protection.


## Module preference revision

The module-management release adds additive revision 0005_module_preferences. The updated verifier accepts known 0004 and 0005 snapshots and checks the new preference schema for 0005. Deploy the updated host backup helper before switching the production DB; old snapshots remain restorable to a separate file. Downgrade with saved preferences is refused to prevent silent preference loss. See [MODULES.md](MODULES.md).
