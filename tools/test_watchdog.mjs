// Run: node tools/test_watchdog.mjs   (needs Node 18+)
import assert from 'node:assert/strict';
import { judge, check } from '../worker/watchdog/index.mjs';

const NOW = Date.parse('2026-11-10T16:00:00Z');
const at = (min, base = NOW) => ({ fetched_at: new Date(base - min * 60000).toISOString() });
assert.equal(judge(at(10), NOW).ok, true);
assert.equal(judge(at(180), NOW).ok, true);                 // exactly the limit is still fine
assert.equal(judge(at(181), NOW).ok, false);
assert.equal(judge(null, NOW).ok, false);
assert.equal(judge({ fetched_at: 'garbage' }, NOW).ok, false);

// check(): one alert per incident, a reminder after 6 h, a recovery message, silence while healthy
const kv = new Map(), pushes = []; let meta = at(10);
const env = { NTFY_TOPIC: 't', STATE: { get: async k => kv.get(k) ?? null, put: async (k, v) => kv.set(k, v) } };
globalThis.fetch = async (u, o) => u.startsWith('https://ntfy.sh/') ? (pushes.push(o.headers.Title), new Response('ok')) : (meta ? new Response(JSON.stringify(meta)) : new Response('x', { status: 500 }));
await check(env, NOW); assert.equal(pushes.length, 0);                                    // healthy: silent
meta = at(400); await check(env, NOW); assert.equal(pushes.length, 1);                    // goes stale: alert
await check(env, NOW + 30 * 60000); assert.equal(pushes.length, 1);                       // still stale: no spam
meta = at(400 + 400); await check(env, NOW + 7 * 3600000); assert.equal(pushes.length, 2);   // 6 h later: reminder
meta = at(5, NOW + 8 * 3600000); await check(env, NOW + 8 * 3600000); assert.equal(pushes.length, 3); assert.match(pushes[2], /fresh again/);
meta = at(5, NOW + 9 * 3600000); await check(env, NOW + 9 * 3600000); assert.equal(pushes.length, 3);                      // healthy again: silent
meta = null; await check(env, NOW + 10 * 3600000); assert.equal(pushes.length, 4);        // unreachable counts as down
console.log('test_watchdog: all passed');
