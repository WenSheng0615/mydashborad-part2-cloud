let ws, chatCursor = null, chatRetry = 0, sendingChat = false;
if (!window.QRCode) { const script = document.createElement('script'); script.src = 'https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js'; document.head.append(script); }
document.addEventListener('DOMContentLoaded', () => { loadChatHistory(); connectWebSocket(); });
function connectWebSocket() {
    ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/chat/ws`);
    ws.onopen = () => { chatRetry = 0; };
    ws.onmessage = event => {
        const p = JSON.parse(event.data);
        if (p.type === 'new_message' || p.type === 'edit') renderMessage(p.data);
        else if (p.type === 'delete') handleWsDelete(p.data.id);
        else if (p.type === 'clear') loadChatHistory();
    };
    ws.onclose = event => { if (![4401,4403].includes(event.code)) setTimeout(connectWebSocket, Math.min(30000, 3000 * 2 ** chatRetry++)); };
}
async function loadChatHistory(older = false) {
    try {
        const data = await FlowUI.request('/api/chat/history' + (older && chatCursor ? '?before=' + encodeURIComponent(chatCursor) : ''));
        const box = document.getElementById('chat-messages');
        if (!older) box.replaceChildren();
        const fragment = document.createDocumentFragment();
        for (const msg of data.messages) if (!findMessage(msg.id)) fragment.append(buildMessageNode(msg));
        if (older) box.prepend(fragment); else box.append(fragment);
        chatCursor = data.next_cursor;
        document.getElementById('keep-older').hidden = !chatCursor;
        if (!box.children.length) renderEmptyState();
        if (!older) scrollToBottom();
    } catch(error) { FlowUI.error(error); }
}
function findMessage(id) { return [...document.querySelectorAll('.msg-wrapper')].find(node => node.dataset.msgId === id); }
function renderEmptyState() {
    const box = document.getElementById('chat-messages'); box.replaceChildren(FlowUI.node('p', '我的隨手記 · 記下文字、連結或檔案。', 'chat-empty-state'));
}
function buildMessageNode(msg) {
    const wrapper = FlowUI.node('div', null, 'msg-wrapper'); wrapper.dataset.msgId = msg.id;
    const actions = FlowUI.node('div', null, 'msg-actions');
    const action = (label, fn) => { const button = FlowUI.node('button', label, 'msg-btn'); button.onclick = fn; actions.append(button); };
    if (['text','link'].includes(msg.type)) action('編輯', () => openEditChatModal(msg.id, msg.content));
    action('刪除', () => deleteMessage(msg.id));
    const bubble = FlowUI.node('div', null, 'msg-bubble ' + (msg.type === 'text' ? 'text-card' : 'link-card'));
    const url = FlowUI.url(msg.content);
    if (['image','file','link'].includes(msg.type) && url) {
        const link = FlowUI.node('a', msg.type === 'image' ? '' : (msg.file_name || msg.content));
        link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer';
        if (msg.type === 'image') { const image = FlowUI.node('img'); image.src = url; image.alt = msg.file_name || '圖片'; image.className = 'chat-image'; link.append(image); }
        bubble.append(link);
    } else bubble.textContent = msg.content;
    const copy = FlowUI.node('button', '複製', 'msg-btn');
    copy.onclick = async () => { try { await navigator.clipboard.writeText(msg.content); copy.textContent = '已複製'; } catch(error) { FlowUI.error(error); } };
    actions.append(copy); wrapper.append(actions, bubble, FlowUI.node('div', msg.time, 'msg-time')); return wrapper;
}
function renderMessage(msg) {
    const old = findMessage(msg.id);
    if (old) old.replaceWith(buildMessageNode(msg));
    else { document.querySelector('.chat-empty-state')?.remove(); document.getElementById('chat-messages').append(buildMessageNode(msg)); }
    scrollToBottom();
}
function handleWsDelete(id) { findMessage(id)?.remove(); }
function scrollToBottom() { const box = document.getElementById('chat-messages'); box.scrollTop = box.scrollHeight; }
async function sendChat() {
    const input = document.getElementById('chat-input'); const content = input.value;
    if (sendingChat || !content.trim()) return;
    sendingChat = true;
    try { const form = new FormData(); form.append('content', content); const data = await FlowUI.request('/api/chat/send', {method:'POST',body:form}); if (input.value === content) input.value = ''; renderMessage(data.message); }
    catch(error) { FlowUI.error(error); } finally { sendingChat = false; }
}
function triggerFileUpload() { document.getElementById('chat-file-input').click(); }
async function onFileSelected(input) {
    if (!input.files[0]) return;
    try { const form = new FormData(); form.append('file',input.files[0]); const data = await FlowUI.request('/api/chat/upload',{method:'POST',body:form}); input.value=''; renderMessage(data.message); }
    catch(error) { FlowUI.error(error); }
}
function openEditChatModal(id, content) { document.getElementById('edit-msg-id').value=id; document.getElementById('edit-msg-content').value=content; document.getElementById('edit-chat-modal').style.display='flex'; }
function closeEditChatModal() { document.getElementById('edit-chat-modal').style.display='none'; }
async function submitEditChat() {
    try { const form=new FormData(); form.append('msg_id',document.getElementById('edit-msg-id').value); form.append('new_content',document.getElementById('edit-msg-content').value); await FlowUI.request('/api/chat/edit',{method:'POST',body:form}); closeEditChatModal(); await loadChatHistory(); }
    catch(error) { FlowUI.error(error); }
}
function deleteMessage(id) { showConfirmModal('刪除','確定刪除這筆紀錄？',async()=>{ try { const form=new FormData(); form.append('msg_id',id); await FlowUI.request('/api/chat/delete',{method:'POST',body:form}); handleWsDelete(id); } catch(error) { FlowUI.error(error); } }); }
function clearAllChat() { showConfirmModal('清空紀錄','此操作會刪除所有 Keep 紀錄。',async()=>{ try { await FlowUI.request('/api/chat/clear',{method:'POST'}); await loadChatHistory(); } catch(error) { FlowUI.error(error); } }); }
async function showQrCode() {
    document.getElementById('qr-modal').style.display='flex'; const box=document.getElementById('qrcode-container'); box.textContent='產生連結中…';
    try { const data=await FlowUI.request('/api/auth/device-link'); box.replaceChildren(); if (!window.QRCode) throw new Error('QR Code 元件尚未載入'); new QRCode(box,{text:data.url,width:170,height:170}); }
    catch(error) { box.textContent=error.message; }
}
function closeQrModal() { document.getElementById('qr-modal').style.display='none'; }
