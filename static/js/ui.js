window.FlowUI = {
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
            throw new Error(typeof detail === 'string' ? detail : `操作失敗 (${response.status})`);
        }
        return data;
    },
    error(error) { showAlert('操作未完成', error.message || '請稍後再試；已保留輸入內容。'); }
};
