// Cache only versioned, same-origin static assets. Never cache private pages or APIs.
const CACHE_NAME = 'focusflow-static-v4';
self.addEventListener('install', event => { self.skipWaiting(); });
self.addEventListener('activate', event => event.waitUntil((async () => {
    for (const name of await caches.keys()) if (name.startsWith('focusflow-') && name !== CACHE_NAME) await caches.delete(name);
    await self.clients.claim();
})()));
self.addEventListener('fetch', event => {
    const request = event.request, url = new URL(request.url);
    if (request.method !== 'GET' || url.origin !== self.location.origin || !url.pathname.startsWith('/static/') || url.pathname.endsWith('/sw.js')) return;
    event.respondWith((async () => {
        const cache = await caches.open(CACHE_NAME);
        try { const response = await fetch(request); if (response.ok) await cache.put(request, response.clone()); return response; }
        catch(error) { const cached = await cache.match(request); if (cached) return cached; throw error; }
    })());
});
