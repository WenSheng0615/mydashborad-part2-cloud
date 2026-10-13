/* Shared mobile destinations across Dashboard and /projects. */
window.updateMobileDock = function (destination) {
    document.querySelectorAll('[data-dock]').forEach(link => {
        if (link.dataset.dock === destination) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
    });
};
const isDashboard = typeof window.openApp === 'function';
updateMobileDock(isDashboard ? 'home' : 'projects');
if (isDashboard) {
    const navigate = () => {
        if (location.hash === '#calendar') openApp('calendar');
        else if (location.hash === '#home') goHome();
    };
    document.querySelector('[data-dock="home"]').addEventListener('click', event => {
        event.preventDefault();
        history.replaceState(null, '', location.pathname + location.search);
        goHome();
    });
    document.querySelector('[data-dock="calendar"]').addEventListener('click', event => {
        event.preventDefault();
        if (location.hash === '#calendar') openApp('calendar');
        else location.hash = 'calendar';
    });
    window.addEventListener('hashchange', navigate);
    navigate();
}
