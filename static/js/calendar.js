let currentDate = new Date();
let currentMonthEvents = [];
// ★ 初始化預設選中今天 ★
let selectedDateStr = new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD

async function initCalendar() {
    // 確保回到今天時更新變數
    if (!selectedDateStr) selectedDateStr = new Date().toLocaleDateString('en-CA');
    renderCalendar();
    document.getElementById('cal-month-title').innerText += " (同步中...)";
    await fetchEvents();
}

function renderCalendar() {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const monthNames = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"];
    document.getElementById('cal-month-title').innerText = `${year}年 ${monthNames[month]}`;

    const grid = document.getElementById('calendar-grid');
    grid.innerHTML = '';

    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const todayStr = new Date().toLocaleDateString('en-CA');

    // 填補空白
    for (let i = 0; i < firstDay; i++) {
        grid.innerHTML += `<div class="day-cell empty"></div>`;
    }

    for (let i = 1; i <= daysInMonth; i++) {
        const mm = String(month + 1).padStart(2, '0');
        const dd = String(i).padStart(2, '0');
        const dateStr = `${year}-${mm}-${dd}`;

        const isToday = (dateStr === todayStr);
        const isSelected = (dateStr === selectedDateStr);

        // 渲染紅點
        const dayEvents = currentMonthEvents.filter(e => {
            const s = e.start.split('T')[0];
            const end = e.end.split('T')[0];
            // 判斷日期是否在行程範圍內
            if (e.is_all_day) return dateStr >= s && dateStr < end;
            return dateStr >= s && dateStr <= end;
        });

        let dotsHtml = '';
        if (dayEvents.length > 0) {
            const count = Math.min(dayEvents.length, 3);
            for (let k = 0; k < count; k++) dotsHtml += `<div class="event-dot"></div>`;
        }

        grid.innerHTML += `
            <div class="day-cell ${isToday ? 'today' : ''} ${isSelected ? 'selected' : ''}" 
                 id="date-${dateStr}" onclick="selectDate('${dateStr}')">
                <div class="day-number">${i}</div>
                <div class="event-dots">${dotsHtml}</div>
            </div>`;
    }
}

async function fetchEvents() {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth() + 1;
    try {
        const data = await FlowUI.request(`/api/calendar/events?year=${year}&month=${month}`);

        // 移除 loading
        const title = document.getElementById('cal-month-title').innerText.split(' (')[0];
        document.getElementById('cal-month-title').innerText = title;

        if (data.error) return;
        currentMonthEvents = data.events || [];

        renderCalendar(); // 重繪紅點
        if (document.getElementById(`date-${selectedDateStr}`)) selectDate(selectedDateStr);

    } catch (e) { FlowUI.error(e); }
}

function selectDate(dateStr) {
    selectedDateStr = dateStr;
    document.querySelectorAll('.day-cell').forEach(el => el.classList.remove('selected'));
    const cell = document.getElementById(`date-${dateStr}`);
    if (cell) cell.classList.add('selected');

    document.getElementById('selected-date-title').innerText = `${dateStr} 行程`;
    const list = document.getElementById('event-list');

    const events = currentMonthEvents.filter(e => {
        const s = e.start.split('T')[0];
        const end = e.end.split('T')[0];
        if (e.is_all_day) return dateStr >= s && dateStr < end;
        return dateStr >= s && dateStr <= end;
    });

    if (events.length === 0) {
        list.innerHTML = '<div style="text-align:center; color:var(--text-sub); margin-top:50px;">無行程</div>';
    } else {
        list.replaceChildren();
        events.forEach(e => {
            const card = FlowUI.node('div', null, 'event-card');
            const time = e.is_all_day ? '全天' : `${new Date(e.start).toLocaleTimeString('zh-TW')} – ${new Date(e.end).toLocaleTimeString('zh-TW')}`;
            const actions = FlowUI.node('div', null, 'event-actions');
            const edit = FlowUI.node('button', '編輯', 'event-action-btn');
            edit.onclick = () => openEventModal('edit', encodeURIComponent(JSON.stringify(e)));
            const remove = FlowUI.node('button', '刪除', 'event-action-btn del');
            remove.onclick = () => deleteEvent(e.id);
            actions.append(edit, remove);
            card.append(FlowUI.node('div', time, 'event-time'), FlowUI.node('div', e.summary, 'event-title'), actions);
            list.append(card);
        });
    }
}

// === Modal & CRUD ===
function openEventModal(mode, dataStr = null) {
    const modal = document.getElementById('event-modal');
    const title = document.getElementById('event-modal-title');

    document.getElementById('evt-id').value = "";
    document.getElementById('evt-summary').value = "";
    document.getElementById('evt-desc').value = "";

    if (mode === 'add') {
        title.innerText = "新增行程";
        // ★ 關鍵：預設日期為當前選取的日期 ★
        document.getElementById('evt-start-date').value = selectedDateStr;
        document.getElementById('evt-end-date').value = selectedDateStr;
        document.getElementById('evt-start-time').value = "09:00";
        document.getElementById('evt-end-time').value = "10:00";
        document.getElementById('evt-all-day').checked = false;
    } else if (mode === 'edit' && dataStr) {
        title.innerText = "編輯行程";
        const evt = JSON.parse(decodeURIComponent(dataStr));
        document.getElementById('evt-id').value = evt.id;
        document.getElementById('evt-summary').value = evt.summary;
        document.getElementById('evt-desc').value = evt.description || "";

        if (evt.is_all_day) {
            document.getElementById('evt-all-day').checked = true;
            document.getElementById('evt-start-date').value = evt.start;
            document.getElementById('evt-end-date').value = evt.end;
        } else {
            document.getElementById('evt-all-day').checked = false;
            document.getElementById('evt-start-date').value = evt.start.split('T')[0];
            document.getElementById('evt-start-time').value = evt.start.split('T')[1].substring(0, 5);
            document.getElementById('evt-end-date').value = evt.end.split('T')[0];
            document.getElementById('evt-end-time').value = evt.end.split('T')[1].substring(0, 5);
        }
    }
    toggleTimeInputs();
    modal.style.display = 'flex';
}

function closeEventModal() { document.getElementById('event-modal').style.display = 'none'; }

function toggleTimeInputs() {
    const isAllDay = document.getElementById('evt-all-day').checked;
    const timeInputs = [document.getElementById('evt-start-time'), document.getElementById('evt-end-time')];
    timeInputs.forEach(el => el.disabled = isAllDay);
    timeInputs.forEach(el => el.style.opacity = isAllDay ? '0.3' : '1');
}

async function submitEvent() {
    const id = document.getElementById('evt-id').value;
    const summary = document.getElementById('evt-summary').value;
    const desc = document.getElementById('evt-desc').value;
    const sDate = document.getElementById('evt-start-date').value;
    const sTime = document.getElementById('evt-start-time').value;
    const eDate = document.getElementById('evt-end-date').value;
    const eTime = document.getElementById('evt-end-time').value;
    const allDay = document.getElementById('evt-all-day').checked;

    if (!summary) return alert("請輸入標題");

    const fd = new FormData();
    fd.append('summary', summary);
    fd.append('description', desc);
    fd.append('start_date', sDate);
    fd.append('end_date', eDate);
    fd.append('start_time', sTime);
    fd.append('end_time', eTime);
    fd.append('is_all_day', allDay);

    let url = '/api/calendar/add';
    if (id) {
        url = '/api/calendar/update';
        fd.append('event_id', id);
    }

    const btn = document.querySelector('#event-modal .btn-confirm');
    const oldText = btn.innerText;
    btn.innerText = "處理中...";
    btn.disabled = true;

    try {
        await FlowUI.request(url, { method: 'POST', body: fd });
        closeEventModal();
        currentMonthEvents = [];
        fetchEvents();
    } catch (e) { FlowUI.error(e); }
    finally { btn.innerText = oldText; btn.disabled = false; }
}

async function deleteEvent(id) {
    showConfirmModal('刪除行程', '確定要從 Google 日曆刪除此項目嗎？', async () => {
        const fd = new FormData();
        fd.append('event_id', id);
        try { await FlowUI.request('/api/calendar/delete', { method: 'POST', body: fd }); await fetchEvents(); }
        catch (error) { FlowUI.error(error); }
    });
}

function changeMonth(delta) { currentDate.setMonth(currentDate.getMonth() + delta); initCalendar(); }
function goToToday() {
    currentDate = new Date();
    selectedDateStr = currentDate.toLocaleDateString('en-CA');
    initCalendar();
}