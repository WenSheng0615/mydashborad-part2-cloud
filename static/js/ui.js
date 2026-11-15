window.FlowUI = {
    toast(message, {duration = 3000, kind = 'info'} = {}) {
        let notice = document.getElementById('flow-toast');
        if (!notice) {
            notice = this.node('div', null, 'flow-toast');notice.id='flow-toast';notice.hidden=true;
            notice.setAttribute('role','status');notice.setAttribute('aria-live','polite');notice.setAttribute('aria-atomic','true');
            const text=this.node('span',null,'flow-toast-message');
            const close=this.node('button','×','flow-toast-close');close.type='button';close.setAttribute('aria-label','關閉通知');
            close.onclick=()=>this.toast('');notice.append(text,close);document.body.append(notice);
        }
        clearTimeout(this._toastTimer);clearTimeout(this._toastHideTimer);
        const dismiss=()=>{
            notice.classList.remove('is-visible');
            this._toastHideTimer=setTimeout(()=>{notice.hidden=true;notice.querySelector('.flow-toast-message').textContent='';},220);
        };
        if (!message) {dismiss();return;}
        notice.querySelector('.flow-toast-message').textContent=message;notice.dataset.kind=kind;
        notice.hidden=false;
        // Start the opacity transition after revealing the fixed-position element.
        void notice.offsetWidth;notice.classList.add('is-visible');
        if(duration>0)this._toastTimer=setTimeout(dismiss,duration);
    },
    node(tag, text, className) {
        const el = document.createElement(tag);
        if (text !== undefined && text !== null) el.textContent = String(text);
        if (className) el.className = className;
        return el;
    },
    skeleton(label = '正在取得內容') {
        const state = this.node('div', null, 'content-skeleton');
        state.setAttribute('role', 'status');
        state.append(this.node('span', label, 'loading-sr-label'));
        const rows = this.node('div', null, 'content-skeleton-rows');
        rows.setAttribute('aria-hidden', 'true');
        for (let i = 0; i < 5; i++) {
            const row = this.node('div', null, 'content-skeleton-row');
            const lines = this.node('div', null, 'content-skeleton-lines');
            lines.append(this.node('span'), this.node('span'));
            row.append(this.node('span', null, 'content-skeleton-cover'), lines);
            rows.append(row);
        }
        state.append(rows);
        return state;
    },
    url(value) {
        try {
            const url = new URL(value, location.origin);
            return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
        } catch { return ''; }
    },
    async request(url, options = {}) {
        const response = await fetch(url, options);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const detail = data.detail || data.error;
            const error=new Error(typeof detail === 'string' ? detail : `操作失敗 (${response.status})`);
            error.connectionRequired=!!data.connection_required;throw error;
        }
        return data;
    },
    connectionPrompt(container,error) {
        if(!error.connectionRequired)return false;
        const state=this.node('div',null,'content-refresh-error');state.setAttribute('role','status');
        state.append(this.node('p',error.message));
        const link=this.node('a','前往帳號與服務連線 →');link.href='/account#connections';state.append(link);
        container.replaceChildren(state);return true;
    },
    error(error) { showAlert('操作未完成', error.message || '請稍後再試；已保留輸入內容。'); }
};
