let currentFolderId = 'root';
let layoutMode = 'grid';
let currentFilesData = [];
let folderStack = [];
let currentSelectedFileId = null;
let currentSelectedFileName = "";

// 點擊空白處清除預覽
function handleContainerClick(event) {
    if (event.target.classList.contains('grid-files') ||
        event.target.classList.contains('file-container-wrapper') ||
        event.target.classList.contains('list-files')) {
        document.querySelectorAll('.file-card').forEach(el => el.classList.remove('selected'));
        currentSelectedFileId = null;
        currentSelectedFileName = "";
        document.getElementById('preview-area').innerHTML = `
            <div class="preview-placeholder">
                <i class="fa-regular fa-file" style="font-size:4rem; opacity:0.3; margin-bottom:15px;"></i>
                <p>點選檔案以檢視預覽</p>
            </div>`;
    }
}

function switchLayout(mode) {
    layoutMode = mode;
    const c = document.getElementById('file-container');
    document.getElementById('btn-grid').classList.toggle('active', mode === 'grid');
    document.getElementById('btn-list').classList.toggle('active', mode === 'list');
    c.className = mode === 'grid' ? 'grid-files' : 'list-files';
    renderFiles(currentFilesData);
}

async function applyFilters() {
    const type = document.getElementById('filter-type').value;
    const q = document.getElementById('drive-search').value;
    loadFiles(currentFolderId, q, type);
}

async function loadFiles(fid = 'root', q = '', type = '') {
    const c = document.getElementById('file-container');
    const btnBack = document.getElementById('btn-back');

    c.innerHTML = `
        <div style="height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; color:#888;">
            <i class="fa-solid fa-circle-notch fa-spin" style="font-size:2rem; margin-bottom:10px; color:var(--accent);"></i>
            <p>讀取中...</p>
        </div>`;

    if (fid !== 'root') btnBack.disabled = false; else btnBack.disabled = true;
    currentFolderId = fid;
    
    // 更新路徑顯示
    const pathEl = document.getElementById('current-path');
    if (pathEl) {
        pathEl.textContent = fid === 'root' ? 'Root' : fid;
        pathEl.style.cursor = "pointer";
        pathEl.onclick = () => {
            navigator.clipboard.writeText(fid);
            showAlert("通知", "資料夾 ID 已複製到剪貼簿");
        };
    }

    try {
        const params = new URLSearchParams({folder_id: fid, query: q, file_type: type});
        const data = await FlowUI.request(`/api/drive/files?${params}`);

        if (data.error && data.error.includes("Login")) {
            c.innerHTML = `<div style="text-align:center; padding:50px;"><p>請先登入 Google</p></div>`;
            return;
        }

        currentFilesData = data.files || [];
        if (!currentFilesData.length) {
            c.innerHTML = `<div style="text-align:center; padding:50px; color:#666;"><p>此資料夾為空</p></div>`;
            return;
        }
        renderFiles(currentFilesData);
    } catch (e) { c.innerHTML = '<p style="text-align:center; color:red;">連線錯誤</p>'; }
}

function renderFiles(files) {
    const container = document.getElementById('file-container');
    container.replaceChildren();
    files.forEach((file, index) => {
        const card = FlowUI.node('div', null, 'file-card'); card.id = `file-${index}`;
        card.onclick = event => selectFile(index, event); card.ondblclick = () => dblClick(index);
        const iconBox = FlowUI.node('div', null, 'file-icon-area');
        const icon = FlowUI.node('img', null, 'file-icon'); icon.src = getIconUrl(file.mimeType, file.name); icon.alt = '';
        iconBox.append(icon);
        const info = FlowUI.node('div', null, 'file-info');
        const name = FlowUI.node('div', file.name, 'file-name'); name.title = file.name; info.append(name);
        card.append(iconBox, info); container.append(card);
    });
}

function selectFile(index, event) {
    if (event) event.stopPropagation();
    document.querySelectorAll('.file-card').forEach(el => el.classList.remove('selected'));
    document.getElementById(`file-${index}`).classList.add('selected');
    const file = currentFilesData[index];
    currentSelectedFileId = file.id; currentSelectedFileName = file.name;
    const content = FlowUI.node('div', null, 'preview-content');
    const box = FlowUI.node('div', null, 'preview-image-box');
    const image = FlowUI.node('img'); image.alt = file.name;
    image.src = FlowUI.url(file.thumbnailLink || getIconUrl(file.mimeType, file.name));
    image.referrerPolicy = 'no-referrer'; box.append(image);
    const buttons = FlowUI.node('div');
    const open = FlowUI.node('button', '開啟', 'btn-preview-action btn-primary');
    const url = FlowUI.url(file.webViewLink); open.disabled = !url;
    open.onclick = () => window.open(url, '_blank', 'noopener,noreferrer');
    const remove = FlowUI.node('button', '移至回收桶', 'btn-preview-action btn-secondary');
    remove.onclick = event => deleteFile(file.id, event); buttons.append(open, remove);
    content.append(box, FlowUI.node('div', file.name, 'preview-header'),
        FlowUI.node('div', `修改：${new Date(file.modifiedTime).toLocaleDateString()}`, 'preview-details'), buttons);
    document.getElementById('preview-area').replaceChildren(content);
}

function dblClick(idx) {
    const f = currentFilesData[idx];
    if (f.mimeType.includes('folder')) { folderStack.push(currentFolderId); loadFiles(f.id); }
    else { const url = FlowUI.url(f.webViewLink); if (url) window.open(url, '_blank', 'noopener,noreferrer'); }
}

function goUpFolder() { if (folderStack.length) loadFiles(folderStack.pop()); else loadFiles('root'); }

async function uploadFile() {
    const fileInput = document.getElementById('file-upload');
    const file = fileInput.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    fd.append('folder_id', currentFolderId);
    try {
        await FlowUI.request('/api/drive/upload', { method: 'POST', body: fd });
        fileInput.value = ''; await loadFiles(currentFolderId);
    } catch (error) { FlowUI.error(error); }
}

async function deleteFile(fileId, event) {
    if (event) event.stopPropagation();
    showConfirmModal('移至回收桶', '檔案將移至 Google Drive 回收桶，可至 Google Drive 還原。是否繼續？', async () => {
        const c = document.getElementById('file-container');
        c.style.opacity = '0.5';
        const fd = new FormData();
        fd.append('file_id', fileId);
        try {
            await FlowUI.request('/api/drive/delete', { method: 'POST', body: fd });
            document.getElementById('preview-area').replaceChildren();
            currentSelectedFileId = null; currentSelectedFileName = '';
            await loadFiles(currentFolderId);
        } catch (error) { FlowUI.error(error); }
        finally { c.style.opacity = '1'; }
    });
}

// === 移動檔案專用邏輯 ===
function prepareMoveFile() {
    if (!currentSelectedFileId) return showAlert("提示", "請先選取檔案");
    document.getElementById('move-file-name').innerText = currentSelectedFileName;
    document.getElementById('move-target-id').value = "";
    document.getElementById('move-modal').style.display = 'flex';
}

function closeMoveModal() {
    document.getElementById('move-modal').style.display = 'none';
}

async function submitMove() {
    const targetId = document.getElementById('move-target-id').value.trim();
    if (!targetId) return showAlert("提示", "請輸入目標 ID");
    
    const btn = document.querySelector('#move-modal .btn-confirm');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = "搬移中...";

    const fd = new FormData();
    fd.append('file_id', currentSelectedFileId);
    fd.append('folder_id', targetId);

    try {
        const res = await fetch('/api/drive/move', { method: 'POST', body: fd });
        const data = await res.json();
        if (data.status === 'success') {
            closeMoveModal();
            showAlert("✅ 成功", `檔案 "${currentSelectedFileName}" 已成功移動。`, () => {
                currentSelectedFileId = null;
                loadFiles(currentFolderId);
            });
        } else {
            showAlert("❌ 失敗", "搬移檔案時發生錯誤，請檢查目標 ID。");
        }
    } catch (e) { showAlert("⚠️ 連線錯誤", "無法連接到伺服器。"); } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
}

function getIconUrl(mime, name) {
    const base = 'https://cdn.jsdelivr.net/gh/vscode-icons/vscode-icons/icons/';
    if (mime.includes('folder')) return `${base}default_folder.svg`;
    const ext = name.split('.').pop().toLowerCase();
    const map = { 'pdf': 'file_type_pdf.svg', 'doc': 'file_type_word.svg', 'docx': 'file_type_word.svg', 'xls': 'file_type_excel.svg', 'xlsx': 'file_type_excel.svg', 'ppt': 'file_type_powerpoint.svg', 'txt': 'file_type_text.svg', 'zip': 'file_type_zip.svg', 'jpg': 'file_type_image.svg', 'png': 'file_type_image.svg', 'mp3': 'file_type_audio.svg', 'mp4': 'file_type_video.svg', 'py': 'file_type_python.svg', 'js': 'file_type_js.svg', 'html': 'file_type_html.svg', 'css': 'file_type_css.svg' };
    return map[ext] ? `${base}${map[ext]}` : `${base}default_file.svg`;
}
