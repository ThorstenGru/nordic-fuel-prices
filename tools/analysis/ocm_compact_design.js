// Offline design measurement: reads poi_<CC>.json (from ocm_probe.js) + ref.json (referencedata),
// applies the proposed filter / dedupe / compaction and prints counts and gzip sizes. No network, no key.
// Usage: node tools/analysis/ocm_compact_design.js <dir> [SE,NO,DK,DE]
const fs = require('fs'), path = require('path'), zlib = require('zlib');
const dir = process.argv[2]; const countries = (process.argv[3] || 'SE,NO,DK,DE').split(',');
const ref = JSON.parse(fs.readFileSync(path.join(dir, 'ref.json'), 'utf8'));
const opName = Object.fromEntries(ref.Operators.map(o => [o.ID, o.Title]));
const T2 = new Set([25, 1036]);
const EXCLUDE_USAGE = new Set([2, 3, 6]);           // private restricted / private notice / staff-visitors-customers
const EXCLUDE_STATUS = new Set([100, 150, 200, 210]); // not operational, planned, removed, duplicate
const FREE = /\b(free|gratis|kostenlos|kostenfrei|umsonst|free of charge|avgiftsfri|ingen avgift)\b/i;
const PARK = /(parking fee|parkeringsavgift|parkgeb|parkplatzgeb|parking cost)/i;

const kwGroup = kw => kw == null ? 0 : kw <= 3.7 ? 1 : kw < 11.1 ? 2 : 3; // 0 unknown, 1 <=3.7, 2 up to 11, 3 22+ (11.1..22+)
function distM(a, b) { const dy = (a.lat - b.lat) * 111320, dx = (a.lon - b.lon) * 111320 * Math.cos(a.lat * Math.PI / 180); return Math.hypot(dx, dy); }

function reduce(pois) {
  const st = { in: pois.length, noT2: 0, usage: 0, status: 0 };
  const out = [];
  for (const p of pois) {
    const t2 = (p.Connections || []).filter(c => T2.has(c.ConnectionTypeID) && !EXCLUDE_STATUS.has(c.StatusTypeID));
    if (!t2.length) { st.noT2++; continue; }
    if (EXCLUDE_USAGE.has(p.UsageTypeID)) { st.usage++; continue; }
    if (EXCLUDE_STATUS.has(p.StatusTypeID)) { st.status++; continue; }
    const kws = t2.map(c => c.PowerKW).filter(x => x > 0);
    const pts = t2.reduce((a, c) => a + (c.Quantity || 1), 0);
    const uc = (p.UsageCost || '').trim();
    let flags = 0;
    if (uc && FREE.test(uc) && !/\d/.test(uc.replace(/\b0\b/g, ''))) flags |= 1;       // free, source text says so, no other number
    if (p.UsageTypeID === 4) flags |= 2;                                                 // membership / access key required
    if (p.UsageTypeID === 7) flags |= 4;                                                 // notice required
    if (p.UsageTypeID === 5) flags |= 8;                                                 // pay at location
    if (PARK.test([uc, p.GeneralComments, p.AddressInfo.AccessComments].filter(Boolean).join(' '))) flags |= 16; // weak text hint
    if (uc) flags |= 32;                                                                 // has cost text (shown verbatim)
    out.push({ lat: p.AddressInfo.Latitude, lon: p.AddressInfo.Longitude, op: p.OperatorID || 0, kw: kws.length ? Math.max(...kws) : null,
      pts, flags, yr: +(p.DateLastVerified || '0').slice(0, 4), prov: p.DataProviderID, title: p.AddressInfo.Title || '', uc, id: p.ID });
  }
  st.kept = out.length;
  return { out, st };
}

function dedupe(list) {
  // grid of 0.0005 deg (~55 m), merge within 30 m; keep the record with more info, never sum points
  const grid = new Map(), key = (a, b) => a + ',' + b, res = []; let merged = 0;
  const score = s => (s.op ? 2 : 0) + (s.flags & 32 ? 3 : 0) + (s.yr / 10000) + (s.prov === 19 ? 0 : 1);
  for (const s of list) {
    const gx = Math.floor(s.lat / 0.0005), gy = Math.floor(s.lon / 0.0005); let hit = null;
    for (let i = -1; i <= 1 && !hit; i++) for (let j = -1; j <= 1 && !hit; j++)
      for (const o of grid.get(key(gx + i, gy + j)) || []) if (distM(s, o) <= 30) { hit = o; break; }
    if (hit) { merged++; if (score(s) > score(hit)) { Object.assign(hit, s, { pts: Math.max(hit.pts, s.pts) }); } else hit.pts = Math.max(hit.pts, s.pts); }
    else { const k = key(gx, gy); (grid.get(k) || grid.set(k, []).get(k)).push(s); res.push(s); }
  }
  return { res, merged };
}

const gz = s => zlib.gzipSync(Buffer.from(s), { level: 9 }).length;
for (const cc of countries) {
  const pois = JSON.parse(fs.readFileSync(path.join(dir, 'poi_' + cc + '.json'), 'utf8'));
  const { out, st } = reduce(pois);
  const { res, merged } = dedupe(out);
  const kwc = {}; for (const s of res) kwc[kwGroup(s.kw)] = (kwc[kwGroup(s.kw)] || 0) + 1;
  const flagc = {}; for (const s of res) for (const b of [1, 2, 4, 8, 16, 32]) if (s.flags & b) flagc[b] = (flagc[b] || 0) + 1;
  const ops = [...new Set(res.map(s => s.op).filter(Boolean))], idx = Object.fromEntries(ops.map((o, i) => [o, i + 1]));
  const rnd = (x, d) => +x.toFixed(d);
  const rows = res.map(s => [rnd(s.lat, 5), rnd(s.lon, 5), idx[s.op] || 0, s.kw == null ? 0 : Math.round(s.kw), s.pts, s.flags, s.yr % 100]);
  const rowsT = res.map((s, i) => rows[i].concat([s.title]));
  const costNotes = res.map((s, i) => s.uc ? [i, s.uc.slice(0, 80)] : null).filter(Boolean);
  const payload = { v: 1, cc, ops: ops.map(o => opName[o]), s: rows };
  const j = JSON.stringify(payload), jt = JSON.stringify({ ...payload, s: rowsT }), jn = JSON.stringify({ ...payload, s: rowsT, notes: costNotes });
  const yrs = {}; for (const s of res) yrs[s.yr] = (yrs[s.yr] || 0) + 1;
  console.log(`\n== ${cc}\nfilter: in ${st.in}, dropped no-usable-T2 ${st.noT2}, private usage ${st.usage}, non-operational ${st.status}, kept ${st.kept}; dedupe(30 m) merged ${merged} -> ${res.length}`);
  console.log('kW group (0 unknown, 1 <=3.7, 2 3.8-11, 3 >11):', JSON.stringify(kwc), ' flags(1 free,2 member,4 notice,8 payloc,16 parkhint,32 costtext):', JSON.stringify(flagc));
  console.log('operators in file', ops.length, 'stations with operator', res.filter(s => s.op).length, ' verified year', JSON.stringify(yrs));
  console.log(`size raw/gzip  compact: ${j.length}/${gz(j)}  +title: ${jt.length}/${gz(jt)}  +title+cost notes(${costNotes.length}): ${jn.length}/${gz(jn)}`);
}
