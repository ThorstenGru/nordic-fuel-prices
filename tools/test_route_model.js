// Tests for the pure route-model functions in web/index.html (between RT-PURE-BEGIN and RT-PURE-END).  node tools/test_route_model.js
const fs = require('fs'), assert = require('assert');
const src = fs.readFileSync(__dirname + '/../web/index.html', 'utf8');
const m = src.match(/\/\/ RT-PURE-BEGIN[^\n]*\n([\s\S]*?)\/\/ RT-PURE-END/); assert(m, 'pure block not found');
const { rtPlan, rtCand, rtRef, rtTier, rtMedian } = new Function(m[1] + '; return { rtPlan, rtCand, rtRef, rtTier, rtMedian };')();
const near = (a, b, e = 0.05) => assert(Math.abs(a - b) <= e, `${a} != ${b}`);

// Owner's Santa Fe PHEV (spec C7 worked example): 503 km, 47 L tank full, 54 km WLTP x 0.75 electric, 7 L/100 km petrol-only
const car = { cons: 7, tank: 47, fuelL: 47, reserveL: 4.7, elecKm: 54 * 0.75, kwh100: 13.8 / 54 * 100 / 0.9, elecEur: 0.25 };
let p = rtPlan({ ...car, km: 503 });
near(p.elecKm, 40.5); near(p.petrolL, (503 - 40.5) * 0.07); near(p.petrolL, 32.4, 0.1); near(p.arriveL, 14.6, 0.1);
assert.strictEqual(p.needStop, false);
// winter: engine heats the cabin while the battery lasts (gEl L/100 km on the electric km) -> a little more petrol, nothing when gEl is absent
near(rtPlan({ ...car, km: 503, gEl: 3 }).petrolL, 32.4 + 40.5 * 0.03, 0.1); near(rtPlan({ ...car, km: 20, gEl: 3 }).petrolL, 0.6, 0.01); near(rtPlan({ ...car, km: 20 }).petrolL, 0, 1e-9);
// petrol-only car: no electric part at all
p = rtPlan({ ...car, elecKm: 0, kwh100: 0, elecEur: null, km: 503 });
near(p.petrolL, 35.21, 0.01); assert.strictEqual(p.elecCost, null);
// Malmo-Munich ~1100 km: beyond range -> a stop is needed; range = electric + (47-4.7)/7*100
p = rtPlan({ ...car, km: 1100 }); assert(p.needStop); near(p.reachKm, 40.5 + 604.3, 0.5);
// starting at 25 % fuel on 503 km: needs a stop
assert(rtPlan({ ...car, fuelL: 47 * 0.25, km: 503 }).needStop);

// Detour while the battery lasts is priced electric (no petrol), later at the pump's petrol price
let c = rtCand({ ...car, km: 503 }, 20, 5.2, 1.85, 1.60);
assert.strictEqual(c.fuelAt, 47); near(c.detourCost, 5.2 * 0.284 * 0.25 / 1, 0.2);
c = rtCand({ ...car, km: 503 }, 120, 5.2, 1.85, 1.60);
near(c.detourCost, 5.2 * 0.07 * 1.85, 0.001);                       // spec: about 0.67 EUR
// Dearer than the reference -> negative saving (spec: filling in Sweden at 1.60 beats DK at 1.85)
assert(c.saving < 0);
// Cheaper pump: saving = (ref - price) x litres - detour; litres = burn to destination, capped by tank space
c = rtCand({ ...car, km: 503 }, 400, 3.9, 1.50, 1.80);
near(c.litres, (503 - 400) * 0.07, 0.01); near(c.saving, 0.30 * c.litres - c.detourCost, 0.001); assert(c.saving > 0);
// Tank space caps litres: full tank at the pump on a long remaining leg
c = rtCand({ ...car, fuelL: 47, km: 1100 }, 10, 0, 1.5, 1.8); near(c.litres, 47 - (47 - 0), 0.01);   // tank still full at km 10 (battery)
// Range check: pump beyond reach is not reachable
assert.strictEqual(rtCand({ ...car, fuelL: 10, km: 503 }, 300, 0, 1.5, 1.8).reachable, false);
assert.strictEqual(rtCand({ ...car, fuelL: 47, km: 503 }, 300, 0, 1.5, 1.8).reachable, true);

// Reference price: median of dated pumps within +/-100 km; falls back to all pumps near, then to the fallback
const rows = [{ along: 10, eur: 1.7, age: 1 }, { along: 50, eur: 1.8, age: 2 }, { along: 90, eur: 1.9, age: 3 }, { along: 60, eur: 1.0, age: null }, { along: 500, eur: 5, age: 1 }];
near(rtRef(rows, 50, 9), 1.8, 1e-9);                                 // 3 dated near -> the undated 1.0 is ignored
near(rtRef(rows, 500, 9), 5, 1e-9); assert.strictEqual(rtRef([], 0, 9), 9);

// Data-quality gate: tier 0 trusted+dated, 1 unknown age, 2 not verified (ps flag, suspect low price, stale country)
assert.strictEqual(rtTier({ age: 3 }), 0); assert.strictEqual(rtTier({ age: null }), 1);
assert.strictEqual(rtTier({ age: 3, ps: 1 }), 2); assert.strictEqual(rtTier({ age: null, sus: true }), 2); assert.strictEqual(rtTier({ age: 3, stale: true }), 2);
assert.strictEqual(rtMedian([]), null);
console.log('route model: all tests passed');
