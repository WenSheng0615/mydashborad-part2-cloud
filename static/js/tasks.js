document.addEventListener('DOMContentLoaded', () => {
    loadTasks();
    // ★ 自動帶入今天日期 ★
    const today = new Date().toISOString().split('T')[0];
    const dateInput = document.getElementById('task-date');
    if (dateInput) dateInput.value = today;
});

async function loadTasks() {
    try {
        const res = await fetch('/api/tasks/');
        const data = await res.json();

        renderColumn('col-todo', data.todo, 'todo');
        renderColumn('col-doing', data.doing, 'doing');
        renderColumn('col-done', data.done, 'done');
    } catch (e) { }
}

function renderColumn(divId, tasks, stage) {
    const div = document.getElementById(divId);
    if (!tasks || tasks.length === 0) {
        div.innerHTML = `<div style="text-align:center; color:var(--text-sub); margin-top:20px; font-style:italic;">空</div>`;
        return;
    }

    let html = '';
    tasks.forEach(t => {
        const contentEnc = encodeURIComponent(t.content);
        // 解析日期與時間
        const dateVal = t.due_date ? t.due_date.split(' ')[0] : '';
        const timeVal = t.due_date && t.due_date.includes(' ') ? t.due_date.split(' ')[1] : '';
        const dueDisplay = t.due_date ? `<div class="due-date-tag"><i class="fa-regular fa-clock"></i> ${t.due_date}</div>` : '';

        html += `
            <div class="task-card" draggable="true" ondragstart="drag(event)" data-id="${t.id}" data-stage="${stage}">
                <div class="task-content">${t.content}</div>
                <div class="task-meta">
                    <div style="display:flex; flex-direction:column; gap:5px;">
                        <span style="opacity:0.7;">建立: ${t.created_at}</span>
                        ${dueDisplay}
                    </div>
                    <div class="task-actions">
                        <button class="task-btn" onclick="openEditTaskModal('${t.id}', '${contentEnc}', '${stage}', '${dateVal}', '${timeVal}')" title="編輯">
                            <i class="fa-solid fa-pen"></i>
                        </button>
                        <button class="task-btn del" onclick="deleteTask('${t.id}', '${stage}')" title="刪除">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </div>
                </div>
            </div>`;
    });
    div.innerHTML = html;
}

// 拖曳邏輯
function allowDrop(ev) { ev.preventDefault(); }
function drag(ev) {
    ev.dataTransfer.setData("taskId", ev.target.dataset.id);
    ev.dataTransfer.setData("fromStage", ev.target.dataset.stage);
    ev.target.classList.add('dragging');
}
function drop(ev, toStage) {
    ev.preventDefault();
    const taskId = ev.dataTransfer.getData("taskId");
    const fromStage = ev.dataTransfer.getData("fromStage");
    if (fromStage && toStage && fromStage !== toStage) {
        moveTask(taskId, fromStage, toStage);
    }
    document.querySelectorAll('.task-card').forEach(el => el.classList.remove('dragging'));
}

// CRUD
async function addTask() {
    const input = document.getElementById('task-input');
    const dateInput = document.getElementById('task-date');
    const timeInput = document.getElementById('task-time');

    if (!input.value.trim()) return;

    // 組合日期時間
    let due = "";
    if (dateInput.value) {
        due = dateInput.value;
        if (timeInput.value) due += " " + timeInput.value;
    }

    const fd = new FormData();
    fd.append('content', input.value);
    fd.append('due_date', due);

    await fetch('/api/tasks/add', { method: 'POST', body: fd });

    input.value = '';
    // 保留日期，清空時間方便連續輸入
    timeInput.value = '';
    loadTasks();
}

async function moveTask(id, from, to) {
    const fd = new FormData();
    fd.append('task_id', id); fd.append('from_stage', from); fd.append('to_stage', to);
    await fetch('/api/tasks/move', { method: 'POST', body: fd });
    loadTasks();
}

async function deleteTask(id, stage) {
    showConfirmModal('刪除任務', '確定要刪除此任務？', async () => {
        const fd = new FormData();
        fd.append('task_id', id); fd.append('stage', stage);
        await fetch('/api/tasks/delete', { method: 'POST', body: fd });
        loadTasks();
    });
}

// Edit Modal
function openEditTaskModal(id, contentEnc, stage, dateVal, timeVal) {
    document.getElementById('edit-task-id').value = id;
    document.getElementById('edit-task-stage').value = stage;
    document.getElementById('edit-task-content').value = decodeURIComponent(contentEnc);
    document.getElementById('edit-task-date').value = dateVal || "";
    document.getElementById('edit-task-time').value = timeVal || "";

    document.getElementById('edit-task-modal').style.display = 'flex';
}

function closeEditTaskModal() { document.getElementById('edit-task-modal').style.display = 'none'; }

async function submitEditTask() {
    const id = document.getElementById('edit-task-id').value;
    const stage = document.getElementById('edit-task-stage').value;
    const content = document.getElementById('edit-task-content').value;
    const dateVal = document.getElementById('edit-task-date').value;
    const timeVal = document.getElementById('edit-task-time').value;

    if (!content.trim()) return alert("內容不能為空");

    let due = "";
    if (dateVal) {
        due = dateVal;
        if (timeVal) due += " " + timeVal;
    }

    const fd = new FormData();
    fd.append('task_id', id);
    fd.append('content', content);
    fd.append('stage', stage);
    fd.append('due_date', due);

    await fetch('/api/tasks/update', { method: 'POST', body: fd });
    closeEditTaskModal();
    loadTasks();
}