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

function syncMiniPlayer() {
    const mini = document.getElementById('music-mini-player');
    if (!mini) return;
    mini.hidden = !currentSong;
    if (currentSong) {
        const cover = musicCover(currentSong.thumbnail) || musicFallbackCover;
        const image = document.getElementById('music-mini-cover');
        if (image.src !== cover) image.src = cover;
        document.getElementById('music-mini-title').textContent = currentSong.title || '未知曲目';
        document.getElementById('music-mini-artist').textContent = currentSong.channel || 'YouTube';
        mini.setAttribute('aria-label', `目前播放：${currentSong.title || '未知曲目'}，${currentSong.channel || 'YouTube'}`);
    }
    document.getElementById('music-mini-prev').disabled = currentTrackIndex <= 0;
    const toggle = document.getElementById('music-mini-toggle');
    toggle.setAttribute('aria-label', isPlaying ? '暫停' : '播放');
    toggle.querySelector('path').setAttribute('d', isPlaying ? 'M6 5h4v14H6z M14 5h4v14h-4z' : 'M8 5v14l11-7z');
}
let musicSheet = null;
function showFullMusicPlayer() {
    musicSheet?.open();syncMiniPlayer();
}
function closeFullMusicPlayer() {
    musicSheet?.close();
}
function initMiniPlayer() {
    const view = document.getElementById('view-music');
    const layout = view.querySelector('.music-layout');
    const player = layout.querySelector('.now-playing');
    const side = layout.querySelector('.playlist-side');
    const tabs = side.querySelector('.tab-group');
    const mini = document.getElementById('music-mini-player');
    const dialog = document.getElementById('music-player-dialog');
    const mobile = matchMedia('(max-width:768px)');
    musicSheet = createMusicSheet({sheet:dialog,grip:document.getElementById('music-sheet-grip'),cover:document.getElementById('player-art-container')});
    // Only controls move: the single audio node stays connected at the view root.
    const updateLayout = () => {
        if (mobile.matches) {
            view.insertBefore(tabs, mini);
            document.getElementById('music-sheet-body').append(player);
        } else {
            musicSheet.closeNow();layout.prepend(player);side.prepend(tabs);
        }
        syncMiniPlayer();
    };
    dialog.addEventListener('close', syncMiniPlayer);
    tabs.querySelectorAll('[role=tab]').forEach((button,index,buttons) => {
        button.addEventListener('keydown', event => {
            let next;
            if (event.key === 'ArrowRight') next = (index + 1) % buttons.length;
            if (event.key === 'ArrowLeft') next = (index + buttons.length - 1) % buttons.length;
            if (event.key === 'Home') next = 0;
            if (event.key === 'End') next = buttons.length - 1;
            if (next === undefined) return;
            event.preventDefault();buttons[next].click();buttons[next].focus();
        });
    });
    mobile.addEventListener('change', updateLayout);updateLayout();
}

function mediaStatus(text) {
    const status = document.getElementById('music-playback-status');
    if (status) status.textContent = text;
    const mobileStatus = document.getElementById('music-mobile-status');
    if (mobileStatus) mobileStatus.textContent = text;
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

// URL detection is host/path based; an 11-character keyword remains a search.
function extractVideoId(value) {
    try {
        const candidate = /^(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)\//i.test(value) ? 'https://' + value : value;
        const url = new URL(candidate);
        if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || url.port) return null;
        const host = url.hostname.toLowerCase(), path = url.pathname.split('/').filter(Boolean);
        let id;
        if (host === 'youtu.be' || host === 'www.youtu.be') {
            if (path.length === 1) id = path[0];
        } else if (['youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'].includes(host)) {
            if (url.pathname === '/watch') id = url.searchParams.get('v');
            else if (path.length === 2 && ['shorts', 'live', 'embed'].includes(path[0])) id = path[1];
        }
        return /^[A-Za-z0-9_-]{11}$/.test(id || '') ? id : null;
    } catch { return null; }
}

function onMusicSearchInput() {
    const div = document.getElementById('yt-results');
    const pending = musicListRequests.get(div);
    if (pending) {musicListRequests.delete(div);pending.controller.abort();}
    div.setAttribute('aria-busy', 'false');
    if (div.querySelector('.music-link-preview, .content-skeleton')) {
        div.replaceChildren();delete div.dataset.musicSource;
    }
    div.querySelector('.content-refresh-error')?.remove();
    document.getElementById('music-search-message').textContent = '';
    document.getElementById('yt-search-input').removeAttribute('aria-invalid');
}

function renderMusicLink(div, id, data = null) {
    const song = {
        id, title: typeof data?.title === 'string' && data.title.trim() ? data.title : 'YouTube 歌曲',
        channel: typeof data?.author_name === 'string' ? data.author_name : 'YouTube',
        thumbnail: `https://img.youtube.com/vi/${id}/mqdefault.jpg`
    };
    const preview = FlowUI.node('article', null, 'music-link-preview');
    preview.setAttribute('aria-label', '連結歌曲預覽');
    const cover = FlowUI.node('img');cover.src = song.thumbnail;cover.alt = '';
    cover.onerror = () => {cover.onerror = null;cover.src = musicFallbackCover;};
    const info = FlowUI.node('div', null, 'music-link-info');
    info.append(FlowUI.node('span', 'YOUTUBE', 'music-link-source'), FlowUI.node('h3', song.title), FlowUI.node('p', song.channel));
    if (!data) info.append(FlowUI.node('p', '暫時無法取得名稱，可直接嘗試播放。', 'music-link-fallback'));
    const play = FlowUI.node('button', '播放', 'music-link-play');play.type = 'button';
    play.setAttribute('aria-label', '播放這首歌曲');
    play.onclick = () => {musicQueue = [song, ...musicQueue];playTrack(0);};
    preview.append(cover, info, play);div.replaceChildren(preview);
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
    document.querySelectorAll('#view-music [role=tab]').forEach(button => {
        const active = button.id === 'music-tab-' + name;
        button.setAttribute('aria-selected', String(active));button.tabIndex = active ? 0 : -1;
    });
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

// Preserve a completed view while refreshing; only first visits show static shapes.
const musicListRequests = new WeakMap();
async function refreshMusicList(div, url, render, retry, onFailure = null) {
    const previous = musicListRequests.get(div);
    if (previous?.url === url) return;
    previous?.controller.abort();
    const request = {url, controller: new AbortController()};
    musicListRequests.set(div, request);
    const keepContent = div.dataset.musicSource === url;
    div.querySelector('.content-refresh-error')?.remove();
    if (!keepContent) {
        delete div.dataset.musicSource;
        div.replaceChildren(FlowUI.skeleton());
    }
    div.setAttribute('aria-busy', 'true');
    const timeout = setTimeout(() => request.controller.abort(), 20000);
    try {
        const data = await FlowUI.request(url, {signal: request.controller.signal});
        if (musicListRequests.get(div) !== request) return;
        if (data.error) throw new Error('Provider unavailable');
        render(data);
        div.dataset.musicSource = url;
    } catch (_) {
        if (musicListRequests.get(div) !== request) return;
        if (onFailure) {onFailure();return;}
        const state = FlowUI.node('div', null, 'content-refresh-error');
        state.setAttribute('role', 'status');
        state.append(FlowUI.node('span', keepContent ? '暫時無法更新，已保留目前內容。' : '暫時無法取得內容，請再試一次。'));
        const button = FlowUI.node('button', '重試');
        button.type = 'button';button.onclick = retry;state.append(button);
        if (keepContent) div.append(state); else div.replaceChildren(state);
    } finally {
        clearTimeout(timeout);
        if (musicListRequests.get(div) === request) {
            div.setAttribute('aria-busy', 'false');
            musicListRequests.delete(div);
        }
    }
}

async function searchYouTube() {
    const input = document.getElementById('yt-search-input');
    const q = input.value.trim();
    if (!q) return;
    const div = document.getElementById('yt-results');
    const id = extractVideoId(q);
    const looksLikeLink = /^(?:[a-z][a-z\d+.-]*:|\/\/|www\.|(?:youtube\.com|youtu\.be)(?:[/?#]|$)|[^\s/]+\.[a-z]{2,}\/)/i.test(q);
    if (!id && looksLikeLink) {
        onMusicSearchInput();
        input.setAttribute('aria-invalid', 'true');
        document.getElementById('music-search-message').textContent = '請貼上有效的 YouTube 單曲連結，或改用歌名、歌手搜尋。';
        return;
    }
    input.removeAttribute('aria-invalid');
    document.getElementById('music-search-message').textContent = '';
    if (id) {
        const url = 'https://www.youtube.com/oembed?' + new URLSearchParams({url:`https://www.youtube.com/watch?v=${id}`,format:'json'});
        return refreshMusicList(div, url, data => renderMusicLink(div, id, data), searchYouTube,
            () => renderMusicLink(div, id));
    }
    return refreshMusicList(div, `/api/music/search?query=${encodeURIComponent(q)}`,
        data => {
            const items = data.items || [];
            renderList(div, items, 'search');
            if (!items.length) div.append(FlowUI.node('p', '找不到符合的歌曲，試試其他關鍵字。'));
        }, searchYouTube);
}

async function loadPlaylists() {
    const div = document.getElementById('playlists-list');
    return refreshMusicList(div, '/api/music/playlists', data => {
        const playlists = data.playlists || [];div.replaceChildren();
        if (!playlists.length) {div.append(FlowUI.node('p', '沒有找到歌單'));return;}
        for (const playlist of playlists) {
            const row = musicRow(playlist.title, `${playlist.count} songs`, playlist.thumbnail);
            row.onclick = () => loadPlaylistItems(playlist.id, playlist.title);div.append(row);
        }
    }, loadPlaylists);
}

function playlistLoadingState() {
    return FlowUI.skeleton('正在載入歌單');
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
    return refreshMusicList(div, '/api/music/history', data => {
        const items = data.items || [];
        // Browsing history never replaces the active playback queue.
        renderList(div, items, 'history');
        if (!items.length) div.append(FlowUI.node('p', '尚無播放紀錄'));
    }, loadHistory);
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
    if (!FlowModules.isEnabled('music') && audio) {audio.pause();musicSheet?.closeNow();}
});
