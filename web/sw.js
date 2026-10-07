// EuroFuelPrices Service Worker
// HTML shell (index.html/admin.html/'/'): network-first, falls back to cache when offline.
//   (Was cache-first — meant anyone who had ever opened the app kept seeing the shell from the
//   day they first visited, forever, with no way to get a layout/bugfix short of clearing site
//   data. Data is king; the app itself must stay just as fresh.)
// Data JSON: the app asks for `<cc>.json?v=<fetched_at from meta.json>` — a URL that never changes
//   content — so those are cache-first (instant on repeat visits, nothing re-downloaded until the
//   data really changed) and older versions of the same country are pruned. meta.json and other
//   unversioned JSON stay network-first, with a short timeout so slow 4G falls back to the cache.
// Versioned CDN libraries (URL contains the version) and small static icons: cache-first — safe,
// because a version bump changes the URL itself.

const SHELL_CACHE = 'efp-shell-v5';
const DATA_CACHE  = 'efp-data-v3';
const SLOW_NET_MS = 3500;   // flaky/slow connection: serve the cached copy instead of waiting

const SHELL_ASSETS = [
  './',
  './index.html',
  './admin.html',
  './manifest.json',
  './icon.svg',
  './logo.svg',
  './icon-192.png',
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
    event.respondWith(networkFirst(event.request, SHELL_CACHE, SLOW_NET_MS));
    return;
  }

  // Data JSON
  if (url.origin === self.location.origin && /\.json$/.test(url.pathname)) {
    if (url.searchParams.has('v') && url.pathname !== '/manifest.json') {
      event.respondWith(versionedData(event.request, url));
    } else {
      event.respondWith(networkFirst(event.request, DATA_CACHE, SLOW_NET_MS));
    }
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

async function networkFirst(request, cacheName, timeoutMs) {
  const cache = await caches.open(cacheName);
  const net = fetch(request, { cache: 'no-store' }).then(res => {
    if (res.ok) cache.put(request, res.clone());
    return res;
  });
  net.catch(() => {});                       // a late failure after the race must not surface
  const offline = () => new Response(JSON.stringify({ error: 'offline' }), {
    status: 503, headers: { 'Content-Type': 'application/json' } });
  try {
    if (!timeoutMs || !(await cache.match(request))) return await net;
    return await Promise.race([net, new Promise((_, rej) => setTimeout(() => rej(new Error('slow')), timeoutMs))]);
  } catch (_) {
    const cached = await cache.match(request);
    if (cached) return cached;
    try { return await net; } catch (e) { return offline(); }
  }
}

// Versioned data URL = immutable content: cache-first, then drop older versions of the same file.
async function versionedData(request, url) {
  const cache = await caches.open(DATA_CACHE);
  const hit = await cache.match(request);
  if (hit) return hit;
  try {
    const res = await fetch(request);
    if (res.ok) {
      await cache.put(request, res.clone());
      for (const k of await cache.keys()) {
        const u = new URL(k.url);
        if (u.pathname === url.pathname && u.search !== url.search) cache.delete(k);
      }
    }
    return res;
  } catch (_) {
    const any = (await cache.keys()).find(k => new URL(k.url).pathname === url.pathname);   // offline: last version we have
    return any ? cache.match(any) : new Response(JSON.stringify({ error: 'offline' }), { status: 503, headers: { 'Content-Type': 'application/json' } });
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
