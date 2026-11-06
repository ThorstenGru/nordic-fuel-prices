// Tests for the pure petrol-vs-electricity functions in web/index.html (between EV-PURE-BEGIN and EV-PURE-END).  node tools/test_ev_compare.js
const fs = require('fs'), assert = require('assert');
const src = fs.readFileSync(__dirname + '/../web/index.html', 'utf8');
const m = src.match(/\/\/ EV-PURE-BEGIN[^\n]*\n([\s\S]*?)\/\/ EV-PURE-END/); assert(m, 'pure block not found');
const { evKwh100, evCompare, evNearest } = new Function(m[1] + '; return { evKwh100, evCompare, evNearest };')();
const near = (a, b, e = 0.01) => assert(Math.abs(a - b) <= e, `${a} != ${b}`);

near(evKwh100(10.4, 54, 1.15), 22.15, 0.01); near(evKwh100(13.8, 54, 1/0.9, 19.2), 21.33, 0.01); near(evKwh100(13.8, 54, 1/0.9), 28.4, 0.05);   // catalogue ev_kwh100 wins over gross battery / range
 assert.strictEqual(evKwh100(0, 54, 1.15), null); assert.strictEqual(evKwh100(10, 54, 0), null);
// Santa Fe PHEV, public charger 5.8 SEK/kWh, petrol 16.5 SEK/L: 22.15 kWh -> 128.5, 7.5 L -> 123.75 => petrol slightly cheaper
let r = evCompare({ kwh100: 22.15, elec: 5.8, cons: 7.5, petrol: 16.5, km: 100 });
near(r.elec100, 128.47); near(r.petrol100, 123.75); assert.strictEqual(r.cheaper, 'petrol'); near(r.pct, 3.67, 0.01);
near(r.breakEven, 123.75 / 22.15, 1e-9);                                        // at the break-even price both cost the same
near(evCompare({ kwh100: 22.15, elec: r.breakEven, cons: 7.5, petrol: 16.5 }).elec100, r.petrol100, 1e-9);
assert.strictEqual(evCompare({ kwh100: 22.15, elec: r.breakEven, cons: 7.5, petrol: 16.5 }).cheaper, 'same');
// home electricity 1.9 SEK/kWh: electric much cheaper
r = evCompare({ kwh100: 22.15, elec: 1.9, cons: 7.5, petrol: 16.5, km: 100 }); assert.strictEqual(r.cheaper, 'electric'); near(r.pct, (1 - 42.085 / 123.75) * 100, 0.01);
// trip longer than the battery: first part electric, rest petrol
r = evCompare({ kwh100: 22.15, elec: 1.9, cons: 7.5, petrol: 16.5, km: 200, elecKm: 40.5 });
assert(r.trip.limited); near(r.trip.elecKm, 40.5); near(r.trip.elec, 40.5 / 100 * 42.085 + 159.5 / 100 * 123.75); near(r.trip.petrol, 247.5);
// petrol-only car (no kWh/100): no verdict, petrol cost still known
r = evCompare({ kwh100: null, elec: 2, cons: 7, petrol: 16, km: 100 }); assert.strictEqual(r.cheaper, null); assert.strictEqual(r.breakEven, null); near(r.petrol100, 112);
// missing petrol price: no verdict
assert.strictEqual(evCompare({ kwh100: 20, elec: 2, cons: 7, petrol: null }).cheaper, null);

// 5 nearest: unverified (tier 2) never used, but counted when nearer than the 5th pick
const L = [3, 1, 2, 4, 5, 6, 7].map((km, i) => ({ km, price: 16 + i * 0.1, tier: km === 2 ? 2 : km === 4 ? 1 : 0 }));
const n = evNearest(L, 5);
assert.deepStrictEqual(n.picked.map(x => x.km), [1, 3, 4, 5, 6]); assert.strictEqual(n.setAside, 1);
near(n.avg, n.picked.reduce((a, x) => a + x.price, 0) / 5, 1e-9);
assert.strictEqual(evNearest([], 5).avg, null); assert.strictEqual(evNearest([{ km: 1, price: 1, tier: 2 }], 5).picked.length, 0);
console.log('ev compare: all tests passed');
