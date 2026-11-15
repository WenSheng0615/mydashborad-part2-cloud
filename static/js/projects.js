const $ = id => document.getElementById(id), el = FlowUI.node;
let catalog = [], spaces = [], selected = null, editorSave = null, renderSerial = 0;
const projectTabs = new Map();
window.showAlert = (title, text) => { $('notice').textContent = `${title}：${text}`; };
const fail = error => { $('notice').textContent = error.message || '操作失敗，請稍後再試。'; };
const request = FlowUI.request;
const json = (method, data) => ({method, headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
function button(label, fn, primary = false) { const b = el('button',label,primary?'primary':''); b.type='button'; b.onclick=()=>Promise.resolve().then(fn).catch(fail); return b; }
function projectPath(p = selected) { return `/api/workspaces/${p.workspace_id}/projects/${p.id}`; }
async function all(url) { const rows=[]; for(let offset=0;;offset+=200) { const page=await request(`${url}${url.includes('?')?'&':'?'}limit=200&offset=${offset}`); rows.push(...page); if(page.length<200) return rows; } }
async function loadCatalog() {
    spaces=await all('/api/workspaces');
    catalog=(await Promise.all(spaces.map(w=>all(`/api/workspaces/${w.id}/projects?include_archived=true`)))).flat();
    const old=$('workspace-select').value;
    $('workspace-select').replaceChildren(...spaces.map(w=>{const option=el('option',w.name);option.value=w.id;return option;}));
    if(spaces.some(w=>w.id===old)) $('workspace-select').value=old;
    if (!spaces.length) { const placeholder=el('option','尚未建立工作空間'); placeholder.value=''; $('workspace-select').append(placeholder); }
    renderRail();
}
function renderRail() {
    $('workspace-actions').replaceChildren();
    const workspace=spaces.find(w=>w.id===$('workspace-select').value);
    if(workspace) {
        $('workspace-actions').append(button('重新命名工作空間',()=>edit('工作空間名稱',[field('name','名稱','text',workspace.name)],async values=>{await request(`/api/workspaces/${workspace.id}`,json('PATCH',values));await loadCatalog();})));
        if(!catalog.some(p=>p.workspace_id===workspace.id)) $('workspace-actions').append(button('刪除空白工作空間',async()=>{if(!window.confirm('確定刪除此空白工作空間？'))return;await request(`/api/workspaces/${workspace.id}`,{method:'DELETE'});await loadCatalog();await showToday();}));
    }
    $('project-list').replaceChildren();
    const list=catalog.filter(p=>p.workspace_id===$('workspace-select').value && ($('show-archived').checked||!p.archived_at));
    for(const p of list) { const b=button(`${p.kind==='course'?'▤':'▧'} ${p.name}${p.archived_at?' · 封存':''}`,()=>openProject(p.id)); if(selected?.id===p.id)b.classList.add('active'); $('project-list').append(b); }
    $('new-project').disabled=!spaces.length;
}
function heading(title, subtitle, eyebrow) { $('page-title').textContent=title; $('page-subtitle').textContent=subtitle; $('eyebrow').textContent=eyebrow; $('page-actions').replaceChildren(); $('content').replaceChildren(); $('notice').textContent=''; }
function section(title, root=$('content')) { const s=el('section',null,'section'); const h=el('div',null,'section-head');h.append(el('h2',title)); const body=el('div');s.append(h,body);root.append(s);return {head:h,body}; }
function empty(body,text) { body.append(el('div',text,'empty')); }
function field(name,label,type='text',value='',options=null) { return {name,label,type,value,options}; }
function edit(title, fields, save) {
    $('editor-title').textContent=title; $('editor-fields').replaceChildren(); $('editor-error').textContent='';
    for(const f of fields) {
        const label=el('label',f.label); const input=el(f.options?'select':f.type==='textarea'?'textarea':'input');
        input.name=f.name; input.id='field-'+f.name;
        if(f.options) for(const [value,text] of f.options) { const o=el('option',text);o.value=value;input.append(o); }
        else if(f.type!=='textarea') input.type=f.type;
        input.value=f.value??''; input.required=['name','title','url','note_id'].includes(f.name);
        if(['name','title'].includes(f.name))input.maxLength=f.name==='name'?120:200;
        if(f.type==='textarea') input.maxLength=f.name==='description'?10000:100000;
        label.append(input);$('editor-fields').append(label);
    }
    editorSave=save; $('editor').showModal(); $('editor-fields').querySelector('input,select,textarea')?.focus();
}
$('editor-form').onsubmit=async event=>{event.preventDefault(); const b=$('editor-save');if(b.disabled)return;b.disabled=true;const values=Object.fromEntries(new FormData(event.target));try{await editorSave(values);$('editor').close();}catch(error){$('editor-error').textContent=error.message;}finally{b.disabled=false;}};
for(const id of ['editor-close','editor-cancel'])$(id).onclick=()=>{if(!$('editor-save').disabled)$('editor').close();};
function taskRow(task,p,refresh) {
    const row=el('div',null,'row'), text=el('div',null,'text'); text.append(el('h3',task.title));
    if(task.project_name) text.append(button(task.project_name,()=>openProject(p.id)));
    else if(task.description) text.append(el('small',task.description));
    const status=el('select',null,'status');status.setAttribute('aria-label',`任務狀態：${task.title}`);
    for(const [v,label] of [['todo','待辦'],['doing','進行中'],['done','完成']]){const o=el('option',label);o.value=v;status.append(o);}status.value=task.status;
    status.onchange=async()=>{status.disabled=true;try{await request(projectPath(p)+'/tasks/'+task.id,json('PATCH',{status:status.value}));await refresh();}catch(error){status.value=task.status;fail(error);}finally{status.disabled=false;}};
    row.append(status,text,el('span',task.due_date||'未排日期','meta'),button('編輯',()=>editTask(task,p,refresh)));return row;
}
function editTask(task,p,refresh) {
    edit(task?'編輯任務':'新增任務',[field('title','任務名稱','text',task?.title),field('description','描述','textarea',task?.description),field('due_date','到期日期（可留空）','date',task?.due_date)],async values=>{
        values.due_date=values.due_date||null;await request(projectPath(p)+'/tasks'+(task?'/'+task.id:''),json(task?'PATCH':'POST',values));await refresh();
    });
}
function rememberView(view, id = '') {
    if(document.body.classList.contains('rail-open')) $('rail-toggle').focus();
    document.body.classList.remove('rail-open');
    $('rail-toggle').setAttribute('aria-expanded', 'false');
    const url = new URL(location.href); url.search = '';
    if (view === 'project') {url.searchParams.set('project', id);url.searchParams.set('tab',projectTabs.get(id)||'tasks');}
    else if (view === 'trash') url.searchParams.set('view', 'trash');
    if (url.href !== location.href) history.pushState(null, '', url);
    $('today-nav').classList.toggle('active', view === 'today');
    $('trash-nav').classList.toggle('active', view === 'trash');
}
async function restoreView() {
    const params = new URLSearchParams(location.search);
    if (params.has('project')) {
        const id=params.get('project');
        if(['tasks','notes','links'].includes(params.get('tab'))) projectTabs.set(id,params.get('tab'));
        return openProject(id);
    }
    if (params.get('view') === 'trash') return showTrash();
    return showToday();
}
window.addEventListener('popstate', () => restoreView().catch(fail));
function quickTask(dueDate = '') {
    const projects = catalog.filter(p => !p.archived_at);
    if (!projects.length) return fail(new Error('請先建立一個未封存的專案或課程。'));
    const options = projects.map(p => [p.id, `${spaces.find(w => w.id === p.workspace_id)?.name || ''} / ${p.name}`]);
    edit('快速新增任務', [field('project_id','專案或課程','select',projects[0].id,options),
        field('title','任務名稱'),field('description','描述','textarea'),field('due_date','到期日期（可留空）','date',dueDate)], async values => {
        const project = catalog.find(p => p.id === values.project_id);
        const {project_id, ...body} = values; body.due_date = body.due_date || null;
        await request(projectPath(project)+'/tasks',json('POST',body)); await showToday();
    });
}
async function showToday() {
    rememberView('today');
    const serial=++renderSerial;selected=null;renderRail();heading('今天，從哪裡開始？','先完成重要的事，再留一點空間給自己。','TODAY / 我的本機任務');
    if(catalog.some(p=>!p.archived_at)) $('page-actions').append(button('＋ 快速新增任務',quickTask,true));
    const data=await request('/api/overview/today');if(serial!==renderSerial)return;
    $('date-label').textContent=data.date;
    const groups=[['today','今天到期'],['overdue','逾期待辦'],['unscheduled','未排日期'],['upcoming','接下來']];
    if(!catalog.some(p=>!p.archived_at)) { renderGettingStarted(); return; }
    const grid=el('div',null,'stat-grid');for(const [key,title] of groups){const card=el('div',null,'stat '+key);card.append(el('strong',data.counts[key]),el('span',title));grid.append(card);}$('content').append(grid);
    const daily=el('div',null,'daily-focus'); $('content').append(daily);
    const primary=el('div',null,'daily-primary'), secondary=el('aside',null,'daily-secondary');
    secondary.setAttribute('aria-label','其他待辦');daily.append(primary,secondary);
    for(const [key,title] of groups){
        if(key==='overdue' && !data.counts[key]) {
            primary.append(el('p','✓ 沒有逾期任務，保持這個節奏。','clear-overdue'));continue;
        }
        let root=primary;
        if(['unscheduled','upcoming'].includes(key)) {
            const details=el('details',null,'task-disclosure');
            const summary=el('summary');summary.append(el('span',title),el('span',`${data.counts[key]} 項`,'group-count'));
            details.append(summary);secondary.append(details);root=details;
        }
        const s=section(title,root);
        s.head.parentElement.dataset.group=key;
        if(key==='today')s.head.append(el('span','優先處理','focus-badge'));
        if(root!==primary)s.head.querySelector('h2').classList.add('sr-only');s.head.append(el('small',`${data.counts[key]} 項`));if(!data[key].length){empty(s.body,key==='today'?'今天沒有到期任務。可以從未排日期挑一件事開始。':'這裡暫時沒有任務。');if(key==='today')s.body.append(button('＋ 新增今天的任務',()=>quickTask(data.date),true));continue;}
        s.body.className='list';
        const append = rows => rows.forEach(task => s.body.append(taskRow(task,{id:task.project_id,workspace_id:task.workspace_id},showToday)));
        append(data[key]); let offset=data[key].length;
        if(data.has_more[key]) {
            const more=button('載入更多',async()=>{
                more.disabled=true;
                try {
                    const next=await request(`/api/overview/today?on=${data.date}&offset=${offset}`);
                    if(serial!==renderSerial)return;
                    append(next[key]);offset+=next[key].length;
                    if(!next.has_more[key])more.remove();
                } finally {more.disabled=false;}
            }); s.head.append(more);
        }
    }
}
function renderGettingStarted() {
    const hasSpace=spaces.length>0;
    const panel=el('section',null,'onboarding');
    const intro=el('div',null,'onboarding-intro');
    intro.append(el('p','從一個小目標開始','eyebrow'),el('h2',hasSpace?'工作空間準備好了。':'讓每件事，都有自己的位置。'),el('p',hasSpace?'加入一個專案或課程，就能把任務與筆記整理在一起。':'先為學習、工作或生活建立工作空間，再放進正在進行的專案。','muted'));
    intro.append(button(hasSpace?'＋ 建立第一個專案':'＋ 建立工作空間',()=>hasSpace?$('new-project').click():newWorkspace(),true));
    const steps=el('ol',null,'setup-steps');
    for(const [number,title,description] of [['01','工作空間','例如：大學生活、個人計畫'],['02','專案或課程','例如：畢業專題、資料庫課程'],['03','任務與筆記','寫下下一步，留下重要想法']]) {
        const item=el('li'); item.append(el('span',number,'step-number'));const text=el('div');text.append(el('h3',title),el('p',description));item.append(text);steps.append(item);
    }
    panel.append(intro,steps);$('content').append(panel);
    if(catalog.some(p=>p.archived_at))$('content').append(el('p','你還有已封存的專案，可從選單勾選「顯示已封存」後還原。','muted'));
}
async function openProject(id) {
    const p=catalog.find(p=>p.id===id);if(!p)throw new Error('專案不存在，請重新載入。');rememberView('project',id);selected=p;if(p.archived_at)$('show-archived').checked=true;$('workspace-select').value=p.workspace_id;renderRail();
    const serial=++renderSerial;heading(p.name,p.archived_at?'已封存 · 內容仍可閱讀及整理':'把任務、筆記和教材放在同一個地方。',p.kind==='course'?'COURSE / 課程':'PROJECT / 專案');
    $('page-subtitle').textContent += ` · ${spaces.find(w=>w.id===p.workspace_id)?.name || ''} · 建立於 ${p.created_at?.slice(0,10) || ''}`;
    $('page-actions').append(button('重新命名',()=>edit('重新命名',[field('name','名稱','text',p.name)],async values=>{await request(projectPath(p),json('PATCH',values));await loadCatalog();await openProject(id);})),button(p.archived_at?'取消封存':'封存專案',async()=>{await request(projectPath(p)+'/archive',json('POST',{archived:!p.archived_at}));await loadCatalog();await openProject(id);}));
    const [tasks,notes,links]=await Promise.all([all(projectPath(p)+'/tasks'),all(projectPath(p)+'/notes'),request(projectPath(p)+'/links')]);if(serial!==renderSerial)return;
    const tablist=el('div',null,'project-tabs');tablist.setAttribute('role','tablist');tablist.setAttribute('aria-label','專案內容');
    $('content').append(tablist);
    const panels={},tabs={};
    const activate=(key,focus=false)=>{
        projectTabs.set(id,key);
        for(const name of Object.keys(panels)) {
            panels[name].hidden=name!==key;tabs[name].setAttribute('aria-selected',String(name===key));tabs[name].tabIndex=name===key?0:-1;
        }
        const url=new URL(location.href);url.searchParams.set('tab',key);history.replaceState(null,'',url);
        if(focus)tabs[key].focus();
    };
    const makePanel=(key,label,count)=>{
        const tab=button(`${label} · ${count}`,()=>activate(key));tab.id='project-tab-'+key;tab.setAttribute('role','tab');tab.setAttribute('aria-controls','project-panel-'+key);
        const panel=el('div',null,'project-panel');panel.id='project-panel-'+key;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',tab.id);panel.tabIndex=0;
        tabs[key]=tab;panels[key]=panel;tablist.append(tab);$('content').append(panel);
        tab.onkeydown=event=>{
            const keys=['tasks','notes','links'],index=keys.indexOf(key);
            const next=event.key==='ArrowRight'?keys[(index+1)%3]:event.key==='ArrowLeft'?keys[(index+2)%3]:event.key==='Home'?keys[0]:event.key==='End'?keys[2]:null;
            if(next){event.preventDefault();activate(next,true);}
        };
        return panel;
    };
    const taskPanel=makePanel('tasks','任務',tasks.length),notePanel=makePanel('notes','筆記',notes.length),linkPanel=makePanel('links','連結',links.length);
    activate(projectTabs.get(id)||'tasks');
    const t=section(`任務 · ${tasks.filter(t=>t.status==='done').length} / ${tasks.length} 完成`,taskPanel);t.head.append(button('＋ 新增任務',()=>editTask(null,p,()=>openProject(id)),true));
    if(!tasks.length)empty(t.body,'寫下一件可以開始做的小事。');else{t.body.className='list';for(const task of tasks)t.body.append(taskRow(task,p,()=>openProject(id)));}
    const n=section('專案筆記',notePanel);const actions=el('div');actions.append(button('掛載既有筆記',()=>attachNote(p)),button('＋ 新增筆記',()=>editNote(null,p),true));n.head.append(actions);n.body.className='note-grid';
    if(!notes.length)empty(n.body,'課堂重點、決策紀錄與想法，都可以放在這裡。');for(const note of notes)n.body.append(noteCard(note,p));
    const l=section('教材與參考連結',linkPanel);l.head.append(button('＋ 新增連結',()=>edit('新增教材或參考連結',[field('title','標題'),field('url','網址','url')],async values=>{await request(projectPath(p)+'/links',json('POST',values));await openProject(id);})));if(!links.length)empty(l.body,'加入 Drive 教材、GitHub repository 或參考文章的網址。');else{l.body.className='list';for(const link of links){const row=el('div',null,'row link-row'),a=el('a',link.title,'text');a.href=FlowUI.url(link.url);a.target='_blank';a.rel='noopener noreferrer';row.append(a,button('移除',async()=>{if(!confirm('移除此參考連結？'))return;await request(projectPath(p)+'/links/'+link.id,{method:'DELETE'});await openProject(id);}));l.body.append(row);}}
}
function noteCard(note,p=null,trash=false) {
    const card=el('article',null,'note');card.append(el('h3',note.title||'未命名筆記'),el('p',note.content??note.description??''));const a=el('div',null,'actions');
    if(trash)a.append(button('還原',async()=>{const form=new FormData();form.append('note_id',note.id);await request('/api/notes/restore',{method:'POST',body:form});await showTrash();}));
    else{a.append(button('編輯',()=>editNote(note,p)));if(p)a.append(button('解除關聯',async()=>{await request(projectPath(p)+'/notes/'+note.id,{method:'DELETE'});await openProject(p.id);}));a.append(button('移到回收桶',async()=>{if(!confirm('將筆記移到回收桶？內容之後可還原。'))return;const form=new FormData();form.append('note_id',note.id);await request('/api/notes/delete',{method:'POST',body:form});if(p)await openProject(p.id);else await showToday();}));}card.append(a);return card;
}
function editNote(note,p) {
    let savedId=note?.id; // If attaching fails, retry the same note instead of creating duplicates.
    edit(note?'編輯筆記':'新增專案筆記',[field('title','標題','text',note?.title),field('content','筆記內容','textarea',note?.content??note?.description)],async values=>{
        const form=new FormData();form.append('title',values.title);form.append('description',values.content);form.append('color',note?.color||'yellow');
        if(savedId)form.append('note_id',savedId);
        const saved=await request(savedId?'/api/notes/edit':'/api/notes/add',{method:'POST',body:form});savedId=savedId||saved.id;
        if(p){await request(projectPath(p)+'/notes/'+savedId,{method:'PUT'});await openProject(p.id);}else await showToday();
    });
}
async function attachNote(p) {
    const data=await request('/api/notes/');const candidates=data.notes.filter(n=>n.project_id!==p.id);
    if(!candidates.length)throw new Error('沒有可掛載的筆記，請先新增。');
    edit('掛載筆記（會從原專案移至此處）',[field('note_id','選擇筆記','select','',candidates.map(n=>[n.id,n.title||'未命名']))],async values=>{await request(projectPath(p)+'/notes/'+values.note_id,{method:'PUT'});await openProject(p.id);});
}
async function showTrash(){rememberView('trash');const serial=++renderSerial;selected=null;renderRail();heading('筆記回收桶','刪除的筆記仍保留在這裡，可隨時還原。','RECOVER / 保留你的心血');const data=await request('/api/notes/trash');if(serial!==renderSerial)return;const grid=el('div',null,'note-grid');if(!data.notes.length)empty(grid,'回收桶是空的。');for(const note of data.notes)grid.append(noteCard(note,null,true));$('content').append(grid);}
function newWorkspace(){edit('新增工作空間',[field('name','名稱，例如：大三上')],async values=>{const w=await request('/api/workspaces',json('POST',values));await loadCatalog();$('workspace-select').value=w.id;renderRail();await showToday();});}
$('rail-toggle').onclick=()=>{ const open=document.body.classList.toggle('rail-open'); $('rail-toggle').setAttribute('aria-expanded', String(open)); };
document.addEventListener('keydown', event=>{if(event.key==='Escape'){document.body.classList.remove('rail-open');$('rail-toggle').setAttribute('aria-expanded','false');}});
$('new-workspace').onclick=newWorkspace;
$('new-project').onclick=()=>{const wid=$('workspace-select').value;edit('新增專案或課程',[field('name','名稱'),field('kind','類型','select','project',[['project','專案'],['course','課程']])],async values=>{const p=await request(`/api/workspaces/${wid}/projects`,json('POST',values));await loadCatalog();await openProject(p.id);});};
$('workspace-select').onchange=renderRail;$('show-archived').onchange=renderRail;
$('today-nav').onclick=()=>showToday().catch(fail);$('trash-nav').onclick=()=>showTrash().catch(fail);
$('search-form').onsubmit=async event=>{event.preventDefault();const q=$('search-input').value.trim();if(!q)return;const serial=++renderSerial;try{const data=await request('/api/overview/search?q='+encodeURIComponent(q));if(serial!==renderSerial)return;heading(`搜尋「${q}」`,'每種類型最多顯示 50 筆結果。','FIND / 找回需要的內容');const daily=el('div',null,'search-results');$('content').append(daily);selected=null;renderRail();$('today-nav').classList.remove('active');$('trash-nav').classList.remove('active');for(const [key,title] of [['projects','專案與課程'],['tasks','任務'],['notes','筆記']]){const s=section(title,daily);s.head.append(el('small',`${data[key].length} 項`));if(!data[key].length)empty(s.body,'沒有符合的內容。');for(const item of data[key]){if(key==='notes')s.body.append(noteCard(item,catalog.find(p=>p.id===item.project_id)));else s.body.append(button(item.name||item.title,()=>openProject(key==='projects'?item.id:item.project_id)));}}}catch(error){fail(error);}};
$('content').replaceChildren(FlowUI.skeleton('正在取得工作空間'));
(async()=>{try{await loadCatalog();try{await restoreView();}catch(error){await showToday();fail(error);}}catch(error){heading('開始使用 FocusFlow','登入後即可管理自己的工作空間。','WELCOME');$('content').append(el('p','請先回 Dashboard 登入 Google，或使用訪客模式。'));const a=el('a','使用訪客模式');a.href='/api/auth/guest';$('content').append(a);fail(error);}})();
