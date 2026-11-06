// One-off probe of the public Valhalla (FOSSGIS) used by web/index.html. ~35 GET requests, >=1.1 s apart.
// Usage: node tools/analysis/valhalla_probe.js [out.json]   (raw results are written to out.json)
const H = 'https://valhalla1.openstreetmap.de/route';
const P = { malmo:[55.605,13.000], hamburg:[53.551,9.994], berlin:[52.520,13.405], sthlm:[59.329,18.069], oslo:[59.913,10.752], bille:[55.917,13.083], cph:[55.676,12.568] };
const loc = k => ({ lat:P[k][0], lon:P[k][1] });
const out = []; const sleep = ms => new Promise(r => setTimeout(r, ms));
async function call(name, body) {
  const url = `${H}?json=${encodeURIComponent(JSON.stringify(body))}`;
  const t0 = Date.now(); let status = 0, j = null, hdr = {}, bytes = 0;
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(60000) }); status = r.status;
    ['retry-after','x-ratelimit-limit','x-ratelimit-remaining','server','cache-control'].forEach(h => { const v = r.headers.get(h); if (v) hdr[h] = v; });
    const txt = await r.text(); bytes = txt.length; try { j = JSON.parse(txt); } catch (_) { j = { raw: txt.slice(0, 300) }; }
  } catch (e) { j = { error: String(e) }; }
  const ms = Date.now() - t0; out.push({ name, req: body, urlLen: url.length, status, ms, bytes, hdr, res: j });
  const tr = j.trip; const sm = tr?.summary;
  console.log(name.padEnd(28), status, ms + 'ms', bytes + 'B', sm ? `${sm.length}km ${(sm.time/60).toFixed(0)}min ferry=${tr.legs.some(l=>l.summary?.has_ferry)} toll=${sm.has_toll} hw=${sm.has_highway}` : (j.error?.slice?.(0,80) || j.error_code || ''), j.alternates ? `alts=${j.alternates.length}` : '');
  await sleep(1100);
}
const base = (a, b, extra = {}, co = {}) => ({ locations:[loc(a), loc(b)], costing:'auto', directions_type:'none', ...extra, ...(Object.keys(co).length ? { costing_options:{ auto: co } } : {}) });
(async () => {
  // 1 alternatives
  for (const [a, b] of [['malmo','hamburg'],['malmo','berlin'],['sthlm','oslo'],['bille','malmo']]) await call(`alt ${a}-${b}`, base(a, b, { alternates: 2 }));
  // 2 costing options (Malmo-Hamburg)
  await call('base malmo-hamburg', base('malmo','hamburg'));
  await call('use_ferry=0', base('malmo','hamburg', {}, { use_ferry: 0 }));
  await call('use_tolls=0', base('malmo','hamburg', {}, { use_tolls: 0 }));
  await call('use_highways=0', base('malmo','hamburg', {}, { use_highways: 0 }));
  await call('top_speed=90', base('malmo','hamburg', {}, { top_speed: 90 }));
  await call('top_speed=130', base('malmo','hamburg', {}, { top_speed: 130 }));
  await call('top_speed=20 (low)', base('malmo','hamburg', {}, { top_speed: 20 }));
  await call('top_speed=200 (high)', base('malmo','hamburg', {}, { top_speed: 200 }));
  // 3 maneuvers + elevation
  await call('maneuvers bille-malmo', { ...base('bille','malmo'), directions_type:'maneuvers' });
  await call('maneuvers malmo-hamburg', { ...base('malmo','hamburg'), directions_type:'maneuvers' });
  await call('elev 100 bille-malmo', base('bille','malmo', { elevation_interval: 100 }));
  await call('elev 100 malmo-hamburg', base('malmo','hamburg', { elevation_interval: 100 }));
  // 5 tolls: bridge
  await call('toll malmo-cph', base('malmo','cph'));
  // 4 ten sequential calls, compact route
  for (let i = 1; i <= 10; i++) await call(`seq ${i}`, base('bille','malmo'));
  require('fs').writeFileSync(process.argv[2] || 'valhalla_probe_out.json', JSON.stringify(out));
  console.log('requests', out.length);
})();
