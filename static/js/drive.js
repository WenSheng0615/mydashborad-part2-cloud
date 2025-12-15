let currentFolderId = 'root';
let layoutMode = 'grid';
let currentFilesData = [];
let folderStack = [];

// 點擊空白處清除預覽
function handleContainerClick(event) {
    if (event.target.classList.contains('grid-files') ||
        event.target.classList.contains('file-container-wrapper') ||
        event.target.classList.contains('list-files')) {
        document.querySelectorAll('.file-card').forEach(el => el.classList.remove('selected'));
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

    // ★ 優化：漂亮的載入動畫 ★
    c.innerHTML = `
        <div style="height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; color:#888;">
            <i class="fa-solid fa-circle-notch fa-spin" style="font-size:2rem; margin-bottom:10px; color:var(--accent);"></i>
            <p>讀取中...</p>
        </div>`;

    if (fid !== 'root') btnBack.disabled = false; else btnBack.disabled = true;
    currentFolderId = fid;

    try {
        const res = await fetch(`/api/drive/files?folder_id=${fid}&query=${q}&file_type=${type}`);
        const data = await res.json();

        if (data.error && data.error.includes("Login")) {
            c.innerHTML = `
                <div style="text-align:center; padding:50px; color:#ff4d4f;">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size:2rem; margin-bottom:10px;"></i>
                    <p>請先登入 Google 帳號</p>
                    <button class="btn-tool" style="width:auto; padding:5px 15px; margin-top:10px;" onclick="checkLogin(true)">登入</button>
                </div>`;
            return;
        }

        const sourceSpan = document.getElementById('data-source');
        if (sourceSpan) sourceSpan.innerText = data.source === 'redis' ? '⚡ Redis' : '🐢 Google';

        currentFilesData = data.files || [];
        if (!currentFilesData.length) {
            c.innerHTML = `
                <div style="text-align:center; padding:50px; color:#666;">
                    <i class="fa-regular fa-folder-open" style="font-size:3rem; margin-bottom:10px; opacity:0.5;"></i>
                    <p>此資料夾為空</p>
                </div>`;
            return;
        }
        renderFiles(currentFilesData);
    } catch (e) { c.innerHTML = '<p style="text-align:center; color:red;">連線錯誤</p>'; }
}

function renderFiles(files) {
    const c = document.getElementById('file-container');
    c.className = layoutMode === 'grid' ? 'grid-files' : 'list-files';
    let html = '';

    files.forEach((f, idx) => {
        let iconHtml = '';
        const isFolder = f.mimeType.includes('folder');

        const iconUrl = getIconUrl(f.mimeType, f.name);
        iconHtml = `<img src="${iconUrl}" class="file-icon" alt="icon">`;


        html += `
            <div class="file-card" id="file-${idx}" onclick="selectFile(${idx})" ondblclick="dblClick(${idx})">
                <div class="file-icon-area">${iconHtml}</div>
                <div class="file-info"><div class="file-name" title="${f.name}">${f.name}</div></div>
            </div>`;
    });
    c.innerHTML = html;
}

function selectFile(idx) {
    event.stopPropagation();
    document.querySelectorAll('.file-card').forEach(el => el.classList.remove('selected'));
    document.getElementById(`file-${idx}`).classList.add('selected');

    const f = currentFilesData[idx];
    const isFolder = f.mimeType.includes('folder');
    let preview = f.thumbnailLink && !isFolder ?
        `<img src="${f.thumbnailLink.replace('s220', 's600')}" referrerpolicy="no-referrer">` :
        `<img src="${getIconUrl(f.mimeType, f.name)}" style="width:120px; height:120px; object-fit:contain;">`;

    let statusText = f.thumbnailLink ? "可預覽" : "無預覽";

    document.getElementById('preview-area').innerHTML = `
        <div class="preview-content">
            <div class="preview-image-box">${preview}</div>
            <div style="text-align:center; font-weight:bold; margin-bottom:20px; word-break:break-all;">${f.name}</div>
            <div class="preview-details" style="flex:1;">
                <div class="detail-row"><span class="detail-label">類型</span><span>${isFolder ? 'Folder' : f.mimeType.split('/').pop()}</span></div>
                <div class="detail-row"><span class="detail-label">修改</span><span>${new Date(f.modifiedTime).toLocaleDateString()}</span></div>
            </div>
            <div style="display:flex; gap:10px; margin-top:20px;">
                <button class="btn-preview-action btn-primary" onclick="window.open('${f.webViewLink}','_blank')">開啟</button>
                <button class="btn-preview-action btn-secondary" onclick="deleteFile('${f.id}', event)">刪除</button>
            </div>
        </div>`;
}

function dblClick(idx) {
    const f = currentFilesData[idx];
    if (f.mimeType.includes('folder')) { folderStack.push(currentFolderId); loadFiles(f.id); }
    else window.open(f.webViewLink, '_blank');
}

function goUpFolder() { if (folderStack.length) loadFiles(folderStack.pop()); else loadFiles('root'); }

// ★★★ 上傳優化 (無 Alert，改用 UI 狀態) ★★★
async function uploadFile() {
    const fileInput = document.getElementById('file-upload');
    const file = fileInput.files[0];
    if (!file) return;

    const fd = new FormData();
    fd.append('file', file);
    fd.append('folder_id', currentFolderId);

    // 顯示上傳中狀態
    const c = document.getElementById('file-container');
    c.innerHTML = `
        <div style="height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; color:var(--accent);">
            <i class="fa-solid fa-cloud-arrow-up fa-spin" style="font-size:3rem; margin-bottom:15px;"></i>
            <p>正在上傳檔案...</p>
        </div>`;

    try {
        await fetch('/api/drive/upload', { method: 'POST', body: fd });
    } catch (e) {
        console.error(e);
        alert("上傳失敗");
    }

    fileInput.value = '';
    loadFiles(currentFolderId); // 重新載入
}

// ★★★ 刪除優化 (改用 showConfirmModal) ★★★
async function deleteFile(fileId, event) {
    if (event) event.stopPropagation();

    // 使用全域彈窗 (定義在 index.html)
    showConfirmModal('刪除檔案', '確定要永久刪除此檔案嗎？', async () => {
        const c = document.getElementById('file-container');
        c.style.opacity = '0.5'; // 視覺回饋：變暗

        const fd = new FormData();
        fd.append('file_id', fileId);
        fd.append('folder_id', currentFolderId || 'root');

        await fetch('/api/drive/delete', { method: 'POST', body: fd });

        c.style.opacity = '1';
        loadFiles(currentFolderId);

        // 重置預覽區
        document.getElementById('preview-area').innerHTML = `
            <div class="preview-placeholder">
                <i class="fa-regular fa-file" style="font-size:4rem; opacity:0.3; margin-bottom:15px;"></i>
                <p>點選檔案以檢視預覽</p>
            </div>`;
    });
}

function getIconUrl(mime, name) {
    const base = 'https://cdn.jsdelivr.net/gh/vscode-icons/vscode-icons/icons/';
    if (mime.includes('folder')) return `${base}default_folder.svg`;
    const ext = name.split('.').pop().toLowerCase();
    const map = { 'pdf': 'file_type_pdf.svg', 'doc': 'file_type_word.svg', 'docx': 'file_type_word.svg', 'xls': 'file_type_excel.svg', 'xlsx': 'file_type_excel.svg', 'ppt': 'file_type_powerpoint.svg', 'txt': 'file_type_text.svg', 'zip': 'file_type_zip.svg', 'jpg': 'file_type_image.svg', 'png': 'file_type_image.svg', 'mp3': 'file_type_audio.svg', 'mp4': 'file_type_video.svg', 'py': 'file_type_python.svg', 'js': 'file_type_js.svg', 'html': 'file_type_html.svg', 'css': 'file_type_css.svg' };
    return map[ext] ? `${base}${map[ext]}` : `${base}default_file.svg`;
}