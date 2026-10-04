// EuroFuelPrices Service Worker
// HTML shell (index.html/admin.html/'/'): network-first, falls back to cache when offline.
//   (Was cache-first — meant anyone who had ever opened the app kept seeing the shell from the
//   day they first visited, forever, with no way to get a layout/bugfix short of clearing site
//   data. Data is king; the app itself must stay just as fresh.)
// Data JSON: network-first with cache fallback (unchanged).
// Versioned CDN libraries (URL contains the version) and small static icons: cache-first — safe,
// because a version bump changes the URL itself.

const SHELL_CACHE = 'efp-shell-v3';
const DATA_CACHE  = 'efp-data-v2';

const SHELL_ASSETS = [
  './',
  './index.html',
  './admin.html',
  './manifest.json',
  './icon.svg',
];

// CDN assets — versioned URLs, safe to cache indefinitely
const CDN_ASSETS = [
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
  'https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css',
  'https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css',
  'https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js',
];

self.addEventListener('install', event => {
  event.waitUntil(
    Promise.all([
      caches.open(SHELL_CACHE).then(c => c.addAll([...SHELL_ASSETS, ...CDN_ASSETS]).catch(() => {})),
    ])
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys
        .filter(k => k !== SHELL_CACHE && k !== DATA_CACHE)
        .map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // HTML navigations and the shell pages themselves: always try the network first, so a deploy
  // reaches every open/installed app on the very next load instead of being stuck behind the cache.
  const isHtmlShell = event.request.mode === 'navigate'
    || url.pathname.endsWith('/index.html') || url.pathname.endsWith('/admin.html')
    || url.pathname === '/' || url.pathname.endsWith('/');
  if (isHtmlShell && url.origin === self.location.origin) {
    event.respondWith(networkFirst(event.request, SHELL_CACHE));
    return;
  }

  // Data JSON files: network-first, fall back to cached copy
  if (url.pathname.match(/\.(json)$/) && !url.pathname.includes('nominatim')) {
    event.respondWith(networkFirst(event.request, DATA_CACHE));
    return;
  }

  // Tile images: network-only (too large to cache, and stale tiles aren't useful)
  if (url.hostname.includes('basemaps.cartocdn.com') || url.hostname.includes('tile.openstreetmap')
      || url.hostname.includes('arcgisonline.com')) {
    event.respondWith(fetch(event.request).catch(() => new Response('', { status: 503 })));
    return;
  }

  // Everything else (versioned CDN libs, manifest, icon): cache-first
  event.respondWith(cacheFirst(event.request));
});

async function networkFirst(request, cacheName) {
  try {
    const response = await fetch(request, { cache: 'no-store' });
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch (_) {
    const cached = await caches.match(request);
    if (cached) return cached;
    return new Response(JSON.stringify({ error: 'offline' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(SHELL_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (_) {
    return new Response('Offline', { status: 503 });
  }
}
