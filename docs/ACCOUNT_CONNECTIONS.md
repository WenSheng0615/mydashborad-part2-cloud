# 帳號與服務連線 — 2026-10-20

## 已實作
- `/account`：帳號與資料、服務連線；模組仍使用原本的管理頁。
- 訪客能建立自己的 Workspace / Project / Task / Note；重複進入訪客模式不換身分，新訪客有效期 7 天。清除 Cookie、登出或到期仍可能無法恢復，正式登入後才可跨裝置。
- Google 登入只要求 OpenID、已驗證 Email 與 Profile。Google userinfo 的穩定 subject 對應既有資料 owner key，避免大量搬移舊資料。
- 服務連線另由目前登入身分發起，逐項 Calendar / Drive / Tasks / YouTube 授權。YouTube 僅要求 readonly；其他三項需支援既有寫入功能。
- callback 綁定 nonce、PKCE、發起 session、owner、連線 generation；重播、換身分、缺 scope、未驗證 Email、無 refresh token、不符 subject 皆拒絕。取消回到帳號頁。
- Google scopes 以實際 grant metadata 判斷；Google 合併授權或拒絕部分 scope 時不推測為已授權。第一版逐服務連接，沒有一次勾選多服務的批次流程。
- 帳號 session 與 provider token 分離；provider 失效不登出 Core。連線由 owner 保存，跨裝置共用，登出只刪目前 session。
- iCloud 私密 CalDAV 表單只接受固定 Apple endpoint、驗證 principal 後加密保存，唯讀行程；既有 server owner 設定仍相容。
- 解除為本機斷開：刪除該服務密文並保存 tombstone，阻止舊 session fallback。保留原始外部資料、本機資料、登入身分與其他連線。
- 不自動對 Google 執行整體 token revoke：其合併授權可能同時撤銷其他服務。UI 明確說明，可至 Google 帳號撤銷遠端授權。
- 未綁定的 Music / Drive / Google Tasks / Calendar 顯示連線引導，模組設定導向同一管理入口。

## 資料與 migration
Alembic `0006_account_connections` 僅新增 `account_profiles`、`service_connections`，保留舊資料及 ownership key，不增加新的登入提供者、密碼註冊或帳號刪除功能。Google subject 是已註冊身分依據；Email 仍作為相容的資料 owner key。

新服務秘密使用既有 cryptography/Fernet 加密。金鑰放在實際 DB 同層的 `.local/secrets/connections.key`（Docker `/data/.local/secrets/connections.key`），首次保存時以 exclusive create 產生，POSIX 模式 0600；不寫進 Git/image/API/log。若已有密文卻遺失金鑰，拒絕自動生成替代 key，Core 仍可用。Windows 部署需另外確保資料目錄 ACL。

舊 session token 僅作相容讀取；`scripts/preserve_connections.py` 可在升級後依明確 scope 加密採納，無網路呼叫。未知 scopes 不推測連線能力。此 release 不自動銷毀舊 DB/session 中既有明文 token；備份仍需視為敏感資料。

## 備份及 rollback
SQLite verifier 已接受 0006 並檢查新增 schema。獨立 restore drill 驗證 DB + 原 key 可解密連線；只有 DB 可還原 Core，但無法復原加密憑證。詳見 BACKUP_RESTORE.md。

切換前停止 app writers、建立 verified DB snapshot。新 image 升級 DB，再採納舊 scopes。原 image 期待 0005，因此不能直接換回舊 image 卻留下 0006 DB。只有在確認沒有新使用者寫入時，才可停止 app 並還原切換前 verified snapshot；已有寫入則保留資料、向前修復。不要強制 downgrade 或 stamp 掩蓋版本差異。

## 驗證範圍
目前 124 tests passed；browser_core / browser_security 通過，無 JS console error。
HTTP regression 使用隔離 SQLite、mocked Google / CalDAV；browser_core 使用真實隔離 DB；browser_security mock 外部網路。已覆蓋資料承接、owner isolation、session context、scope denial、加密/失去 key、解除 tombstone、取消、iCloud redaction、restore，以及手機/桌面畫面。
真實 Google consent、撤銷後重連及新的 iCloud 表單連線仍需使用者完成外部授權驗收；不以 mocked 結果宣稱外部服務已驗證。

Google 流程依官方文件：
- https://developers.google.com/identity/protocols/oauth2/web-server
- https://developers.google.com/identity/protocols/oauth2/resources/granular-permissions
