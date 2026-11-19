# 2026-11-19 Google 登入一併連線

使用者要求登入後一併連接 FocusFlow 的 Google 服務，取代過去只登入身分、再逐項授權的流程。

## 新行為

- 一般 Google 登入會一併要求 OpenID/Email/Profile，以及 Calendar、Drive、Tasks、YouTube readonly 四項既有服務權限。未新增其他 Google 產品權限。
- callback 只依 Google 實際 grant metadata 保存連線，不用 requested scopes 推測權限；各服務仍加密保存、與登入 session 分離。
- 四項連線以同一筆資料庫交易保存。缺少 refresh token 時僅沿用同 client、同 owner、已允許該服務的既有 refresh token；不將短期登入誤當作永久連線。
- 只勾選部分權限仍可登入 Core；未授予的服務不偽裝連接成功。
- 已登入帳號發起整合授權時，擷取四項 generation；授權期間若解除連線，舊 callback 不重新啟用該服務。
- 未知 owner 的匿名登入不會復活既有 tombstone；該帳號登入後可透過「一併授權 Google 服務」明確重新連接。
- 已保存的連線跨登出保留，不需要逐項重新授權；個別連接的相容入口仍可使用。

## 連線頁

開啟帳號／服務連線頁，自動平行呼叫四項 Google 唯讀檢查。新增 /api/connections/{provider}/check，與 App 是否顯示分開管理。檢查後再次讀取連線狀態，避免將已解除的服務顯示成成功。

成功顯示「已連線／重新檢查」；暫時網路失敗仍可重試檢查；授權缺少或失效才引導授權。提供「一併授權 Google 服務」給既有權限未齊全的帳號。iCloud 維持獨立設定，本次不自動授權 Apple。

## 驗證及部署

- OAuth／連線49項 targeted tests 通過；完整後端134項通過（638項既有datetime/SDK棄用警告）。
- browser_core：真實隔離SQLite驗證既有流程；Google整合UI以mock驗證自動四項檢查、4/4、暫時失敗3/4與重試、一次授權說明，以及320/390/768/1440px版面。
- 不代替使用者按 Google consent。真實授權需使用者於 Google 畫面確認；未將 mocked 結果稱為正式Google連線成功。
- 無 schema 或依賴變更，使用既有0006；無正式資料重寫／批次授權。

Google 官方依據：https://developers.google.com/identity/protocols/oauth2/web-server 與 https://developers.google.com/identity/protocols/oauth2/resources/granular-permissions 。
