# FocusFlow 介面實測與常駐部署評估

日期：2026-09-17。結論：可繼續本機試用，目前不建議直接開放公網。先修已重現的安全／儲存失敗問題，再進入受限存取的 staging。

## 測試方法與界線

- 重新執行隔離 DB pytest：49 passed，263 warnings。不是只引用前次結果。
- Playwright：九個 Dashboard 面板 × 桌面 1440px／手機 390px，共 18 組切換與面板寬度檢查；均能顯示，面板外框未測到橫向溢出。未窮舉每個子容器、彈窗與有資料排版。
- 瀏覽器所有 /api 請求被 mock，外部 CDN 封鎖；不使用真實登入、不建立／刪除使用者雲端資料。圖示、YouTube 播放及實際網路不可據此判定正常。
- 另重跑工作空間 mock 流程及 Calendar/Drive 安全渲染／失敗保留表單測試。
- 輸入測試只在測試頁面執行 harmless 計數器，未送至後端或其他使用者。
- 測試腳本在本次 Codex workspace 的 work/audit_interfaces.py、daily_browser.py、priority_browser.py；原始結果保存 interface-test-results.json。

## 逐介面結果

| 介面 | 實際驗證 | 發現／仍需驗證 |
|---|---|---|
| 首頁／帳號 | 頁面及訪客 API 回歸通過，切入九面板 | 真實 OAuth 只有先前使用者確認，本次未重跑；未驗證正式網域 callback |
| Today／工作空間 | mock 快速新增任務、刷新／上一頁、精確計數與 101 筆 API 分頁／owner 隔離通過 | 需真實連續使用與跨裝置同時修改測試 |
| 專案／課程 | Task lifecycle、Note 關聯與隔離 API 測試通過；專案 URL 還原通過 | File/Event 尚未建立；本次未逐一操作所有編輯彈窗 |
| 搜尋／匯出 | 本次原始碼檢視，未新增行為測試 | 搜尋上限、匯出不完整備份；列入補測 |
| 回收桶 | mock 導覽、刷新通過 | 本次未實測完整刪除→還原 UI |
| Notes | 隔離 DB 新增／讀取與關聯測試；面板切換 | Firebase 真實上傳、完整編輯／還原 UI 仍待驗證 |
| Drive | mock 動態檔名安全、危險 URL 禁用；API mock 回收桶／超限清理通過 | 未驗證真實雲端讀寫；只取 50 筆、查詢跳脫仍待改善 |
| Calendar | mock 行程安全渲染、502 後保留表單；API patch／日期驗證通過 | 尚未驗證真實新增／改時間、全天與跨月完整顯示 |
| Google Tasks | 模擬一筆任務與 POST 500 | 確認 HTML 注入、建立時間顯示 undefined、500 後草稿被清空 |
| Money | 隔離 DB 交易／統計 smoke；動態交易文字測試 | 確認 HTML 注入；CSV 正確跳脫／公式字串需補測，Float 金額仍待設計 |
| Keep | 隔離 DB 文字寫入／歷史 smoke；面板切換 | Redis 跨裝置、Firebase、QR code 連線未實際驗證 |
| Music | 面板切換、函式存在性檢查、標題輸入測試 | 確認 HTML 注入；8 個 inline handler 缺函式；未測真實播放 |
| Quiz | 隔離 DB 題庫建立、匯入拒絕且無部分寫入；面板切換 | 完整考試／錯題／歷史 UI 仍需端到端案例 |
| Settings | mock 帳號／空間頁面切換 | 真實通知及通知拒絕流程未測；清快取會清掉所有 localStorage 設定 |

## 已重現問題：部署阻擋項目

### P1：Tasks／Money／Music 動態 HTML 可執行事件

將含 img/onerror 的文字送入各自 renderer，產生了真正的 img 節點；頁面計數器總計增加 4 次（Tasks 1、Money item/note 2、Music 1）。這是 renderer 層的瀏覽器重現，不代表已測所有後端輸入路徑或跨使用者攻擊。

修正：用 textContent/DOM API 與事件綁定；新增輸入回歸測試。此三項通過前不開放公網。

### P1：Google Tasks 儲存失敗仍清空草稿

mock `/api/tasks/add` 回 500；輸入 `Draft must stay` 後執行提交，欄位變空。應檢查 response.ok、顯示錯誤、保留內容並防重複送出。

### P2：Music 八個按鈕 handler 不存在

openAddToPlaylistModal、openCreatePlaylistModal、closePlaylist、closeCreatePlaylistModal、submitCreatePlaylist、closeAddToPlaylistModal、closeRemoveSongModal、closeDeletePlaylistModal。

應補完整 API／前端流程，或暫時停用且標明未提供，不能讓按鈕看似可用。

### P2：Google Tasks 資料契約失配

實際 renderer 可見 `建立: undefined`。日期處理亦需統一；先以後端確實提供的欄位顯示，不憑空補建立時間。

## 常駐網站決策

### 建議拓撲

HTTPS 網域 → 單一 Uvicorn worker（無 reload）→ SQLite 持久化磁碟；Google/Firebase 為外部服務；備份存另一位置。Redis 只在確實需要 Keep 即時廣播時配置。

目前 OAuth pending state 在單程序記憶體，不能直接加 workers 或多副本；SQLite 先採單機持久化，不必為了常駐立刻換 PostgreSQL。

### 方案比較

| 方案 | 適合程度 | 責任與限制 |
|---|---|---|
| Render 付費 Web Service + Persistent Disk | 想少維運時優先評估 | 必須配置磁碟及 DB 絕對路徑；附磁碟部署不是零停機，需規劃維護窗口與備份 |
| 自管 Linux VPS + HTTPS proxy + systemd/Docker restart policy | 想學維運與掌握環境 | 自己管理更新、防火牆、TLS、程序重啟與備份；先做 staging 與復原演練 |
| 家用電腦／NAS | 可作私人試用 | 睡眠、斷電、網路與開機啟動會影響可用性；不要以開著開發終端視為可靠常駐 |
| Render Free + 本機 SQLite | 不適合目前正式資料 | 閒置會休眠，沒有可掛載的 persistent disk；重啟／部署等可失去本機變更 |

Render 官方說明：免費服務 15 分鐘無流量會休眠，且無持久化磁碟；付費服務可掛磁碟。來源：[Free](https://render.com/docs/free)、[Persistent Disks](https://render.com/docs/disks)、[Deploys](https://render.com/docs/deploys)。查核日期 2026-09-17，未查價或選定方案。
Uvicorn 的 reload 用於開發；正式啟動另配置監督重啟，參考 [Deployment](https://www.uvicorn.org/deployment/)。

### 上線前必須落地

1. 修正上述 P1；停用未完成按鈕；加瀏覽器回歸測試到 CI。
2. 選定存取對象：自己使用先做 allowlist／受限入口；目前訪客入口可建立資料，未看到完整流量／儲存配額控制。
3. `DATABASE_URL=sqlite:////data/focusflow.db`，同磁碟保留 migration backup；另做異地備份及還原演練。只在同磁碟備份無法防磁碟故障。
4. secrets 由平台秘密檔／環境提供，勿 commit；正式 Google redirect URI 完全匹配 HTTPS 網域。
5. `COOKIE_SECURE=true`；驗證 reverse proxy 的 scheme/host 與目前 Origin 檢查相容，避免正式站所有 POST 被誤拒絕。只信任實際代理來源。
6. 正式啟動前執行 check_database.py；Dockerfile 目前直接啟動 uvicorn，會繞過 main.py 的 CLI preflight。migration 應先備份、單獨執行，不用多副本同時升級。
7. 新增 health/readiness、異常日誌與磁碟告警、程序失敗自動重啟；目前尚無專用 health endpoint。
8. staging 驗證：部署／重啟後資料還在，OAuth 成功，CRUD／上傳／下載／WebSocket 正常，備份可恢復。
9. 最後才開放預定使用者。此次沒有部署、開帳號、付費、設定排程或修改 production。

## 建議下一輪

先做安全 renderer + Tasks 儲存失敗保留 + Music 未完成按鈕處置；再完成部署啟動腳本、readiness 與備份還原測試。其後選擇 Render 付費磁碟或 VPS，依預算與願意承擔的維運工作決定。


## 2026-09-17 修復更新

本次實測發現的 Tasks/Money/Music HTML 注入、Tasks 500 清草稿、undefined 欄位已修復；Music 返回歌單已補、未完成的歌單寫入按鈕已明確停用。新增 serve.py、health/live、health/ready、Docker preflight 及瀏覽器 CI 回歸。詳細驗證與限制見 FIXES_2026_09_17.md。正式啟動使用 `python serve.py`，先依既有步驟備份及完成 migration；不能當作已完成公網部署。
