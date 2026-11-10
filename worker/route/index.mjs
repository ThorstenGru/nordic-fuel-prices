// Routing proxy for eurofuelprices.com, served at eurofuelprices.com/api/route (Worker Route on the zone).
// Why: one place to cache, validate and (later) swap the routing provider; the browser never talks to the router directly.
// Privacy: coordinates are rounded to ~100 m and never logged (no console.log of the request, no analytics binding).
const UPSTREAM = 'https://valhalla1.openstreetmap.de/route';   // FOSSGIS public Valhalla: ferries included. Swap provider here only.
const SITE = /^https:\/\/(www\.)?eurofuelprices\.com(\/|$)/;
const EUROPE = { la: [27, 72], lo: [-32, 45] };                  // rough bounding box; everything outside is refused
const TTL = 6 * 3600;                                           // a route does not change within hours; prices are priced client-side

const json = (o, status, extra) => new Response(JSON.stringify(o), { status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store', ...extra } });
const num = (v, [lo, hi]) => typeof v === 'number' && isFinite(v) && v >= lo && v <= hi;

// Pure: turn the client's request into a canonical, safe Valhalla request (or null). Exported for tests.
export function normalise(raw) {
  let j; try { j = JSON.parse(raw); } catch (_) { return null; }
  const L = j && j.locations;
  if (!Array.isArray(L) || L.length !== 2) return null;
  for (const p of L) if (!p || !num(p.lat, EUROPE.la) || !num(p.lon, EUROPE.lo)) return null;
  return {
    locations: L.map(p => ({ lat: +p.lat.toFixed(3), lon: +p.lon.toFixed(3) })),
    costing: 'auto', directions_type: 'maneuvers',
    alternates: Math.max(0, Math.min(2, j.alternates | 0)),
  };
}

export default {
  async fetch(req, env, ctx) {
    if (req.method !== 'GET') return json({ error: 'method' }, 405);
    const from = req.headers.get('Origin') || req.headers.get('Referer') || '';
    if (req.headers.get('Sec-Fetch-Site') !== 'same-origin' && !SITE.test(from)) return json({ error: 'origin' }, 403);   // not a browser on our own pages
    const q = normalise(new URL(req.url).searchParams.get('json'));
    if (!q) return json({ error: 'request' }, 400);

    const body = JSON.stringify(q);
    const key = new Request('https://eurofuelprices.com/api/route/c?j=' + encodeURIComponent(body));
    const hit = await caches.default.match(key);
    if (hit) return new Response(hit.body, { status: 200, headers: { 'content-type': 'application/json', 'cache-control': 'no-store', 'x-cache': 'HIT' } });

    let r;
    try { r = await fetch(UPSTREAM + '?json=' + encodeURIComponent(body), { headers: { 'user-agent': 'eurofuelprices.com route proxy' }, signal: AbortSignal.timeout(12000) }); }
    catch (_) { return json({ error: 'upstream' }, 502); }
    if (!r.ok) return json({ error: 'upstream', status: r.status }, 502);   // never cached: the client falls back to its own router chain
    const text = await r.text();
    ctx.waitUntil(caches.default.put(key, new Response(text, { headers: { 'content-type': 'application/json', 'cache-control': 'public, max-age=' + TTL } })));
    return new Response(text, { status: 200, headers: { 'content-type': 'application/json', 'cache-control': 'no-store', 'x-cache': 'MISS' } });
  },
};
