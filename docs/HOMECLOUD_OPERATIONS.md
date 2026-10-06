# HomeCloud Operations

更新日期：2026-10-05

本文件記錄 FocusFlow 在 HomeCloud 上的日常維運方式。

目標是提供：

- 服務狀態確認
- Backup 狀態確認
- Monitoring / Alert 檢查
- 基本故障排查
- 不涉及 secrets 的操作紀錄

## 1. Daily Service Check

進入 application directory：

`cd /home/wensheng/services/focusflow`

查看 containers：

`docker compose ps`

正常情況應看到：

- `focusflow` healthy
- `focusflow-redis` healthy

直接檢查 FocusFlow readiness：

`curl -fsS http://127.0.0.1:8000/health/ready`

經 nginx 檢查：

`curl -fsS http://127.0.0.1/health/ready`

查看 nginx：

`systemctl status nginx --no-pager`

查看 Tailscale daemon：

`systemctl status tailscaled --no-pager`

## 2. Logs

FocusFlow logs：

`docker compose logs --tail=100 focusflow`

Redis logs：

`docker compose logs --tail=100 redis`

需要持續追蹤：

`docker compose logs -f focusflow`

HomeCloud health monitoring log：

`journalctl -u homecloud-health.service -n 100 --no-pager`

Backup log：

`journalctl -u focusflow-backup.service -n 100 --no-pager`

## 3. SQLite Backup

HomeCloud 本機備份腳本：

`/home/wensheng/scripts/backup-focusflow.sh`

備份目的地：

`/home/wensheng/backups/focusflow`

檔名格式：

`focusflow-YYYYMMDD-HHMMSS.db`

備份流程使用 SQLite Backup API，
不直接複製執行中的 SQLite database 檔案。

建立備份後會執行 integrity verification，
包含：

- `PRAGMA quick_check`
- table count 檢查

只有驗證成功的 backup 才視為有效。

HomeCloud 端保留最近 14 天的 FocusFlow backups。

## 4. Backup Schedule

Ubuntu 使用 systemd timer：

`focusflow-backup.timer`

排程：

每天 03:00

查看 timer：

`systemctl status focusflow-backup.timer --no-pager`

查看下一次執行時間：

`systemctl list-timers focusflow-backup.timer --no-pager`

查看最近一次 backup service：

`systemctl status focusflow-backup.service --no-pager`

Backup service 為 `Type=oneshot`，
成功執行完成後顯示 `inactive (dead)` 屬正常狀態。

Timer 使用 `Persistent=true`。

如果 HomeCloud 在排定時間關機，
VM 下次啟動後 systemd 會補跑 missed backup。

## 5. Windows VM-External Backup

HomeCloud backup 完成後，
Windows host 會建立第二份 SQLite backup copy。

Windows backup directory：

`C:\Users\urua0\HomeCloud-Backups`

PowerShell script：

`C:\Users\urua0\HomeCloud-Backups\backup-homecloud.ps1`

Dedicated SSH key：

`C:\Users\urua0\.ssh\homecloud_backup`

Private key 不得提交 Git、貼入文件或分享。

Windows 透過 Tailscale SSH 至 HomeCloud，
取得最新：

`/home/wensheng/backups/focusflow/focusflow-*.db`

Windows 端保留 FocusFlow backups 30 天。

這份 Windows copy 屬於 VM-external second copy，
可以降低 VMware virtual disk 故障造成資料全失的風險。

它不是 geographic off-site backup，
也不能抵抗 Windows host / SSD 同時故障。

## 6. Windows Backup Schedule

Windows Task Scheduler 工作名稱：

`HomeCloud FocusFlow Offsite Backup`

排程：

每天 03:15

正常流程：

03:00
→ HomeCloud 建立 SQLite backup

03:15
→ Windows 透過 SSH / SCP 取得最新 backup

Task Scheduler 已設定：

- missed schedule 後儘快執行
- failure 後每 10 分鐘重試
- 最多重試 6 次

目前 task 使用互動式 Windows user session。

因此不能視為「使用者完全未登入時也保證執行」。

Laptop battery / Windows power condition
也可能影響 scheduled task 是否啟動。

## 7. Health Monitoring

HomeCloud health check script：

`/home/wensheng/scripts/health-check.sh`

systemd timer：

`homecloud-health.timer`

排程：

每小時執行一次。

查看 timer：

`systemctl status homecloud-health.timer --no-pager`

查看最近一次 health check：

`systemctl status homecloud-health.service --no-pager`

查看 health check journal：

`journalctl -u homecloud-health.service -n 100 --no-pager`

Health check 目前檢查：

- Root filesystem disk usage
- Docker daemon
- `focusflow` container health
- `focusflow-redis` container health
- FocusFlow localhost readiness
- nginx proxy readiness
- tailscaled service
- FocusFlow backup freshness

目前不代表已驗證：

- 外部 Internet 可達性
- Tailscale HTTPS endpoint 的完整 end-to-end availability
- Windows backup task 狀態

## 8. Health Thresholds

Disk usage：

- `< 75%`：正常
- `75% - 84%`：WARNING
- `>= 85%`：CRITICAL

Backup freshness：

- `< 36 hours`：正常
- `36 - 72 hours`：WARNING
- `> 72 hours`：CRITICAL
- backup 不存在：CRITICAL

Health script exit code：

- `0`：OK
- `1`：WARNING
- `2`：CRITICAL

## 9. Discord Alert

Health check 發現 WARNING 或 CRITICAL 時，
會透過 Discord webhook 發送 alert。

Webhook secret 儲存在：

`/etc/homecloud-health.env`

該檔案應保持私密，
不得提交 Git 或寫入文件。

Alert 內容目前會包含：

- WARNING / CRITICAL level
- 實際問題原因
- Hostname
- Timestamp
- Health check exit code
- journalctl 查詢提示

目前 alert 沒有 deduplication。

如果問題持續存在，
每次 hourly health check 都可能再次發送 alert。

目前也沒有獨立 recovery notification。

## 10. Basic Troubleshooting Order

HomeCloud 發生異常時，
建議依序檢查：

1. 確認 VMware VM 是否已啟動。
2. 確認 HomeCloud 可 SSH 登入。
3. 檢查 Docker / nginx / tailscaled。
4. 執行 `docker compose ps`。
5. 檢查 `/health/ready`。
6. 查看 FocusFlow logs。
7. 查看 nginx logs / service status。
8. 查看 `homecloud-health.service` journal。
9. 檢查最近一次 backup。
10. 再進行 restart 或 rebuild。

不要一開始就：

- 刪除 container volume
- 刪除正式 SQLite database
- 執行 Docker system prune -a
- 手動修改 DB revision
- 重建 VM

除非已確認問題來源並存在可用 backup。

## 11. Restart Guidance

一般 application restart：

`cd /home/wensheng/services/focusflow`

`docker compose restart focusflow`

若 Docker networking 發生異常，
可先確認服務與 logs，
必要時再考慮：

`sudo systemctl restart docker`

Docker daemon restart 會影響同一 host 上所有 containers，
未來 HomeCloud 承載更多服務後，
必須先評估影響範圍。

## 12. Operations Boundary

目前 HomeCloud 維運策略：

- 基礎設施保持簡單
- 有實際需求才增加新服務
- 有問題才修改 production foundation
- 不為了 Homelab 本身無限增加工具

Step 8A 完成後，
HomeCloud 進入 Infrastructure Freeze / Maintenance Mode。

下一階段開發主線回到 FocusFlow Step 4 Daily Driver。
