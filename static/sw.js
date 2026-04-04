const CACHE_NAME = 'focusflow-v1';
const urlsToCache = [
  '/',
  '/static/css/drive.css',
  '/static/css/music.css',
  '/static/css/settings.css',
  '/static/js/drive.js',
  '/static/js/music.js'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(urlsToCache);
    })
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request);
    })
  );
});
