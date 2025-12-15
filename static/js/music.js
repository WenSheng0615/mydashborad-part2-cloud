let musicQueue = [], currentTrackIndex = 0, isPlaying = false, loopMode = 0, isShuffle = false, currentSong = null;
const audio = document.getElementById('audio-player');

document.addEventListener('DOMContentLoaded', () => {
    // 初始化事件監聽
    audio.addEventListener('ended', onAudioEnded);
    audio.addEventListener('timeupdate', updateProgress);
    audio.addEventListener('play', () => updatePlayBtn(true));
    audio.addEventListener('pause', () => updatePlayBtn(false));

    // 初始化載入使用者資訊
    loadUserInfo();
});

// 音量控制
function setVolume(val) {
    audio.volume = val;
}

// 播放核心邏輯
async function playTrack(idx) {
    // ★ 防呆：如果佇列裡沒這首歌，就停止
    if (!musicQueue[idx]) {
        console.error("Queue index out of bound:", idx);
        return;
    }

    currentTrackIndex = idx;
    currentSong = musicQueue[idx];

    // UI 更新：顯示載入中
    document.getElementById('current-track-title').innerText = "解析中...";
    document.getElementById('current-cover-img').src = currentSong.thumbnail || "https://via.placeholder.com/400?text=Music";
    document.getElementById('loading-spinner').style.display = 'flex';

    try {
        // 呼叫後端解析真實音訊網址
        const res = await fetch(`/api/music/stream?video_id=${currentSong.id}`);
        const data = await res.json();

        if (data.url) {
            audio.src = data.url;
            await audio.play();

            // 更新 UI 資訊
            document.getElementById('current-track-title').innerText = currentSong.title;
            document.getElementById('current-track-channel').innerText = currentSong.channel;

            // 加入歷史紀錄 (不等待)
            addToHistory(currentSong);

            // 更新列表的高亮狀態
            renderCurrentListState();
        } else {
            console.error("解析失敗，網址為空");
            // 如果失敗，自動跳下一首 (避免卡死)
            playNext(true);
        }
    } catch (e) {
        console.error("播放錯誤:", e);
        playNext(true);
    } finally {
        document.getElementById('loading-spinner').style.display = 'none';
    }
}

// 為了讓列表能即時更新 active 狀態 (不重新渲染整個列表)
function renderCurrentListState() {
    document.querySelectorAll('.track-item').forEach((el, idx) => {
        if (idx === currentTrackIndex) el.classList.add('active');
        else el.classList.remove('active');
    });
}

function updatePlayBtn(playing) {
    isPlaying = playing;
    const btn = document.getElementById('btn-play-pause');
    if (playing) btn.innerHTML = '<i class="fa-solid fa-pause"></i>';
    else btn.innerHTML = '<i class="fa-solid fa-play" style="margin-left:4px;"></i>';
}

function togglePlayState() {
    if (!audio.src) return;
    if (audio.paused) audio.play(); else audio.pause();
}

function onAudioEnded() {
    // 單曲循環模式
    if (loopMode === 2) {
        audio.currentTime = 0;
        audio.play();
    } else {
        playNext(true);
    }
}

function controlPlayer(act) {
    if (act === 'next') playNext();
    if (act === 'prev') playPrev();
    if (act === 'forward') audio.currentTime += 10;
    if (act === 'rewind') audio.currentTime -= 10;
}

function playNext(auto = false) {
    // 列表循環模式 (0: 不循環, 1: 列表循環, 2: 單曲)
    if (auto && loopMode === 0 && currentTrackIndex >= musicQueue.length - 1) return;

    if (isShuffle) {
        let nextIdx = Math.floor(Math.random() * musicQueue.length);
        playTrack(nextIdx);
    } else {
        if (currentTrackIndex < musicQueue.length - 1) {
            playTrack(currentTrackIndex + 1);
        } else if (loopMode >= 1) {
            playTrack(0); // 回到第一首
        }
    }
}

function playPrev() {
    if (currentTrackIndex > 0) playTrack(currentTrackIndex - 1);
}

function updateProgress() {
    if (audio.duration) {
        document.getElementById('progress-bar').value = (audio.currentTime / audio.duration) * 100;
        document.getElementById('current-time').innerText = fmt(audio.currentTime);
        document.getElementById('duration').innerText = fmt(audio.duration);
    }
}

function seekTo(val) {
    if (audio.duration) audio.currentTime = (val / 100) * audio.duration;
}

function fmt(s) {
    const m = Math.floor(s / 60);
    const sc = Math.floor(s % 60);
    return `${m}:${sc < 10 ? '0' : ''}${sc}`;
}

function toggleLoop() {
    loopMode = (loopMode + 1) % 3;
    const btn = document.getElementById('btn-loop');
    // 視覺回饋：0=灰, 1=亮, 2=亮+icon變化
    btn.className = loopMode === 0 ? "btn-tool btn-extra" : "btn-tool btn-extra active";
    if (loopMode === 2) btn.innerHTML = '<i class="fa-solid fa-1"></i>';
    else btn.innerHTML = '<i class="fa-solid fa-repeat"></i>';
}

function toggleShuffle() {
    isShuffle = !isShuffle;
    document.getElementById('btn-shuffle').classList.toggle('active');
}

// === 分頁切換 ===
function switchTab(name) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    // 找出對應的按鈕並設為 active (因為按鈕沒有 ID，用索引判斷)
    const btns = document.querySelectorAll('.tab-btn');
    if (name === 'search') btns[0].classList.add('active');
    if (name === 'playlists') { btns[1].classList.add('active'); loadPlaylists(); }
    if (name === 'history') { btns[2].classList.add('active'); loadHistory(); }

    document.getElementById('tab-' + name).classList.add('active');
}

// === API 串接 ===

async function searchYouTube() {
    const q = document.getElementById('yt-search-input').value;
    if (!q) return;

    const div = document.getElementById('yt-results');
    div.innerHTML = '<p style="text-align:center; margin-top:20px;">搜尋中...</p>';

    try {
        const res = await fetch(`/api/music/search?query=${encodeURIComponent(q)}`);
        const data = await res.json();

        if (data.error) {
            div.innerHTML = `<p style="color:#ff4d4f; text-align:center; margin-top:20px;">${data.error}</p>`;
            return;
        }

        // ★ 更新佇列：現在播放清單變成「搜尋結果」
        musicQueue = data.items || [];
        renderList(div, musicQueue, 'search');
    } catch (e) {
        div.innerHTML = '<p style="color:#ff4d4f; text-align:center;">連線錯誤</p>';
    }
}

async function loadPlaylists() {
    const div = document.getElementById('playlists-list');
    div.innerHTML = '<p style="text-align:center; margin-top:20px;">載入中...</p>';

    try {
        const res = await fetch('/api/music/playlists');
        const data = await res.json();

        if (data.error) { return; } // auth.py 會處理 401

        let html = '';
        const playlists = data.playlists || [];

        if (playlists.length === 0) {
            div.innerHTML = '<p style="text-align:center; color:#666; margin-top:20px;">沒有找到歌單</p>';
            return;
        }

        playlists.forEach(pl => {
            // 安全處理單引號
            const safeTitle = pl.title.replace(/'/g, "");
            html += `
            <div class="track-item" onclick="loadPlaylistItems('${pl.id}', '${safeTitle}')">
                <img src="${pl.thumbnail}" class="track-img">
                <div class="track-info">
                    <div class="track-title">${pl.title}</div>
                    <div class="track-channel">${pl.count} songs</div>
                </div>
                <i class="fa-solid fa-chevron-right" style="color:#666;"></i>
            </div>`;
        });
        div.innerHTML = html;
    } catch (e) { }
}

async function loadPlaylistItems(pid, title) {
    document.getElementById('playlists-list').style.display = 'none';
    document.getElementById('playlist-detail').style.display = 'flex';
    document.getElementById('playlist-title').innerText = title;
    document.getElementById('playlist-detail').dataset.pid = pid;

    const div = document.getElementById('playlist-songs');
    div.innerHTML = '<p style="text-align:center; margin-top:20px;">載入歌曲...</p>';

    try {
        const res = await fetch(`/api/music/playlist/items?playlist_id=${pid}`);
        const data = await res.json();

        // ★ 更新佇列：現在播放清單變成「這個歌單的內容」
        musicQueue = data.items || [];
        renderList(div, musicQueue, 'playlist');
    } catch (e) { }
}

function closePlaylist() {
    document.getElementById('playlist-detail').style.display = 'none';
    document.getElementById('playlists-list').style.display = 'block';
}

// ★★★ 關鍵修正：載入歷史紀錄 ★★★
async function loadHistory() {
    const div = document.getElementById('history-list');
    div.innerHTML = '<p style="text-align:center; margin-top:20px;">讀取中...</p>';

    try {
        const res = await fetch('/api/music/history');
        const data = await res.json();

        // ★ 修正重點：把歷史紀錄設為當前的播放佇列
        // 這樣 playTrack(0) 才會播放歷史紀錄裡的第 1 首歌
        musicQueue = data.history || [];

        if (musicQueue.length === 0) {
            div.innerHTML = '<p style="text-align:center; color:#666; margin-top:20px;">尚無播放紀錄</p>';
        } else {
            renderList(div, musicQueue, 'history');
        }
    } catch (e) { }
}

async function addToHistory(s) {
    const fd = new FormData();
    fd.append('id', s.id);
    fd.append('title', s.title);
    fd.append('channel', s.channel);
    fd.append('thumbnail', s.thumbnail);
    await fetch('/api/music/history/add', { method: 'POST', body: fd });
}

async function loadUserInfo() {
    try {
        const res = await fetch('/api/music/user');
        const data = await res.json();
        if (!data.error && data.info) {
            // 這裡其實 index.html 已經做了，這邊只是保險
        }
    } catch (e) { }
}

// 通用列表渲染
function renderList(div, items, type = 'search') {
    let html = '';
    items.forEach((item, idx) => {
        // 如果正在播放這首歌，加上 active 樣式
        // 注意：如果是切換到 history 頁籤，我們希望看到現在正在播哪首 (如果有在名單內)
        const isCurrentSong = (currentSong && item.id === currentSong.id);
        const activeClass = isCurrentSong ? 'active' : '';

        let delBtn = '';
        // 歌單模式下顯示刪除按鈕
        if (type === 'playlist' && item.itemId) {
            delBtn = `<button class="btn-tool" style="width:30px; height:30px;" onclick="removeFromPlaylist('${item.itemId}', event)"><i class="fa-solid fa-trash"></i></button>`;
        }

        html += `
        <div class="track-item ${activeClass}" onclick="playTrack(${idx})">
            <img src="${item.thumbnail || 'https://via.placeholder.com/50'}" class="track-img">
            <div class="track-info">
                <div class="track-title">${item.title}</div>
                <div class="track-channel">${item.channel}</div>
            </div>
            ${delBtn}
        </div>`;
    });
    div.innerHTML = html;
}

// 歌單管理功能
async function openAddToPlaylistModal() {
    if (!currentSong) return alert('請先播放歌曲');
    // 這裡可以實作開啟 Modal 的邏輯，目前簡化處理
    const res = await fetch('/api/music/playlists');
    const data = await res.json();

    if (!data.playlists || data.playlists.length === 0) return alert("沒有歌單可加入");

    let menu = '請輸入歌單編號:\n';
    data.playlists.forEach((pl, i) => menu += `${i + 1}. ${pl.title}\n`);

    const idx = parseInt(prompt(menu)) - 1;
    if (!isNaN(idx) && data.playlists[idx]) {
        const fd = new FormData();
        fd.append('playlist_id', data.playlists[idx].id);
        fd.append('video_id', currentSong.id);
        await fetch('/api/music/playlist/add_song', { method: 'POST', body: fd });
        alert('已加入');
    }
}

async function removeFromPlaylist(itemId, e) {
    e.stopPropagation();
    if (!confirm('確定移除此歌曲?')) return;

    const pid = document.getElementById('playlist-detail').dataset.pid;
    const title = document.getElementById('playlist-title').innerText;

    const fd = new FormData();
    fd.append('item_id', itemId);

    await fetch('/api/music/playlist/remove_song', { method: 'POST', body: fd });

    // 移除後重新載入該歌單
    loadPlaylistItems(pid, title);
}