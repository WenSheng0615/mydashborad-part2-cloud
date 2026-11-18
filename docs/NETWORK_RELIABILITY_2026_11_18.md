# 2026-11-18 HomeCloud 斷線修復與防復發

## 本次證據與處理

- Tailscale 顯示 HomeCloud 離線，HTTPS 連線逾時。
- 區網 SSH 可進入 192.168.46.131，已用原有 100.113.77.65 SSH host key 驗證相同主機，未關閉主機驗證。
- Ubuntu 的 Docker、nginx、tailscaled 都 active，本機 /health/ready 正常。
- Ubuntu 當下無法 ping 預設閘道 192.168.46.2，也無法連外；Windows 本身仍能連外。
- VMware NAT Service 顯示 Running，卻沒有正常轉送：本次故障定位為 VMware NAT 資料平面失效，不是網站程式故障。
- 重啟 NAT 後，Ubuntu 閘道、外網恢復，Tailscale 重連，正式 HTTPS readiness 回200；容器維持原本 e3ed6d5，沒有重啟 VM、Docker 或更動正式 DB。
- Windows 電源事件顯示多次進出 Modern Standby，包括 Power Button 事件。這是可能觸發因素，尚不能證明唯一原因。不要將本次判斷寫成 VMware 已永不再掛。

## 已安裝 Windows Network Guard

來源：scripts/homecloud-network-watch.ps1、install-homecloud-network-watch.ps1。

- 排程名稱 HomeCloud Network Guard；每分鐘及開機時執行。
- 使用 WenSheng 帳號的 S4U 排程，不保存 Windows 密碼；已實際在背景登入環境執行成功，LastTaskResult=0。
- SYSTEM 執行腳本受現有安全政策限制，因此最終改用既有管理帳號的排程環境；沒有降低執行政策或新增信任憑證。
- 執行檔與資料位於 C:\ProgramData\HomeCloud\NetworkGuard；程式只有 Administrators/SYSTEM 可修改。
- 探測 SSH key 複本僅 Administrators/SYSTEM 可讀，固定驗證原有 host key；日誌不包含憑證。
- 每輪檢查 Windows 外網、VM MAC／DHCP 地址、VM 區網 readiness、Tailnet HTTPS，以及從 Ubuntu 內部檢查閘道與外網。
- 僅 NAT 停止，或 VM 區網正常但 Ubuntu 閘道與外網同時失敗時，才列為 NAT 復原條件；自動模式需連續兩次確認。
- Windows 斷網、VM 關閉、應用程式單獨故障，或探測不完整時不按 NAT 假死處理。
- 冷卻15分鐘，每小時最多兩次復原；不重啟 VM／Docker、不重設整套虛擬網路。
- 成功復原、分類結果及失敗均寫入 events.jsonl，約5MB輪替，避免無限制增加。
- 虛擬閘道由 vmnetnat.conf 讀取，VM IP 由指定 MAC 的 DHCP lease 讀取，避免直接綁死舊 IP。

Windows 主機本身不一定能探測到自己的 VMware 虛擬閘道，不能用主機 ARP 失敗作為復原依據；最終分類以 Ubuntu 內部探測為準。

## 電源設定

使用者已同意插電時不自動睡眠。已將目前電源方案的 AC standby/hibernate timeout 設為0；螢幕與DC電池設定未變更。原設定保存於 NetworkGuard/power-before.txt。

手動睡眠、按電源鍵進待命、闔蓋動作、Windows 關機或 VM 關閉仍會造成離線；這套修復程序只能在 Windows 醒著時運作。長期24x7仍需考慮常開主機。

## 驗證與回復

- scripts/test-homecloud-network-watch.ps1：重複故障、健康閘道、主機斷網、VM不在、應用層失敗、探測失敗、冷卻與重試上限測試通過。
- 已觀察真實 NAT 故障被修復，並驗證 Ubuntu ping 閘道／1.1.1.1、HTTPS readiness、容器 health。
- 排程實際執行已成功，日誌顯示 TailnetReady/GuestGatewayReachable/GuestInternet=true；未刻意製造第二次正式停網。
- 稽核檔：installed.json、task-diagnostic.json、events.jsonl、power-timeline.json。早期 install-error.json 保留安裝過程歷史，應以 installed.json 較新的成功時間及排程結果為準。
- 停用：以管理員執行 Disable-ScheduledTask -TaskName 'HomeCloud Network Guard'；移除則用 Unregister-ScheduledTask 同名排程，再按需要還原原電源方案。不要刪除原有 HomeCloud 備份任務或 SSH key。

官方排查參考：https://knowledge.broadcom.com/external/article/307964
