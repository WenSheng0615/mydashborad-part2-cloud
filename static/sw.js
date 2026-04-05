const CACHE_NAME = 'focusflow-v2';
const urlsToCache = [
  '/',
  '/static/manifest.json',
  '/static/css/drive.css',
  '/static/css/music.css',
  '/static/css/calendar.css',
  '/static/css/notes.css',
  '/static/css/tasks.css',
  '/static/css/money.css',
  '/static/css/chat.css',
  '/static/css/settings.css',
  '/static/js/drive.js',
  '/static/js/music.js',
  '/static/js/calendar.js',
  '/static/js/notes.js',
  '/static/js/tasks.js',
  '/static/js/money.js',
  '/static/js/chat.js',
  '/static/js/settings.js'
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
