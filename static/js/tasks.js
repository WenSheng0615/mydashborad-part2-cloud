let googleTaskListId = "@default";
document.addEventListener('DOMContentLoaded', () => {
    // Tasks is loaded by openApp only, after the user chooses this panel.
    // ★ 自動帶入今天日期 ★
    const today = new Date().toLocaleDateString('en-CA');
    const dateInput = document.getElementById('task-date');
    if (dateInput) dateInput.value = today;
});

async function loadTasks() {
    try {
        const data = await FlowUI.request('/api/tasks/');
        googleTaskListId = data.list_id || '@default';

        renderColumn('col-todo', data.todo, 'todo');
        renderColumn('col-doing', data.doing, 'doing');
        renderColumn('col-done', data.done, 'done');
    } catch (e) { FlowUI.error(e); }
}

function renderColumn(divId, tasks, stage) {
    const div = document.getElementById(divId); div.replaceChildren();
    if (!tasks?.length) { div.append(FlowUI.node('p','空')); return; }
    for (const task of tasks) {
        const card = FlowUI.node('div',null,'task-card'); card.draggable=true;
        card.dataset.id=task.id; card.dataset.stage=stage; card.ondragstart=drag;
        const date = (task.due_date || '').slice(0,10);
        const meta=FlowUI.node('div',null,'task-meta'), actions=FlowUI.node('div',null,'task-actions');
        const edit=FlowUI.node('button','編輯','task-btn');
        edit.onclick=()=>openEditTaskModal(task.id,encodeURIComponent(task.content),stage,date,'');
        const remove=FlowUI.node('button','刪除','task-btn del');remove.onclick=()=>deleteTask(task.id,stage);
        actions.append(edit,remove);meta.append(FlowUI.node('span',date ? `到期：${date}` : '未排日期','due-date-tag'),actions);
        card.append(FlowUI.node('div',task.content,'task-content'),meta);div.append(card);
    }
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

    if (!input.value.trim()) return;

    const fd = new FormData(); fd.append("list_id", googleTaskListId);
    fd.append('content', input.value);
    
    // Google Tasks 截止日期處理
    if (dateInput.value) {
        fd.append('due_date', dateInput.value); // 後端會處理成 RFC3339
    }

    await FlowUI.request('/api/tasks/add', { method: 'POST', body: fd });
    input.value = '';
    loadTasks();
}

async function moveTask(id, from, to) {
    const fd = new FormData(); fd.append("list_id", googleTaskListId);
    fd.append('task_id', id); fd.append('from_stage', from); fd.append('to_stage', to);
    await FlowUI.request('/api/tasks/move', { method: 'POST', body: fd });
    loadTasks();
}

async function deleteTask(id, stage) {
    showConfirmModal('刪除任務', '確定要刪除此任務？', async () => {
        const fd = new FormData(); fd.append("list_id", googleTaskListId);
        fd.append('task_id', id); fd.append('stage', stage);
        try { await FlowUI.request('/api/tasks/delete', { method: 'POST', body: fd }); await loadTasks(); }
        catch (error) { FlowUI.error(error); }
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

    const fd = new FormData(); fd.append("list_id", googleTaskListId);
    fd.append('task_id', id);
    fd.append('content', content);
    fd.append('stage', stage);
    fd.append('due_date', due);

    await FlowUI.request('/api/tasks/update', { method: 'POST', body: fd });
    closeEditTaskModal();
    loadTasks();
}
const taskWrites = new Set();
function guardedTaskWrite(key, fn) {
    return async (...args) => {
        if (taskWrites.has(key)) return;
        taskWrites.add(key);
        try { return await fn(...args); }
        catch (error) { FlowUI.error(error); }
        finally { taskWrites.delete(key); }
    };
}
addTask = guardedTaskWrite('add', addTask);
moveTask = guardedTaskWrite('move', moveTask);
submitEditTask = guardedTaskWrite('edit', submitEditTask);
