// Routing proxy for eurofuelprices.com, served at eurofuelprices.com/api/route (Worker Route on the zone).
// Why: one place to cache, validate and (later) swap the routing provider; the browser never talks to the router directly.
// Privacy: coordinates are rounded to ~100 m and never logged (no console.log of the request, no analytics binding).
const UPSTREAM = 'https://valhalla1.openstreetmap.de/route';   // FOSSGIS public Valhalla: ferries included. Swap provider here only.
const SITE = /^https:\/\/(www\.)?eurofuelprices\.com(\/|$)/;
const EUROPE = { la: [27, 72], lo: [-32, 45] };                  // rough bounding box; everything outside is refused
const TTL = 6 * 3600;
const RL_MAX = 20;                                              // uncached (= upstream) requests per visitor and minute; a trip needs 1-3. Best effort per data centre: the origin check below can be faked by a script                                           // a route does not change within hours; prices are priced client-side

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

// ── Backup router: OpenRouteService (free key). api.openrouteservice.org is shut down (Nov 2026); the supported host is api.heigit.org.
// Answer is converted to the Valhalla trip shape the app already reads, so the browser needs no second code path.
const ORS_URL = 'https://api.heigit.org/openrouteservice/v2/directions/driving-car/geojson';
const orsBody = q => ({ coordinates: q.locations.map(p => [p.lon, p.lat]), extra_info: ['waytype', 'tollways'], instructions: true, units: 'km' });
function encode6(pts) {                                          // [[lat,lon]...] -> Google polyline, 6 decimals (what the app decodes)
  let la = 0, lo = 0, out = '';
  const enc = v => { v = v < 0 ? ~(v << 1) : v << 1; let s = ''; while (v >= 32) { s += String.fromCharCode((32 | (v & 31)) + 63); v >>= 5; } return s + String.fromCharCode(v + 63); };
  for (const [a, b] of pts) { const A = Math.round(a * 1e6), B = Math.round(b * 1e6); out += enc(A - la) + enc(B - lo); la = A; lo = B; }
  return out;
}
// Pure: ORS geojson -> { trip } in Valhalla's shape. Motorway flag is an approximation (average step speed >= 85 km/h): ORS has no motorway class.
export function orsToValhalla(j) {
  const f = j.features[0], p = f.properties, c = f.geometry.coordinates;
  const way = (p.extras && p.extras.waytypes && p.extras.waytypes.values) || [];
  const ferryAt = i => way.some(([a, b, t]) => t === 9 && i >= a && i < b);                  // waytype 9 = ferry; ranges share end points, so half-open
  const toll = ((p.extras && p.extras.tollways && p.extras.tollways.values) || []).some(v => v[2] === 1);
  const steps = (p.segments || []).flatMap(s => s.steps || []);
  const maneuvers = steps.map(s => ({ length: s.distance, time: s.duration, highway: s.duration > 0 && s.distance / (s.duration / 3600) >= 85, ferry: ferryAt(s.way_points[0]) }));
  const hasFerry = way.some(v => v[2] === 9);
  return { trip: { status: 0, summary: { length: p.summary.distance, time: p.summary.duration, has_toll: toll },
    legs: [{ shape: encode6(c.map(([lo, la]) => [la, lo])), maneuvers, summary: { has_ferry: hasFerry, has_toll: toll } }] } };
}

// Per-visitor counter in the Worker cache (no KV, free). Not exact (read-then-write), which is fine for a safety valve.
export async function overLimit(req, now = Date.now()) {
  const ip = req.headers.get('CF-Connecting-IP') || 'none';
  const key = new Request('https://eurofuelprices.com/api/route/rl/' + encodeURIComponent(ip) + '/' + Math.floor(now / 60000));
  const hit = await caches.default.match(key);
  const n = hit ? (+(await hit.text()) || 0) + 1 : 1;
  await caches.default.put(key, new Response(String(n), { headers: { 'cache-control': 'max-age=120' } }));
  return n > RL_MAX;
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

    if (await overLimit(req)) return json({ error: 'rate' }, 429, { 'retry-after': '60' });   // before any upstream call; cache hits above are free
    let text = null, src = 'valhalla';
    try {
      const r = await fetch(UPSTREAM + '?json=' + encodeURIComponent(body), { headers: { 'user-agent': 'eurofuelprices.com route proxy' }, signal: AbortSignal.timeout(12000) });
      if (r.ok) text = await r.text();
    } catch (_) {}
    if (text == null && env.ORS_KEY) {            // backup router, only when the secret ORS_KEY is set (wrangler secret put ORS_KEY)
      try {
        const r = await fetch(ORS_URL, { method: 'POST', headers: { 'content-type': 'application/json', authorization: env.ORS_KEY }, body: JSON.stringify(orsBody(q)), signal: AbortSignal.timeout(12000) });
        if (r.ok) { text = JSON.stringify(orsToValhalla(await r.json())); src = 'ors'; }
      } catch (_) {}
    }
    if (text == null) return json({ error: 'upstream' }, 502);   // never cached: the client falls back to its own router chain
    ctx.waitUntil(caches.default.put(key, new Response(text, { headers: { 'content-type': 'application/json', 'cache-control': 'public, max-age=' + TTL } })));
    return new Response(text, { status: 200, headers: { 'content-type': 'application/json', 'cache-control': 'no-store', 'x-cache': 'MISS', 'x-src': src } });
  },
};
