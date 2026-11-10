// Run: node tools/test_route_worker.mjs   (needs Node 18+)
import assert from 'node:assert/strict';
import w, { normalise } from '../worker/route/index.mjs';

const ok = { locations: [{ lat: 55.6049, lon: 13.0038 }, { lat: 53.5511, lon: 9.9937 }], alternates: 2 };
const n = normalise(JSON.stringify(ok));
assert.deepEqual(n.locations, [{ lat: 55.605, lon: 13.004 }, { lat: 53.551, lon: 9.994 }]);   // rounded to ~100 m
assert.equal(n.alternates, 2); assert.equal(n.costing, 'auto');
assert.equal(normalise(JSON.stringify({ ...ok, alternates: 99 })).alternates, 2);           // capped
assert.equal(normalise('not json'), null);
assert.equal(normalise(JSON.stringify({ locations: [ok.locations[0]] })), null);              // needs exactly two points
assert.equal(normalise(JSON.stringify({ locations: [{ lat: 40.7, lon: -74 }, ok.locations[1]] })), null);   // outside Europe
assert.equal(normalise(JSON.stringify({ locations: [{ lat: '55', lon: '13' }, ok.locations[1]] })), null); // strings refused
assert.equal(Object.keys(normalise(JSON.stringify({ ...ok, costing: 'bus', date_time: 1 }))).sort().join(), 'alternates,costing,directions_type,locations');  // no pass-through

// fetch handler with a fake cache and a fake upstream
const store = new Map(); let upstream = 0, mode = 'ok';
globalThis.caches = { default: { match: async k => store.get(k.url) && new Response(store.get(k.url)), put: async (k, r) => { store.set(k.url, await r.text()); } } };
globalThis.fetch = async () => { upstream++; return mode === 'ok' ? new Response('{"trip":{"status":0}}') : new Response('x', { status: 500 }); };
const pending = []; const ctx = { waitUntil: p => pending.push(p) };
const call = (h, url) => w.fetch(new Request(url, { headers: h }), {}, ctx);
const url = 'https://eurofuelprices.com/api/route?json=' + encodeURIComponent(JSON.stringify(ok));

assert.equal((await call({}, url)).status, 403);                                              // no site header
assert.equal((await call({ Referer: 'https://evil.example/' }, url)).status, 403);
assert.equal((await call({ 'Sec-Fetch-Site': 'same-origin' }, 'https://eurofuelprices.com/api/route?json=x')).status, 400);
let r = await call({ 'Sec-Fetch-Site': 'same-origin' }, url);
assert.equal(r.status, 200); assert.equal(r.headers.get('x-cache'), 'MISS'); assert.equal(upstream, 1); await Promise.all(pending);
r = await call({ Referer: 'https://eurofuelprices.com/' }, url);
assert.equal(r.headers.get('x-cache'), 'HIT'); assert.equal(upstream, 1);                    // second call served from cache
mode = 'fail'; store.clear();
assert.equal((await call({ 'Sec-Fetch-Site': 'same-origin' }, url)).status, 502);
assert.equal(store.size, 0);                                                                  // failures are not cached
assert.equal((await w.fetch(new Request(url, { method: 'POST' }), {}, ctx)).status, 405);
console.log('test_route_worker: all passed');
