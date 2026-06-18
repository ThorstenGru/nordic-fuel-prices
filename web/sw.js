const CACHE = 'eurofuel-v2';

self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE).then(c =>
      c.addAll(['index.html']).catch(() => {})
    )
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Country JSON: network-first (fresh prices), fallback to cache
  if (url.pathname.match(/\/[a-z]{2}\.json$/) || url.pathname.endsWith('meta.json')) {
    e.respondWith(
      fetch(e.request)
        .then(r => {
          if (r.ok) {
            const clone = r.clone();
            caches.open(CACHE).then(c => c.put(e.request, clone));
          }
          return r;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // CDN assets (Leaflet, tiles): cache-first
  if (url.hostname !== self.location.hostname) {
    e.respondWith(
      caches.match(e.request).then(cached => {
        if (cached) return cached;
        return fetch(e.request).then(r => {
          if (r.ok && r.type !== 'opaque') {
            const clone = r.clone();
            caches.open(CACHE).then(c => c.put(e.request, clone));
          }
          return r;
        }).catch(() => cached || Response.error());
      })
    );
    return;
  }

  // Same-origin (index.html, sw.js, manifest): stale-while-revalidate
  e.respondWith(
    caches.open(CACHE).then(c =>
      c.match(e.request).then(cached => {
        const network = fetch(e.request).then(r => {
          if (r.ok) c.put(e.request, r.clone());
          return r;
        });
        return cached || network;
      })
    )
  );
});
