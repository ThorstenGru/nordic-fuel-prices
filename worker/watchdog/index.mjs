// Stale-data alarm for eurofuelprices.com. Cron every 30 min: reads meta.json, pushes a phone notification via ntfy.sh when the
// price data stops updating (the scrape chain can die silently). Free: Workers cron + KV + ntfy.sh. Secret: NTFY_TOPIC (random, acts as the password).
const META = 'https://eurofuelprices.com/meta.json';
const STALE_MIN = 180;                 // the pipeline runs every ~15-30 min; 3 h without a new fetch means it is down
const REMIND_MIN = 360;                // while still stale, repeat the alert every 6 h
const CTY_REMIND_MIN = 1440;           // a country that stays stale: repeat once a day

// Pure: { ok, ageMin, why } from the meta.json text (or null when it could not be fetched). Exported for tests.
export function judge(meta, nowMs) {
  if (!meta) return { ok: false, ageMin: null, why: 'meta.json could not be fetched' };
  const t = Date.parse(meta.fetched_at);
  if (!isFinite(t)) return { ok: false, ageMin: null, why: 'meta.json has no valid fetched_at' };
  const ageMin = Math.round((nowMs - t) / 60000);
  return ageMin > STALE_MIN ? { ok: false, ageMin, why: `no new price data for ${(ageMin / 60).toFixed(1)} h` } : { ok: true, ageMin, why: 'fresh' };
}

// Pure: sorted codes of the countries meta.json marks stale (one country's feed dying while the rest is fresh never moves the global fetched_at).
export function staleCountries(meta) {
  return ((meta && meta.countries) || []).filter(c => c && c.status === 'stale' && c.country).map(c => c.country).sort();
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
  // per country: alert when the same set is stale in two checks in a row (30 min, no flapping), again only when the set changes or after a day
  if (meta) {
    const now = staleCountries(meta).join(','), c = JSON.parse((await env.STATE.get('c')) || '{"seen":"","alerted":"","t":0}');
    if (now && now === c.seen && (now !== c.alerted || nowMs - c.t > CTY_REMIND_MIN * 60000)) {
      await push(env, 'EuroFuelPrices: country feed stale', 'Stale: ' + now + '. The rest of the data is still updating.', 'warning');
      c.alerted = now; c.t = nowMs;
    } else if (!now && c.alerted) {
      await push(env, 'EuroFuelPrices: country feeds fresh again', 'Was stale: ' + c.alerted + '.', 'white_check_mark');
      c.alerted = ''; c.t = nowMs;
    }
    c.seen = now;
    await env.STATE.put('c', JSON.stringify(c));
  }
  return v;
}

export default { scheduled: (_e, env, ctx) => ctx.waitUntil(check(env)) };
