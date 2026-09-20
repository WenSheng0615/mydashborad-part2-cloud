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
// ★★★ 訪客救星：手動解析網址 ★★★
let lastCheckedVid = null;
let lastEmbedInfo = null;

function onUrlInput(val) {
    const vid = extractVideoId(val.trim());
    const btn = document.getElementById('btn-quick-play');
    const status = document.getElementById('url-status');

    if (!vid) {
        btn.disabled = true;
        btn.style.opacity = 0.5;
        status.innerText = "";
        return;
    }

    if (vid === lastCheckedVid) return;
    lastCheckedVid = vid;

    status.innerHTML = "⏳ 正在讀取影片資訊...";

    // 使用公開的 oEmbed API (不需要 API Key)
    fetch(`https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=${vid}&format=json`)
        .then(r => r.json())
        .then(data => {
            lastEmbedInfo = {
                id: vid,
                title: data.title,
                thumbnail: `https://img.youtube.com/vi/${vid}/mqdefault.jpg`,
                channel: data.author_name
            };
            status.textContent = `✅ 準備就緒：${data.title}`;
            btn.disabled = false;
            btn.style.opacity = 1;
        })
        .catch(() => {
            status.innerHTML = "❌ 無法取得資訊，但仍可嘗試播放";
            lastEmbedInfo = { id: vid, title: "未知影片", thumbnail: "" };
            btn.disabled = false;
            btn.style.opacity = 1;
        });
}

function extractVideoId(url) {
    url = url.trim();
    const patterns = [
        /[?&]v=([A-Za-z0-9_-]{11})/,
        /\/live\/([A-Za-z0-9_-]{11})/,
        /embed\/([A-Za-z0-9_-]{11})/,
        /youtu\.be\/([A-Za-z0-9_-]{11})/,
        /shorts\/([A-Za-z0-9_-]{11})/,
        /^([A-Za-z0-9_-]{11})$/ // 直接輸入 ID
    ];
    for (const p of patterns) {
        const m = url.match(p);
        if (m) return m[1];
    }
    return null;
}

async function quickPlay() {
    if (!lastEmbedInfo) return;

    // 將這首歌加入當前播放佇列的第一位，並同步刷新畫面上的清單（否則播放中的曲目跟清單會對不起來）
    musicQueue.unshift(lastEmbedInfo);
    renderList(document.getElementById('yt-results'), musicQueue, 'search');

    // 重置輸入框與按鈕狀態，讓同一首歌可以再次貼上加入
    const btn = document.getElementById('btn-quick-play');
    document.getElementById('yt-url-input').value = "";
    document.getElementById('url-status').innerText = "🚀 正在啟動播放...";
    btn.disabled = true;
    btn.style.opacity = 0.5;
    lastCheckedVid = null;
    lastEmbedInfo = null;

    // 立即播放
    playTrack(0);
}

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
            showAlert('播放失敗','無法取得音訊，請稍後再試或選擇其他歌曲。');
        }
    } catch (e) {
        console.error("播放錯誤:", e);
        showAlert('播放失敗','目前無法播放，請稍後再試。');
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
            div.textContent = data.error;
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
        const playlists = data.playlists || [];div.replaceChildren();
        if(!playlists.length){div.append(FlowUI.node('p','沒有找到歌單'));return;}
        for(const playlist of playlists){
            const row=musicRow(playlist.title,`${playlist.count} songs`,playlist.thumbnail);
            row.onclick=()=>loadPlaylistItems(playlist.id,playlist.title);div.append(row);
        }
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

function musicRow(title, subtitle, thumbnail) {
    const row=FlowUI.node('div',null,'track-item');
    const image=FlowUI.node('img',null,'track-img');image.alt='';
    const url=FlowUI.url(thumbnail);if(url)image.src=url;
    const info=FlowUI.node('div',null,'track-info');
    info.append(FlowUI.node('div',title,'track-title'),FlowUI.node('div',subtitle,'track-channel'));
    row.append(image,info);return row;
}
function renderList(div, items, type='search') {
    div.replaceChildren();
    items.forEach((item,index)=>{
        const row=musicRow(item.title,item.channel||'YouTube',item.thumbnail);
        row.classList.toggle('active',currentSong?.id===item.id);
        row.onclick=()=>{musicQueue=items;playTrack(index);};div.append(row);
    });
}
function closePlaylist(){document.getElementById('playlist-detail').style.display='none';document.getElementById('playlists-list').style.display='';}
