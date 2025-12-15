let ws;

if (!window.QRCode) {
    const script = document.createElement('script');
    script.src = "https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js";
    document.head.appendChild(script);
}

document.addEventListener('DOMContentLoaded', initChat);

function initChat() {
    loadChatHistory();
    connectWebSocket();
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${protocol}://${window.location.host}/api/chat/ws`);
    ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.type === 'new_message') renderMessage(payload.data);
        else if (payload.type === 'system' && payload.action === 'reload') loadChatHistory();
    };
    ws.onclose = () => setTimeout(connectWebSocket, 3000);
}

async function loadChatHistory() {
    try {
        const res = await fetch('/api/chat/history');
        const data = await res.json();
        const container = document.getElementById('chat-messages');
        container.innerHTML = '';

        if (data.messages && data.messages.length > 0) {
            data.messages.forEach(msg => renderMessage(msg, false));
            scrollToBottom();
        } else {
            // ★ 修改：使用新的空狀態結構 ★
            container.innerHTML = `
                <div class="chat-empty-state">
                    <div class="chat-empty-content">
                        <div class="empty-icon"><i class="fa-solid fa-paper-plane"></i></div>
                        <div class="empty-text">跨裝置傳送門</div>
                        <div class="empty-sub">手機掃描 QR Code，即刻傳送文字與圖片</div>
                        <button class="empty-btn" onclick="showQrCode()">
                            <i class="fa-solid fa-qrcode"></i> 手機連線
                        </button>
                    </div>
                </div>`;
        }
    } catch (e) { }
}

async function sendChat() {
    const input = document.getElementById('chat-input');
    const content = input.value.trim();
    if (!content) return;
    input.value = '';

    // 按鈕特效
    const btn = document.querySelector('.btn-send');
    btn.style.transform = "scale(0.9)";
    setTimeout(() => btn.style.transform = "scale(1)", 150);

    await fetch(`/api/chat/send?content=${encodeURIComponent(content)}`, { method: 'POST' });
}

function renderMessage(msg, autoScroll = true) {
    const container = document.getElementById('chat-messages');

    // 如果有空狀態元素，移除它
    const emptyState = container.querySelector('.chat-empty-state');
    if (emptyState) emptyState.remove();

    const wrapper = document.createElement('div');
    wrapper.className = 'msg-wrapper';

    let contentHtml = '';
    let bubbleClass = 'msg-bubble';

    // 1. 圖片
    if (msg.type === 'image') {
        bubbleClass += ' image-card';
        contentHtml = `<a href="${msg.content}" target="_blank"><img src="${msg.content}" class="chat-image" onload="scrollToBottom()"></a>`;
    }
    // 2. YouTube 影片
    else if (getYTVideoId(msg.content)) {
        bubbleClass += ' video-card';
        const ytId = getYTVideoId(msg.content);
        contentHtml = `
            <img src="https://img.youtube.com/vi/${ytId}/hqdefault.jpg" class="yt-thumbnail">
            <i class="fa-solid fa-circle-play play-icon"></i>
        `;
        wrapper.onclick = (e) => { if (!e.target.closest('.msg-actions')) window.open(msg.content, '_blank'); };
    }
    // 3. 連結
    else if (msg.type === 'link') {
        bubbleClass += ' link-card';
        const imgHtml = msg.meta && msg.meta.image ? `<img src="${msg.meta.image}" style="width:40px; height:40px; border-radius:4px; object-fit:cover;">` : '<i class="fa-solid fa-link" style="font-size:1.5rem;"></i>';
        const title = msg.meta ? msg.meta.title : msg.content;
        let domain = '';
        try { domain = new URL(msg.content).hostname; } catch (e) { }

        contentHtml = `
            ${imgHtml}
            <div style="flex:1; overflow:hidden;">
                <div style="font-weight:bold; font-size:0.9rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${title}</div>
                <div class="link-domain">${domain}</div>
            </div>
            <i class="fa-solid fa-arrow-up-right-from-square" style="font-size:0.9rem; opacity:0.5;"></i>`;

        wrapper.onclick = (e) => { if (!e.target.closest('.msg-actions')) window.open(msg.content, '_blank'); };
    }
    // 4. 文字
    else {
        bubbleClass += ' text-card';
        contentHtml = `${msg.content}`;
        // 複製按鈕
        wrapper.innerHTML += `<button class="copy-btn" onclick="copyToClipboard('${encodeURIComponent(msg.content)}', this)" title="複製"><i class="fa-regular fa-copy"></i></button>`;
    }

    const encodedContent = encodeURIComponent(msg.content);

    // 組合 HTML
    const inner = `
        <div class="msg-actions">
            <button class="msg-btn" onclick="openEditChatModal('${msg.id}', '${encodedContent}')"><i class="fa-solid fa-pen"></i></button>
            <button class="msg-btn del" onclick="deleteMessage('${msg.id}')"><i class="fa-solid fa-trash"></i></button>
        </div>
        <div class="${bubbleClass}">
            ${contentHtml}
        </div>
        <div class="msg-time">${msg.time}</div>
    `;

    if (msg.type === 'text') wrapper.innerHTML += inner; // 文字的複製按鈕已加，直接 append inner
    else wrapper.innerHTML = inner;

    container.appendChild(wrapper);
    if (autoScroll) scrollToBottom();
}

function getYTVideoId(url) {
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
    const match = url.match(regExp);
    return (match && match[2].length === 11) ? match[2] : null;
}

function scrollToBottom() {
    const container = document.getElementById('chat-messages');
    container.scrollTop = container.scrollHeight;
}

function copyToClipboard(text, btn) {
    const decoded = decodeURIComponent(text);
    navigator.clipboard.writeText(decoded).then(() => {
        const icon = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-check" style="color:var(--accent);"></i>';
        setTimeout(() => btn.innerHTML = icon, 1500);
    });
}
async function showQrCode() {
    const modal = document.getElementById('qr-modal');
    const container = document.getElementById('qrcode-container');
    container.innerHTML = '<p style="color:#000;">取得 IP...</p>';
    modal.style.display = 'flex';
    try {
        const res = await fetch('/api/chat/ip'); const data = await res.json();
        container.innerHTML = '';
        new QRCode(container, { text: data.url, width: 170, height: 170, colorDark: "#000000", colorLight: "#ffffff", correctLevel: QRCode.CorrectLevel.H });
        document.getElementById('qr-ip-text').innerText = data.url;
    } catch (e) { container.innerHTML = '失敗'; }
}
function closeQrModal() { document.getElementById('qr-modal').style.display = 'none'; }
async function deleteMessage(id) { showConfirmModal('刪除', '確定刪除？', async () => { const fd = new FormData(); fd.append('msg_id', id); await fetch('/api/chat/delete', { method: 'POST', body: fd }); }); }
async function clearAllChat() { showConfirmModal('清空', '刪除所有紀錄？', async () => { await fetch('/api/chat/clear', { method: 'POST' }); }); }
function openEditChatModal(id, content) { document.getElementById('edit-msg-id').value = id; document.getElementById('edit-msg-content').value = decodeURIComponent(content); document.getElementById('edit-chat-modal').style.display = 'flex'; }
function closeEditChatModal() { document.getElementById('edit-chat-modal').style.display = 'none'; }
async function submitEditChat() { const id = document.getElementById('edit-msg-id').value; const content = document.getElementById('edit-msg-content').value; if (!content.trim()) return; const fd = new FormData(); fd.append('msg_id', id); fd.append('new_content', content); await fetch('/api/chat/edit', { method: 'POST', body: fd }); closeEditChatModal(); }