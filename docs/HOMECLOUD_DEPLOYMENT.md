# HomeCloud Deployment

更新日期：2026-10-05

本文件記錄 FocusFlow V2 實際運作中的 HomeCloud Production Foundation。

目前定位為私人 self-hosted environment，
透過 Tailscale tailnet 提供 HTTPS 存取，
不是公開 Internet production service。

## 1. Architecture

目前請求路徑：

Client
→ Tailscale
→ https://homecloud.tailea7aa9.ts.net
→ Tailscale Serve (HTTPS termination)
→ nginx :80
→ 127.0.0.1:8000
→ FocusFlow container

FocusFlow 使用：

- SQLite：`/data/focusflow.db`
- Redis：`redis://redis:6379`

## 2. Host and Runtime

HomeCloud：

- Hostname：`homecloud`
- OS：Ubuntu Server
- Application directory：`/home/wensheng/services/focusflow`
- Deployment branch：`homecloud-deployment`
- Container runtime：Docker + Docker Compose
- Reverse proxy：nginx
- Private networking / HTTPS：Tailscale Serve

## 3. Containers

目前主要 containers：

- `focusflow`
- `focusflow-redis`

FocusFlow application port 僅綁定：

`127.0.0.1:8000`

因此 port 8000 不直接暴露到 LAN。

Redis 不發布 host port，只透過 Docker internal network
供 FocusFlow 使用。

兩個 containers 均設定：

`restart: unless-stopped`

並具有 healthcheck 與 Docker json-file log rotation。

## 4. Persistent Data

正式 SQLite database：

`/home/wensheng/services/focusflow/data/focusflow.db`

Container 內的位置：

`/data/focusflow.db`

Redis 資料使用 Docker named volume 保存。

正式 database、`.env`、OAuth credentials 與其他 secrets
不得提交至 Git。

## 5. Environment and OAuth

Production environment 設定檔：

`/home/wensheng/services/focusflow/.env`

目前重要設定包含：

- SQLite database location
- `Asia/Taipei` timezone
- External HTTPS URL
- Google OAuth callback URL
- Secure cookie
- Redis connection

Secrets、credentials、tokens、webhook URLs 與 private keys
不得寫入本文件或提交 Git。

Google OAuth redirect URI 必須與實際使用的
Tailscale HTTPS callback 完全一致。

Google OAuth credentials 於 runtime 以 read-only bind mount
提供給 FocusFlow container，不寫入 Docker image。

## 6. Reverse Proxy and HTTPS

nginx 在 HomeCloud host 上由 systemd 管理。

目前流量路徑：

Tailscale Serve
→ nginx localhost HTTP
→ FocusFlow `127.0.0.1:8000`

Tailscale Serve 負責私人 tailnet 的 HTTPS 入口，
nginx 負責 reverse proxy 至 FocusFlow。

目前正式私人入口：

`https://homecloud.tailea7aa9.ts.net`

## 7. Health Endpoints

FocusFlow 提供：

- `/health/live`
- `/health/ready`

Production readiness 主要使用：

`/health/ready`

Docker healthcheck、HomeCloud monitoring 與人工檢查
均可使用 readiness endpoint 驗證服務狀態。

## 8. Deployment and Restart

進入 application directory：

`cd /home/wensheng/services/focusflow`

啟動或套用既有設定：

`docker compose up -d`

需要重建 image 時：

`docker compose up -d --build`

查看 container 狀態：

`docker compose ps`

查看 FocusFlow logs：

`docker compose logs --tail=100 focusflow`

不要在未建立正式 DB backup 的情況下執行破壞性 database 操作。

## 9. Database Migration

Migration 必須針對與正式 container 相同的 persistent database 執行。

建議流程：

1. 建立正式 DB backup。
2. 驗證 backup integrity。
3. 確認目前 schema revision。
4. 執行 migration。
5. 驗證 `/health/ready`。
6. 驗證核心功能。

不要以手動修改 revision 的方式掩蓋 schema drift。

## 10. Boot Recovery

HomeCloud guest OS 啟動後：

- Docker service 由 systemd 啟動。
- nginx 由 systemd 啟動。
- tailscaled 由 systemd 啟動。
- FocusFlow / Redis 透過 Docker restart policy 恢復。

目前 VMware VM 本身的自動 power-on
不屬於 guest OS deployment 範圍。

如果 VM 未啟動，HomeCloud 服務仍不可用。

## 11. Security Boundary

目前服務定位：

**Private HomeCloud service**

不是公開 Internet service。

主要存取邊界：

Tailscale authenticated device
→ HomeCloud private HTTPS
→ nginx
→ localhost-only FocusFlow

Application port `8000` 僅綁 localhost。

Redis 僅存在 Docker internal network。

## 12. Verified Production Foundation

截至 2026-10-05 已實際驗證：

- Docker deployment
- Redis integration
- Persistent SQLite
- Google OAuth
- nginx reverse proxy
- Tailscale private HTTPS
- localhost-only application port
- Container restart policy
- Container healthcheck
- Docker log rotation
- Scheduled SQLite backup
- Restore drill
- HomeCloud health monitoring
- Discord warning / critical alert
- Windows VM-external backup copy

## 13. Known Boundaries

目前尚未宣稱：

- Public Internet production hosting
- High availability
- Zero-downtime deployment
- Multi-node failover
- Encrypted geographic off-site backup
- Automatic VMware VM power-on
- Multi-user production readiness

HomeCloud Production Foundation 的目標是提供穩定的
私人 self-hosted environment，
供 FocusFlow 日常使用與後續開發驗證。
