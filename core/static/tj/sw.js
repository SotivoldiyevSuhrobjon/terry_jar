/* Terry Jar service worker: ilova qobig'i va kutubxonalar keshda — internet uzilsa ham sahifa ochiladi.
   Ma'lumotlar keshda emas: ular brauzer xotirasida (localStorage) va navbatda saqlanadi. */
const CACHE = 'tj-__VERSION__';
const LIBS = [
  'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js',
  'https://cdn.jsdelivr.net/npm/xlsx-js-style@1.2.0/dist/xlsx.bundle.js',
];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => Promise.all(LIBS.map(u => c.add(new Request(u, { mode: 'no-cors' })).catch(() => {})))));
  self.skipWaiting();
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener('fetch', e => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== 'GET' || u.pathname.startsWith('/api/') || u.pathname.startsWith('/ws/')) return;
  if (u.pathname === '/app/') {
    // tarmoq birinchi; uzilgan bo'lsa oxirgi ochilgan sahifa
    e.respondWith(fetch(r).then(res => {
      if (res.ok && res.url.endsWith('/app/')) { const cp = res.clone(); caches.open(CACHE).then(c => c.put('/app/', cp)); }
      return res;
    }).catch(() => caches.match('/app/')));
    return;
  }
  if (u.pathname.startsWith('/static/') || LIBS.includes(r.url)) {
    e.respondWith(caches.match(r).then(hit => hit || fetch(r).then(res => {
      const cp = res.clone(); caches.open(CACHE).then(c => c.put(r, cp)); return res;
    })));
  }
});
