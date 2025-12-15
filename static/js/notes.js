let notesData = [];
let noteLayout = 'grid'; // 預設格狀

document.addEventListener('DOMContentLoaded', loadNotes);

async function loadNotes() {
    const res = await fetch('/api/notes/');
    const data = await res.json();
    notesData = data.notes || [];
    renderNotes();
}

// 切換版面
function switchNoteLayout(mode) {
    noteLayout = mode;
    document.getElementById('btn-note-grid').classList.toggle('active', mode === 'grid');
    document.getElementById('btn-note-list').classList.toggle('active', mode === 'list');
    renderNotes();
}

// ★ 核心渲染：配色與版面 ★
function renderNotes() {
    const container = document.getElementById('notes-view-container');
    container.className = noteLayout === 'grid' ? 'notes-grid' : 'notes-list';

    if (notesData.length === 0) {
        container.innerHTML = `
            <div style="grid-column:1/-1; text-align:center; color:#666; margin-top:50px;">
                <i class="fa-regular fa-note-sticky" style="font-size:3rem; margin-bottom:15px; opacity:0.5;"></i>
                <p>這裡空空的，點擊 + 新增筆記</p>
            </div>`;
        return;
    }

    let html = '';

    // ★ Google Keep 深色模式配色 (不刺眼但有區分) ★
    const colors = {
        'yellow': { bg: '#4c472b', border: '#e6c229' }, // 暗黃
        'blue': { bg: '#2b3d52', border: '#5dade2' }, // 暗藍
        'green': { bg: '#283e2f', border: '#58d68d' }, // 暗綠
        'pink': { bg: '#4b2a2e', border: '#ec7063' }  // 暗紅
    };

    notesData.forEach(note => {
        // 取得配色，若無則預設黃色
        const theme = colors[note.color] || colors['yellow'];

        // ★ 強制寫入背景色與邊框色 ★
        const style = `background-color: ${theme.bg} !important; border-left: 5px solid ${theme.border} !important;`;

        // 內容處理 (換行)
        const descHtml = note.description ? `<div class="note-desc">${note.description}</div>` : '<div class="note-desc" style="opacity:0.5; font-style:italic;">無內容</div>';

        if (noteLayout === 'grid') {
            // === 格狀卡片 ===
            html += `
                <div class="note-card" style="${style}">
                    <div class="note-header">
                        <div class="note-title">${note.title}</div>
                        ${descHtml}
                    </div>
                    <div class="note-footer">
                        <span class="note-time">${note.created_at}</span>
                        <button onclick="deleteNote('${note.id}')" class="note-del-btn"><i class="fa-solid fa-trash"></i></button>
                    </div>
                </div>`;
        } else {
            // === 條列清單 ===
            html += `
                <div class="note-card" style="${style}">
                    <div class="note-content-wrapper">
                        <div class="note-title" style="min-width:150px;">${note.title}</div>
                        ${descHtml}
                    </div>
                    <div class="note-footer" style="margin-left:20px; border:none; padding:0;">
                        <span class="note-time">${note.created_at}</span>
                        <button onclick="deleteNote('${note.id}')" class="note-del-btn"><i class="fa-solid fa-trash"></i></button>
                    </div>
                </div>`;
        }
    });
    container.innerHTML = html;
}

// Modal & CRUD
function openNoteModal() {
    document.getElementById('note-modal').style.display = 'flex';
    document.getElementById('modal-note-title').focus();
}

function closeNoteModal() { document.getElementById('note-modal').style.display = 'none'; }

async function submitNote() {
    const title = document.getElementById('modal-note-title').value;
    const desc = document.getElementById('modal-note-desc').value;
    const color = document.getElementById('modal-note-color').value;

    if (!title.trim()) return alert("請輸入標題");

    const fd = new FormData();
    fd.append('title', title);
    fd.append('description', desc);
    fd.append('color', color);

    await fetch('/api/notes/add', { method: 'POST', body: fd });

    document.getElementById('modal-note-title').value = '';
    document.getElementById('modal-note-desc').value = '';
    closeNoteModal();
    loadNotes();
}

async function deleteNote(id) {
    showConfirmModal('刪除筆記', '確定刪除這張筆記嗎？', async () => {
        const fd = new FormData();
        fd.append('note_id', id);
        await fetch('/api/notes/delete', { method: 'POST', body: fd });
        loadNotes();
    });
}