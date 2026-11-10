// Stale-data alarm for eurofuelprices.com. Cron every 30 min: reads meta.json, pushes a phone notification via ntfy.sh when the
// price data stops updating (the scrape chain can die silently). Free: Workers cron + KV + ntfy.sh. Secret: NTFY_TOPIC (random, acts as the password).
const META = 'https://eurofuelprices.com/meta.json';
const STALE_MIN = 180;                 // the pipeline runs every ~15-30 min; 3 h without a new fetch means it is down
const REMIND_MIN = 360;                // while still stale, repeat the alert every 6 h

// Pure: { ok, ageMin, why } from the meta.json text (or null when it could not be fetched). Exported for tests.
export function judge(meta, nowMs) {
  if (!meta) return { ok: false, ageMin: null, why: 'meta.json could not be fetched' };
  const t = Date.parse(meta.fetched_at);
  if (!isFinite(t)) return { ok: false, ageMin: null, why: 'meta.json has no valid fetched_at' };
  const ageMin = Math.round((nowMs - t) / 60000);
  return ageMin > STALE_MIN ? { ok: false, ageMin, why: `no new price data for ${(ageMin / 60).toFixed(1)} h` } : { ok: true, ageMin, why: 'fresh' };
}

async function push(env, title, body, tags) {
  await fetch('https://ntfy.sh/' + env.NTFY_TOPIC, { method: 'POST', body, headers: { Title: title, Tags: tags, Priority: tags === 'rotating_light' ? 'high' : 'default' } });
}

export async function check(env, nowMs = Date.now()) {
  let meta = null;
  try { const r = await fetch(META + '?w=' + Math.floor(nowMs / 60000), { signal: AbortSignal.timeout(15000) }); if (r.ok) meta = await r.json(); } catch (_) {}
  const v = judge(meta, nowMs);
  const prev = JSON.parse((await env.STATE.get('s')) || '{"s":"ok","t":0}');
  if (!v.ok && (prev.s !== 'stale' || nowMs - prev.t > REMIND_MIN * 60000)) {
    await push(env, 'EuroFuelPrices: data is stale', v.why + '. Check the scrape workflow on GitHub Actions.', 'rotating_light');
    await env.STATE.put('s', JSON.stringify({ s: 'stale', t: nowMs }));
  } else if (v.ok && prev.s === 'stale') {
    await push(env, 'EuroFuelPrices: data is fresh again', `Last fetch ${v.ageMin} min ago.`, 'white_check_mark');
    await env.STATE.put('s', JSON.stringify({ s: 'ok', t: nowMs }));
  }
  return v;
}

export default { scheduled: (_e, env, ctx) => ctx.waitUntil(check(env)) };
