# 2026-11-15 全站介面一致性檢查

## 已補齊

- 帳號與資料、服務連線頁：移除獨立寫死的深綠色主題，改用全站 theme.css/theme.js，保留使用者深淺色偏好；頁首／對話框／表單／提示均改用共用色彩。
- 帳號頁舊 F· 標誌改成新版 Logo，補齊瀏覽器與 Apple 圖示。
- 帳號頁及各 App header 使用共享右上角帳號選單；重用原本 header placeholder，避免出現兩組入口。
- Drive、Settings、Money 的部分寫死灰色改用共用主題；設定頁匿名頭像改用站內 Logo。
- 更新受影響靜態資源版本。

## 覆蓋與驗證範圍

已檢視 Home、Workspace / Today / Project、Account / Connections，以及 Music、Drive、Notes、Calendar、Tasks、Money、Keep、Settings、Quiz、Modules 共 10 個 App 的桌面／手機外觀。各 App 390/1440px 頁面無 document 橫向溢出；帳號頁沿用 320/390/768/1440px 檢查。帳號頁驗證深淺色偏好、Logo 來源及帳號選單。

python tests/browser_core.py 通過，使用隔離 SQLite 與 guest identity，涵蓋既有任務／筆記／連結、模組、帳號對話框與新介面回歸。

雲端 App 因訪客授權限制僅在測試頁檢視其現有 DOM 版面，未繞過伺服器授權、未連接正式 Google/iCloud，不能視為外部整合端對端驗證。截圖阻擋外站，CDN 圖示可能未顯示；沒有刪除實際圖示。正確／錯誤與記帳分類的語意顏色保留。
