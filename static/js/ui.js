window.FlowUI = {
    node(tag, text, className) {
        const el = document.createElement(tag);
        if (text !== undefined && text !== null) el.textContent = String(text);
        if (className) el.className = className;
        return el;
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
