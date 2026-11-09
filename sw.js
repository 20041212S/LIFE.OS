// LIFE.OS service worker — offline cache
const CACHE='lifeos-v1';
const ASSETS=['index.html','manifest.json','api/.env.example','README.md'];

self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)));});
self.addEventListener('fetch',e=>{e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)));});
