/* Built-in App preferences; server is authoritative and no provider credentials live here. */
window.FlowModules = (() => {
    let entries = null;
    const state = document.getElementById('module-status') || document.createElement('p');
    function isEnabled(id) { return !entries || entries.find(m => m.id === id)?.enabled !== false; }
    function render() {
        const list = document.getElementById('module-list');
        if (!list) return;
        list.replaceChildren();
        if (!entries) return;
        for (const module of entries) {
            const row = FlowUI.node('div', null, 'module-row');
            const info = FlowUI.node('div');
            const name = FlowUI.node('strong', module.name);
            info.append(name, FlowUI.node('p', module.description, 'setting-desc'));
            info.append(FlowUI.node('small', module.core ? '平台核心 · 固定啟用' : '內建 App · ' + (module.integrations.length ? module.integrations.join(' / ') : '本機資料')));
            row.append(info);
            if (module.core) row.append(FlowUI.node('span', '核心', 'module-core'));
            else {
                const label = FlowUI.node('label', null, 'module-toggle');
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox'; checkbox.checked = module.enabled;
                checkbox.setAttribute('aria-label', '啟用' + module.name);
                checkbox.addEventListener('change', async () => {
                    checkbox.disabled = true;
                    state.textContent = '正在儲存…';
                    try {
                        const data = await FlowUI.request('/api/modules/' + module.id, {
                            method: 'PATCH', headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({enabled: checkbox.checked})
                        });
                        if (!Array.isArray(data.modules)) throw new Error('模組資料格式錯誤');
                        entries = data.modules;
                        apply(); render();
                        document.querySelector(`[aria-label="啟用${module.name}"]`)?.focus();
                        state.textContent = '已儲存；停用只關閉 App，資料會保留。';
                        window.dispatchEvent(new CustomEvent('modules-changed'));
                        if (module.id === 'drive') initSettings();
                    } catch (error) {
                        checkbox.checked = module.enabled;
                        state.textContent = '儲存失敗，已保留原設定：' + error.message;
                    } finally { checkbox.disabled = false; }
                });
                label.append(checkbox, FlowUI.node('span', module.enabled ? '已啟用' : '已停用'));
                row.append(label);
            }
            list.append(row);
        }
    }
    function apply() {
        for (const module of entries || []) {
            document.querySelectorAll(`[data-module-id="${module.id}"]`).forEach(el => el.hidden = !module.enabled);
            const panel = document.getElementById('view-' + module.id);
            if (!module.enabled && panel?.classList.contains('active')) goHome();
        }
    }
    async function refresh() {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 8000);
        try {
            const response = await fetch('/api/modules', {signal: controller.signal});
            if (response.status === 401) {
                state.textContent = '請先登入或進入訪客模式，再設定自己的 App。';
                return;
            }
            if (!response.ok) throw new Error('讀取失敗');
            const data = await response.json();
            if (!Array.isArray(data.modules)) throw new Error('資料格式錯誤');
            entries = data.modules;
            apply(); render();
            state.textContent = '設定會跟隨帳號；停用不會刪除資料或撤銷外部服務授權。';
        } catch (_) { state.textContent = '暫時無法載入模組設定，請重試。'; }
        finally { clearTimeout(timer); }
    }
    document.getElementById('module-reload')?.addEventListener('click', () => { api.ready = refresh(); });
    // Apply persisted preferences before any App performs its initial request.
    const api = {isEnabled, refresh, ready: null};
    api.ready = refresh();
    return api;
})();
