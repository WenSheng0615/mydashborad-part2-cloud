/* Trusted built-in App management. Server preferences remain authoritative. */
window.FlowModules = (() => {
    let entries = null, filter = 'all', query = '', connections = {}, connectionRequest = null;
    const checking = new Set();
    const state = document.getElementById('module-status') || document.createElement('p');
    const glyphs = {
        workspace:'M3 7h18v14H3z M8 7V3h8v4 M3 12h18', settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2',
        notes:'M5 3h14v18H5z M8 8h8 M8 12h8 M8 16h5',tasks:'M4 6l2 2 4-4 M13 6h7 M4 14l2 2 4-4 M13 14h7',calendar:'M4 5h16v16H4z M8 3v4 M16 3v4 M4 10h16 M8 14h2 M14 14h2',
        drive:'M3 7h7l2 3h9v11H3z M3 7V4h7l2 3h7v3', music:'M9 18V5l11-2v13 M9 8l11-2 M9 18a3 3 0 1 1-3-3 M20 16a3 3 0 1 1-3-3',money:'M3 6h17v15H3z M3 6V3h14 M15 11h6v5h-6z',chat:'M3 4h18v13H9l-5 4v-4H3z M7 9h10 M7 13h6',quiz:'M2 8l10-5 10 5-10 5z M6 10v8q6 5 12 0v-8 M22 8v9'
    };
    function icon(id) {
        const box=FlowUI.node('span',null,'module-icon module-icon-'+id);
        const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
        svg.setAttribute('viewBox','0 0 24 24'); svg.setAttribute('aria-hidden','true');
        const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',glyphs[id] || glyphs.workspace);svg.append(path);box.append(svg);return box;
    }
    function isEnabled(id) { return !entries || entries.find(m => m.id === id)?.enabled !== false; }
    function connectionRows(module, container, withActions=false) {
        container.replaceChildren();
        const summary=connections[module.id] || [{provider:'連線狀態',status:'unknown',message:'尚未載入；可重新載入設定'}];
        const visible=withActions?summary:summary.filter(info=>info.provider!=='附件儲存（選用）');
        for(const info of visible) {
            const row=FlowUI.node('div',null,'module-connection');
            row.dataset.connectionStatus=info.status;
            row.append(FlowUI.node('strong',info.provider),FlowUI.node('span',info.message));
            if(withActions && info.action==='google') {
                const button=FlowUI.node('button','連接／重新授權 Google','module-button');button.type='button';
                button.onclick=()=>checkLogin(true);row.append(button);
            }
            if(withActions && info.action==='icloud') {
                const button=FlowUI.node('button','iCloud 設定說明','module-button');button.type='button';
                const guide=FlowUI.node('p','目前由伺服器管理者設定私密 CalDAV：將你的 FocusFlow 登入帳號對應到 Apple 帳號及 App 專用密碼，設定後重新建立容器。請透過私密的部署設定操作，不要在聊天、模組搜尋欄或一般表單貼上密碼。此連線只提供唯讀行事曆。','module-footnote');guide.hidden=true;
                button.setAttribute('aria-expanded','false');button.onclick=()=>{guide.hidden=!guide.hidden;button.setAttribute('aria-expanded',String(!guide.hidden));};
                row.append(button,guide);
            }
            container.append(row);
        }
    }
    async function loadConnections() {
        if(!document.getElementById('module-list'))return;
        if(connectionRequest)return connectionRequest;
        connectionRequest=(async()=>{
            const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),10000);
            try {
                const data=await FlowUI.request('/api/modules/connections',{signal:controller.signal});
                if(data.connections && typeof data.connections==='object')connections=data.connections;
            } catch(_) {state.textContent='連線狀態暫時無法載入，App 設定仍可使用。';}
            finally {clearTimeout(timer);render();connectionRequest=null;}
        })();
        return connectionRequest;
    }
    async function checkConnections(module, button, rows, feedback) {
        if(checking.has(module.id))return;
        checking.add(module.id);button.disabled=true;button.textContent='正在檢查…';
        const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),45000);
        try {
            const data=await FlowUI.request('/api/modules/'+module.id+'/connections/check',{method:'POST',signal:controller.signal});
            if(!Array.isArray(data.connections))throw new Error();
            connections[module.id]=data.connections;connectionRows(module,rows,true);render();
            feedback.textContent='檢查完成；結果僅代表本次連線，未變更資料。';
        } catch(_) {feedback.textContent='檢查未完成，請稍後重試；已保留原設定。';}
        finally {clearTimeout(timer);checking.delete(module.id);button.disabled=false;button.textContent='檢查連線';}
    }
    function detail(module) {
        const dialog=document.getElementById('module-detail');
        document.getElementById('module-detail-title').textContent=module.name;
        const body=document.getElementById('module-detail-body');body.replaceChildren();
        body.append(icon(module.id),FlowUI.node('p',module.description,'module-description'));
        const facts=document.createElement('dl');
        for(const [label,value] of [
            ['狀態',module.core?'平台核心 · 固定啟用':module.enabled?'已啟用':'已停用'],
            ['來源','FocusFlow 內建'],['外部服務需求',module.integrations.join('、') || '不需要外部服務'],
            ['資料保存',module.core?'核心資料持續保留。':'停用不會刪除資料；重新啟用即可繼續使用。'],
            ['更新方式','隨 FocusFlow 一起更新']
        ]) facts.append(FlowUI.node('dt',label),FlowUI.node('dd',value));
        body.append(facts);
        if(module.integrations.length)body.append(FlowUI.node('p','啟用 App 不代表外部服務已連線；帳號授權與連線設定需另行完成。','module-footnote'));
        const heading=FlowUI.node('h3','服務連線','module-connections-heading');
        const rows=FlowUI.node('div',null,'module-connections');connectionRows(module,rows,true);body.append(heading,rows);
        if(['tasks','calendar','drive','music'].includes(module.id)) {
            const check=FlowUI.node('button','檢查連線','module-button');check.type='button';check.disabled=!module.enabled || checking.has(module.id);
            check.onclick=()=>checkConnections(module,check,rows,feedback);body.append(check);
            const feedback=FlowUI.node('p',module.enabled?'只在按下按鈕後進行唯讀連線檢查。':'請先啟用此 App 再檢查連線。','module-footnote');
            feedback.id='module-check-status';feedback.setAttribute('role','status');body.append(feedback);
        }
        dialog.showModal();
    }
    async function save(module, checkbox) {
        checkbox.disabled=true;state.textContent='正在儲存…';
        try {
            const data=await FlowUI.request('/api/modules/'+module.id, {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:checkbox.checked})});
            if(!Array.isArray(data.modules))throw new Error('模組資料格式錯誤');
            entries=data.modules;apply();render();
            (document.querySelector(`[aria-label="啟用${module.name}"]`) || document.querySelector('[data-module-filter][aria-pressed="true"]'))?.focus();
            state.textContent='已儲存；停用只關閉 App，資料會保留。';
            window.dispatchEvent(new CustomEvent('modules-changed'));
        } catch(error) {
            checkbox.checked=module.enabled;
            state.textContent='儲存失敗，已保留原設定：'+error.message;
        } finally {checkbox.disabled=false;}
    }
    function tile(module) {
        const card=FlowUI.node('article',null,'module-row module-tile'+(!module.enabled?' is-disabled':''));
        card.dataset.moduleCard=module.id;
        const head=FlowUI.node('div',null,'module-tile-top');
        const title=FlowUI.node('div');title.append(FlowUI.node('h3',module.name,'module-name'),FlowUI.node('small',module.core?'平台核心':'FocusFlow 內建','module-source'));
        head.append(icon(module.id),title);
        card.append(head,FlowUI.node('p',module.description,'module-description'));
        const footer=FlowUI.node('div',null,'module-tile-footer');
        const details=FlowUI.node('button','詳細資料','module-button');details.type='button';details.setAttribute('aria-label',module.name+'詳細資料');details.onclick=()=>detail(module);footer.append(details);
        if(module.core)footer.append(FlowUI.node('span','固定啟用','module-core'));
        else {
            const label=FlowUI.node('label',null,'module-toggle');
            const text=FlowUI.node('span',module.enabled?'已啟用':'已停用');
            const checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=module.enabled;checkbox.setAttribute('aria-label','啟用'+module.name);
            const visual=FlowUI.node('span',null,'module-switch');visual.setAttribute('aria-hidden','true');
            checkbox.addEventListener('change',()=>save(module,checkbox));
            label.append(text,checkbox,visual);footer.append(label);
        }
        const connection=FlowUI.node('div',null,'module-connections module-card-connections');connectionRows(module,connection);
        card.append(connection,footer);return card;
    }
    function render() {
        const list=document.getElementById('module-list'), coreList=document.getElementById('module-core-list');
        if(!list || !coreList)return;
        list.replaceChildren();coreList.replaceChildren();
        if(!entries)return;
        const matches=m=>[m.name,m.description,...m.integrations].join(' ').toLocaleLowerCase().includes(query);
        const optional=entries.filter(m=>!m.core);
        const shown=optional.filter(m=>matches(m)&&(filter==='all'||m.enabled===(filter==='enabled')));
        shown.forEach(m=>list.append(tile(m)));
        const core=filter==='all'?entries.filter(m=>m.core&&matches(m)):[];
        core.forEach(m=>coreList.append(tile(m)));
        document.getElementById('module-core-section').hidden=!core.length;
        document.getElementById('module-empty').hidden=!!shown.length;
        document.getElementById('module-count').textContent=shown.length+' 個 App';
        const counts={all:optional.length,enabled:optional.filter(m=>m.enabled).length,disabled:optional.filter(m=>!m.enabled).length};
        document.querySelectorAll('[data-module-filter]').forEach(b=>{
            const id=b.dataset.moduleFilter;b.setAttribute('aria-pressed',String(id===filter));
            b.textContent=({all:'全部 App',enabled:'已啟用',disabled:'已停用'})[id]+' · '+counts[id];
        });
    }
    function apply() {
        for(const module of entries || []){
            document.querySelectorAll(`[data-module-id="${module.id}"]`).forEach(el=>el.hidden=!module.enabled);
            const panel=document.getElementById('view-'+module.id);
            if(!module.enabled&&panel?.classList.contains('active'))goHome();
        }
    }
    async function refresh() {
        const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),8000);
        try{
            const response=await fetch('/api/modules',{signal:controller.signal});
            if(response.status===401){state.textContent='請先登入或進入訪客模式，再設定自己的 App。';return;}
            if(!response.ok)throw new Error('讀取失敗');
            const data=await response.json();if(!Array.isArray(data.modules))throw new Error('資料格式錯誤');
            entries=data.modules;apply();render();
            state.textContent='設定會跟隨帳號；停用不會刪除資料或撤銷外部服務授權。';
        }catch(_){state.textContent='暫時無法載入模組設定，請重試。';}finally{clearTimeout(timer);}
    }
    document.getElementById('module-reload')?.addEventListener('click',()=>{api.ready=refresh();loadConnections();});
    document.getElementById('module-search')?.addEventListener('input',e=>{query=e.target.value.trim().toLocaleLowerCase();render();});
    document.querySelectorAll('[data-module-filter]').forEach(button=>button.addEventListener('click',()=>{filter=button.dataset.moduleFilter;render();}));
    document.getElementById('module-detail-close')?.addEventListener('click',()=>document.getElementById('module-detail').close());
    const api={isEnabled,refresh,loadConnections,ready:null};api.ready=refresh();return api;
})();
