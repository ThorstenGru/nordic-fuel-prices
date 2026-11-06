// Tests for the temperature / blended-consumption functions in web/index.html (between PH-PURE-BEGIN and PH-PURE-END).  node tools/test_phev_blend.js
const fs = require('fs'), assert = require('assert');
const src = fs.readFileSync(__dirname + '/../web/index.html', 'utf8');
const m = src.match(/\/\/ PH-PURE-BEGIN[^\n]*\n([\s\S]*?)\/\/ PH-PURE-END/); assert(m, 'pure block not found');
const { PH_T, phLerp, phevF, phevBlend, phevDay, phevBand } = new Function(m[1] + '; return { PH_T, phLerp, phevF, phevBlend, phevDay, phevBand };')();
const near = (a, b, e = 0.01) => assert(Math.abs(a - b) <= e, `${a} != ${b}`);

assert.strictEqual(phLerp([0, 10], [0, 100], 5), 50); assert.strictEqual(phLerp([0, 10], [0, 100], -3), 0); assert.strictEqual(phLerp([0, 10], [0, 100], 99), 100);
// doc table 3.3: f(20) = 1; f(-10) 0.76; m_el(-20) 1.43; g(-20) 3.0 l/100 km at 19.2 kWh/100 km
let x = phevF(20); near(x.f, 1); near(x.mEl, 1); near(x.gk, 0); near(x.mp, 1);
x = phevF(-10); near(x.f, 0.755, 0.005); near(x.mEl, 1.324, 0.005); near(x.mp, 1.13);
x = phevF(-20); near(x.mEl, 1.43, 0.01); near(x.gk * 19.2, 3.04, 0.05);
// unknown temperature = no adjustment; clamped outside -20..35
for (const T of [null, undefined, NaN]) assert.deepStrictEqual(phevF(T), { f: 1, mEl: 1, gk: 0, mp: 1 });
near(phevF(-40).f, phevF(-20).f, 1e-12); near(phevF(50).f, phevF(35).f, 1e-12);
// energy is conserved at every knot: R * kwh100 * m_el = R_wltp * kwh100 (the battery holds the same energy at any temperature)
for (const T of PH_T) { const y = phevF(T); near(54 * y.f * y.mEl, 54, 1e-9); }
// range is monotone non-increasing from 20 C down to -15 C (engine heating flattens the last step) and from 25 C up to 35 C
for (let T = 20; T > -15; T -= 1) assert(phevF(T - 1).f <= phevF(T).f + 1e-12, 'f not monotone at ' + T);
for (let T = 25; T < 35; T += 1) assert(phevF(T + 1).f <= phevF(T).f + 1e-12);
// pessimistic bound has the shortest range, optimistic the longest and never above WLTP
for (const T of [-15, -10, 0, 5, 25, 30]) { assert(phevF(T, 'pess').f <= phevF(T).f + 1e-12); assert(phevF(T, 'opt').f > phevF(T).f - 1e-12); assert(phevF(T, 'opt').f <= 1); }

// Santa Fe PHEV 253 hp: 54 km, 19.2 kWh/100 km (wall, loss 1.0 here), 7.5 l/100 km. Doc worked example prices 2.2 SEK/kWh, 17 SEK/l
const car = { range: 54, kwh100: 19.2, cons: 7.5, pKwh: 2.2, pL: 17 };
let r = phevBlend({ ...car, d: 100, T: 20 }); near(r.e, 54); near(r.p, 46); near(r.kwh, 10.37, 0.01); near(r.litres, 3.45, 0.01); near(r.per100, 81.5, 0.5);
r = phevBlend({ ...car, d: 100, T: -10 }); near(r.e, 40.8, 0.1); near(r.kwh, 10.37, 0.02); near(r.litres, 5.64, 0.05); near(r.per100, 118.7, 1);
// short trip inside the range: no charge-sustaining km; 20 km at 20 C is purely electric, in winter it costs more and burns a little petrol for heat
r = phevBlend({ ...car, d: 20, T: 20 }); near(r.p, 0); near(r.litres, 0); near(r.share, 1); near(r.per100, 19.2 * 2.2, 0.01);
r = phevBlend({ ...car, d: 20, T: -10 }); near(r.p, 0); assert(r.litres > 0 && r.litres < 0.4); assert(r.per100 > phevBlend({ ...car, d: 20, T: 20 }).per100 * 1.3);
// cost per 100 km rises with trip length while petrol per km is dearer than electricity per km
let prev = 0; for (const d of [20, 54, 100, 300]) { const y = phevBlend({ ...car, d, T: 20 }).per100; assert(y >= prev - 1e-9); prev = y; }
// 300 km: mostly petrol, close to the pure charge-sustaining cost
r = phevBlend({ ...car, d: 300, T: 20 }); near(r.per100, (54 * 0.192 * 2.2 + 246 * 0.075 * 17) / 3, 0.01);
// partially charged battery, bad inputs
near(phevBlend({ ...car, d: 100, T: 20, soc: 0.5 }).e, 27); assert.strictEqual(phevBlend({ ...car, d: 0, T: 20 }), null); assert.strictEqual(phevBlend({ ...car, d: 50, range: 0 }), null);
// optimistic variant never costs more than the central estimate
const c0 = phevBlend({ ...car, d: 100, T: -10 }).per100; assert(phevBlend({ ...car, d: 100, T: -10, v: 'opt' }).per100 <= c0 + 1e-9);

// typical day: share = 1 - exp(-R/D): R 54, D 40 -> 0.74 (doc section 5)
let dd = phevDay({ ...car, D: 40, T: 20 }); near(dd.share, 1 - Math.exp(-54 / 40), 1e-9); near(dd.share, 0.74, 0.01);
const dw = phevDay({ ...car, D: 40, T: -10 }); assert(dw.share < dd.share); assert(dw.day > dd.day);
assert.strictEqual(phevDay({ ...car, D: 0, T: 20 }), null);
// month band: curve applied per day then averaged; the cold year costs more than the warm year; mean between them
const cold = Array(30).fill(-8), warm = Array(30).fill(2), b = phevBand({ ...car, D: 40 }, [cold, warm]);
near(b.day, (phevDay({ ...car, D: 40, T: -8 }).day + phevDay({ ...car, D: 40, T: 2 }).day) / 2, 1e-9); assert(b.high > b.low); near(b.high, phevDay({ ...car, D: 40, T: -8 }).day, 1e-9);
// non-linearity: a month alternating -20/+20 differs from a month at the 0 C mean
const alt = phevBand({ ...car, D: 40 }, [[-20, 20, -20, 20]]).day, flat = phevDay({ ...car, D: 40, T: 0 }).day; assert(Math.abs(alt - flat) > 0.05);
assert.strictEqual(phevBand(car, []), null); assert.strictEqual(phevBand({ ...car, D: 40 }, [[]]), null);
console.log('phev blend: all tests passed');
