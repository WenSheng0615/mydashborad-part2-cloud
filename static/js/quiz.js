// ── 狀態 ──
let quizBanks = [];
let currentBankId = null;
let practiceQuestions = [];
let practiceIndex = 0;
let practiceCorrect = 0;
let practiceAnswered = false;
let practiceWrongQuestions = [];

// ── 初始化 ──
async function initQuiz() {
    await loadBanks();
}

// ── 題庫 ──
async function loadBanks() {
    const res = await fetch('/api/quiz/banks');
    const data = await res.json();
    quizBanks = data.banks || [];
    renderBanks();
}

function renderBanks() {
    const el = document.getElementById('quiz-bank-list');
    if (!quizBanks.length) {
        el.innerHTML = '<div style="font-size:0.8rem;color:var(--text-sub);text-align:center;margin-top:20px;">尚無題庫</div>';
        return;
    }
    el.innerHTML = quizBanks.map(b => `
        <div class="quiz-bank-card ${b.id === currentBankId ? 'selected' : ''}" onclick="selectBank('${b.id}')">
            <div class="bank-card-actions">
                <button class="bank-edit" onclick="editBankPrompt(event,'${b.id}')"><i class="fa-solid fa-pen"></i></button>
                <button class="bank-del" onclick="deleteBank(event,'${b.id}')"><i class="fa-solid fa-trash"></i></button>
            </div>
            <div class="bank-name">${escHtml(b.name)}</div>
            <div class="bank-meta">${b.count} 題${b.description ? ' · ' + escHtml(b.description) : ''}</div>
        </div>
    `).join('');
}

let editingBankId = null;

function openBankModal() {
    editingBankId = null;
    document.getElementById('quiz-bank-modal-title').textContent = '新增題庫';
    document.getElementById('bank-json-section').style.display = '';
    document.getElementById('bank-submit-btn').textContent = '建立';
    document.getElementById('quiz-bank-modal').style.display = 'flex';
    document.getElementById('bank-name-input').focus();
}
function editBankPrompt(e, bankId) {
    e.stopPropagation();
    const bank = quizBanks.find(b => b.id === bankId);
    if (!bank) return;
    editingBankId = bankId;
    document.getElementById('quiz-bank-modal-title').textContent = '編輯題庫';
    document.getElementById('bank-name-input').value = bank.name;
    document.getElementById('bank-desc-input').value = bank.description || '';
    document.getElementById('bank-json-section').style.display = 'none';
    document.getElementById('bank-submit-btn').textContent = '儲存';
    document.getElementById('quiz-bank-modal').style.display = 'flex';
}
function closeBankModal() {
    editingBankId = null;
    document.getElementById('quiz-bank-modal').style.display = 'none';
    document.getElementById('bank-name-input').value = '';
    document.getElementById('bank-desc-input').value = '';
    document.getElementById('bank-json-input').value = '';
    document.getElementById('bank-json-filename').textContent = '上傳 JSON 題目檔（可選）';
    document.getElementById('bank-json-status').textContent = '';
}

function onBankJsonSelected() {
    const input = document.getElementById('bank-json-input');
    const label = document.getElementById('bank-json-filename');
    label.textContent = input.files.length ? input.files[0].name : '上傳 JSON 題目檔（可選）';
}

async function submitBank() {
    const name = document.getElementById('bank-name-input').value.trim();
    if (!name) return;

    if (editingBankId) {
        const fd = new FormData();
        fd.append('bank_id', editingBankId);
        fd.append('name', name);
        fd.append('description', document.getElementById('bank-desc-input').value.trim());
        const res = await fetch('/api/quiz/banks/edit', { method: 'POST', body: fd });
        const data = await res.json();
        if (data.status !== 'success') return;
        const idx = quizBanks.findIndex(b => b.id === editingBankId);
        if (idx !== -1) { quizBanks[idx].name = data.bank.name; quizBanks[idx].description = data.bank.description; }
        if (currentBankId === editingBankId) {
            document.getElementById('quiz-current-bank-name').textContent = data.bank.name;
        }
        closeBankModal();
        renderBanks();
        return;
    }

    const fd = new FormData();
    fd.append('name', name);
    fd.append('description', document.getElementById('bank-desc-input').value.trim());
    const res = await fetch('/api/quiz/banks/add', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.status !== 'success') return;

    quizBanks.unshift(data.bank);

    const jsonInput = document.getElementById('bank-json-input');
    if (jsonInput.files.length) {
        const importFd = new FormData();
        importFd.append('bank_id', data.bank.id);
        importFd.append('file', jsonInput.files[0]);
        const importRes = await fetch('/api/quiz/import', { method: 'POST', body: importFd });
        const importData = await importRes.json();
        if (importData.status === 'success') {
            data.bank.count = importData.added;
        } else {
            document.getElementById('bank-json-status').textContent = 'JSON 匯入失敗，請確認檔案格式';
            document.getElementById('bank-json-status').style.color = '#e57373';
            renderBanks();
            selectBank(data.bank.id);
            return;
        }
    }

    closeBankModal();
    renderBanks();
    selectBank(data.bank.id);
}

async function deleteBank(e, bankId) {
    e.stopPropagation();
    if (!confirm('確定刪除這個題庫及所有題目？')) return;
    const fd = new FormData(); fd.append('bank_id', bankId);
    await fetch('/api/quiz/banks/delete', { method: 'POST', body: fd });
    quizBanks = quizBanks.filter(b => b.id !== bankId);
    if (currentBankId === bankId) { currentBankId = null; resetMain(); }
    renderBanks();
}

function resetMain() {
    currentBankId = null;
    document.getElementById('quiz-current-bank-name').textContent = '請選擇題庫';
    document.getElementById('btn-quiz-assess').style.display = 'none';
    document.getElementById('quiz-questions-container').innerHTML = '<div class="quiz-empty"><i class="fa-solid fa-graduation-cap"></i><span>先從左側選擇或建立一個題庫</span></div>';
}

// ── 題目 ──
async function selectBank(bankId) {
    if (historyPanelOpen) {
        historyPanelOpen = false;
        document.getElementById('quiz-history-panel').style.display = 'none';
        document.getElementById('quiz-questions-container').style.display = '';
        document.getElementById('btn-history').style.background = 'var(--input-bg)';
        document.getElementById('btn-history').style.color = 'var(--text-sub)';
    }
    if (currentBankId === bankId) { resetMain(); return; }
    currentBankId = bankId;
    renderBanks();
    const bank = quizBanks.find(b => b.id === bankId);
    document.getElementById('quiz-current-bank-name').textContent = bank ? bank.name : '';
    document.getElementById('btn-quiz-assess').style.display = '';
    await loadQuestions(bankId);
}

let currentQuestions = [];

async function loadQuestions(bankId) {
    const res = await fetch(`/api/quiz/questions?bank_id=${bankId}`);
    const data = await res.json();
    currentQuestions = data.questions || [];
    renderQuestions(currentQuestions);
}

function renderQuestions(questions) {
    const el = document.getElementById('quiz-questions-container');
    if (!questions.length) {
        el.innerHTML = '<div class="quiz-empty"><i class="fa-solid fa-circle-question"></i><span>還沒有題目，點右上角新增</span></div>';
        return;
    }
    el.innerHTML = questions.map((q, i) => `
        <div class="quiz-q-card">
            <div class="quiz-q-header">
                <div class="quiz-q-content"><span style="color:var(--text-sub);margin-right:6px;">Q${i+1}.</span>${escHtml(q.content)}</div>
                ${q.tag ? `<span class="quiz-q-tag-badge"><i class="fa-solid fa-tag"></i>${escHtml(q.tag)}</span>` : ''}
                <span class="quiz-q-type-badge">${q.type === 'single' ? '單選' : '複選'}</span>
                <button class="quiz-q-edit" onclick="editQuestion('${q.id}')"><i class="fa-solid fa-pen"></i></button>
                <button class="quiz-q-del" onclick="deleteQuestion('${q.id}')"><i class="fa-solid fa-trash"></i></button>
            </div>
            <div class="quiz-q-options">
                ${q.options.map(o => `
                    <div class="quiz-opt-row ${o.is_correct ? 'correct' : ''}">
                        <div class="quiz-opt-dot">${o.is_correct ? '<div class="quiz-opt-dot-inner"></div>' : ''}</div>
                        <span>${escHtml(o.text)}</span>
                    </div>
                `).join('')}
            </div>
        </div>
    `).join('');
}

async function deleteQuestion(qId) {
    if (!confirm('確定刪除這道題目？')) return;
    const fd = new FormData(); fd.append('question_id', qId);
    await fetch('/api/quiz/questions/delete', { method: 'POST', body: fd });
    await loadQuestions(currentBankId);
    // 同步更新題庫數量顯示
    const bank = quizBanks.find(b => b.id === currentBankId);
    if (bank) { bank.count = Math.max(0, bank.count - 1); renderBanks(); }
}

// ── 新增題目 Modal ──
let optionCount = 0;

function switchAddTab(tab) {
    const isManual = tab === 'manual';
    document.getElementById('add-panel-manual').style.display = isManual ? 'flex' : 'none';
    document.getElementById('add-panel-import').style.display = isManual ? 'none' : 'flex';
    document.getElementById('add-tab-manual').style.background = isManual ? 'var(--accent)' : 'transparent';
    document.getElementById('add-tab-manual').style.color = isManual ? 'white' : 'var(--text-sub)';
    document.getElementById('add-tab-import').style.background = isManual ? 'transparent' : 'var(--accent)';
    document.getElementById('add-tab-import').style.color = isManual ? 'var(--text-sub)' : 'white';
}

let editingQuestionId = null;

function populateTagSuggestions() {
    const dl = document.getElementById('q-tag-suggestions');
    const tags = [...new Set(currentQuestions.map(q => q.tag).filter(Boolean))];
    dl.innerHTML = tags.map(t => `<option value="${escHtml(t)}"></option>`).join('');
}

function openAddQuestionModal(tab = 'manual') {
    editingQuestionId = null;
    document.getElementById('quiz-question-modal-title').innerHTML = '<i class="fa-solid fa-plus"></i> 新增題目';
    document.getElementById('q-submit-btn').textContent = '儲存';
    document.getElementById('add-tab-import').style.display = '';
    optionCount = 0;
    document.getElementById('q-content-input').value = '';
    document.getElementById('q-type-select').value = 'single';
    document.getElementById('q-tag-input').value = '';
    populateTagSuggestions();
    document.getElementById('q-options-list').innerHTML = '';
    addOptionRow(); addOptionRow(); addOptionRow(); addOptionRow();
    document.getElementById('import-file-input').value = '';
    document.getElementById('import-status').textContent = '';
    switchAddTab(tab);
    document.getElementById('quiz-question-modal').style.display = 'flex';
}

function editQuestion(qId) {
    const q = currentQuestions.find(x => x.id === qId);
    if (!q) return;
    editingQuestionId = qId;
    document.getElementById('quiz-question-modal-title').innerHTML = '<i class="fa-solid fa-pen"></i> 編輯題目';
    document.getElementById('q-submit-btn').textContent = '儲存變更';
    document.getElementById('add-tab-import').style.display = 'none';
    optionCount = 0;
    document.getElementById('q-content-input').value = q.content;
    document.getElementById('q-type-select').value = q.type;
    document.getElementById('q-tag-input').value = q.tag || '';
    populateTagSuggestions();
    document.getElementById('q-options-list').innerHTML = '';
    q.options.forEach(o => {
        addOptionRow();
        const row = document.getElementById('q-options-list').lastElementChild;
        row.querySelector('input[type=text]').value = o.text;
        if (o.is_correct) row.querySelector('.quiz-opt-correct-toggle').classList.add('active');
    });
    switchAddTab('manual');
    document.getElementById('quiz-question-modal').style.display = 'flex';
}

function closeAddQuestionModal() {
    editingQuestionId = null;
    document.getElementById('quiz-question-modal').style.display = 'none';
}
// 匯入 modal 現在直接開啟同一個 modal 的 import tab
function openImportModal() { openAddQuestionModal('import'); }
function closeImportModal() { closeAddQuestionModal(); }

function addOptionRow() {
    optionCount++;
    const id = `opt-row-${optionCount}`;
    const el = document.createElement('div');
    el.className = 'quiz-opt-input-row';
    el.id = id;
    el.innerHTML = `
        <button class="quiz-opt-correct-toggle" onclick="toggleCorrect(this)" title="標記為正確答案"><i class="fa-solid fa-check"></i></button>
        <input type="text" placeholder="選項 ${optionCount}" data-opt-idx="${optionCount}">
        <button class="quiz-opt-del-btn" onclick="removeOptRow('${id}')"><i class="fa-solid fa-xmark"></i></button>
    `;
    document.getElementById('q-options-list').appendChild(el);
}

function removeOptRow(id) {
    const rows = document.getElementById('q-options-list');
    if (rows.children.length <= 2) return;
    document.getElementById(id)?.remove();
}

function toggleCorrect(btn) {
    const qType = document.getElementById('q-type-select').value;
    if (qType === 'single') {
        document.querySelectorAll('#q-options-list .quiz-opt-correct-toggle').forEach(b => b.classList.remove('active'));
    }
    btn.classList.toggle('active');
}

async function submitQuestion() {
    const content = document.getElementById('q-content-input').value.trim();
    const type = document.getElementById('q-type-select').value;
    const tag = document.getElementById('q-tag-input').value.trim();
    const rows = document.querySelectorAll('#q-options-list .quiz-opt-input-row');
    const options = [];
    rows.forEach(row => {
        const text = row.querySelector('input[type=text]').value.trim();
        const isCorrect = row.querySelector('.quiz-opt-correct-toggle').classList.contains('active');
        if (text) options.push({ text, is_correct: isCorrect });
    });
    if (!content || options.length < 2) { alert('請填寫題目並至少新增 2 個選項'); return; }
    if (!options.some(o => o.is_correct)) { alert('請至少標記一個正確答案'); return; }

    if (editingQuestionId) {
        const res = await fetch('/api/quiz/questions/edit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question_id: editingQuestionId, content, type, tag, options })
        });
        const data = await res.json();
        if (data.status === 'success') {
            closeAddQuestionModal();
            await loadQuestions(currentBankId);
        }
        return;
    }

    const res = await fetch('/api/quiz/questions/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bank_id: currentBankId, content, type, tag, options })
    });
    const data = await res.json();
    if (data.status === 'success') {
        closeAddQuestionModal();
        await loadQuestions(currentBankId);
        const bank = quizBanks.find(b => b.id === currentBankId);
        if (bank) { bank.count++; renderBanks(); }
    }
}

// ── 練習模式 ──
async function startPractice(tags = null) {
    if (!currentBankId) return;
    let url = `/api/quiz/practice?bank_id=${currentBankId}`;
    if (tags) url += `&tags=${encodeURIComponent(tags)}`;
    const res = await fetch(url);
    const data = await res.json();
    practiceQuestions = data.questions || [];
    if (!practiceQuestions.length) { alert('這個題庫還沒有題目！'); return; }
    practiceIndex = 0;
    practiceCorrect = 0;
    practiceWrongQuestions = [];
    document.getElementById('quiz-practice-overlay').style.display = 'flex';
    document.getElementById('prac-result').style.display = 'none';
    ['prac-question', 'prac-hint', 'prac-options'].forEach(id => { document.getElementById(id).style.display = ''; });
    showPracticeQuestion();
}

function reviewWrongPractice() {
    if (!practiceWrongQuestions.length) return;
    practiceQuestions = practiceWrongQuestions;
    practiceIndex = 0;
    practiceCorrect = 0;
    practiceWrongQuestions = [];
    document.getElementById('prac-result').style.display = 'none';
    ['prac-question', 'prac-hint', 'prac-options'].forEach(id => { document.getElementById(id).style.display = ''; });
    showPracticeQuestion();
}

function showPracticeQuestion() {
    practiceAnswered = false;
    const q = practiceQuestions[practiceIndex];
    const total = practiceQuestions.length;
    document.getElementById('prac-progress-text').textContent = `第 ${practiceIndex + 1} / ${total} 題`;
    document.getElementById('prac-progress-fill').style.width = `${(practiceIndex / total) * 100}%`;
    document.getElementById('prac-question').textContent = q.content;
    document.getElementById('prac-hint').textContent = q.type === 'multiple' ? '（複選題，請選出所有正確答案）' : '（單選題）';
    document.getElementById('prac-feedback').textContent = '';
    document.getElementById('prac-next-btn').style.display = 'none';

    const optsEl = document.getElementById('prac-options');
    const isMulti = q.type === 'multiple';
    optsEl.innerHTML = q.options.map((o, i) => `
        <button class="quiz-practice-opt" data-idx="${i}" data-correct="${o.is_correct}" onclick="selectPracticeOpt(this, '${q.type}')">
            <span class="quiz-opt-marker ${isMulti ? 'checkbox' : 'radio'}">${isMulti ? '' : '<span class="quiz-opt-marker-dot"></span>'}</span>
            <span style="font-weight:600;min-width:18px;">${String.fromCharCode(65+i)}.</span>
            <span>${escHtml(o.text)}</span>
        </button>
    `).join('');
}

function selectPracticeOpt(btn, type) {
    if (practiceAnswered) return;
    if (type === 'single') {
        document.querySelectorAll('.quiz-practice-opt').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        checkAnswer(type);
    } else {
        btn.classList.toggle('selected');
    }
}

function checkAnswer(type) {
    practiceAnswered = true;
    const q = practiceQuestions[practiceIndex];
    const btns = document.querySelectorAll('.quiz-practice-opt');
    const correctIds = new Set(q.options.map((o, i) => o.is_correct ? i : null).filter(v => v !== null));
    const selectedIds = new Set([...btns].map((b, i) => b.classList.contains('selected') ? i : null).filter(v => v !== null));

    let isCorrect = false;
    if (type === 'single') {
        const sel = [...selectedIds][0];
        isCorrect = correctIds.has(sel);
    } else {
        isCorrect = [...correctIds].every(i => selectedIds.has(i)) && [...selectedIds].every(i => correctIds.has(i));
    }

    btns.forEach((b, i) => {
        b.disabled = true;
        if (correctIds.has(i)) b.classList.add('correct');
        else if (selectedIds.has(i)) b.classList.add('wrong');
    });

    if (isCorrect) practiceCorrect++;
    else practiceWrongQuestions.push(q);
    const fb = document.getElementById('prac-feedback');
    fb.textContent = isCorrect ? '✓ 答對了！' : '✗ 答錯了';
    fb.className = 'quiz-practice-feedback ' + (isCorrect ? 'ok' : 'fail');

    const isLast = practiceIndex >= practiceQuestions.length - 1;
    const nextBtn = document.getElementById('prac-next-btn');
    nextBtn.style.display = '';
    nextBtn.style.width = 'auto';
    nextBtn.style.whiteSpace = 'nowrap';
    nextBtn.innerHTML = isLast ? '查看結果' : '下一題 <i class="fa-solid fa-arrow-right"></i>';
    nextBtn.onclick = isLast ? showResult : nextPracticeQuestion;
}

// 複選題確認按鈕：在複選題下方動態顯示
document.addEventListener('DOMContentLoaded', () => {
    // 在 prac-options 下方加入確認按鈕（複選專用）
    const overlay = document.getElementById('quiz-practice-overlay');
    if (overlay) {
        const confirmBtn = document.createElement('button');
        confirmBtn.id = 'prac-confirm-btn';
        confirmBtn.className = 'btn-tool';
        confirmBtn.style.cssText = 'display:none;margin-top:14px;background:var(--accent);color:white;padding:0 20px;width:100%;';
        confirmBtn.textContent = '確認作答';
        confirmBtn.onclick = () => checkAnswer('multiple');
        document.getElementById('prac-options').insertAdjacentElement('afterend', confirmBtn);
    }
});

// 覆寫 showPracticeQuestion 以處理複選確認按鈕
const _origShow = showPracticeQuestion;
// 在選題切換時顯示/隱藏 confirm btn — 用 MutationObserver 偵測
function refreshConfirmBtn() {
    const q = practiceQuestions[practiceIndex];
    const btn = document.getElementById('prac-confirm-btn');
    if (!btn) return;
    btn.style.display = (q && q.type === 'multiple') ? '' : 'none';
}

function nextPracticeQuestion() {
    practiceIndex++;
    showPracticeQuestion();
    refreshConfirmBtn();
}

// patch showPracticeQuestion to also refresh
const origShowPQ = showPracticeQuestion;
window.showPracticeQuestion = function() { origShowPQ(); refreshConfirmBtn(); }

function showResult() {
    const total = practiceQuestions.length;
    const wrongCount = practiceWrongQuestions.length;
    const pct = Math.round((practiceCorrect / total) * 100);
    document.getElementById('prac-progress-fill').style.width = '100%';
    document.getElementById('prac-question').style.display = 'none';
    document.getElementById('prac-hint').style.display = 'none';
    document.getElementById('prac-options').style.display = 'none';
    document.getElementById('prac-feedback').textContent = '';
    document.getElementById('prac-next-btn').style.display = 'none';
    const cb = document.getElementById('prac-confirm-btn');
    if (cb) cb.style.display = 'none';

    document.getElementById('prac-result').style.display = 'block';
    document.getElementById('prac-score-text').textContent = `${pct}%`;
    document.getElementById('prac-score-detail').textContent = `答對 ${practiceCorrect} / ${total} 題${wrongCount ? `，答錯 ${wrongCount} 題` : ''}`;
    document.getElementById('prac-review-wrong-btn').style.display = wrongCount > 0 ? '' : 'none';
}

function exitPractice() {
    document.getElementById('quiz-practice-overlay').style.display = 'none';
    // 恢復 showPracticeQuestion 用到的元素顯示狀態
    ['prac-question','prac-hint','prac-options'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = '';
    });
}

// ── 匯入 JSON ──
function openImportModal() {
    document.getElementById('import-file-input').value = '';
    document.getElementById('import-status').textContent = '';
    document.getElementById('quiz-import-modal').style.display = 'flex';
}
function closeImportModal() {
    document.getElementById('quiz-import-modal').style.display = 'none';
}

async function submitImport() {
    const fileInput = document.getElementById('import-file-input');
    const statusEl = document.getElementById('import-status');
    if (!fileInput.files.length) {
        statusEl.style.color = 'var(--accent)';
        statusEl.textContent = '請先選擇 JSON 檔案';
        return;
    }
    statusEl.style.color = 'var(--text-sub)';
    statusEl.textContent = '匯入中...';

    const fd = new FormData();
    fd.append('bank_id', currentBankId);
    fd.append('file', fileInput.files[0]);

    const res = await fetch('/api/quiz/import', { method: 'POST', body: fd });
    const data = await res.json();

    if (data.status === 'success') {
        statusEl.style.color = '#4caf50';
        statusEl.textContent = `✓ 成功匯入 ${data.added} 題${data.updated ? `，更新 ${data.updated} 題分類` : ''}${data.skipped ? `，略過 ${data.skipped} 題` : ''}`;
        await loadQuestions(currentBankId);
        const bank = quizBanks.find(b => b.id === currentBankId);
        if (bank) { bank.count += data.added; renderBanks(); }
        setTimeout(closeImportModal, 1500);
    } else if (data.status === 'invalid_json') {
        statusEl.style.color = 'var(--accent)';
        statusEl.textContent = '✗ 檔案格式錯誤，請確認是有效的 JSON';
    } else {
        statusEl.style.color = 'var(--accent)';
        statusEl.textContent = '✗ 匯入失敗，請稍後再試';
    }
}

// ── 測驗出題數同步 ──
function syncExamCount(from, val) {
    const slider = document.getElementById('exam-count-slider');
    const input  = document.getElementById('exam-count-display');
    const max = parseInt(slider.max) || 50;
    let n = Math.max(1, Math.min(max, parseInt(val) || 1));
    slider.value = n;
    input.value  = n;
}

// ── 測驗分類篩選 ──
let examTagCounts = {};   // {tag: count}
let examSelectedTags = new Set();

function updateExamCountMax() {
    let max;
    if (examSelectedTags.size > 0) {
        max = 0;
        examSelectedTags.forEach(t => { max += examTagCounts[t] || 0; });
    } else {
        max = Object.values(examTagCounts).reduce((a, b) => a + b, 0);
    }
    max = Math.max(max, 1);
    const slider = document.getElementById('exam-count-slider');
    const input = document.getElementById('exam-count-display');
    slider.max = max; input.max = max;
    const def = Math.min(parseInt(input.value) || 10, max);
    slider.value = def; input.value = def;
    document.getElementById('exam-count-hint').textContent =
        `此範圍共 ${max} 題`;
}

function toggleExamTag(tag) {
    if (examSelectedTags.has(tag)) {
        examSelectedTags.delete(tag);
    } else {
        examSelectedTags.add(tag);
    }
    renderExamTagFilter();
    updateExamCountMax();
}

function renderExamTagFilter() {
    const wrap = document.getElementById('exam-tag-filter-wrap');
    const el = document.getElementById('exam-tag-filter');
    const tags = Object.keys(examTagCounts);
    if (tags.length <= 1) {
        wrap.style.display = 'none';
        el.innerHTML = '';
        return;
    }
    wrap.style.display = '';
    el.innerHTML = tags.map(tag => {
        const active = examSelectedTags.has(tag);
        return `<button type="button" class="tag-filter-btn ${active ? 'active' : ''}" onclick="toggleExamTag('${tag.replace(/'/g, "\\'")}')">
            <i class="fa-solid fa-check tag-check"></i>${escHtml(tag)} (${examTagCounts[tag]})
        </button>`;
    }).join('');
}

// ── 評測 Modal ──
function openAssessModal() {
    if (!currentBankId) return;
    document.getElementById('quiz-assess-modal').style.display = 'flex';
}
function closeAssessModal() {
    document.getElementById('quiz-assess-modal').style.display = 'none';
}

// ── 練習設定（標籤篩選） ──
let practiceTagCounts = {};
let practiceSelectedTags = new Set();

async function openPracticeSettings() {
    if (!currentBankId) return;
    practiceSelectedTags = new Set();
    const res = await fetch(`/api/quiz/tags?bank_id=${currentBankId}`);
    const data = await res.json();
    practiceTagCounts = {};
    (data.tags || []).forEach(t => { practiceTagCounts[t.tag] = t.count; });
    renderPracticeTagFilter();
    document.getElementById('quiz-practice-settings-modal').style.display = 'flex';
}
function closePracticeSettings() { document.getElementById('quiz-practice-settings-modal').style.display = 'none'; }

function renderPracticeTagFilter() {
    const wrap = document.getElementById('prac-tag-filter-wrap');
    const el = document.getElementById('prac-tag-filter');
    const tags = Object.keys(practiceTagCounts);
    if (tags.length <= 1) {
        wrap.style.display = 'none';
        el.innerHTML = '';
    } else {
        wrap.style.display = '';
        el.innerHTML = tags.map(tag => {
            const active = practiceSelectedTags.has(tag);
            return `<button type="button" class="tag-filter-btn ${active ? 'active' : ''}" onclick="togglePracticeTag('${tag.replace(/'/g, "\\'")}')">
                <i class="fa-solid fa-check tag-check"></i>${escHtml(tag)} (${practiceTagCounts[tag]})
            </button>`;
        }).join('');
    }
    updatePracticeHint();
}

function togglePracticeTag(tag) {
    if (practiceSelectedTags.has(tag)) practiceSelectedTags.delete(tag);
    else practiceSelectedTags.add(tag);
    renderPracticeTagFilter();
}

function updatePracticeHint() {
    let count;
    if (practiceSelectedTags.size > 0) {
        count = 0;
        practiceSelectedTags.forEach(t => { count += practiceTagCounts[t] || 0; });
    } else {
        count = Object.values(practiceTagCounts).reduce((a, b) => a + b, 0);
    }
    document.getElementById('prac-tag-hint').textContent = `此範圍共 ${count} 題`;
}

function confirmStartPractice() {
    const tags = practiceSelectedTags.size > 0 ? Array.from(practiceSelectedTags).join(',') : null;
    closePracticeSettings();
    startPractice(tags);
}

// ══════════════════════════════════════════
// ── 測驗模式 ──
// ══════════════════════════════════════════
let examQuestions = [];   // [{id, content, type, options:[{text,is_correct}]}]
let examAnswers = {};     // {question_id: Set of selected texts}
let examIndex = 0;
let examBankId = null;
let examSessionId = null;
let examAllAnswers = [];  // 提交後伺服器回傳的完整答題資料（for review）
let examWrongQuestions = [];

async function openExamSettings() {
    if (!currentBankId) return;
    examBankId = currentBankId;
    examSelectedTags = new Set();

    // 取得分類標籤
    const res = await fetch(`/api/quiz/tags?bank_id=${examBankId}`);
    const data = await res.json();
    examTagCounts = {};
    (data.tags || []).forEach(t => { examTagCounts[t.tag] = t.count; });
    renderExamTagFilter();

    // 設定最大出題數
    const def = 10;
    const input = document.getElementById('exam-count-display');
    input.value = def;
    updateExamCountMax();

    document.getElementById('quiz-exam-settings-modal').style.display = 'flex';
}
function closeExamSettings() { document.getElementById('quiz-exam-settings-modal').style.display = 'none'; }

async function startExam() {
    const count = parseInt(document.getElementById('exam-count-display').value) || 10;
    closeExamSettings();
    let url = `/api/quiz/exam/questions?bank_id=${examBankId}&count=${count}`;
    if (examSelectedTags.size > 0) {
        url += `&tags=${encodeURIComponent(Array.from(examSelectedTags).join(','))}`;
    }
    const res = await fetch(url);
    const data = await res.json();
    const questions = data.questions || [];
    if (!questions.length) { alert('此題庫沒有題目！'); return; }
    beginExam(questions);
}

function retakeWrongExam() {
    if (!examWrongQuestions.length) return;
    beginExam(examWrongQuestions);
}

function beginExam(questions) {
    examQuestions = questions;
    examAnswers = {};
    examIndex = 0;
    examSessionId = null;
    examWrongQuestions = [];

    // 重設 UI
    document.getElementById('exam-result').style.display = 'none';
    document.getElementById('exam-progress-text').style.display = '';
    document.getElementById('exam-progress-fill').parentElement.style.display = '';
    document.getElementById('exam-nav-dots').style.display = '';
    document.getElementById('exam-question').style.display = '';
    document.getElementById('exam-hint').style.display = '';
    document.getElementById('exam-options').style.display = '';
    document.querySelector('.exam-actions').style.display = '';

    document.getElementById('quiz-exam-overlay').style.display = 'flex';
    renderExamQuestion();
}

function renderExamQuestion() {
    const q = examQuestions[examIndex];
    const total = examQuestions.length;

    // 進度
    document.getElementById('exam-progress-text').textContent = `第 ${examIndex + 1} / ${total} 題`;
    document.getElementById('exam-progress-fill').style.width = `${((examIndex + 1) / total) * 100}%`;

    // 導覽點
    const dotsEl = document.getElementById('exam-nav-dots');
    dotsEl.innerHTML = examQuestions.map((_, i) => {
        const answered = examAnswers[examQuestions[i].id] && examAnswers[examQuestions[i].id].size > 0;
        const cls = i === examIndex ? 'current' : (answered ? 'answered' : '');
        return `<div class="exam-nav-dot ${cls}" onclick="examGoto(${i})">${i + 1}</div>`;
    }).join('');

    // 題目
    document.getElementById('exam-question').textContent = q.content;
    document.getElementById('exam-hint').textContent = q.type === 'multiple' ? '（複選題，請選出所有正確答案）' : '（單選題）';

    // 選項
    const sel = examAnswers[q.id] || new Set();
    const optsEl = document.getElementById('exam-options');
    const isMulti = q.type === 'multiple';
    optsEl.innerHTML = q.options.map((o, i) => `
        <button class="quiz-practice-opt ${sel.has(o.text) ? 'selected' : ''}"
                onclick="examSelectOpt(this,'${q.id}','${escHtml(o.text)}','${q.type}')">
            <span class="quiz-opt-marker ${isMulti ? 'checkbox' : 'radio'}">${isMulti ? '' : '<span class="quiz-opt-marker-dot"></span>'}</span>
            <span style="font-weight:600;min-width:18px;">${String.fromCharCode(65 + i)}.</span>
            <span>${escHtml(o.text)}</span>
        </button>
    `).join('');

    // 上一題 / 下一題 / 交卷
    document.getElementById('exam-prev-btn').style.display = examIndex === 0 ? 'none' : '';
    document.getElementById('exam-next-btn').style.display = examIndex === total - 1 ? 'none' : '';
    document.getElementById('exam-submit-btn').style.display = examIndex === total - 1 ? '' : 'none';
}

function examGoto(idx) {
    if (idx < 0 || idx >= examQuestions.length) return;
    examIndex = idx;
    renderExamQuestion();
}

function examSelectOpt(btn, qId, text, type) {
    if (!examAnswers[qId]) examAnswers[qId] = new Set();
    const sel = examAnswers[qId];
    if (type === 'single') {
        sel.clear();
        sel.add(text);
        document.querySelectorAll('#exam-options .quiz-practice-opt').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
    } else {
        if (sel.has(text)) { sel.delete(text); btn.classList.remove('selected'); }
        else { sel.add(text); btn.classList.add('selected'); }
    }
    // 更新導覽點
    document.getElementById('exam-nav-dots').innerHTML = examQuestions.map((_, i) => {
        const answered = examAnswers[examQuestions[i].id] && examAnswers[examQuestions[i].id].size > 0;
        const cls = i === examIndex ? 'current' : (answered ? 'answered' : '');
        return `<div class="exam-nav-dot ${cls}" onclick="examGoto(${i})">${i + 1}</div>`;
    }).join('');
}

function confirmSubmitExam() {
    const unanswered = examQuestions.filter(q => !examAnswers[q.id] || examAnswers[q.id].size === 0).length;
    if (unanswered > 0) {
        if (!confirm(`還有 ${unanswered} 題未作答，確定要交卷嗎？`)) return;
    }
    submitExam();
}

async function submitExam() {
    // ⚠️ 只送 question_id + selected，正確答案由後端查資料庫核算，避免竄改 payload 作弊
    const answers = examQuestions.map(q => ({
        question_id: q.id,
        selected: examAnswers[q.id] ? [...examAnswers[q.id]] : []
    }));
    const res = await fetch('/api/quiz/exam/submit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ bank_id: examBankId, answers })
    });
    const data = await res.json();
    examSessionId = data.session_id;
    examAllAnswers = data.results || [];
    showExamResult(data);
}

function showExamResult(data) {
    // 隱藏答題區
    ['exam-progress-text','exam-nav-dots','exam-question','exam-hint','exam-options'].forEach(id => {
        document.getElementById(id).style.display = 'none';
    });
    document.getElementById('exam-progress-fill').parentElement.style.display = 'none';
    document.querySelector('.exam-actions').style.display = 'none';

    const pct = data.score;
    const pass = pct >= 60;
    const scoreEl = document.getElementById('exam-result-score');
    scoreEl.textContent = `${pct}%`;
    scoreEl.className = 'exam-result-score ' + (pass ? 'pass' : 'fail');
    document.getElementById('exam-result-meta').textContent =
        `答對 ${data.correct} / ${data.total} 題`;

    const wrongIds = new Set(examAllAnswers.filter(r => !r.is_correct).map(r => r.question_id));
    examWrongQuestions = examQuestions.filter(q => wrongIds.has(q.id));
    const retakeBtn = document.getElementById('exam-retake-wrong-btn');
    if (retakeBtn) retakeBtn.style.display = examWrongQuestions.length > 0 ? '' : 'none';

    renderExamReview('all');
    document.getElementById('exam-result').style.display = '';
}

function renderExamReview(filter) {
    const listEl = document.getElementById('exam-review-list');
    const src = examAllAnswers.map((r, i) => {
        const sel = new Set(r.selected);
        const correctSet = new Set(r.options.filter(o => o.is_correct).map(o => o.text));
        return { r, sel, correctSet, isCorrect: r.is_correct, idx: i };
    });

    const filtered = filter === 'wrong' ? src.filter(x => !x.isCorrect)
                   : filter === 'correct' ? src.filter(x => x.isCorrect)
                   : src;

    if (!filtered.length) { listEl.innerHTML = '<div style="color:var(--text-sub);font-size:0.85rem;padding:20px 0;">沒有符合的題目</div>'; return; }

    listEl.innerHTML = filtered.map(({ r, sel, correctSet, isCorrect, idx }) => `
        <div class="exam-review-item ${isCorrect ? 'correct' : 'wrong'}">
            <div class="exam-review-header">
                <span class="exam-review-badge ${isCorrect ? 'correct' : 'wrong'}">${isCorrect ? '✓ 答對' : '✗ 答錯'}</span>
                <span class="exam-review-content">Q${idx + 1}. ${escHtml(r.content)}</span>
            </div>
            <div class="exam-review-opts">
                ${r.options.map(o => {
                    const isC = correctSet.has(o.text);
                    const isSel = sel.has(o.text);
                    let cls = '', icon = '';
                    if (isC) { cls = 'is-correct'; icon = '✓'; }
                    else if (isSel) { cls = 'is-wrong-sel'; icon = '✗'; }
                    return `<div class="exam-review-opt ${cls}">
                        <span class="exam-review-opt-icon">${icon}</span>
                        <span>${escHtml(o.text)}</span>
                    </div>`;
                }).join('')}
            </div>
            ${!isCorrect ? `<div class="exam-review-answer-line">正確答案：<b>${[...correctSet].map(escHtml).join('、')}</b></div>` : ''}
        </div>
    `).join('');
}

function filterExamReview(type, btn) {
    document.querySelectorAll('#exam-result .history-tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderExamReview(type);
}

function confirmExitExam() {
    if (examSessionId) { exitExam(); return; }
    if (confirm('確定要放棄這次測驗嗎？')) exitExam();
}
function exitExam() {
    document.getElementById('quiz-exam-overlay').style.display = 'none';
    examSessionId = null;
}

// ══════════════════════════════════════════
// ── 歷史紀錄（內嵌面板）──
// ══════════════════════════════════════════
let historyPanelOpen = false;
let historySelectedId = null;
let _historyDetailData = null;

function toggleHistoryPanel() {
    if (historyPanelOpen) {
        // 關閉歷史、恢復原本狀態
        historyPanelOpen = false;
        document.getElementById('quiz-history-panel').style.display = 'none';
        document.getElementById('quiz-questions-container').style.display = '';
        document.getElementById('btn-history').style.background = 'var(--input-bg)';
        document.getElementById('btn-history').style.color = 'var(--text-sub)';
        // 恢復 toolbar title
        if (currentBankId) {
            const bank = quizBanks.find(b => b.id === currentBankId);
            document.getElementById('quiz-current-bank-name').textContent = bank ? bank.name : '';
            document.getElementById('btn-quiz-assess').style.display = '';
        } else {
            document.getElementById('quiz-current-bank-name').textContent = '請選擇題庫';
        }
    } else {
        historyPanelOpen = true;
        historySelectedId = null;
        _historyDetailData = null;
        document.getElementById('quiz-questions-container').style.display = 'none';
        const panel = document.getElementById('quiz-history-panel');
        panel.style.display = 'flex';
        panel.style.flexDirection = 'column';
        document.getElementById('btn-history').style.background = 'var(--accent-dim)';
        document.getElementById('btn-history').style.color = 'var(--accent)';
        document.getElementById('btn-quiz-assess').style.display = 'none';
        document.getElementById('quiz-current-bank-name').textContent = '歷史答題紀錄';
        document.getElementById('history-filter-tabs').style.display = 'none';
        document.getElementById('history-inline-summary').style.display = 'none';
        // 填篩選選項
        const sel = document.getElementById('history-bank-filter');
        sel.innerHTML = '<option value="">全部題庫</option>' +
            quizBanks.map(b => `<option value="${b.id}">${escHtml(b.name)}</option>`).join('');
        loadQuizHistory();
    }
}

async function loadQuizHistory() {
    const bankId = document.getElementById('history-bank-filter').value;
    const url = bankId ? `/api/quiz/history?bank_id=${bankId}` : '/api/quiz/history';
    const res = await fetch(url);
    const data = await res.json();
    historySelectedId = null;
    _historyDetailData = null;
    document.getElementById('history-filter-tabs').style.display = 'none';
    document.getElementById('history-inline-summary').style.display = 'none';
    renderHistorySessionList(data.sessions || []);
}

function renderHistorySessionList(sessions) {
    const el = document.getElementById('history-inline-content');
    if (!sessions.length) {
        el.innerHTML = '<div class="quiz-empty"><i class="fa-solid fa-clock-rotate-left"></i><span>尚無測驗紀錄</span></div>';
        return;
    }
    el.innerHTML = sessions.map(s => {
        const pass = s.score >= 60;
        return `
        <div class="history-session-card ${s.id === historySelectedId ? 'selected' : ''}"
             onclick="selectHistorySession('${s.id}')">
            <div class="history-session-bank">${escHtml(s.bank_name)}</div>
            <div class="history-session-meta">
                <span class="history-score-badge ${pass ? 'pass' : 'fail'}">${s.score}%</span>
                <span>${s.correct}/${s.total} 題</span>
                <span style="margin-left:auto;">${s.created_at}</span>
            </div>
        </div>`;
    }).join('');
}

async function selectHistorySession(sessionId) {
    if (historySelectedId === sessionId) {
        // 再點一次收合，回到列表
        historySelectedId = null;
        _historyDetailData = null;
        document.getElementById('history-filter-tabs').style.display = 'none';
        document.getElementById('history-inline-summary').style.display = 'none';
        loadQuizHistory();
        return;
    }
    historySelectedId = sessionId;
    const res = await fetch(`/api/quiz/history/${sessionId}`);
    _historyDetailData = await res.json();
    renderInlineHistoryDetail(_historyDetailData);
}

function renderInlineHistoryDetail(data) {
    // 更新摘要列
    const pass = data.score >= 60;
    const summary = document.getElementById('history-inline-summary');
    summary.style.display = '';
    summary.innerHTML = `
        <div class="history-detail-summary" style="cursor:pointer;" onclick="loadQuizHistory()" title="返回列表">
            <div style="font-size:0.8rem;color:var(--text-sub);margin-right:auto;display:flex;align-items:center;gap:6px;">
                <i class="fa-solid fa-arrow-left"></i> 返回
            </div>
            <div class="history-summary-score ${pass ? 'pass' : 'fail'}" style="font-size:1.8rem;">${data.score}%</div>
            <div class="history-summary-info">
                <div><b>${escHtml(data.bank_name)}</b></div>
                <div>答對 ${data.correct} / ${data.total} 題</div>
                <div style="color:var(--text-sub);font-size:0.78rem;">${data.created_at}</div>
            </div>
        </div>`;

    // 顯示篩選 tab
    const tabs = document.getElementById('history-filter-tabs');
    tabs.style.display = 'flex';
    document.getElementById('hft-wrong').textContent = `答錯 ${data.answers.filter(a=>!a.is_correct).length}`;
    document.getElementById('hft-correct').textContent = `答對 ${data.answers.filter(a=>a.is_correct).length}`;
    tabs.querySelectorAll('.history-tab-btn').forEach(b => b.classList.remove('active'));
    tabs.querySelector('.history-tab-btn').classList.add('active');

    renderHistoryAnswers(data.answers, 'all');
}

function filterHistoryDetail(filter, btn, data) {
    document.querySelectorAll('#history-filter-tabs .history-tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderHistoryAnswers((data || _historyDetailData).answers, filter);
}

function renderHistoryAnswers(answers, filter) {
    const listEl = document.getElementById('history-inline-content');
    const filtered = filter === 'wrong' ? answers.filter(a => !a.is_correct)
                   : filter === 'correct' ? answers.filter(a => a.is_correct)
                   : answers;
    if (!filtered.length) {
        listEl.innerHTML = '<div style="color:var(--text-sub);font-size:0.85rem;padding:20px 0;text-align:center;">沒有符合的題目</div>';
        return;
    }
    listEl.innerHTML = filtered.map(a => {
        const sel = new Set(a.selected);
        const correctTexts = a.options.filter(o => o.is_correct).map(o => o.text);
        return `
        <div class="exam-review-item ${a.is_correct ? 'correct' : 'wrong'}">
            <div class="exam-review-header">
                <span class="exam-review-badge ${a.is_correct ? 'correct' : 'wrong'}">${a.is_correct ? '✓ 答對' : '✗ 答錯'}</span>
                <span class="exam-review-content">${escHtml(a.question_content)}</span>
            </div>
            <div class="exam-review-opts">
                ${a.options.map(o => {
                    const isC = o.is_correct, isSel = sel.has(o.text);
                    const cls = isC ? 'is-correct' : isSel ? 'is-wrong-sel' : '';
                    const icon = isC ? '✓' : isSel ? '✗' : '';
                    return `<div class="exam-review-opt ${cls}">
                        <span class="exam-review-opt-icon">${icon}</span>
                        <span>${escHtml(o.text)}</span>
                    </div>`;
                }).join('')}
            </div>
            ${!a.is_correct ? `<div class="exam-review-answer-line">正確答案：<b>${correctTexts.map(escHtml).join('、')}</b></div>` : ''}
        </div>`;
    }).join('');
}

// 相容舊呼叫（保留以防其他地方還有引用）
function openHistoryOverlay() { toggleHistoryPanel(); }
function closeHistoryOverlay() { if (historyPanelOpen) toggleHistoryPanel(); }

// ── 工具函式 ──
function escHtml(str) {
    const d = document.createElement('div');
    d.appendChild(document.createTextNode(str || ''));
    return d.innerHTML;
}
