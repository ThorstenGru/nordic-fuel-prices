// Tests for the pure route-model functions in web/index.html (between RT-PURE-BEGIN and RT-PURE-END).  node tools/test_route_model.js
const fs = require('fs'), assert = require('assert');
const src = fs.readFileSync(__dirname + '/../web/index.html', 'utf8');
const m = src.match(/\/\/ RT-PURE-BEGIN[^\n]*\n([\s\S]*?)\/\/ RT-PURE-END/); assert(m, 'pure block not found');
const { rtPlan, rtCand, rtRef, rtTier, rtMedian, rtSpeedF, rtBand, rtFresh, rtSegs, rtProfile, rtReachKm, rtMakePlan, rtSpeedCmp, rtMinFill } = new Function(m[1] + '; return { rtPlan, rtCand, rtRef, rtTier, rtMedian, rtSpeedF, rtBand, rtFresh, rtSegs, rtProfile, rtMakePlan, rtSpeedCmp, rtMinFill };')();
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

// ── Wave 1 ──
assert.strictEqual(rtTier({ age: 49 }), 2); assert.strictEqual(rtTier({ age: 20 }), 0);       // no 10 h cliff any more: 20 h old is still usable, only 48 h+ is not verified
// R3: price band grows with age; undated is the widest
assert(rtBand(1) < rtBand(8) && rtBand(8) < rtBand(20) && rtBand(20) < rtBand(40) && rtBand(40) < rtBand(null));
// measured error of an undated source narrows ONLY the undated band, within 0.02 .. 0.10
near(rtBand(null, 0.04), 0.04, 1e-9); near(rtBand(null, 0.001), 0.02, 1e-9); near(rtBand(null, 0.5), 0.10, 1e-9); near(rtBand(null), 0.10, 1e-9); near(rtBand(5, 0.04), rtBand(5), 1e-9);
let fr = rtFresh([{ age: 1 }, { age: 6 }, { age: null }]); assert.deepStrictEqual([fr.n, fr.nDated, fr.minH, fr.maxH], [3, 2, 1, 6]);
assert.strictEqual(rtFresh([{ age: null }]).minH, null);
// R7: speed -> energy per km; 1.0 at 110, less when slower, more when faster; clamped
near(rtSpeedF(110), 1, 1e-9); assert(rtSpeedF(90) < 1 && rtSpeedF(130) > 1); near(rtSpeedF(130) / rtSpeedF(110), 1.238, 0.01); assert.strictEqual(rtSpeedF(10), rtSpeedF(70));
// segments: ferry uses no energy; cruise only replaces the speed on motorway stretches and changes their time
let sg = rtSegs([{ km: 110, min: 60, hw: true }, { km: 19, min: 50, ferry: true }, { km: 60, min: 60, hw: false }], 130);
near(sg[0].min, 110 / 130 * 60, 1e-6); near(sg[0].f, rtSpeedF(130), 1e-9); assert.strictEqual(sg[1].f, 0); near(sg[2].min, 60, 1e-9); near(sg[2].f, rtSpeedF(60), 1e-9);
sg = rtSegs([{ km: 110, min: 60, hw: true }], null); near(sg[0].min, 60, 1e-9); near(sg[0].f, rtSpeedF(110), 1e-9);
// profile with f = 1 everywhere reproduces the simple energy walk (rtPlan)
const flat = [{ km: 503, min: 300, flat: true }];
let pr = rtProfile(rtSegs(flat, null), car, 1), pl = rtPlan({ ...car, km: 503 });
near(pr.P(pr.total.L), pl.petrolL, 1e-9); near(pr.K(pr.total.L), pl.kwh, 1e-9); near(pr.batEmpty, 40.5, 1e-9);
// a motorway at 130 km/h burns more than the same road at 90 (more petrol once the battery is gone)
const hw = [{ km: 300, min: 180, hw: true }], pe = c => { const q = rtProfile(rtSegs(hw, c), car, 1); return q.P(q.total.L); };
assert(pe(130) > pe(null) && pe(null) > pe(90));
// R6 what-if: slower saves energy and costs time; perHour is the saving per hour of time given up
let sc = rtSpeedCmp(hw, car, 1.7, 90); assert(sc.dMin > 0 && sc.dEur < 0 && sc.perHour > 0); assert.strictEqual(rtSpeedCmp(hw, car, 1.7, null), null);
sc = rtSpeedCmp(hw, car, 1.7, 130); assert(sc.dMin < 0 && sc.dEur > 0);

// R2 stop plan. Malmo-Hamburg-like: 373 km, Santa Fe, plenty of cheap pumps
const mkc = (along, eur, age = 2, extra = {}) => ({ id: 'p' + along, along, eur, detourKm: 2, age, tier: age != null && age > 48 ? 2 : age == null ? 1 : 0, ...extra });
const ref = 1.8, rcar = { ...car, km: 373, reserveL: 4.7 };
// full tank, battery full: no stop at all (petrol burn ~ 23 L of 47)
let mp = rtMakePlan({ o: rcar, segs: null, min: 280, cands: [mkc(100, 1.7), mkc(250, 1.6)], ref, asm: {} });
assert.strictEqual(mp.status, 'ok'); assert.strictEqual(mp.nStops, 0); assert(mp.arrive.mid > 14 && mp.arrive.lo < mp.arrive.mid && mp.arrive.mid < mp.arrive.hi);
// 20 L start, empty battery: one stop is needed, it buys at least the minimum fill, and the reserve holds at arrival (pessimistic case)
const low = { ...rcar, fuelL: 20, elecKm: 0, kwh100: 0, elecEur: null };
mp = rtMakePlan({ o: low, segs: null, min: 280, cands: [mkc(60, 1.9), mkc(150, 1.7), mkc(250, 1.6), mkc(330, 1.55)], ref, asm: {} });
assert.strictEqual(mp.status, 'ok'); assert.strictEqual(mp.nStops, 1); assert(mp.stops[0].litres >= rtMinFill(47) - 1e-6, 'min fill');
assert(mp.arrive.lo >= low.reserveL - 0.01, 'reserve kept (pessimistic)'); assert(mp.fuelCost.lo < mp.fuelCost.mid && mp.fuelCost.mid < mp.fuelCost.hi);
// the plan prefers the cheaper pump when both are reachable and fill is sensible
assert.strictEqual(mp.stops[0].along, 150);      // 250 and 330 are cheaper but beyond what 20 L carries
// "no stop for just 5 litres": start fuel is 5 L short of the destination; still buys a sensible amount, not 5
const short = { ...rcar, fuelL: 26, elecKm: 0, kwh100: 0, elecEur: null };       // burns ~26 L + 10 % margin on 373 km at 7 L/100
mp = rtMakePlan({ o: short, segs: null, min: 280, cands: [mkc(200, 1.7)], ref, asm: {} });
assert.strictEqual(mp.nStops, 1); assert(mp.stops[0].litres >= 13.9, 'sensible fill, got ' + mp.stops[0].litres);
// fewer stops: a long trip (1100 km, 47 L tank, no battery) needs 2 stops, never more than needed, each at least the minimum fill
const pumps = []; for (let a = 50; a < 1100; a += 40) pumps.push(mkc(a, 1.7 + (a % 120) / 1000));
mp = rtMakePlan({ o: { ...rcar, km: 1100, fuelL: 47, elecKm: 0, kwh100: 0, elecEur: null }, segs: null, min: 800, cands: pumps, ref, asm: {} });
assert.strictEqual(mp.status, 'ok'); assert(mp.nStops >= 2 && mp.nStops <= 3, 'stops ' + mp.nStops);
mp.stops.forEach(s => assert(s.litres >= 13.9)); assert(mp.arrive.lo >= 4.7 - 0.01);
// stops are in route order and the track never drops below zero fuel
for (let i = 1; i < mp.stops.length; i++) assert(mp.stops[i].along > mp.stops[i - 1].along); assert(mp.track.every(t => t.fuelL > -0.01));
// a country with no price times at all (Germany via ANWB, cu) is still planned: the late, cheap undated pumps win over a dated expensive one, but ONLY in such a country
{ const dk = (a, e) => ({ ...mkc(a, e), s: { country: 'DK' } }), de = (a, e, cu) => ({ ...mkc(a, e, null), s: { country: 'DE' }, cu });
  const o2 = { ...rcar, km: 373, fuelL: 20, elecKm: 0, kwh100: 0, elecEur: null };
  const withCu = rtMakePlan({ o: o2, segs: null, min: 280, cands: [dk(60, 2.3), de(150, 1.7, true)], ref, asm: {} });
  assert.strictEqual(withCu.stops[0].s.country, 'DE', 'undated pump of an undated-only country is planned'); assert.strictEqual(withCu.undated, true);
  const noCu = rtMakePlan({ o: o2, segs: null, min: 280, cands: [dk(60, 2.3), de(150, 1.7, false)], ref, asm: {} });
  assert.strictEqual(noCu.stops[0].s.country, 'DK', 'an undated pump in a country that has dated pumps is still not planned around'); }
// unverified (tier 2) pumps are never planned around; no usable pump and fuel short -> unreachable with the distance the start fuel carries
mp = rtMakePlan({ o: low, segs: null, min: 280, cands: [mkc(100, 1.0, 100)], ref, asm: {} });
assert.strictEqual(mp.status, 'unreachable'); assert(mp.energy.reachKm > 100 && mp.energy.reachKm < 373);
// only way to reach: pump so late that a full minimum fill is not possible is still allowed (relaxed), flagged
const tight = { ...rcar, fuelL: 20, elecKm: 0, kwh100: 0, elecEur: null, tank: 47 };
mp = rtMakePlan({ o: { ...tight, km: 300 }, segs: null, min: 200, cands: [mkc(190, 1.7)], ref, asm: {} });
assert.strictEqual(mp.status, 'ok'); assert.strictEqual(mp.nStops, 1);
// undated prices still produce a plan but a wider cost range than dated ones
const rng = age => { const x = rtMakePlan({ o: low, segs: null, min: 280, cands: [mkc(150, 1.65, age)], ref, asm: {} }); return (x.fuelCost.hi - x.fuelCost.lo) / x.fuelCost.mid; };
assert(rng(null) > rng(1)); assert.strictEqual(rtMakePlan({ o: low, segs: null, min: 280, cands: [mkc(150, 1.65, null)], ref, asm: {} }).fresh.nDated, 0);
// segment-aware plan: a ferry in the middle uses no fuel and the segments add up to the route
const sgs = [{ km: 150, min: 90, hw: true }, { km: 19, min: 50, ferry: true }, { km: 200, min: 130, hw: true }];
mp = rtMakePlan({ o: { ...rcar, km: 369, elecKm: 0, kwh100: 0, elecEur: null }, segs: sgs, cands: [], ref, asm: { cruise: 110 } });
near(mp.segs[mp.segs.length - 1].kmEnd, 369, 1e-6); near(mp.time.driveMin, 150 / 110 * 60 + 50 + 200 / 110 * 60, 1e-6);
assert.strictEqual(mp.nStops, 0);
// start fuel below the reserve: an all-electric 25 km hop is fine (no false 'unreachable'); a petrol burn is still refused
const ev25 = { ...car, km: 25, fuelL: 11.75, reserveL: 15 };
for (const cands of [[], [mkc(10, 1.7)]]) { mp = rtMakePlan({ o: ev25, segs: null, min: 20, cands, ref, asm: {} }); assert.strictEqual(mp.status, 'ok'); assert.strictEqual(mp.nStops, 0); }
assert.strictEqual(rtMakePlan({ o: { ...ev25, km: 200, elecKm: 0, kwh100: 0, elecEur: null }, segs: null, min: 150, cands: [], ref, asm: {} }).status, 'unreachable');
// reach: battery runs out inside one segment; flat 373 km, 25 % fuel, 10 % reserve (hand-computed (7.05 L / 0.075 + 40.5) / 1.1 = 122.7 km with cons 7.5)
const sf = { ...car, cons: 7.5, km: 373, fuelL: 11.75, reserveL: 4.7 };
near(rtMakePlan({ o: sf, segs: null, min: 280, cands: [], ref, asm: {} }).energy.reachKm, (7.05 / 0.075 + 40.5) / 1.1, 0.3);
near(rtMakePlan({ o: { ...sf, km: 1100, fuelL: 47 * 0.25 }, segs: null, min: 800, cands: [], ref, asm: {} }).energy.reachKm, (7.05 / 0.075 + 40.5) / 1.1, 0.3);
// plan trust: a dated pump is chosen over a cheaper undated one; undated only when nothing dated fits, and then the plan says so
mp = rtMakePlan({ o: low, segs: null, min: 280, cands: [mkc(150, 1.8, 2), mkc(140, 1.4, null)], ref, asm: {} });
assert.strictEqual(mp.stops[0].along, 150); assert.strictEqual(mp.undated, false);
mp = rtMakePlan({ o: low, segs: null, min: 280, cands: [mkc(140, 1.4, null)], ref, asm: {} });
assert.strictEqual(mp.status, 'ok'); assert.strictEqual(mp.undated, true); assert.strictEqual(mp.stops[0].reason, 'need');
// measured-error range for undated German prices (uncFromAcc)
{ const u = src.match(/\/\/ UNC-PURE-BEGIN[^\n]*\n([\s\S]*?)\/\/ UNC-PURE-END/); assert(u, 'unc block not found');
  const uncFromAcc = new Function(u[1] + '; return uncFromAcc;')();
  const acc = { by: { 'petrol|metro': { n: 500, abs_p90_ct: 1 }, 'petrol|rural': { n: 300, abs_p90_ct: 3 }, 'diesel|metro': { n: 500, abs_p90_ct: 2 }, 'diesel|rural': { n: 50, abs_p90_ct: 9 } } };
  assert.strictEqual(uncFromAcc(acc, 'DE', 'P95'), 0.03);          // worse of the two petrol strata
  assert.strictEqual(uncFromAcc(acc, 'DE', 'DIESEL'), 0.02);       // the 50-check rural stratum is too small to count
  assert.strictEqual(uncFromAcc(acc, 'SE', 'P95'), null);          // only Germany
  assert.strictEqual(uncFromAcc(null, 'DE', 'P95'), null);
  assert.strictEqual(uncFromAcc({ by: { 'petrol|metro': { n: 10, abs_p90_ct: 1 } } }, 'DE', 'P95'), null);
  assert.strictEqual(uncFromAcc({}, 'DE', 'DIESEL'), null); }

console.log('route model: all tests passed');
