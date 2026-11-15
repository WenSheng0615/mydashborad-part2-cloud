/* Account disclosure shared by Home and Workspace. No credentials enter the UI. */
window.FocusAccount = (() => {
    let nextId=0;
    const closeAll=(focus=false)=>document.querySelectorAll('.account-control').forEach(control=>{
        const trigger=control.querySelector('button'),panel=control.querySelector('.account-panel');
        if(!panel.hidden && focus)trigger.focus();
        panel.hidden=true;trigger.setAttribute('aria-expanded','false');
    });
    document.addEventListener('click',event=>{if(!event.target.closest('.account-control'))closeAll();});
    document.addEventListener('keydown',event=>{if(event.key==='Escape')closeAll(true);});
    document.addEventListener('focusin',event=>{if(!event.target.closest('.account-control'))closeAll();});
    function render(mount,data) {
        mount.replaceChildren();
        if(!data.logged_in) {
            const link=document.createElement('a');link.className='account-login';link.href='/account';link.textContent=data.error?'帳號狀態':'登入';
            mount.append(link);return;
        }
        const control=document.createElement('div');control.className='account-control';
        const trigger=document.createElement('button');trigger.type='button';trigger.className='account-trigger';
        trigger.setAttribute('aria-label','開啟帳號選單');trigger.setAttribute('aria-expanded','false');
        const image=document.createElement('img');image.alt='';image.src=FlowUI.url(data.info?.picture)||'/static/icons/icon-192.png?v=20261114';
        image.onerror=()=>{image.onerror=null;image.src='/static/icons/icon-192.png?v=20261114';};
        const name=document.createElement('span');name.className='account-name';name.textContent=data.info?.name||'訪客';
        const chevron=document.createElement('span');chevron.className='account-chevron';chevron.textContent='⌄';chevron.setAttribute('aria-hidden','true');trigger.append(image,name,chevron);
        const panel=document.createElement('div');panel.className='account-panel';panel.id='account-panel-'+(++nextId);panel.hidden=true;trigger.setAttribute('aria-controls',panel.id);
        const identity=document.createElement('div');identity.className='account-identity';identity.textContent=data.is_guest?'訪客試用':data.info?.name||'我的帳號';panel.append(identity);
        for(const [label,href] of [['帳號與資料','/account'],['服務連線','/account#connections']]) {
            const link=document.createElement('a');link.href=href;link.textContent=label;panel.append(link);
        }
        const logout=document.createElement('button');logout.type='button';logout.textContent='登出';logout.className='account-logout';
        logout.onclick=async()=>{
            logout.disabled=true;
            try{const response=await fetch('/api/auth/logout');if(!response.ok)throw new Error();location.assign('/');}
            catch(_){logout.disabled=false;logout.textContent='登出失敗，請重試';}
        };
        panel.append(logout);control.append(trigger,panel);mount.append(control);
        trigger.onclick=()=>{const open=panel.hidden;closeAll();panel.hidden=!open;trigger.setAttribute('aria-expanded',String(open));};
        trigger.onkeydown=event=>{if(event.key==='ArrowDown'){event.preventDefault();closeAll();panel.hidden=false;trigger.setAttribute('aria-expanded','true');panel.querySelector('a').focus();}};
    }
    async function refresh(){try{const response=await fetch('/api/auth/user');if(!response.ok)throw new Error();const data=await response.json();document.querySelectorAll('[data-account-control]').forEach(mount=>render(mount,data));}catch(_){document.querySelectorAll('[data-account-control]').forEach(mount=>render(mount,{error:true}));}}
    return {render,refresh};
})();
