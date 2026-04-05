let musicQueue = [], currentTrackIndex = 0, isPlaying = false, loopMode = 0, isShuffle = false, currentSong = null;
const audio = document.getElementById('audio-player');

document.addEventListener('DOMContentLoaded', () => {
    // 初始化事件監聽
    if (audio) {
        audio.addEventListener('ended', onAudioEnded);
        audio.addEventListener('timeupdate', updateProgress);
        audio.addEventListener('play', () => updatePlayBtn(true));
        audio.addEventListener('pause', () => updatePlayBtn(false));
    }
});

// ★★★ 音樂功能入口函式 ★★★
function loadMusic() {
    console.log("🎵 音樂功能載入中...");
    loadUserInfo();
    loadHistory();
}

// 音量控制
function setVolume(val) {
    if (audio) audio.volume = val;
}

// 播放核心邏輯
async function playTrack(idx) {
    if (!musicQueue[idx]) {
        console.error("Queue index out of bound:", idx);
        return;
    }

    currentTrackIndex = idx;
    currentSong = musicQueue[idx];

    // UI 更新
    document.getElementById('current-track-title').innerText = "解析中...";
    document.getElementById('current-cover-img').src = currentSong.thumbnail || "https://via.placeholder.com/400?text=Music";
    document.getElementById('loading-spinner').style.display = 'flex';

    try {
        const res = await fetch(`/api/music/stream?video_id=${currentSong.id}`);
        const data = await res.json();

        if (data.url) {
            audio.src = data.url;
            await audio.play();

            document.getElementById('current-track-title').innerText = currentSong.title;
            document.getElementById('current-track-channel').innerText = currentSong.channel || "YouTube";

            // 加入歷史紀錄 (注意：欄位名稱必須與後端 routers/music.py 一致)
            addToHistory(currentSong);

            renderCurrentListState();
        } else {
            console.error("解析失敗");
            playNext(true);
        }
    } catch (e) {
        console.error("播放錯誤:", e);
        playNext(true);
    } finally {
        document.getElementById('loading-spinner').style.display = 'none';
    }
}

function renderCurrentListState() {
    document.querySelectorAll('.track-item').forEach((el, idx) => {
        if (idx === currentTrackIndex) el.classList.add('active');
        else el.classList.remove('active');
    });
}

function updatePlayBtn(playing) {
    isPlaying = playing;
    const btn = document.getElementById('btn-play-pause');
    if (btn) {
        if (playing) btn.innerHTML = '<i class="fa-solid fa-pause"></i>';
        else btn.innerHTML = '<i class="fa-solid fa-play" style="margin-left:4px;"></i>';
    }
}

function togglePlayState() {
    if (!audio.src) return;
    if (audio.paused) audio.play(); else audio.pause();
}

function onAudioEnded() {
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
    if (musicQueue.length === 0) return;
    if (auto && loopMode === 0 && currentTrackIndex >= musicQueue.length - 1) return;

    if (isShuffle) {
        let nextIdx = Math.floor(Math.random() * musicQueue.length);
        playTrack(nextIdx);
    } else {
        if (currentTrackIndex < musicQueue.length - 1) {
            playTrack(currentTrackIndex + 1);
        } else if (loopMode >= 1) {
            playTrack(0);
        }
    }
}

function playPrev() {
    if (currentTrackIndex > 0) playTrack(currentTrackIndex - 1);
}

function updateProgress() {
    if (audio && audio.duration) {
        document.getElementById('progress-bar').value = (audio.currentTime / audio.duration) * 100;
        document.getElementById('current-time').innerText = fmt(audio.currentTime);
        document.getElementById('duration').innerText = fmt(audio.duration);
    }
}

function seekTo(val) {
    if (audio && audio.duration) audio.currentTime = (val / 100) * audio.duration;
}

function fmt(s) {
    const m = Math.floor(s / 60);
    const sc = Math.floor(s % 60);
    return `${m}:${sc < 10 ? '0' : ''}${sc}`;
}

function toggleLoop() {
    loopMode = (loopMode + 1) % 3;
    const btn = document.getElementById('btn-loop');
    if (btn) {
        btn.className = loopMode === 0 ? "btn-tool btn-extra" : "btn-tool btn-extra active";
        if (loopMode === 2) btn.innerHTML = '<i class="fa-solid fa-1"></i>';
        else btn.innerHTML = '<i class="fa-solid fa-repeat"></i>';
    }
}

function toggleShuffle() {
    isShuffle = !isShuffle;
    const btn = document.getElementById('btn-shuffle');
    if (btn) btn.classList.toggle('active');
}

function switchTab(name) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    const btns = document.querySelectorAll('.tab-btn');
    if (name === 'search' && btns[0]) btns[0].classList.add('active');
    if (name === 'playlists' && btns[1]) { btns[1].classList.add('active'); loadPlaylists(); }
    if (name === 'history' && btns[2]) { btns[2].classList.add('active'); loadHistory(); }

    const targetTab = document.getElementById('tab-' + name);
    if (targetTab) targetTab.classList.add('active');
}

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
        let html = '';
        const playlists = data.playlists || [];
        if (playlists.length === 0) {
            div.innerHTML = '<p style="text-align:center; color:#666; margin-top:20px;">沒有找到歌單</p>';
            return;
        }
        playlists.forEach(pl => {
            const safeTitle = pl.title.replace(/'/g, "");
            html += `<div class="track-item" onclick="loadPlaylistItems('${pl.id}', '${safeTitle}')">
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
    const div = document.getElementById('playlist-songs');
    div.innerHTML = '<p style="text-align:center; margin-top:20px;">載入歌曲...</p>';
    try {
        const res = await fetch(`/api/music/playlist/items?playlist_id=${pid}`);
        const data = await res.json();
        musicQueue = data.items || [];
        renderList(div, musicQueue, 'playlist');
    } catch (e) { }
}

async function loadHistory() {
    const div = document.getElementById('history-list');
    if (!div) return;
    div.innerHTML = '<p style="text-align:center; margin-top:20px;">讀取中...</p>';
    try {
        const res = await fetch('/api/music/history');
        const data = await res.json();
        // 這裡後端回傳的是 {"items": [...]}
        const historyItems = data.items || [];
        if (historyItems.length === 0) {
            div.innerHTML = '<p style="text-align:center; color:#666; margin-top:20px;">尚無播放紀錄</p>';
        } else {
            // 切換到歷史分頁時，將歷史紀錄設為當前 Queue
            musicQueue = historyItems;
            renderList(div, musicQueue, 'history');
        }
    } catch (e) { console.error("Load History Error:", e); }
}

async function addToHistory(s) {
    const fd = new FormData();
    // ★★★ 重要：欄位名稱必須與後端 routers/music.py 一致 (video_id) ★★★
    fd.append('video_id', s.id); 
    fd.append('title', s.title);
    fd.append('thumbnail', s.thumbnail);
    try {
        await fetch('/api/music/history/add', { method: 'POST', body: fd });
    } catch (e) { console.error("Add to History Error:", e); }
}

async function loadUserInfo() {
    try {
        // 修正：指向正確的 auth 接口
        const res = await fetch('/api/auth/user');
        const data = await res.json();
    } catch (e) { }
}

function renderList(div, items, type = 'search') {
    let html = '';
    items.forEach((item, idx) => {
        const isCurrentSong = (currentSong && item.id === currentSong.id);
        const activeClass = isCurrentSong ? 'active' : '';
        html += `<div class="track-item ${activeClass}" onclick="playTrack(${idx})">
            <img src="${item.thumbnail || 'https://via.placeholder.com/50'}" class="track-img">
            <div class="track-info">
                <div class="track-title">${item.title}</div>
                <div class="track-channel">${item.channel || 'YouTube'}</div>
            </div>
        </div>`;
    });
    div.innerHTML = html;
}
