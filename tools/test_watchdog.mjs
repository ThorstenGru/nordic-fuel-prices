// Run: node tools/test_watchdog.mjs   (needs Node 18+)
import assert from 'node:assert/strict';
import { judge, check, staleChargers, droppedCountries, nextBase } from '../worker/watchdog/index.mjs';

const NOW = Date.parse('2026-11-10T16:00:00Z');
const at = (min, base = NOW) => ({ fetched_at: new Date(base - min * 60000).toISOString() });
assert.equal(judge(at(10), NOW).ok, true);
assert.equal(judge(at(60), NOW).ok, true);                  // exactly the limit is still fine
assert.equal(judge(at(61), NOW).ok, false);
assert.equal(judge(null, NOW).ok, false);
assert.equal(judge({ fetched_at: 'garbage' }, NOW).ok, false);

// check(): one alert per incident, a reminder after 6 h, a recovery message, silence while healthy
const kv = new Map(), pushes = []; let meta = at(10);
const env = { NTFY_TOPIC: 't', STATE: { get: async k => kv.get(k) ?? null, put: async (k, v) => kv.set(k, v) } };
let evGen = new Date(NOW).toISOString();
globalThis.fetch = async (u, o) => u.startsWith('https://ntfy.sh/') ? (pushes.push(o.headers.Title), new Response('ok')) : u.includes('/ev_') ? new Response(JSON.stringify({ generated: evGen })) : (meta ? new Response(JSON.stringify(meta)) : new Response('x', { status: 500 }));
await check(env, NOW); assert.equal(pushes.length, 0);                                    // healthy: silent
meta = at(400); await check(env, NOW); assert.equal(pushes.length, 1);                    // goes stale: alert
await check(env, NOW + 30 * 60000); assert.equal(pushes.length, 1);                       // still stale: no spam
meta = at(400 + 400); await check(env, NOW + 7 * 3600000); assert.equal(pushes.length, 2);   // 6 h later: reminder
meta = at(5, NOW + 8 * 3600000); await check(env, NOW + 8 * 3600000); assert.equal(pushes.length, 3); assert.match(pushes[2], /fresh again/);
meta = at(5, NOW + 9 * 3600000); await check(env, NOW + 9 * 3600000); assert.equal(pushes.length, 3);                      // healthy again: silent
meta = null; await check(env, NOW + 10 * 3600000); assert.equal(pushes.length, 4);        // unreachable counts as down
// per-country alarm: needs the same stale set twice in a row, then one alert, silence, a new member alerts again, recovery message
kv.clear(); pushes.length = 0;
const T = 100 * 3600000, ctys = l => ({ ...at(5, T), countries: l.map(c => ({ country: c, status: 'stale' })).concat([{ country: 'SE', status: 'ok' }]) });
meta = ctys(['IT']); await check(env, T); assert.equal(pushes.length, 0);                    // first sighting: wait
await check(env, T + 30 * 60000); assert.equal(pushes.length, 1); assert.match(pushes[0], /country feed stale/);
meta = { ...ctys(['IT']), ...at(5, T + 60 * 60000) }; await check(env, T + 60 * 60000); assert.equal(pushes.length, 1);   // same set: silent
meta = { ...ctys(['IT', 'PL']), ...at(5, T + 90 * 60000) }; await check(env, T + 90 * 60000); assert.equal(pushes.length, 1);  // changed set: confirm first
await check(env, T + 120 * 60000); assert.equal(pushes.length, 2);
meta = { ...ctys([]), ...at(5, T + 150 * 60000) }; await check(env, T + 150 * 60000); assert.equal(pushes.length, 3); assert.match(pushes[2], /fresh again/);
// charger files: stale after 14 days, same two-checks rule
assert.deepEqual(staleChargers({ DK: '2026-11-01', DE: '2026-10-20' }, Date.parse('2026-11-14')), ['DE']);
assert.deepEqual(staleChargers({ DK: 'garbage' }, NOW), []);
kv.clear(); pushes.length = 0; evGen = '2026-10-01'; const T2 = Date.parse('2026-11-14T10:00:00Z');
meta = { ...at(5, T2), countries: [] }; await check(env, T2); assert.equal(pushes.length, 0);
await check(env, T2 + 30 * 60000); assert.equal(pushes.length, 1); assert.match(pushes[0], /charger data stale/);
evGen = new Date(T2).toISOString(); meta = { ...at(5, T2 + 3600000), countries: [] }; await check(env, T2 + 3600000); assert.equal(pushes.length, 2); assert.match(pushes[1], /charger data fresh again/);
// station-count drop: baseline kept while dropped, alert after two sightings, recovery message
assert.deepEqual(droppedCountries({ countries: [{ country: 'FI', station_count: 100 }, { country: 'SE', station_count: 20 }] }, { FI: 400, SE: 30 }), ['FI 400>100']);   // SE had < 50: ignored
assert.deepEqual(nextBase({ countries: [{ country: 'FI', station_count: 100 }, { country: 'NO', station_count: 900 }] }, { FI: 400 }), { FI: 400, NO: 900 });
assert.deepEqual(nextBase({ countries: [{ country: 'FI', station_count: 350 }] }, { FI: 400 }), { FI: 350 });
kv.clear(); pushes.length = 0; const T3 = Date.parse('2026-11-17T10:00:00Z'), cn = n => ({ ...at(5, T3), countries: [{ country: 'FI', station_count: n, status: 'ok' }] });
meta = cn(400); await check(env, T3); meta = { ...cn(400), ...at(5, T3 + 30 * 60000) }; await check(env, T3 + 30 * 60000); assert.equal(pushes.length, 0);   // baseline learned, silent
meta = { ...cn(100), ...at(5, T3 + 60 * 60000) }; await check(env, T3 + 60 * 60000); assert.equal(pushes.length, 0);                                           // first sighting: wait
meta = { ...cn(100), ...at(5, T3 + 90 * 60000) }; await check(env, T3 + 90 * 60000); assert.equal(pushes.length, 1); assert.match(pushes[0], /lost stations/);
meta = { ...cn(390), ...at(5, T3 + 120 * 60000) }; await check(env, T3 + 120 * 60000); assert.equal(pushes.length, 2); assert.match(pushes[1], /recovered/);
console.log('test_watchdog: all passed');
