// Standalone probe: Open Charge Map v3 Type 2 stations per country. Writes raw responses to OUT_DIR
// and prints counts/sizes. Key comes from env OCM_API_KEY only and is never printed or written.
// Usage: OCM_API_KEY=... node tools/archive/ocm_probe.js <out_dir> [SE,NO,DK,DE]
const fs = require('fs'), path = require('path'), zlib = require('zlib');
const key = process.env.OCM_API_KEY;
if (!key) { console.error('OCM_API_KEY not set'); process.exit(1); }
const out = process.argv[2];
const countries = (process.argv[3] || 'SE,NO,DK,DE').split(',');
if (!out) { console.error('usage: node ocm_probe.js <out_dir> [countries]'); process.exit(1); }
fs.mkdirSync(out, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function get(params) {
  const url = 'https://api.openchargemap.io/v3/poi?' + new URLSearchParams(params);
  const t0 = Date.now();
  const res = await fetch(url, { headers: { 'X-API-Key': key, 'User-Agent': 'EuroFuelPrices-probe/1.0' } });
  const buf = Buffer.from(await res.arrayBuffer());
  const hdr = {}; for (const [k, v] of res.headers) if (/ratelimit|retry-after|x-|content-encoding/i.test(k) && !/key/i.test(k)) hdr[k] = v;
  return { status: res.status, ms: Date.now() - t0, buf, hdr };
}

(async () => {
  for (const cc of countries) {
    const r = await get({ output: 'json', countrycode: cc, connectiontypeid: '25,1036', compact: 'true', verbose: 'false', includecomments: 'false', maxresults: '100000' });
    let n = null;
    try { n = JSON.parse(r.buf.toString('utf8')).length; } catch (e) {}
    fs.writeFileSync(path.join(out, 'poi_' + cc + '.json'), r.buf);
    console.log(cc, 'status', r.status, 'ms', r.ms, 'pois', n, 'raw', r.buf.length, 'gzip', zlib.gzipSync(r.buf, { level: 9 }).length, JSON.stringify(r.hdr));
    await sleep(1500);
  }
})();
