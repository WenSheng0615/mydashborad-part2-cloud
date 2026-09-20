// Read the same preference as Dashboard settings before the page is painted.
try {
    document.body.classList.toggle('light-mode', localStorage.getItem('theme') === 'light');
} catch (_) { /* Storage may be disabled; retain the default dark theme. */ }
window.addEventListener('storage', event => {
    if (event.key === 'theme') document.body.classList.toggle('light-mode', event.newValue === 'light');
});
