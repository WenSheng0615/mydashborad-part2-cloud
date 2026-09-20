let currentTransactions = [];
let currentCategories = [];

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('m-date').valueAsDate = new Date();
    loadMoney();
});

async function loadMoney() {
    try {
        const data = await FlowUI.request('/api/money/');
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

function moneyCell(text, width, flex) {
    const cell=FlowUI.node('div',text,'nt-cell');
    if(width)cell.style.width=width+'px';if(flex)cell.style.flex=flex;
    return cell;
}
function moneyAction(label, action) {
    const button=FlowUI.node('button',label,'action-icon');button.type='button';button.onclick=action;return button;
}
function renderCategories(cats) {
    const expense=document.getElementById('category-expense-list'), income=document.getElementById('category-income-list');
    expense.replaceChildren();income.replaceChildren();
    for(const category of cats){
        const row=FlowUI.node('div',null,'nt-row');
        row.append(moneyCell(category.name,null,'1'),moneyCell(`$ ${category.spent}`,category.type==='income'?120:100));
        if(category.type!=='income') {
            const status=['warning','over'].includes(category.status)?category.status:'normal';
            const cell=moneyCell(null,100);cell.append(FlowUI.node('span',{normal:'正常',warning:'預警',over:'超支'}[status],'status-badge '+status));
            row.append(moneyCell(`$ ${category.budget}`,100),cell);
        }
        const actions=moneyCell(null,70);actions.append(moneyAction('編輯',()=>openEditCategoryModal(encodeURIComponent(JSON.stringify(category)))),moneyAction('刪除',()=>deleteCategory(category.name)));
        row.append(actions);(category.type==='income'?income:expense).append(row);
    }
    if(!expense.childElementCount)expense.append(FlowUI.node('p','無支出類別'));
    if(!income.childElementCount)income.append(FlowUI.node('p','無收入類別'));
}
function renderTransactions(txs) {
    const list=document.getElementById('transaction-list');list.replaceChildren();
    if(!txs.length){list.append(FlowUI.node('p','無交易紀錄'));return;}
    for(const tx of txs){
        const row=FlowUI.node('div',null,'nt-row');const expense=tx.type==='expense';
        const type=moneyCell(null,80);type.append(FlowUI.node('span',expense?'支':'收','tag '+(expense?'expense':'income')));
        const actions=moneyCell(null,50);actions.append(moneyAction('刪除',()=>deleteTx(tx.id)));
        row.append(moneyCell(tx.date,120),type,moneyCell(tx.category,100),moneyCell(tx.item,null,'1.5'),moneyCell(`${expense?'-':'+'} $${tx.amount}`,120),moneyCell(tx.note,null,'1'),actions);
        list.append(row);
    }
}

// Category & Transaction CRUD
async function addCategory(type) {
    const nameInput = document.getElementById(type === 'expense' ? 'new-exp-name' : 'new-inc-name');
    const budgetInput = document.getElementById(type === 'expense' ? 'new-exp-budget' : 'new-inc-budget');
    const name = nameInput.value; let budget = 0;
    if (type === 'expense') { budget = budgetInput.value; if (!budget) return alert("請輸入預算"); }
    if (!name) return alert("請輸入名稱");
    const fd = new FormData(); fd.append('name', name); fd.append('budget', budget); fd.append('type', type);
    await FlowUI.request('/api/money/category/add', { method: 'POST', body: fd });
    nameInput.value = ''; if (budgetInput) budgetInput.value = '';
    loadMoney();
}
async function deleteCategory(name) { showConfirmModal('刪除類別', `確定刪除 "${name}"？`, async () => { const fd = new FormData(); fd.append('name', name); await FlowUI.request('/api/money/category/delete', { method: 'POST', body: fd }); loadMoney(); }); }
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
    await FlowUI.request('/api/money/add', { method: 'POST', body: fd });
    closeMoneyModal(); document.getElementById('m-item').value = ''; document.getElementById('m-amount').value = ''; loadMoney();
}
async function deleteTx(id) { showConfirmModal('刪除紀錄', '確定刪除?', async () => { const fd = new FormData(); fd.append('id', id); await FlowUI.request('/api/money/delete', { method: 'POST', body: fd }); loadMoney(); }); }
async function resetMoney() { showConfirmModal('清空', '確定清空所有交易?', async () => { await FlowUI.request('/api/money/reset', { method: 'POST' }); loadMoney(); }); }
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
    await FlowUI.request('/api/money/category/update', { method: 'POST', body: fd });
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
const moneyWrites = new Set();
function guardedMoneyWrite(key, fn) {
    return async (...args) => {
        if(moneyWrites.has(key))return;
        moneyWrites.add(key);
        try {return await fn(...args);} catch(error){FlowUI.error(error);}
        finally{moneyWrites.delete(key);}
    };
}
addCategory=guardedMoneyWrite('category',addCategory);
submitTransaction=guardedMoneyWrite('transaction',submitTransaction);
submitEditCategory=guardedMoneyWrite('edit-category',submitEditCategory);
