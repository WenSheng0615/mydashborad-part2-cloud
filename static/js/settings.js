function initSettings() {
    // 1. 初始化深色模式開關
    const isLight = document.body.classList.contains('light-mode');
    const toggle = document.getElementById('theme-switch');
    if (toggle) toggle.checked = isLight;

    // 2. 初始化通知開關
    const notifyToggle = document.getElementById('notify-switch');
    if (notifyToggle) {
        notifyToggle.checked = (Notification.permission === 'granted');
    }

    // 3. 載入儲存空間
    loadStorageInfo();
}

// 切換深色/淺色
function toggleTheme() {
    const isChecked = document.getElementById('theme-switch').checked;
    if (isChecked) {
        document.body.classList.add('light-mode');
        localStorage.setItem('theme', 'light');
    } else {
        document.body.classList.remove('light-mode');
        localStorage.setItem('theme', 'dark');
    }
}

// 切換系統通知
function toggleNotifications() {
    const isChecked = document.getElementById('notify-switch').checked;

    if (isChecked) {
        if (Notification.permission !== 'granted') {
            Notification.requestPermission().then(permission => {
                if (permission === 'granted') {
                    new Notification("FocusFlow OS", { body: "系統通知已啟用！" });
                } else {
                    document.getElementById('notify-switch').checked = false;
                    alert("您拒絕了通知權限，請至瀏覽器設定開啟。");
                }
            });
        } else {
            new Notification("FocusFlow OS", { body: "系統通知功能正常運作中。" });
        }
    }
}

// 載入真實的 Google Drive 空間
async function loadStorageInfo() {
    const usageText = document.getElementById('storage-usage-text');
    const totalText = document.getElementById('storage-total-text');
    const bar = document.getElementById('storage-bar');

    if (!usageText) return;

    try {
        const res = await fetch('/api/drive/storage');
        if (res.status === 401) {
            usageText.innerText = "請先登入";
            bar.style.width = '0%';
            return;
        }

        const data = await res.json();
        const totalGB = (data.total / (1024 ** 3)).toFixed(1);
        const usedGB = (data.used / (1024 ** 3)).toFixed(1);
        const percent = Math.min((data.used / data.total) * 100, 100).toFixed(1);

        usageText.innerText = `已使用 ${percent}%`;
        totalText.innerText = `${usedGB} GB / ${totalGB} GB`;
        bar.style.width = `${percent}%`;

        // 根據用量變色
        if (percent > 90) bar.style.backgroundColor = '#ff4d4f'; // 紅色警戒
        else if (percent > 75) bar.style.backgroundColor = '#faad14'; // 黃色注意
        else bar.style.backgroundColor = 'var(--accent)'; // 正常

    } catch (e) {
        console.error("Storage info error:", e);
        usageText.innerText = "讀取失敗";
    }
}

async function clearSystemCache() {
    if (!confirm("確定清除系統快取？(將會重新整理)")) return;
    localStorage.clear();
    location.reload();
}

// 監聽進入設定頁面的動作，確保資料刷新
document.addEventListener('click', (e) => {
    if (e.target.closest('#nav-settings') || e.target.closest('.app-icon-card[onclick*="settings"]')) {
        setTimeout(initSettings, 100);
    }
});