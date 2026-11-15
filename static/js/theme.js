// Read the same preference as Dashboard settings before the page is painted.
try {
    document.body.classList.toggle('light-mode', localStorage.getItem('theme') !== 'dark');
} catch (_) { document.body.classList.add('light-mode'); }
window.addEventListener('storage', event => {
    if (event.key === 'theme') document.body.classList.toggle('light-mode', event.newValue !== 'dark');
});
