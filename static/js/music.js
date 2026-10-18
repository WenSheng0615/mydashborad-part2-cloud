let musicQueue = [], currentTrackIndex = 0, isPlaying = false, loopMode = 0, isShuffle = false, currentSong = null;
const audio = document.getElementById('audio-player');
let playRequest = 0;
let playlistLoadController = null;
const musicFallbackCover = new URL('/static/icons/icon-192.png', location.origin).href;
function musicCover(value) { return typeof value === 'string' && value.trim() ? FlowUI.url(value) : ''; }

// Keep only a few signed URLs in memory; preparing a track does not download its audio.
const preparedStreams = new Map(), preparingStreams = new Map();
let plannedNext = null, warmFailure = null, mediaWaiting = false, isSeekingPreview = false;
function preparedStream(id) {
    const cached = preparedStreams.get(id);
    if (!cached || cached.until <= Date.now()) { preparedStreams.delete(id); return null; }
    return cached.data;
}
function prepareStream(song) {
    const cached = preparedStream(song.id);
    if (cached) return Promise.resolve(cached);
    if (preparingStreams.has(song.id)) return preparingStreams.get(song.id);
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 25000);
    const pending = (async () => {
        try {
            const data = await FlowUI.request('/api/music/stream?video_id=' + encodeURIComponent(song.id), {signal:controller.signal});
            if (!data.url) throw new Error('No audio source');
            const expires = Number(data.expires_at) * 1000;
            const until = Math.min(Date.now() + 15 * 60 * 1000, Number.isFinite(expires) && expires > 0 ? expires - 30000 : Date.now() + 5 * 60 * 1000);
            preparedStreams.set(song.id, {data, until});
            while (preparedStreams.size > 3) preparedStreams.delete(preparedStreams.keys().next().value);
            return data;
        } finally { clearTimeout(timeout); preparingStreams.delete(song.id); }
    })();
    preparingStreams.set(song.id, pending);return pending;
}
function nextIndex() {
    if (!musicQueue.length) return null;
    if (isShuffle) {
        if (plannedNext && plannedNext.queue === musicQueue && plannedNext.from === currentTrackIndex &&
            plannedNext.shuffle === isShuffle && plannedNext.loop === loopMode &&
            musicQueue[plannedNext.index] === plannedNext.song) return plannedNext.index;
        if (musicQueue.length === 1) return 0;
        const pick = Math.floor(Math.random() * (musicQueue.length - 1));
        return pick >= currentTrackIndex ? pick + 1 : pick;
    }
    if (currentTrackIndex < musicQueue.length - 1) return currentTrackIndex + 1;
    return loopMode >= 1 ? 0 : null;
}
function warmNextTrack() {
    if (!FlowModules.isEnabled('music')) return;
    const index = nextIndex();
    if (index === null || musicQueue[index] === currentSong) return;
    plannedNext = {queue:musicQueue,from:currentTrackIndex,shuffle:isShuffle,loop:loopMode,index,song:musicQueue[index]};
    const song = musicQueue[index];
    if (preparedStream(song.id) || preparingStreams.has(song.id) ||
        (warmFailure?.id === song.id && warmFailure.retryAfter > Date.now())) return;
    prepareStream(song).then(() => { if (warmFailure?.id === song.id) warmFailure = null; })
        .catch(() => { warmFailure = {id:song.id,retryAfter:Date.now()+30000}; }); // Avoid retrying on every timeupdate.
}
let musicDetailsPassed = false;
function syncMiniPlayer() {
    const mini = document.getElementById('music-mini-player');
    if (!mini) return;
    mini.hidden = !currentSong || !musicDetailsPassed;
    if (currentSong) {
        const cover = musicCover(currentSong.thumbnail) || musicFallbackCover;
        const image = document.getElementById('music-mini-cover');
        if (image.src !== cover) image.src = cover;
        document.getElementById('music-mini-title').textContent = currentSong.title || '未知曲目';
        document.getElementById('music-mini-artist').textContent = currentSong.channel || 'YouTube';
        mini.setAttribute('aria-label', `目前播放：${currentSong.title || '未知曲目'}，${currentSong.channel || 'YouTube'}`);
    }
    const toggle = document.getElementById('music-mini-toggle');
    toggle.setAttribute('aria-label', isPlaying ? '暫停' : '播放');
    toggle.querySelector('path').setAttribute('d', isPlaying ? 'M6 5h4v14H6z M14 5h4v14h-4z' : 'M8 5v14l11-7z');
}
function showFullMusicPlayer() {
    const layout = document.querySelector('#view-music .music-layout');
    layout.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
}
function initMiniPlayer() {
    if (!('IntersectionObserver' in window)) return;
    const layout = document.querySelector('#view-music .music-layout');
    const observer = new IntersectionObserver(([entry]) => {
        musicDetailsPassed = !!entry.rootBounds && entry.boundingClientRect.bottom <= entry.rootBounds.top;
        syncMiniPlayer();
    }, {root:layout,threshold:[0,1]});
    observer.observe(document.querySelector('#view-music .track-info-area'));
}

function mediaStatus(text) {
    const status = document.getElementById('music-playback-status');
    if (status) status.textContent = text;
}
let playbackObservation = null;
function observePlaybackPosition() {
    const now = performance.now(), position = audio.currentTime;
    const previous = playbackObservation;
    playbackObservation = {src:audio.src,position,time:now};
    if (!previous || previous.src !== audio.src || audio.paused || audio.ended || audio.seeking || audio.error || audio.readyState < 2) return;
    const moved = position - previous.position;
    const plausible = Math.max(2, (now - previous.time) / 1000 * (audio.playbackRate || 1) * 3);
    // Actual forward progress recovers a missed/late playing event, not a seek jump or timer.
    if (moved > 0 && moved <= plausible) {
        if (mediaWaiting) setMediaWaiting(false);
        if (!isPlaying) updatePlayBtn(true);
    }
}
function resetPlaybackObservation() {
    playbackObservation = {src:audio.src,position:audio.currentTime,time:performance.now()};
}
function setMediaWaiting(waiting) {
    mediaWaiting = waiting;
    if (waiting) resetPlaybackObservation();
    if ('mediaSession' in navigator) {
        try { navigator.mediaSession.playbackState = !waiting && !audio.paused && !audio.ended ? 'playing' : 'paused'; } catch (_) { }
    }
    syncMediaPosition();
    if (!waiting) mediaStatus('');
}

let sourceDuration = null, sourceIsLive = false, playbackFinished = false;
function inflatedMediaDuration() {
    return !sourceIsLive && Number.isFinite(sourceDuration) && sourceDuration > 0 &&
        Number.isFinite(audio.duration) && audio.duration >= sourceDuration * 1.5 &&
        audio.duration - sourceDuration >= 30;
}
function playbackDuration() {
    if (inflatedMediaDuration()) return sourceDuration;
    if (!sourceIsLive && Number.isFinite(sourceDuration) && sourceDuration > 0 &&
        (!Number.isFinite(audio.duration) || audio.duration <= 0)) return sourceDuration;
    return audio.duration;
}
function finishInflatedTail() {
    // Compare provider metadata, never amplitude/silence. Leave normal/live/unknown tracks alone.
    if (!playbackFinished && inflatedMediaDuration() && !audio.paused && !audio.seeking &&
        !mediaWaiting && audio.currentTime >= sourceDuration + 1) {
        document.getElementById('progress-bar').value = 100;
        document.getElementById('current-time').innerText = fmt(sourceDuration);
        document.getElementById('duration').innerText = fmt(sourceDuration);
        onAudioEnded();return true;
    }
    return false;
}

function syncMediaMetadata(song) {
    if (!('mediaSession' in navigator) || typeof MediaMetadata === 'undefined') return;
    try {
        const cover = musicCover(song.thumbnail) || musicFallbackCover;
        navigator.mediaSession.metadata = new MediaMetadata({
            title: song.title || '未知曲目', artist: song.channel || 'YouTube',
            album: 'FocusFlow Music', artwork: [{src: cover}]
        });
    } catch (_) { /* System metadata must never interrupt audio playback. */ }
}

function syncMediaPosition() {
    if (!('mediaSession' in navigator) || !navigator.mediaSession.setPositionState) return;
    try {
        const duration = playbackDuration();
        if (!Number.isFinite(duration) || duration <= 0) {
            navigator.mediaSession.setPositionState(); return;
        }
        if (mediaWaiting) { navigator.mediaSession.setPositionState(); return; }
        navigator.mediaSession.setPositionState({duration,
            playbackRate: audio.playbackRate || 1,
            position: Math.max(0, Math.min(audio.currentTime, duration))});
    } catch (_) { /* Not every browser implements position updates. */ }
}

function seekMedia(position) {
    const duration = playbackDuration();
    if (!Number.isFinite(position) || !Number.isFinite(duration) || duration <= 0) return;
    audio.currentTime = Math.max(0, Math.min(position, duration));
    syncMediaPosition();
}

function initMediaSession() {
    if (!('mediaSession' in navigator)) return;
    const handlers = {
        play: () => { if (audio.src) { if (playbackFinished) { audio.currentTime = 0; playbackFinished = false; } audio.play().catch(() => showAlert('播放失敗', '請回播放器重新選擇歌曲。')); } },
        pause: () => audio.pause(),
        previoustrack: () => playPrev(), nexttrack: () => playNext(),
        seekbackward: details => seekMedia(audio.currentTime - (details.seekOffset || 10)),
        seekforward: details => seekMedia(audio.currentTime + (details.seekOffset || 10)),
        seekto: details => seekMedia(details.seekTime),
        stop: () => { audio.pause(); seekMedia(0); }
    };
    for (const [action, handler] of Object.entries(handlers)) {
        try { navigator.mediaSession.setActionHandler(action, handler); } catch (_) { /* Unsupported action. */ }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const cover = document.getElementById('player-art-container');
    cover.setAttribute('role', 'button');
    cover.tabIndex = 0;
    cover.setAttribute('aria-label', '播放或暫停');
    cover.addEventListener('click', togglePlayState);
    cover.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); togglePlayState(); }
    });
    // 初始化事件監聽
    if (audio) {
        initMediaSession();
        initMiniPlayer();
        const slider = document.getElementById('progress-bar');
        for (const event of ['pointercancel', 'blur']) slider.addEventListener(event, () => { isSeekingPreview = false; updateProgress(); });
        audio.addEventListener('ended', onAudioEnded);
        audio.addEventListener('timeupdate', updateProgress);
        audio.addEventListener('play', () => { playbackFinished = false; mediaWaiting = true; resetPlaybackObservation(); updatePlayBtn(true); });
        audio.addEventListener('playing', () => { setMediaWaiting(false); updatePlayBtn(true); });
        audio.addEventListener('waiting', () => setMediaWaiting(true));
        audio.addEventListener('seeking', () => setMediaWaiting(true));
        audio.addEventListener('error', () => { setMediaWaiting(true); mediaStatus('音訊載入失敗，請回播放器重試或重新選擇歌曲。'); });
        audio.addEventListener('pause', () => { mediaWaiting = false; resetPlaybackObservation(); updatePlayBtn(false); if (!audio.error) mediaStatus(''); });
        audio.addEventListener('seeked', () => { resetPlaybackObservation(); if (audio.paused) { mediaWaiting = false; if (!audio.error) mediaStatus(''); updatePlayBtn(false); } });
        for (const event of ['loadedmetadata', 'durationchange', 'seeked', 'ratechange']) audio.addEventListener(event, syncMediaPosition);
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

    const requestId = ++playRequest;
    currentTrackIndex = idx;
    currentSong = musicQueue[idx];
    const song = currentSong;

    // UI 更新
    document.getElementById('current-track-title').innerText = "解析中...";
    document.getElementById('current-cover-img').src = musicCover(song.thumbnail) || musicFallbackCover;
    document.getElementById('loading-spinner').style.display = 'flex';

    try {
        // A prepared track reaches audio.play() without first awaiting a network request.
        const data = preparedStream(song.id) || await prepareStream(song);
        if (requestId !== playRequest) return;

        if (data.url) {
            // Stream extraction also supplies metadata for history/playlist entries without an author.
            song.title = data.title || song.title || '未知曲目';
            song.channel = data.channel || song.channel || 'YouTube';
            song.thumbnail = musicCover(data.thumbnail) || musicCover(song.thumbnail) || musicFallbackCover;
            sourceDuration = typeof data.duration === 'number' && Number.isFinite(data.duration) && data.duration > 0 ? data.duration : null;
            sourceIsLive = data.is_live === true;
            playbackFinished = false;
            setMediaWaiting(true);
            audio.src = data.url;
            document.getElementById('current-track-title').innerText = song.title;
            document.getElementById('current-track-channel').innerText = song.channel;
            document.getElementById('current-cover-img').src = song.thumbnail;
            syncMediaMetadata(song);
            syncMiniPlayer();
            syncMediaPosition();
            await audio.play();
            if (requestId !== playRequest) return;

            // 加入歷史紀錄 (注意：欄位名稱必須與後端 routers/music.py 一致)
            addToHistory(song);

            renderCurrentListState();
            warmNextTrack();
        } else {
            console.error("解析失敗");
            showAlert('播放失敗','無法取得音訊，請稍後再試或選擇其他歌曲。');
        }
    } catch (e) {
        if (requestId !== playRequest) return;
        console.error("播放錯誤:", e);
        setMediaWaiting(true);
        mediaStatus('播放未開始，請回播放器重試。');
        showAlert('播放失敗','目前無法播放，請稍後再試。');
    } finally {
        if (requestId === playRequest) document.getElementById('loading-spinner').style.display = 'none';
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
    syncMiniPlayer();
    if ('mediaSession' in navigator) {
        try { navigator.mediaSession.playbackState = playing && !mediaWaiting ? 'playing' : 'paused'; } catch (_) { }
    }
    syncMediaPosition();
    const btn = document.getElementById('btn-play-pause');
    if (btn) {
        if (playing) btn.innerHTML = '<i class="fa-solid fa-pause"></i>';
        else btn.innerHTML = '<i class="fa-solid fa-play" style="margin-left:4px;"></i>';
    }
}

function togglePlayState() {
    if (!audio.src) return;
    if (audio.paused) {
        if (playbackFinished) { audio.currentTime = 0; playbackFinished = false; }
        audio.play().catch(() => showAlert('播放失敗', '請重新選擇歌曲後再試。'));
    } else audio.pause();
}

function onAudioEnded(event) {
    if (playbackFinished || (event?.type === 'ended' && !audio.ended)) return;
    playbackFinished = true;
    updatePlayBtn(false);
    if (loopMode === 2) {
        audio.currentTime = 0;
        playbackFinished = false;
        audio.play().catch(() => mediaStatus('請按播放以繼續。'));
    } else {
        if (playNext(true) === false) audio.pause();
    }
}

function controlPlayer(act) {
    if (act === 'next') playNext();
    if (act === 'prev') playPrev();
    if (act === 'forward') seekMedia(audio.currentTime + 10);
    if (act === 'rewind') seekMedia(audio.currentTime - 10);
}

function playNext(auto = false) {
    if (musicQueue.length === 0) return false;
    if (auto && !isShuffle && loopMode === 0 && currentTrackIndex >= musicQueue.length - 1) return false;

    const index = nextIndex();
    if (index !== null) return playTrack(index);
    return false;
}

function playPrev() {
    if (currentTrackIndex > 0) playTrack(currentTrackIndex - 1);
}

function updateProgress() {
    observePlaybackPosition();
    if (finishInflatedTail()) return;
    const duration = playbackDuration();
    syncMediaPosition();
    if (currentSong && Number.isFinite(duration) && duration - audio.currentTime < 45) warmNextTrack();
    if (isSeekingPreview) return;
    if (Number.isFinite(duration) && duration > 0) {
        document.getElementById('progress-bar').value = (Math.min(audio.currentTime, duration) / duration) * 100;
        document.getElementById('current-time').innerText = fmt(Math.min(audio.currentTime, duration));
        document.getElementById('duration').innerText = fmt(duration);
    }
}

function previewSeek(val) {
    const duration = playbackDuration();
    if (!Number.isFinite(duration) || duration <= 0) return;
    isSeekingPreview = true;
    document.getElementById('current-time').innerText = fmt((Number(val) / 100) * duration);
}

function seekTo(val) {
    isSeekingPreview = false;
    const duration = playbackDuration();
    if (Number.isFinite(duration) && duration > 0) seekMedia((Number(val) / 100) * duration);
}

function fmt(s) {
    const m = Math.floor(s / 60);
    const sc = Math.floor(s % 60);
    return `${m}:${sc < 10 ? '0' : ''}${sc}`;
}

function toggleLoop() {
    loopMode = (loopMode + 1) % 3;
    plannedNext = null; if (currentSong) warmNextTrack();
    const btn = document.getElementById('btn-loop');
    if (btn) {
        btn.className = loopMode === 0 ? "btn-tool btn-extra" : "btn-tool btn-extra active";
        if (loopMode === 2) btn.innerHTML = '<i class="fa-solid fa-1"></i>';
        else btn.innerHTML = '<i class="fa-solid fa-repeat"></i>';
    }
}

function toggleShuffle() {
    isShuffle = !isShuffle;
    plannedNext = null; if (currentSong) warmNextTrack();
    const btn = document.getElementById('btn-shuffle');
    if (btn) btn.classList.toggle('active');
}

function switchTab(name) {
    if (name !== 'playlists') closePlaylist();
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
        renderList(div, data.items || [], 'search');
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

function playlistLoadingState() {
    const state = FlowUI.node('div', null, 'playlist-loading');
    const label = FlowUI.node('p', '正在載入歌單', 'playlist-loading-label');
    label.setAttribute('role', 'status');state.append(label);
    const skeleton = FlowUI.node('div', null, 'playlist-skeleton');
    skeleton.setAttribute('aria-hidden', 'true');
    for (let i = 0; i < 5; i++) {
        const row = FlowUI.node('div', null, 'playlist-skeleton-row');
        const lines = FlowUI.node('div', null, 'playlist-skeleton-lines');
        lines.append(FlowUI.node('span'), FlowUI.node('span'));
        row.append(FlowUI.node('span', null, 'playlist-skeleton-cover'), lines);skeleton.append(row);
    }
    state.append(skeleton);return state;
}

async function loadPlaylistItems(pid, title) {
    if (playlistLoadController) playlistLoadController.abort();
    const controller = new AbortController();
    playlistLoadController = controller;
    document.getElementById('playlists-list').style.display = 'none';
    document.getElementById('playlist-detail').style.display = 'flex';
    document.getElementById('playlist-title').innerText = title;
    const div = document.getElementById('playlist-songs');
    div.setAttribute('aria-busy', 'true');
    div.replaceChildren(playlistLoadingState());
    const items = [], pages = new Set();
    let token = '';
    try {
        do {
            if (pages.has(token)) throw new Error('Repeated playlist page');
            pages.add(token);
            const query = new URLSearchParams({playlist_id:pid});
            if (token) query.set('page_token', token);
            const timeout = setTimeout(() => controller.abort(), 20000);
            let data;
            try {
                data = await FlowUI.request('/api/music/playlist/items?' + query, {signal:controller.signal});
            } finally { clearTimeout(timeout); }
            if (controller !== playlistLoadController) return;
            if (!Array.isArray(data.items)) throw new Error('Invalid playlist page');
            items.push(...data.items);
            token = data.next_page_token || '';
            if (typeof token !== 'string') throw new Error('Invalid playlist token');
        } while (token);
        if (controller !== playlistLoadController) return;
        // Display only complete playlists; selecting a row activates its queue.
        renderList(div, items, 'playlist');
        div.prepend(FlowUI.node('p', items.length ? `${items.length} 首歌曲` : '這份歌單還沒有歌曲', 'playlist-summary'));
    } catch (_) {
        if (controller !== playlistLoadController) return;
        const state = FlowUI.node('div', null, 'playlist-error');
        const symbol = FlowUI.node('span', '↻', 'playlist-state-symbol');symbol.setAttribute('aria-hidden', 'true');
        const status = FlowUI.node('h3', '暫時無法開啟歌單');status.setAttribute('role', 'status');
        state.append(symbol, status, FlowUI.node('p', '請稍後再試，目前的播放佇列會保留。'));
        const retry = FlowUI.node('button', '重新載入歌曲', 'btn-tool');
        retry.type = 'button'; retry.onclick = () => loadPlaylistItems(pid, title);
        state.append(retry);div.replaceChildren(state);
    } finally {
        if (controller === playlistLoadController) { div.setAttribute('aria-busy', 'false'); playlistLoadController = null; }
    }
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
            // 瀏覽歷史不改動播放中的佇列；點選曲目後才切換。
            renderList(div, historyItems, 'history');
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
function closePlaylist(){if(playlistLoadController)playlistLoadController.abort();playlistLoadController=null;document.getElementById('playlist-detail').style.display='none';document.getElementById('playlists-list').style.display='';}

window.addEventListener('modules-changed', () => {
    if (!FlowModules.isEnabled('music') && audio) audio.pause();
});
