// Tests for the wave 2 pure route functions in web/index.html (trip cost, alternatives, fares, border tip, noon rule).  node tools/test_route_wave2.js
const fs = require('fs'), assert = require('assert');
const src = fs.readFileSync(__dirname + '/../web/index.html', 'utf8');
const m = src.match(/\/\/ RT-PURE-BEGIN[^\n]*\n([\s\S]*?)\/\/ RT-PURE-END/); assert(m, 'pure block not found');
const names = 'rtKeepAlts rtFaresFor rtRouteEnergy rtFuelUnit rtTripCost rtPick rtBorders rtTrackAt rtTank rtNoonOn rtLastNoon rtNoonNote rtMakePlan RT_NOON'.split(' ');
const F = new Function(m[1] + '; return { ' + names.join(', ') + ' };')();
const near = (a, b, e = 0.01) => assert(Math.abs(a - b) <= e, `${a} != ${b}`);
const fares = JSON.parse(fs.readFileSync(__dirname + '/../web/fares.json', 'utf8'));
const NOW = Date.parse('2026-11-06T10:00:00Z'), toEur = c => ({ EUR: 1, DKK: 0.134, CZK: 0.041, SEK: 0.09 })[c] || null;

// --- alternatives: drop duplicates, drop much slower ones, cap at 2
const main = { km: 600, min: 400 };
assert.strictEqual(F.rtKeepAlts(main, [{ km: 601, min: 400.5 }, { km: 640, min: 430 }, { km: 700, min: 500 }, { km: 650, min: 440 }, { km: 660, min: 450 }]).length, 2);
assert.deepStrictEqual(F.rtKeepAlts(main, [{ km: 601, min: 400.5 }, { km: 700, min: 500 }]), []);
assert.deepStrictEqual(F.rtKeepAlts(main, undefined), []);

// --- fares: a route Malmo -> Copenhagen -> Rodby -> Puttgarden -> Hamburg (points near the endpoints), ferry flagged
const pts = [[55.6, 12.99], [55.5655, 12.875], [55.613, 12.649], [54.65, 11.35], [54.5, 11.23], [53.55, 10.0]];
const ids = r => [r.priced.map(x => x.e.id), r.unknown.map(x => x.e.id)];
let r = F.rtFaresFor(fares, { pts, ferry: true, toll: true, via: 'valhalla', cc: ['SE', 'DK', 'DE'] }, NOW, toEur);
assert.deepStrictEqual(ids(r)[0], ['oresund-bridge']);                         // priced: trip_price, seen today
near(r.priced[0].eur, 470 * 0.134);
assert(ids(r)[1].includes('rodby-puttgarden'));                               // matched but trip_price null -> unknown, never min..max
assert(!ids(r)[1].includes('fehmarnbelt-tunnel'), 'tunnel not built: open:false never matches');
assert(!r.unmatched && !r.noFlags);
// the same route without a ferry: the ferry entries do not apply, the bridge does
r = F.rtFaresFor(fares, { pts, ferry: false, toll: true, via: 'valhalla', cc: ['SE', 'DK', 'DE'] }, NOW, toEur);
assert(!ids(r)[1].includes('rodby-puttgarden')); assert.deepStrictEqual(ids(r)[0], ['oresund-bridge']);
// a fare last seen over 90 days ago is not counted, it becomes unknown (old)
r = F.rtFaresFor(fares, { pts, ferry: false, toll: true, via: 'valhalla', cc: ['SE', 'DK'] }, Date.parse('2027-03-01'), toEur);
assert.strictEqual(r.priced.length, 0); assert(r.unknown.find(x => x.e.id === 'oresund-bridge').old);
// no rate for the currency: not counted
assert.strictEqual(F.rtFaresFor(fares, { pts, ferry: false, toll: true, via: 'valhalla', cc: [] }, NOW, () => null).priced.length, 0);
// vignette by countries driven; no match at all but the router flags a toll: generic unknown; OSRM fallback: noFlags
r = F.rtFaresFor(fares, { pts: [[48, 11]], ferry: false, toll: false, via: 'valhalla', cc: ['DE', 'AT'] }, NOW, toEur); assert.deepStrictEqual(ids(r)[0], ['vignette-at']);
r = F.rtFaresFor(fares, { pts: [[10, 10]], ferry: false, toll: true, via: 'valhalla', cc: ['FI'] }, NOW, toEur); assert(r.unmatched && !r.priced.length);
r = F.rtFaresFor(fares, { pts: [[10, 10]], ferry: false, toll: false, via: 'osrm', cc: [] }, NOW, toEur); assert(r.noFlags && !r.unmatched);
assert.strictEqual(F.rtFaresFor(null, { pts: [], via: 'valhalla' }, NOW, toEur).priced.length, 0);   // fares file missing: no figure invented

// --- trip cost: Santa Fe PHEV numbers from the wave 1 tests
const car = { cons: 7, tank: 47, fuelL: 47, reserveL: 4.7, elecKm: 40.5, kwh100: 13.8 / 54 * 100 / 0.9, elecEur: 0.25 };
const base = { o: car, cruise: null, vot: 0, u: 1.80, h: 0.03, elecEur: 0.25, fares, now: NOW, toEur, stopMin: 10 };
const A = { pts, km: 503, min: 330, segs: null, ferry: true, toll: true, via: 'valhalla', cc: ['SE', 'DK', 'DE'] };
let c = F.rtTripCost({ ...A }, base);
near(c.petrolL, (503 - 40.5) * 0.07, 0.1); near(c.fuel.lo, c.petrolL * 1.77, 0.01); near(c.fuel.hi, c.petrolL * 1.83, 0.01);
near(c.elec, 40.5 * car.kwh100 / 100 * 0.25, 0.01); near(c.fare, 470 * 0.134, 0.01); near(c.min, 340, 0.5);
assert(c.fareUnknown, 'rodby-puttgarden is matched without a trip price');
near(c.total.lo, c.fuel.lo + c.elec + c.fare, 0.001);
// no fuel price: no total (nothing invented)
c = F.rtTripCost({ ...A, fr: undefined }, { ...base, u: null }); assert.strictEqual(c.total, null); assert.strictEqual(c.value, null);
// picks: B is shorter and cheaper but slower; C is faster and dearer
const mk = (km, min, ferry) => ({ pts: [[0, 0]], km, min, segs: null, ferry, toll: false, via: 'valhalla', cc: [] });
const cs = [mk(500, 330, false), mk(480, 360, false), mk(520, 300, false)].map(x => F.rtTripCost(x, base));
let pk = F.rtPick(cs, 0); assert.strictEqual(pk.cheap, 1); assert.strictEqual(pk.fast, 2); assert.strictEqual(pk.bal, null);
pk = F.rtPick(cs.map(x => F.rtTripCost({ ...mk(x.km, x.min - 10, false) }, { ...base, vot: 200 })), 200);   // time is expensive: the fast one is the balanced one
assert.strictEqual(pk.bal, 2);
assert.deepStrictEqual(F.rtPick([{ mid: null, min: 5, value: null }], 20), { cheap: null, fast: 0, bal: null, skipped: false });
// an unknown fare is not free: Cheapest and Balanced go to the route whose fares are all known
pk = F.rtPick([{ mid: 50, min: 90, value: 60, fareUnknown: true }, { mid: 120, min: 80, value: 125, fareUnknown: false }], 20);
assert.strictEqual(pk.cheap, 1); assert.strictEqual(pk.bal, 1); assert.strictEqual(pk.fast, 1); assert.strictEqual(pk.skipped, true);
pk = F.rtPick([{ mid: 50, min: 90, value: 60, fareUnknown: true }, { mid: 40, min: 80, value: 55, fareUnknown: true }], 20); assert.strictEqual(pk.cheap, 1); assert.strictEqual(pk.skipped, false);

// --- fuel unit: plan stops -> litres-weighted price with its range; no stops -> median
const P0 = { stops: [{ litres: 20, cost: { mid: 36, lo: 35, hi: 37 } }, { litres: 20, cost: { mid: 40, lo: 38, hi: 42 } }] };
let u = F.rtFuelUnit(P0, 1.7); near(u.u, 1.9); near(u.h, 0.075);
u = F.rtFuelUnit({ stops: [] }, 1.7); near(u.u, 1.7); assert(u.h > 0); assert.strictEqual(F.rtFuelUnit({ stops: [] }, null), null);

// --- border tankering on a real plan. 700 km route, petrol only, A (SE) pumps 0-300 km, B (DK/DE) pumps 330-700 km.
const o2 = { cons: 7, tank: 47, fuelL: 14, reserveL: 4.7, elecKm: 0, kwh100: 0, elecEur: null, km: 700 };
const cand = (id, cc, along, eur, extra = {}) => ({ id, s: { country: cc, name: id }, along, eur, detourKm: 1, age: 2, tier: 0, ...extra });
const cands = [cand('a1', 'SE', 60, 1.80), cand('a2', 'SE', 120, 1.55), cand('a3', 'SE', 180, 1.60), cand('b1', 'DE', 400, 1.85), cand('b2', 'DE', 520, 1.90)];
const o3 = { ...o2, km: 1000 }, cands3 = [...cands, cand('b3', 'DE', 700, 1.88), cand('b4', 'DE', 850, 1.90)];   // long enough that the plan must also buy in DE
const plan = F.rtMakePlan({ o: o3, segs: null, min: 600, cands: cands3, ref: 1.75, asm: { vot: 0 } });
assert.strictEqual(plan.status, 'ok');
const bs = F.rtBorders(cands); assert.strictEqual(bs.length, 1); assert.strictEqual(bs[0].from, 'SE'); assert.strictEqual(bs[0].to, 'DE'); near(bs[0].along, (180 + 400) / 2, 0.1);
let tips = F.rtTank(cands3, plan, o3, 1000);
assert(plan.stops.some(s => s.s.country === 'SE'), 'plan fills in the cheap country');
// A is the cheap side and the tank has room: tip is "before"; litres capped by tank space and by the burn after the border
assert(tips.length === 1 && tips[0].dir === 'before', JSON.stringify(tips.map(x => x.dir)));
assert(tips[0].litres > 0 && tips[0].litres <= 47); near(tips[0].save, tips[0].diff * tips[0].litres, 1e-6); assert.strictEqual(tips[0].pump.id, 'a3');   // a2 (1.55) is cheaper but not reachable with the plan's 10 % energy margin from 14 L
// the plan already buys at the border-side pump and nothing after the border: no tip. Plan from the review: SE pumps, DE pumps far ahead.
{ const o = { cons: 7, tank: 47, fuelL: 20, reserveL: 4.7, elecKm: 0, kwh100: 0, elecEur: null, km: 600 };
  const cs = [cand('s1', 'SE', 100, 1.70), cand('s2', 'SE', 200, 1.60), cand('s3', 'SE', 250, 1.65), cand('d1', 'DE', 350, 1.90), cand('d2', 'DE', 450, 1.92), cand('d3', 'DE', 520, 1.95)];
  const pl = F.rtMakePlan({ o, segs: null, min: 400, cands: cs, ref: 1.8, asm: { vot: 0 } });
  assert(pl.status === 'ok' && !pl.stops.some(s => s.s.country === 'DE'));
  assert.deepStrictEqual(F.rtTank(cs, pl, o, 600), []); }
// same prices on both sides (within 3 cents): nothing
assert.deepStrictEqual(F.rtTank(cands3.map(x => ({ ...x, eur: 1.7 })), plan, o3, 1000), []);
// unverified or undated pumps are not used: tier 1 and 2 dropped, so one side is empty
assert.deepStrictEqual(F.rtTank(cands3.map(x => x.s.country === "DE" ? { ...x, tier: 2 } : x), plan, o3, 1000), []);
// a single pump per country is not enough to place a border
assert.deepStrictEqual(F.rtBorders([cand('a', 'SE', 10, 1), cand('b', 'DE', 300, 1)]), []);
// B cheaper and the plan stops in A: tip is "after" (skip the stop), only when the fuel reaches the pump without those litres. Hand-made plan: start 40 L, buys 15 L at km 120.
const stopA = { id: 'a2', s: { country: 'SE' }, along: 120, litres: 15, eur: 1.9 };
const planH = { status: 'ok', stops: [stopA], track: [{ km: 0, fuelL: 40 }, { km: 120, fuelL: 31.6 }, { km: 120, fuelL: 46.6 }, { km: 700, fuelL: 46.6 - 0.07 * 580 }] };
const cH = [cand('a1', 'SE', 60, 1.92), { ...cand('a2', 'SE', 120, 1.9) }, cand('b1', 'DE', 330, 1.55), cand('b2', 'DE', 420, 1.60)];
const oH = { ...o2, fuelL: 40 };
tips = F.rtTank(cH, planH, oH, 700);
assert(tips.length === 1 && tips[0].dir === 'after' && tips[0].pump.id === 'b1', JSON.stringify(tips));
near(tips[0].litres, 15, 0.01); near(tips[0].save, 0.35 * 15, 0.01);
// with only 22 L at the start the fuel does not reach the German pump without the stop (reserve + margin): no tip
assert.deepStrictEqual(F.rtTank(cH, { ...planH, track: [{ km: 0, fuelL: 22 }, { km: 120, fuelL: 13.6 }, { km: 120, fuelL: 28.6 }, { km: 700, fuelL: 28.6 - 0.07 * 580 }] }, { ...o2, fuelL: 22 }, 700), []);
// plan not ok / no track: nothing
assert.deepStrictEqual(F.rtTank(cands, { status: 'unreachable', stops: [], track: [] }, o2, 700), []);
near(F.rtTrackAt([{ km: 0, fuelL: 40 }, { km: 100, fuelL: 33 }, { km: 100, fuelL: 47 }, { km: 200, fuelL: 40 }], 50), 36.5); near(F.rtTrackAt([{ km: 0, fuelL: 40 }, { km: 100, fuelL: 33 }, { km: 100, fuelL: 47 }, { km: 200, fuelL: 40 }], 100), 33);

// --- noon rule: config table, DE/AT only, wording state only (no figures)
assert(F.rtNoonOn('DE', '2026-11-06') && F.rtNoonOn('AT', '2026-11-06'));
assert(!F.rtNoonOn('SE', '2026-11-06') && !F.rtNoonOn('SI', '2026-11-06') && !F.rtNoonOn('HR', '2026-11-06'));
assert(!F.rtNoonOn('DE', '2026-03-31'), 'DE rule starts 2026-04-01'); assert(!F.rtNoonOn('AT', '2029-01-01'), 'AT rule expires 2028-12-31: show nothing after');
// Berlin winter (UTC+1): 2026-11-06 14:30 UTC = 15:30 local, last noon = 11:00 UTC the same day
const iso = s => Date.parse(s);
assert.strictEqual(F.rtLastNoon(iso('2026-11-06T14:30:00Z')), iso('2026-11-06T11:00:00Z'));
assert.strictEqual(F.rtLastNoon(iso('2026-11-06T09:30:00Z')), iso('2026-11-05T11:00:00Z'));          // 10:30 local: yesterday's noon
assert.strictEqual(F.rtLastNoon(iso('2026-07-01T10:30:00Z')), iso('2026-07-01T10:00:00Z'));          // summer UTC+2
const now = iso('2026-11-06T14:30:00Z');
assert.strictEqual(F.rtNoonNote('DE', now - 2 * 36e5, now), 'hint');                                  // seen 12:30 UTC = 13:30 local, after the noon
assert.strictEqual(F.rtNoonNote('AT', now - 5 * 36e5, now), 'risen');                                 // seen before the last noon
assert.strictEqual(F.rtNoonNote('DE', null, now), 'hint');                                            // undated: labelled elsewhere, hint only
assert.strictEqual(F.rtNoonNote('SE', now - 5 * 36e5, now), null); assert.strictEqual(F.rtNoonNote('DK', null, now), null);
assert.strictEqual(F.rtNoonNote('AT', null, iso('2029-01-10T10:00:00Z')), null);
console.log('route wave 2: all tests passed');
