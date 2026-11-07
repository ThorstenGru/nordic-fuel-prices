// Tests for the "usually cheapest" country line in web/index.html (TRD-PURE block; decode and thresholds come from RT-PURE rtDepartHint).  node tools/test_trends.js
const fs = require('fs'), assert = require('assert');
const src = fs.readFileSync(__dirname + '/../web/index.html', 'utf8');
const rt = src.match(/\/\/ RT-PURE-BEGIN[^\n]*\n([\s\S]*?)\/\/ RT-PURE-END/), tr = src.match(/\/\/ TRD-PURE-BEGIN[^\n]*\n([\s\S]*?)\/\/ TRD-PURE-END/);
assert(rt && tr, 'pure blocks not found');
const F = new Function(rt[1] + ';' + tr[1] + '; return { trdPart, trdLines };')();

const A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
const enc = (lvl, n) => { const x = Math.max(0, Math.min(4095, Math.round(lvl / 0.01) + 2048)); return A[x >> 6] + A[x & 63] + A[n]; };
const series = f => { let c = ''; for (let i = 0; i < 168; i++) c += f(Math.floor(i / 24), i % 24); return c; };
const file = (p95, diesel) => ({ schema: 1, series: { SE: { ...(p95 ? { p95: { c: p95 } } : {}), ...(diesel ? { diesel: { c: diesel } } : {}) } } });

// day parts
assert.deepStrictEqual([0, 5, 6, 11, 12, 17, 18, 23].map(F.trdPart), ['night', 'night', 'morning', 'morning', 'afternoon', 'afternoon', 'evening', 'evening']);

// Tuesday (wd 1) 19:00 and 20:00 at -0.9 / -0.7 (n 15): petrol "Tuesday evening"; diesel dips on Wednesday 03:00 and 04:00
const p = series((wd, hr) => wd === 1 && hr === 19 ? enc(-0.9, 15) : wd === 1 && hr === 20 ? enc(-0.7, 15) : enc(0.1, 15));
const d = series((wd, hr) => wd === 2 && (hr === 3 || hr === 4) ? enc(-0.8, 14) : enc(0.1, 14));
assert.deepStrictEqual(F.trdLines(file(p, d), 'SE'), [{ fuel: 'p95', wd: 1, part: 'evening' }, { fuel: 'diesel', wd: 2, part: 'night' }]);
assert.deepStrictEqual(F.trdLines(file(p, null), 'SE'), [{ fuel: 'p95', wd: 1, part: 'evening' }]);   // one fuel only

// nothing at all: thin series (below 12 samples), a dip under 0.3 %, an empty series, an unknown country, a bad file
assert.deepStrictEqual(F.trdLines(file(series(() => enc(-1.5, 11)), null), 'SE'), []);
assert.deepStrictEqual(F.trdLines(file(series((wd, hr) => enc(hr === 3 ? -0.1 : 0.2, 20)), null), 'SE'), []);
assert.deepStrictEqual(F.trdLines(file(series(() => enc(0, 0)), null), 'SE'), []);
assert.deepStrictEqual(F.trdLines(file(p, d), 'NO'), []);
assert.deepStrictEqual(F.trdLines(null, 'SE'), []);
assert.deepStrictEqual(F.trdLines({ schema: 2, series: {} }, 'SE'), []);
// a window that starts 23:00 is still "evening" of that weekday
const w = series((wd, hr) => wd === 4 && hr === 23 ? enc(-1, 13) : wd === 5 && hr === 0 ? enc(-1, 13) : enc(0.2, 13));
assert.deepStrictEqual(F.trdLines(file(w, null), 'SE'), [{ fuel: 'p95', wd: 4, part: 'evening' }]);
console.log('test_trends ok');
