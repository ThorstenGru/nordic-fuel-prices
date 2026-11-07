// Tests for the pure charging-post functions in web/index.html (operator matching, price order, cost with fees, nearest posts, kW groups).  node tools/test_chargers.js
const fs = require('fs'), assert = require('assert');
const src = fs.readFileSync(__dirname + '/../web/index.html', 'utf8');
const m = src.match(/\/\/ CHG-PURE-BEGIN[^\n]*\n([\s\S]*?)\/\/ CHG-PURE-END/); assert(m, 'pure block not found');
const names = 'CHG_F CHG_OLD_DAYS CHG_RADIUS_KM chgNorm chgDays chgDecode chgMatchTariff chgPrice chgMinutes chgCost chgRank chgKm chgNearest chgKwGroup chgKwCounts chgParking chgTags chgStale'.split(' ');
const F = new Function(m[1] + '; return { ' + names.join(', ') + ' };')();
const near = (a, b, e = 0.01) => assert(Math.abs(a - b) <= e, `${a} != ${b}`);
const T = JSON.parse(fs.readFileSync(__dirname + '/../web/ac_tariffs.json', 'utf8')).entries;
const NOW = Date.parse('2026-11-20');

// --- decode: 1-based operator index, notes by row, bad rows skipped, wrong schema refused
const file = { v: 1, cc: 'SE', generated: '2026-11-07', sources: ['OCM'], attribution: ['Open Charge Map contributors (CC BY 4.0)'], ops: ['E.ON Drive', 'MER'],
  s: [[55.6, 13.0, 1, 22, 2, 1, 24, 'Hotel car park'], [55.61, 13.01, 0, 0, 0, 144, 0, ''], ['x', 1, 1, 1, 1, 0, 0, ''], [55.62, 13.02, 2, 11, 4, 0, 25, 'Torget']], notes: [[3, 'Parking 20 kr/h']] };
let d = F.chgDecode(file);
assert.strictEqual(d.posts.length, 3); assert.strictEqual(d.posts[0].op, 'E.ON Drive'); assert.strictEqual(d.posts[1].op, ''); assert.strictEqual(d.posts[2].op, 'MER');
assert.strictEqual(d.posts[2].note, 'Parking 20 kr/h'); assert.strictEqual(d.posts[2].i, 3); assert.strictEqual(d.posts[0].yy, 24); assert.strictEqual(d.posts[1].yy, 0);
assert.strictEqual(F.chgDecode({ ...file, v: 2 }), null); assert.strictEqual(F.chgDecode(null), null); assert.strictEqual(F.chgDecode({ ...file, s: 'no' }), null);
assert.strictEqual(F.chgDecode({ ...file, ops: ['A'], s: [[55, 13, 9, 7, 1, 0, 0, '']] }).posts[0].op, '');   // index beyond the list: unknown, never a wrong name

// --- operator matching: same key space as chargers.py, country must be listed
assert.strictEqual(F.chgNorm('E.ON (DK)'), 'eon'); assert.strictEqual(F.chgNorm('Powered by E.ON Drive & Clever'), 'powered by eon drive clever');
assert.strictEqual(F.chgNorm('Mer Sweden AB'), 'mer'); assert.strictEqual(F.chgNorm(null), '');
assert.strictEqual(F.chgMatchTariff(T, 'SE', 'MER').id, 'mer-se'); assert.strictEqual(F.chgMatchTariff(T, 'NO', 'MER').id, 'mer-no');
assert.strictEqual(F.chgMatchTariff(T, 'SE', 'E.ON Drive').id, 'eon-drive-se'); assert.strictEqual(F.chgMatchTariff(T, 'DK', 'E.ON Drive').id, 'eon-drive-dk');
assert.strictEqual(F.chgMatchTariff(T, 'DE', 'Aral pulse').id, 'aral-pulse-de'); assert.strictEqual(F.chgMatchTariff(T, 'DE', 'Allego BV').id, 'allego-de');
assert.strictEqual(F.chgMatchTariff(T, 'SE', 'Allego BV').ac, null);                 // Nordic Allego entry exists but holds no price
assert.strictEqual(F.chgMatchTariff(T, 'SE', 'Stadtwerke Irgendwo'), null); assert.strictEqual(F.chgMatchTariff(T, 'DE', 'MER'), null);   // wrong country: no match
assert.strictEqual(F.chgMatchTariff(T, 'SE', ''), null); assert.strictEqual(F.chgMatchTariff(undefined, 'SE', 'MER'), null);
assert.strictEqual(F.chgMatchTariff(T, 'SE', 'Recharge (Formerly Fortum Charge & Drive)').id, 'recharge-se');

// --- price order: free flag > own price > list > none; old entries are flagged and never used
const post = (o = {}) => ({ f: 0, kw: 22, ...o });
const mer = T.find(e => e.id === 'mer-se'), dk = T.find(e => e.id === 'eon-drive-dk'), al = T.find(e => e.id === 'allego-de');
assert.strictEqual(F.chgPrice(post({ f: F.CHG_F.free }), mer, { p: 3, cur: 'SEK' }, NOW).kind, 'free');
let p = F.chgPrice(post(), mer, { p: 3, cur: 'SEK' }, NOW); assert.strictEqual(p.kind, 'own'); assert.strictEqual(p.lo, 3);
p = F.chgPrice(post(), mer, { p: 3 }, NOW); assert.strictEqual(p.kind, 'list');                                    // own price without a currency is ignored
p = F.chgPrice(post(), mer, null, NOW); assert.strictEqual(p.kind, 'list'); assert.strictEqual(p.lo, 6); assert.strictEqual(p.cur, 'SEK'); assert.strictEqual(p.start, null);
assert.strictEqual(p.member, 5.6); assert.strictEqual(p.memberSub, true); assert.strictEqual(p.from, false);
assert.strictEqual(F.chgPrice(post(), null, null, NOW).kind, 'none'); assert.strictEqual(F.chgPrice(post(), F.chgMatchTariff(T, 'SE', 'Circle K'), null, NOW).kind, 'none');
p = F.chgPrice(post(), al, null, NOW); assert.strictEqual(p.lo, 0.48); assert.strictEqual(p.hi, 0.6); assert.strictEqual(p.from, true);
assert.strictEqual(F.chgPrice(post(), mer, null, Date.parse('2027-03-01')).kind, 'old');                            // 114 days
assert.strictEqual(F.chgPrice(post(), mer, null, Date.parse('2027-02-04')).kind, 'list');                           // exactly 89 days: still fresh
assert.strictEqual(F.chgPrice(post(), { ...mer, seen_on: 'garbage' }, null, NOW).kind, 'old');                     // unreadable date counts as old, not as fresh
assert.strictEqual(F.chgCost(F.chgPrice(post(), mer, null, Date.parse('2027-03-01')), 10, 60), null);               // an old price is never used in a cost
assert.strictEqual(F.chgCost(F.chgPrice(post(), null, null, NOW), 10, 60), null);                                   // none: no cost

// --- minutes at the lower of post and car rate
near(F.chgMinutes(13.8, 22, 3.6), 230); near(F.chgMinutes(13.8, 0, 3.6), 230); near(F.chgMinutes(13.8, 2, 3.6), 414); assert.strictEqual(F.chgMinutes(13.8, 22, 0), null); assert.strictEqual(F.chgMinutes(0, 22, 3.6), null);

// --- cost: energy + start fee + idle fee only when the unit is stated and the charge runs past the limit
const lp = (o = {}) => ({ kind: 'list', lo: 5, hi: 5, cur: 'SEK', start: null, idle: null, ...o });
let c = F.chgCost(lp(), 13.8, 230); near(c.lo, 69); near(c.hi, 69); assert.strictEqual(c.startIn, false);
c = F.chgCost(lp({ start: 10 }), 13.8, 230); near(c.lo, 79); assert.strictEqual(c.startIn, true);
c = F.chgCost(lp({ idle: { amount: 1, currency: 'SEK', unit: 'minute', after_min: 200 } }), 13.8, 230); near(c.lo, 99); assert.strictEqual(c.idleIn, true);   // 30 min over
c = F.chgCost(lp({ idle: { amount: 1, currency: 'SEK', unit: 'minute', after_min: 240 } }), 13.8, 230); near(c.lo, 69); assert.strictEqual(c.idleIn, false);  // under the limit
c = F.chgCost(lp({ idle: { amount: 50, currency: 'SEK', unit: 'session', after_min: 120 } }), 13.8, 230); near(c.lo, 119);
c = F.chgCost(lp({ idle: { amount: 2, currency: 'SEK', unit: 'unspecified', after_min: 120 } }), 13.8, 230); near(c.lo, 69);                                  // unit unknown: not added
c = F.chgCost(lp({ idle: { amount: 1, currency: 'EUR', unit: 'minute', after_min: 10 } }), 13.8, 230); near(c.lo, 69);                                          // other currency: not added
c = F.chgCost(lp({ idle: { amount: 1, currency: 'SEK', unit: 'minute', after_min: 10 } }), 13.8, null); near(c.lo, 69);                                         // no charging time known: no idle fee
c = F.chgCost(lp({ lo: 0.48, hi: 0.6, cur: 'EUR' }), 10, 170); near(c.lo, 4.8); near(c.hi, 6);
c = F.chgCost({ kind: 'own', lo: 3, hi: 3, cur: 'SEK', start: null, idle: null }, 13.8, 230); near(c.lo, 41.4);
c = F.chgCost({ kind: 'free' }, 13.8, 230); assert.strictEqual(c.free, true); assert.strictEqual(c.lo, 0);
assert.strictEqual(F.chgCost(lp(), 0, 60), null); assert.strictEqual(F.chgCost(lp(), undefined, 60), null);

// --- rank: known cost first (cheapest first), then free, then not published; ties by distance
const it = (id, eur, km, free) => ({ id, eur, km, free: !!free });
const r = F.chgRank([it('u1', null, 0.1), it('f', 0, 0.2, true), it('b', 80, 0.3), it('a', 40, 0.9), it('u0', null, 0.05), it('a2', 40, 0.4), it('f0', 0, 0.05, true)]);
assert.deepStrictEqual(r.map(x => x.id), ['a2', 'a', 'b', 'f0', 'f', 'u0', 'u1']);
assert.deepStrictEqual(F.chgRank([]), []);

// --- nearest: radius, order, max, bounding-box edge, high latitude
const ps = [{ lat: 55.600, lon: 13.000 }, { lat: 55.605, lon: 13.000 }, { lat: 55.620, lon: 13.000 }, { lat: 55.600, lon: 13.020 }, { lat: 55.610, lon: 13.0 }];
let n = F.chgNearest(ps, 55.6, 13.0, 2); assert.strictEqual(n.length, 4); assert.strictEqual(n[0].km, 0); near(n[1].km, 0.556, 0.01); assert.strictEqual(n.every((x, i) => !i || x.km >= n[i - 1].km), true);
assert.strictEqual(F.chgNearest(ps, 55.6, 13.0, 2, 2).length, 2); assert.strictEqual(F.chgNearest(ps, 55.6, 13.0, 0.3).length, 1); assert.strictEqual(F.chgNearest([], 55, 13, 2).length, 0); assert.strictEqual(F.chgNearest(undefined, 55, 13, 2).length, 0);
near(F.chgKm(55.6, 13.0, 55.6, 13.02), 1.27, 0.02);                                                                                      // 0.02 deg lon at 55.6 N
n = F.chgNearest([{ lat: 69.0, lon: 20.04 }], 69.0, 20.0, 2); assert.strictEqual(n.length, 1); near(n[0].km, 1.59, 0.03);                       // longitude shrinks with latitude

// --- kW groups, parking, tags, stale
assert.deepStrictEqual([0, 3.6, 7, 11, 22, 43].map(F.chgKwGroup), ['unk', 'low', 'low', 'mid', 'mid', 'high']);
assert.deepStrictEqual(F.chgKwCounts([{ kw: 0 }, { kw: 3 }, { kw: 11 }, { kw: 22 }, { kw: 50 }]), { low: 1, mid: 2, high: 1, unk: 1 });
assert.strictEqual(F.chgParking(128), 'yes'); assert.strictEqual(F.chgParking(16), 'hint'); assert.strictEqual(F.chgParking(144), 'yes'); assert.strictEqual(F.chgParking(1), 'none');
assert.deepStrictEqual(F.chgTags(1 | 2 | 64 | 16), ['free', 'card', 'tether']); assert.deepStrictEqual(F.chgTags(0), []);
assert.strictEqual(F.chgStale('2026-11-07', NOW), 0); assert.strictEqual(F.chgStale('2026-10-01', NOW), 50); assert.strictEqual(F.chgStale('', NOW), 0);

// --- wiring checks on the page source (the DOM code itself is exercised in the browser)
assert(/chgDecode\(j\)/.test(src) && /'ev_' \+ cc\.toLowerCase\(\) \+ '\.json'/.test(src), 'data file loader missing');
assert(!/NOBIL_API_KEY|OCM_API_KEY|X-API-Key/.test(src), 'a key name reached the page');
assert(/id="chip-chg"/.test(src) && /fetch\('ac_tariffs\.json'\)/.test(src) && !/AC_V/.test(src), 'tariff file must load without a hand-bumped version');
console.log('test_chargers: all passed');
