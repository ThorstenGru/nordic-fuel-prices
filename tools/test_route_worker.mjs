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
assert.equal([...store.keys()].filter(k => !k.includes('/rl/')).length, 0);                    // failures are not cached (rate counters are not routes)
// rate limit: more than RL_MAX uncached requests from one visitor in a minute -> 429, before the upstream is called again
store.clear(); mode = 'ok'; upstream = 0;
const via = (ip, i) => call({ 'Sec-Fetch-Site': 'same-origin', 'CF-Connecting-IP': ip }, 'https://eurofuelprices.com/api/route?json=' + encodeURIComponent(JSON.stringify({ ...ok, locations: [{ lat: 55.6 + i / 1000, lon: 13.0 }, ok.locations[1]] })));
for (let i = 0; i < 20; i++) assert.equal((await via('1.2.3.4', i)).status, 200);
const before = upstream; r = await via('1.2.3.4', 99);
assert.equal(r.status, 429); assert.equal(r.headers.get('retry-after'), '60'); assert.equal(upstream, before);
assert.equal((await via('5.6.7.8', 0)).status, 200);                                          // another visitor is not affected
assert.equal((await w.fetch(new Request(url, { method: 'POST' }), {}, ctx)).status, 405);
// ── ORS backup: conversion to the Valhalla shape the app reads
import { orsToValhalla } from '../worker/route/index.mjs';
const decode6 = s => { const o = []; let i = 0, a = 0, b = 0; const n = () => { let c, sh = 0, r = 0; do { c = s.charCodeAt(i++) - 63; r |= (c & 31) << sh; sh += 5; } while (c >= 32); return (r & 1) ? ~(r >> 1) : (r >> 1); }; while (i < s.length) { a += n(); b += n(); o.push([a / 1e6, b / 1e6]); } return o; };
const coords = [[13.0038, 55.6049], [12.9, 55.0], [11.0, 54.1], [9.9937, 53.5511]];                 // [lon, lat]
const ors = { features: [{ geometry: { coordinates: coords }, properties: { summary: { distance: 374.2, duration: 16000 },
  segments: [{ steps: [{ distance: 100, duration: 4000, way_points: [0, 1] }, { distance: 40, duration: 6000, way_points: [1, 2] }, { distance: 234.2, duration: 6000, way_points: [2, 3] }] }],
  extras: { waytypes: { values: [[0, 1, 1], [1, 2, 9], [2, 3, 1]] }, tollways: { values: [[0, 3, 0]] } } } }] };
const v = orsToValhalla(ors), leg = v.trip.legs[0];
assert.equal(v.trip.status, 0); assert.equal(v.trip.summary.length, 374.2); assert.equal(v.trip.summary.time, 16000);
assert.equal(leg.summary.has_ferry, true); assert.equal(v.trip.summary.has_toll, false);
assert.deepEqual(leg.maneuvers.map(m => m.ferry), [false, true, false]);                              // ferry step flagged
assert.deepEqual(leg.maneuvers.map(m => m.highway), [true, false, true]);                             // 90 km/h, 24 km/h, 140 km/h
const back = decode6(leg.shape); assert.equal(back.length, 4);
back.forEach(([la, lo], i) => { assert.ok(Math.abs(la - coords[i][1]) < 1e-6 && Math.abs(lo - coords[i][0]) < 1e-6); });   // polyline6 round trip

// fallback order: Valhalla first, ORS only when Valhalla fails and the secret exists
const seen = []; store.clear(); pending.length = 0;
globalThis.fetch = async (u, o) => { seen.push(String(u).includes('heigit') ? 'ors' : 'valhalla'); return String(u).includes('heigit') ? new Response(JSON.stringify(ors)) : new Response('x', { status: 503 }); };
const sameSite = { 'Sec-Fetch-Site': 'same-origin' };
assert.equal((await w.fetch(new Request(url, { headers: sameSite }), {}, ctx)).status, 502);          // no secret: no ORS call
assert.deepEqual(seen, ['valhalla']);
seen.length = 0; r = await w.fetch(new Request(url, { headers: sameSite }), { ORS_KEY: 'k' }, ctx);
assert.equal(r.status, 200); assert.equal(r.headers.get('x-src'), 'ors'); assert.deepEqual(seen, ['valhalla', 'ors']);
assert.equal(JSON.parse(await r.text()).trip.legs[0].summary.has_ferry, true);
console.log('test_route_worker: all passed');
