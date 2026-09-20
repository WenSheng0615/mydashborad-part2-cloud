let notesData = [];
let noteLayout = 'grid';
let editingNoteId = null;
document.addEventListener('DOMContentLoaded', loadNotes);
async function loadNotes() {
    try { notesData = (await FlowUI.request('/api/notes/')).notes || []; renderNotes(); }
    catch (error) { FlowUI.error(error); }
}
function switchNoteLayout(mode) {
    noteLayout = mode;
    document.getElementById('btn-note-grid').classList.toggle('active', mode === 'grid');
    document.getElementById('btn-note-list').classList.toggle('active', mode === 'list');
    renderNotes();
}
function renderNotes() {
    const box = document.getElementById('notes-view-container');
    box.className = noteLayout === 'grid' ? 'notes-grid' : 'notes-list';
    box.replaceChildren();
    if (!notesData.length) { box.append(FlowUI.node('p', '還沒有筆記，點擊 + 開始記錄。')); return; }
    const colors = {yellow: ['#4c472b','#e6c229'], blue: ['#2b3d52','#5dade2'], green: ['#283e2f','#58d68d'], pink: ['#4b2a2e','#ec7063']};
    for (const note of notesData) {
        const card = FlowUI.node('article', null, 'note-card');
        const [bg, border] = colors[note.color] || colors.yellow;
        card.style.backgroundColor = bg; card.style.borderLeft = `5px solid ${border}`;
        const head = FlowUI.node('div', null, 'note-header');
        if (note.image_url && FlowUI.url(note.image_url)) {
            const image = FlowUI.node('img'); image.src = FlowUI.url(note.image_url); image.alt = '筆記附件';
            image.style.cssText = 'max-width:100%;max-height:200px;object-fit:contain'; head.append(image);
        }
        head.append(FlowUI.node('div', note.title, 'note-title'), FlowUI.node('div', note.description || '無內容', 'note-desc'));
        const footer = FlowUI.node('div', null, 'note-footer');
        footer.append(FlowUI.node('span', note.created_at, 'note-time'));
        for (const [label, callback] of [['編輯', () => openNoteModal(note)], ['刪除', () => deleteNote(note.id)]]) {
            const button = FlowUI.node('button', label, 'btn-tool'); button.onclick = callback; footer.append(button);
        }
        card.append(head, footer); box.append(card);
    }
}
function openNoteModal(note = null) {
    editingNoteId = note && note.id || null;
    document.getElementById('note-modal').style.display = 'flex';
    document.querySelector('#note-modal .modal-title').textContent = note ? '編輯筆記' : '新增筆記';
    if (note) {
        document.getElementById('modal-note-title').value = note.title || '';
        document.getElementById('modal-note-desc').value = note.description || '';
        document.getElementById('modal-note-color').value = note.color || 'yellow';
    }
    document.getElementById('modal-note-image').disabled = !!note;
    document.getElementById('modal-note-title').focus();
}
function closeNoteModal() { document.getElementById('note-modal').style.display = 'none'; }
async function submitNote() {
    const title = document.getElementById('modal-note-title').value;
    if (!title.trim()) return showAlert('請填寫標題', '內容仍保留在編輯視窗。');
    const button = document.getElementById('note-save-btn');
    if (button.disabled) return;
    const form = new FormData();
    form.append('title', title); form.append('description', document.getElementById('modal-note-desc').value);
    form.append('color', document.getElementById('modal-note-color').value);
    if (editingNoteId) form.append('note_id', editingNoteId);
    else if (document.getElementById('modal-note-image').files[0]) form.append('image', document.getElementById('modal-note-image').files[0]);
    button.disabled = true; button.textContent = '儲存中…';
    try {
        await FlowUI.request(editingNoteId ? '/api/notes/edit' : '/api/notes/add', {method: 'POST', body: form});
        for (const id of ['modal-note-title','modal-note-desc','modal-note-image']) document.getElementById(id).value = '';
        editingNoteId = null; closeNoteModal(); await loadNotes();
    } catch (error) { FlowUI.error(error); }
    finally { button.disabled = false; button.textContent = '儲存'; }
}
async function deleteNote(id) {
    showConfirmModal('刪除筆記', '確定移除這張筆記？', async () => {
        try { const form = new FormData(); form.append('note_id', id); await FlowUI.request('/api/notes/delete', {method:'POST',body:form}); await loadNotes(); }
        catch (error) { FlowUI.error(error); }
    });
}
