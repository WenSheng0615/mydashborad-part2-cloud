let currentTransactions = [];
let currentCategories = [];

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('m-date').valueAsDate = new Date();
    loadMoney();
});

async function loadMoney() {
    try {
        const res = await fetch('/api/money/');
        const data = await res.json();
        currentTransactions = data.transactions || [];
        currentCategories = data.categories || [];
        document.getElementById('disp-income').innerText = `$ ${data.total_income}`;
        document.getElementById('disp-expense').innerText = `$ ${data.total_expense}`;
        document.getElementById('disp-balance').innerText = `$ ${data.balance}`;
        renderCategories(currentCategories);
        renderTransactions(currentTransactions);
        updateCategoryOptions();
    } catch (e) { console.error(e); }
}

function renderCategories(cats) {
    const expList = document.getElementById('category-expense-list');
    const incList = document.getElementById('category-income-list');
    let expHtml = '', incHtml = '';

    cats.forEach(c => {
        const editData = encodeURIComponent(JSON.stringify(c));
        if (c.type === 'income') {
            incHtml += `
                <div class="nt-row">
                    <div class="nt-cell" style="flex:1">${c.name}</div>
                    <div class="nt-cell" style="width:120px; justify-content:flex-end; font-weight:bold;">$ ${c.spent}</div>
                    <div class="nt-cell" style="width:70px; justify-content:center; gap:10px;">
                        <i class="fa-solid fa-pen action-icon" onclick="openEditCategoryModal('${editData}')"></i>
                        <i class="fa-solid fa-xmark action-icon" onclick="deleteCategory('${c.name}')"></i>
                    </div>
                </div>`;
        } else {
            let statusHtml = `<span class="status-badge normal"><div class="dot"></div>正常</span>`;
            if (c.status === 'warning') statusHtml = `<span class="status-badge warning"><div class="dot"></div>預警</span>`;
            if (c.status === 'over') statusHtml = `<span class="status-badge over"><div class="dot"></div>超支</span>`;
            expHtml += `
                <div class="nt-row">
                    <div class="nt-cell" style="flex:1">${c.name}</div>
                    <div class="nt-cell" style="width:100px; justify-content:flex-end; font-weight:bold;">$ ${c.spent}</div>
                    <div class="nt-cell" style="width:100px; justify-content:flex-end; color:var(--text-sub);">$ ${c.budget}</div>
                    <div class="nt-cell" style="width:100px; justify-content:center;">${statusHtml}</div>
                    <div class="nt-cell" style="width:70px; justify-content:center; gap:10px;">
                        <i class="fa-solid fa-pen action-icon" onclick="openEditCategoryModal('${editData}')"></i>
                        <i class="fa-solid fa-xmark action-icon" onclick="deleteCategory('${c.name}')"></i>
                    </div>
                </div>`;
        }
    });
    expList.innerHTML = expHtml || '<div style="padding:10px;text-align:center;color:var(--text-sub);">無支出類別</div>';
    incList.innerHTML = incHtml || '<div style="padding:10px;text-align:center;color:var(--text-sub);">無收入類別</div>';
}

function renderTransactions(txs) {
    const list = document.getElementById('transaction-list');
    if (txs.length === 0) { list.innerHTML = '<p style="text-align:center; color:var(--text-sub); margin-top:20px;">無交易紀錄</p>'; return; }
    let html = '';
    txs.forEach(tx => {
        const isExp = tx.type === 'expense';
        const color = isExp ? '#ff7875' : '#73d13d';
        const sign = isExp ? '-' : '+';
        const typeTag = isExp ? '<span class="tag expense">支</span>' : '<span class="tag income">收</span>';
        html += `
            <div class="nt-row">
                <div class="nt-cell" style="width:120px; color:var(--text-sub); font-size:0.8rem;">${tx.date}</div>
                <div class="nt-cell" style="width:80px; justify-content:center;">${typeTag}</div>
                <div class="nt-cell" style="width:100px;">${tx.category}</div>
                <div class="nt-cell" style="flex:1.5; font-weight:500;">${tx.item}</div>
                <div class="nt-cell" style="width:120px; justify-content:flex-start; padding-left:20px; color:${color}; font-weight:bold;">${sign} $${tx.amount}</div>
                <div class="nt-cell" style="flex:1; opacity:0.7; font-size:0.8rem;">${tx.note}</div>
                <div class="nt-cell" style="width:50px; justify-content:center;"><i class="fa-solid fa-trash action-icon" onclick="deleteTx('${tx.id}')"></i></div>
            </div>`;
    });
    list.innerHTML = html;
}

// Category & Transaction CRUD
async function addCategory(type) {
    const nameInput = document.getElementById(type === 'expense' ? 'new-exp-name' : 'new-inc-name');
    const budgetInput = document.getElementById(type === 'expense' ? 'new-exp-budget' : 'new-inc-budget');
    const name = nameInput.value; let budget = 0;
    if (type === 'expense') { budget = budgetInput.value; if (!budget) return alert("請輸入預算"); }
    if (!name) return alert("請輸入名稱");
    const fd = new FormData(); fd.append('name', name); fd.append('budget', budget); fd.append('type', type);
    await fetch('/api/money/category/add', { method: 'POST', body: fd });
    nameInput.value = ''; if (budgetInput) budgetInput.value = '';
    loadMoney();
}
async function deleteCategory(name) { showConfirmModal('刪除類別', `確定刪除 "${name}"？`, async () => { const fd = new FormData(); fd.append('name', name); await fetch('/api/money/category/delete', { method: 'POST', body: fd }); loadMoney(); }); }
function openMoneyModal() { updateCategoryOptions(); document.getElementById('money-modal').style.display = 'flex'; }
function closeMoneyModal() { document.getElementById('money-modal').style.display = 'none'; }
function updateCategoryOptions() {
    const type = document.getElementById('m-type').value;
    const catSelect = document.getElementById('m-category');
    catSelect.innerHTML = '';
    const cats = currentCategories.filter(c => c.type === type);
    if (cats.length > 0) cats.forEach(c => catSelect.add(new Option(c.name, c.name)));
    else catSelect.add(new Option("未分類", "未分類"));
}
async function submitTransaction() {
    const fd = new FormData();
    fd.append('item', document.getElementById('m-item').value);
    fd.append('amount', document.getElementById('m-amount').value);
    fd.append('date', document.getElementById('m-date').value);
    fd.append('type', document.getElementById('m-type').value);
    fd.append('category', document.getElementById('m-category').value);
    fd.append('note', document.getElementById('m-note').value);
    if (!fd.get('item') || !fd.get('amount')) return alert("請輸入完整資訊");
    await fetch('/api/money/add', { method: 'POST', body: fd });
    closeMoneyModal(); document.getElementById('m-item').value = ''; document.getElementById('m-amount').value = ''; loadMoney();
}
async function deleteTx(id) { showConfirmModal('刪除紀錄', '確定刪除?', async () => { const fd = new FormData(); fd.append('id', id); await fetch('/api/money/delete', { method: 'POST', body: fd }); loadMoney(); }); }
async function resetMoney() { showConfirmModal('清空', '確定清空所有交易?', async () => { await fetch('/api/money/reset', { method: 'POST' }); loadMoney(); }); }
function openEditCategoryModal(dataStr) {
    const c = JSON.parse(decodeURIComponent(dataStr));
    document.getElementById('edit-cat-old-name').value = c.name;
    document.getElementById('edit-cat-type').value = c.type;
    document.getElementById('edit-cat-name').value = c.name;
    document.getElementById('edit-cat-budget').value = c.budget || 0;
    document.getElementById('edit-cat-budget-group').style.display = c.type === 'expense' ? 'block' : 'none';
    document.getElementById('edit-category-modal').style.display = 'flex';
}
function closeEditCategoryModal() { document.getElementById('edit-category-modal').style.display = 'none'; }
async function submitEditCategory() {
    const fd = new FormData();
    fd.append('old_name', document.getElementById('edit-cat-old-name').value);
    fd.append('new_name', document.getElementById('edit-cat-name').value);
    fd.append('budget', document.getElementById('edit-cat-budget').value);
    fd.append('type', document.getElementById('edit-cat-type').value);
    await fetch('/api/money/category/update', { method: 'POST', body: fd });
    closeEditCategoryModal(); loadMoney();
}
function exportExcel() {
    if (!currentTransactions || currentTransactions.length === 0) return alert("無資料");
    let csv = "\uFEFF日期,類型,類別,項目,金額,備註\n";
    currentTransactions.forEach(tx => {
        const type = tx.type === 'expense' ? '支出' : '收入';
        csv += `${tx.date},${type},${tx.category},${tx.item},${tx.amount},${tx.note}\n`;
    });
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `記帳_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}