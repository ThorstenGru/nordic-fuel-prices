// Tests for the wave 3 pure route functions in web/index.html (navigation links, backup pump, return trip, public AC verdict, energy strip, departure hint).  node tools/test_route_wave3.js
const fs = require('fs'), assert = require('assert');
const src = fs.readFileSync(__dirname + '/../web/index.html', 'utf8');
const m = src.match(/\/\/ RT-PURE-BEGIN[^\n]*\n([\s\S]*?)\/\/ RT-PURE-END/); assert(m, 'pure block not found');
const names = 'rtWazeUrl rtNavLinks rtNavText rtBackup rtBackTrip rtAcVerdict rtStrip rtDepartHint rtCycCell rtMakePlan RT_NAV_MAX'.split(' ');
const F = new Function(m[1] + '; return { ' + names.join(', ') + ' };')();
const near = (a, b, e = 0.01) => assert(Math.abs(a - b) <= e, `${a} != ${b}`);

// --- R13 links: Waze = one destination, no waypoints, no tracking tag; Google/Apple carry every stop; more than 3 stops: no multi-stop link
const s1 = { lat: 55.1, lon: 14.0 }, s2 = { lat: 53.9, lon: 13.9 }, s3 = { lat: 53.0, lon: 13.0 }, s4 = { lat: 52.5, lon: 13.2 }, end = { lat: 52.52, lon: 13.405 };
assert.strictEqual(F.rtWazeUrl(s1), 'https://waze.com/ul?ll=55.10000%2C14.00000&navigate=yes');
let L = F.rtNavLinks([s1, s2], end);
assert.deepStrictEqual(L.waze, [F.rtWazeUrl(s1), F.rtWazeUrl(s2), F.rtWazeUrl(end)]);
assert(L.waze.every(u => !/utm_|waypoint/.test(u)));
assert.strictEqual(L.google, 'https://www.google.com/maps/dir/?api=1&destination=52.52000%2C13.40500&waypoints=55.10000%2C14.00000%7C53.90000%2C13.90000&travelmode=driving&dir_action=navigate');
assert.strictEqual(L.apple, 'https://maps.apple.com/directions?destination=52.52000%2C13.40500&waypoint=55.10000%2C14.00000&waypoint=53.90000%2C13.90000&mode=driving');
assert(L.google.length < 2048);
L = F.rtNavLinks([s1, s2, s3, s4], end);
assert.strictEqual(L.google, null); assert.strictEqual(L.apple, null); assert.strictEqual(L.waze.length, 5);   // Waze legs stay
assert.strictEqual(F.rtNavLinks([s1, s2, s3], end).google !== null, true);                                    // exactly the mobile limit
assert.strictEqual(F.rtNavLinks([], end).google, null);                                                      // no stop: nothing to export
assert.strictEqual(F.rtNavText([{ label: 'A. Circle K', p: s1 }, { label: 'Destination: Berlin', p: end }]), 'A. Circle K\n   55.10000,14.00000\nDestination: Berlin\n   52.52000,13.40500');

// --- R15 backup pump: nearest trusted pump further on that the fuel after the fill-up reaches above the reserve
const o = { cons: 7, reserveL: 5 };
const stop = { id: 'a', along: 100, fuelAfter: 40 };
const cand = (id, along, tier = 0, detourKm = 1) => ({ id, along, tier, detourKm, eur: 1.8 });
let b = F.rtBackup(stop, [cand('a', 100), cand('x', 101), cand('y', 130), cand('z', 160)], o);
assert.strictEqual(b.pump.id, 'y'); near(b.km, 30);                                                         // not itself, not within 2 km, nearest after that
b = F.rtBackup(stop, [cand('far', 700)], o); assert.strictEqual(b, null);                                    // 600 km on 40 L: out of reach, nothing shown
b = F.rtBackup(stop, [cand('u', 120, 1), cand('t', 170, 0)], o); assert.strictEqual(b.pump.id, 't');         // a trusted pump beats a nearer undated one
b = F.rtBackup(stop, [cand('u', 120, 1), cand('bad', 110, 2)], o); assert.strictEqual(b.pump.id, 'u');       // undated only when no trusted one is reachable; unverified never
assert.strictEqual(F.rtBackup(stop, [cand('bad', 110, 2)], o), null);
assert.strictEqual(F.rtBackup(stop, undefined, o), null);
// reach uses the 10 % margin: 40 L, 5 L reserve, 7 L/100 km -> 35 L / 0.077 = 454 km; a pump at +440 km with 1 km detour just fits, one at +460 does not
assert(F.rtBackup(stop, [cand('e', 540)], o)); assert.strictEqual(F.rtBackup(stop, [cand('e', 560)], o), null);

// --- R14 return trip with a charger at the destination
let r = F.rtBackTrip({ cons: 7.5, gEl: 0 }, 40, 600, 1.7);
near(r.elecKm, 40); near(r.litres, 3); near(r.eur, 5.1);
r = F.rtBackTrip({ cons: 7.5, gEl: 1 }, 40, 25, 1.7); near(r.elecKm, 25); near(r.litres, 25 * 6.5 / 100);       // short trip: only the trip's km; heat petrol is not saved
assert.strictEqual(F.rtBackTrip({ cons: 7.5 }, 40, 100, null).eur, null);                                     // no reference price: litres only
assert.strictEqual(F.rtBackTrip({ cons: 7.5 }, 0, 100, 1.7), null); assert.strictEqual(F.rtBackTrip({ cons: 0 }, 40, 100, 1.7), null);

// --- R16 public AC verdict: Santa Fe numbers (3.6 kW, 21.3 kWh/100 km at the wall, 7.5 L/100 km), 3.50 SEK = 0.32 EUR per kWh, petrol 1.70 EUR/L
const ac = { chgKw: 3.6, min: 30, kwh100: 21.3, cons: 7.5, gEl: 0, acEur: 3.5 * 0.0912, petrolEur: 1.7, battKwh: 13.8, leftKm: 400, stopEur: 2 };
let v = F.rtAcVerdict(ac);
near(v.kwh, 1.8); near(v.km, 1.8 / 21.3 * 100, 0.01); near(v.litres, v.km * 7.5 / 100); near(v.cost, 1.8 * 3.5 * 0.0912); near(v.saved, v.litres * 1.7);
assert(!v.pays && !v.dearer, 'saves a little against the electricity but not against the stop: usually not worth it');   // 1.08 saved - 0.57 cost - 2 stop < 0
near(v.breakEven, 7.5 * 1.7 / 21.3, 0.001);
// a long stop with a cheap price pays; a high price is dearer than petrol per km; the stop cost can be switched off
v = F.rtAcVerdict({ ...ac, min: 240, acEur: 0.05, battKwh: 99 }); assert(v.pays && v.net > 0);
v = F.rtAcVerdict({ ...ac, acEur: 0.9 }); assert(v.dearer && !v.pays);
v = F.rtAcVerdict({ ...ac, stopEur: 0 }); assert(v.pays, 'without a stop cost the small saving counts');
// the battery room and the km left cap what the stop can add; heat petrol reduces the saving
v = F.rtAcVerdict({ ...ac, min: 600, battKwh: 13.8, stopEur: 0 }); near(v.kwh, 13.8);
v = F.rtAcVerdict({ ...ac, leftKm: 3 }); near(v.km, 3); near(v.kwh, 3 * 0.213);
near(F.rtAcVerdict({ ...ac, gEl: 1.5 }).litres, F.rtAcVerdict(ac).litres * 6 / 7.5);
// missing inputs: nothing
for (const k of ['chgKw', 'kwh100', 'cons', 'acEur', 'petrolEur', 'leftKm', 'min']) assert.strictEqual(F.rtAcVerdict({ ...ac, [k]: undefined }), null, k);
assert.strictEqual(F.rtAcVerdict({ ...ac, chgKw: 0 }), null);

// --- R8 energy strip: from a real plan (Santa Fe, 600 km, one stop)
const oP = { km: 600, cons: 7.5, tank: 47, fuelL: 47, reserveL: 5, elecKm: 40, kwh100: 21, elecEur: 0.2, gEl: 0 };
const cs = [{ id: 'p1', s: { id: 'p1' }, p: {}, along: 330, eur: 1.7, detourKm: 1, age: 1, tier: 0 }];
const P = F.rtMakePlan({ o: oP, segs: null, min: 400, cands: cs, ref: 1.8, asm: { battPct: 100 } });
let S = F.rtStrip(P, oP);
assert(S && P.status === 'ok');
assert(S.fuel.length === P.track.length && S.fuel.every(p => p[0] >= 0 && p[0] <= 1 && p[1] >= 0 && p[1] <= 1));
assert(S.batt && S.batt[0][1] === 1 && S.batt[S.batt.length - 1][1] === 0, 'battery from full to empty');
near(S.reserve, 5 / 47, 1e-9);
assert.strictEqual(S.marks.length, P.nStops); if (P.nStops) near(S.marks[0].x, P.stops[0].along / 600, 1e-9);
near(S.batEmptyAt, 40, 0.5);
assert(S.low.L > 0 && S.low.L <= 47);
// battery starting at 50 %: the strip starts at half; a car without electric range has no battery line; no track: nothing
S = F.rtStrip({ ...P, asm: { battPct: 50 } }, oP); near(S.batt[0][1], 0.5);
assert.strictEqual(F.rtStrip(P, { ...oP, elecKm: 0 }).batt, null);
assert.strictEqual(F.rtStrip({ ...P, track: [] }, oP), null); assert.strictEqual(F.rtStrip(null, oP), null);

// --- R18 departure hint: synthetic price_cycles series (schema docs/PRICE_CYCLES.md): level = 0.01 % steps, offset 2048, 2 chars, then n
const A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
const enc = (lvl, n) => { const x = Math.max(0, Math.min(4095, Math.round(lvl / 0.01) + 2048)); return A[x >> 6] + A[x & 63] + A[n]; };
const series = f => { let c = ''; for (let i = 0; i < 168; i++) c += f(Math.floor(i / 24), i % 24); return c; };
const file = c => ({ schema: 1, updated: '2026-11-06T12:00:00Z', series: { SE: { p95: { b: 1.7, t: '2026-11-06T12:00Z', c } } } });
assert.deepStrictEqual(F.rtCycCell(enc(-0.85, 14), 0), { lvl: -0.85, n: 14 });
// Tuesday (wd 1) 14:00 and 15:00 at -0.9 / -0.7 with 15 samples: window 14-16, level -0.8; the rest around +0.1
let c = series((wd, hr) => wd === 1 && hr === 14 ? enc(-0.9, 15) : wd === 1 && hr === 15 ? enc(-0.7, 15) : enc(0.1, 15));
let h = F.rtDepartHint(file(c), 'SE', 'p95');
assert.deepStrictEqual(h, { wd: 1, hr: 14, width: 2, lvl: -0.8, n: 15 });
// min_n 12: one thin cell in the window skips it (the next best qualifying window is used or none)
c = series((wd, hr) => wd === 1 && hr === 14 ? enc(-0.9, 15) : wd === 1 && hr === 15 ? enc(-0.7, 11) : enc(0.1, 15));
h = F.rtDepartHint(file(c), 'SE', 'p95'); assert(!h || !(h.wd === 1 && (h.hr === 14 || h.hr === 15)), JSON.stringify(h));   // 13+14 (-0.4) is a legitimate window: both cells have enough samples
assert.strictEqual(F.rtDepartHint(file(series(() => enc(-1.5, 11))), 'SE', 'p95'), null);                   // a fresh file: every cell below 12 samples
assert.strictEqual(F.rtDepartHint(file(series(() => enc(0, 0))), 'SE', 'p95'), null);                        // the collector's EMPTY series
assert.strictEqual(F.rtDepartHint(file(series((wd, hr) => enc(hr === 3 ? -0.1 : 0.2, 20))), 'SE', 'p95'), null);   // a dip smaller than 0.3 %: no claim
// wraps inside the day: 23:00 + 00:00
c = series((wd, hr) => wd === 4 && hr === 23 ? enc(-1.2, 20) : wd === 4 && hr === 0 ? enc(-1, 20) : enc(0, 20));
h = F.rtDepartHint(file(c), 'SE', 'p95'); assert.strictEqual(h.wd, 4); assert.strictEqual(h.hr, 23); near(h.lvl, -1.1);
// country or fuel missing, wrong schema, damaged data: nothing, never throws
assert.strictEqual(F.rtDepartHint(file(c), 'NO', 'p95'), null); assert.strictEqual(F.rtDepartHint(file(c), 'SE', 'diesel'), null);
assert.strictEqual(F.rtDepartHint({ ...file(c), schema: 2 }, 'SE', 'p95'), null);
assert.strictEqual(F.rtDepartHint(file(c.slice(1)), 'SE', 'p95'), null); assert.strictEqual(F.rtDepartHint(file('!'.repeat(504)), 'SE', 'p95'), null);
assert.strictEqual(F.rtDepartHint(null, 'SE', 'p95'), null); assert.strictEqual(F.rtDepartHint({}, 'SE', 'p95'), null);
console.log('route wave 3: all tests passed');
