// Tests for the home-tariff and price-outlook functions in web/index.html (between TF-PURE-BEGIN and TF-PURE-END).  node tools/test_tariff.js
const fs = require('fs'), assert = require('assert');
const src = fs.readFileSync(__dirname + '/../web/index.html', 'utf8');
const m = src.match(/\/\/ TF-PURE-BEGIN[^\n]*\n([\s\S]*?)\/\/ TF-PURE-END/); assert(m, 'pure block not found');
const { TF_DEFAULT, tfClean, tfFixedKwh, tfMarginal, tfSpotFor, tfMonthlyFee, tfAllIn, elHourly, elCheap, elOutlook, elLastMonth } =
  new Function(m[1] + '; return { TF_DEFAULT, tfClean, tfFixedKwh, tfMarginal, tfSpotFor, tfMonthlyFee, tfAllIn, elHourly, elCheap, elOutlook, elLastMonth };')();
const near = (a, b, e = 1e-9) => assert(Math.abs(a - b) <= e, `${a} != ${b}`);

// Owner formula: marginal inc VAT = (spot + variable) * 1.25 + 0.773 (markup and discount cancel, transfer 0.2584 + tax 0.36 = 0.6184 ex VAT)
near(tfFixedKwh(TF_DEFAULT), 0.773, 1e-9);
near(tfMarginal(TF_DEFAULT, 1.20202), (1.20202 + 0.07) * 1.25 + 0.773);
near(tfMarginal(TF_DEFAULT, 1.20202), 2.3628, 0.0005);                     // Sep 2026 invoice month
near(tfMarginal(TF_DEFAULT, -0.05), (0.02) * 1.25 + 0.773);                // negative spot still works
// inverse
near(tfSpotFor(TF_DEFAULT, tfMarginal(TF_DEFAULT, 0.77)), 0.77);
// monthly fees: (0 + 656) * 1.25 = 820; all-in average at 500 kWh adds 1.64 per kWh
near(tfMonthlyFee(TF_DEFAULT), 820); near(tfAllIn(TF_DEFAULT, 1, 500), tfMarginal(TF_DEFAULT, 1) + 1.64);
assert.strictEqual(tfAllIn(TF_DEFAULT, 1, 0), null);
// discount and markup are separate fields: dropping the discount (after 2027-05-31) raises the price by 0.06 * 1.25
near(tfMarginal({ ...TF_DEFAULT, discount: 0 }, 1) - tfMarginal(TF_DEFAULT, 1), 0.075);
// cleaning: junk falls back to the default, VAT above 100 and zero kWh are refused, area must look like SE4
let c = tfClean({ varCost: 'x', markup: -1, vat: 300, kwh: 0, area: 'se4', transfer: '0.30', tax: 0 });
near(c.varCost, 0.07); near(c.markup, 0.06); near(c.vat, 25); near(c.kwh, 500); assert.strictEqual(c.area, 'SE4'); near(c.transfer, 0.3); near(c.tax, 0);
assert.deepStrictEqual(tfClean(null), TF_DEFAULT); assert.strictEqual(tfClean({ area: 'SE2' }).area, 'SE2');

// day arrays: 96 quarter hours -> 24 hours; 24 stay; junk -> null
const q = []; for (let h = 0; h < 24; h++) for (let k = 0; k < 4; k++) q.push(h + k * 0.1);
const hr = elHourly(q); assert.strictEqual(hr.length, 24); near(hr[5], 5.15); assert.strictEqual(elHourly([1, 2, NaN]), null); assert.strictEqual(elHourly([]), null);
assert.strictEqual(elHourly(Array(23).fill(1)).length, 23);                   // DST day left as it is
// cheapest window: not before 'from', never beyond the day
const d = [5, 4, 1, 1, 9, 9, 0.5, 8]; let w = elCheap(d, 2); assert.strictEqual(w.start, 2); near(w.mean, 1);
w = elCheap(d, 2, 5); assert.strictEqual(w.start, 6); assert.strictEqual(elCheap(d, 2, 7), null); assert.strictEqual(elCheap(d, 9), null);

// outlook: from the pipeline's seasonal block, n months from the current one, with year rollover; months without history are null
const sn = { 11: { mean: 3, lo: 2, hi: 4, n: 4 }, 12: { mean: 2, lo: 1, hi: 4, n: 4 }, 1: { mean: 1, lo: 1, hi: 1, n: 1 }, 10: { mean: 0.9, lo: 0.5, hi: 1.3, n: 4 }, 5: { mean: null, lo: 1, hi: 2, n: 3 } };
let o = elOutlook(sn, '2026-11', 12);
assert.strictEqual(o.length, 12); assert.strictEqual(o[0].ym, '2026-11'); assert.strictEqual(o[1].ym, '2026-12'); assert.strictEqual(o[2].ym, '2027-01'); assert.strictEqual(o[11].ym, '2027-10');
assert.strictEqual(o[0].n, 4); near(o[0].mean, 3); near(o[0].low, 2); near(o[0].high, 4);
near(o[1].mean, 2); assert.strictEqual(o[2].n, 1);
assert.strictEqual(o[3].n, 0); assert.strictEqual(o[3].mean, null); assert.strictEqual(o[3].low, null);   // February: no history, honest null
assert.strictEqual(o[6].mean, null);                                                                     // a broken entry (null mean) is no data too
near(o[11].mean, 0.9);
assert.strictEqual(elOutlook({}, '2026-12', 2)[1].ym, '2027-01'); assert.strictEqual(elOutlook(null, '2026-12', 1)[0].mean, null);
// the band goes through the tariff in the same order: low < mean < high
assert(tfMarginal(TF_DEFAULT, o[0].low) < tfMarginal(TF_DEFAULT, o[0].mean) && tfMarginal(TF_DEFAULT, o[0].mean) < tfMarginal(TF_DEFAULT, o[0].high));

// latest complete month: skips null and the partial month, walks back over years
const mo = { '2025': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], '2026': [1, 2, 3, 4, 5, 6, 7, 8, 9, 1.5, 3, null] };
assert.deepStrictEqual(elLastMonth(mo, { month: '2026-11', days: 6 }), { ym: '2026-10', v: 1.5 });
assert.deepStrictEqual(elLastMonth(mo, null), { ym: '2026-11', v: 3 });
assert.deepStrictEqual(elLastMonth({ '2025': [null, 5, null] , '2026': [null, null] }, null), { ym: '2025-02', v: 5 });
assert.strictEqual(elLastMonth({}, null), null); assert.strictEqual(elLastMonth(undefined, null), null);
// expiry 2027-05-31: month granularity, May 2027 still discounted, June 2027 not; retail fee 39.20 comes back with VAT
near(tfMarginal(TF_DEFAULT, 1, '2027-05') , tfMarginal(TF_DEFAULT, 1)); near(tfMarginal(TF_DEFAULT, 1, '2027-06') - tfMarginal(TF_DEFAULT, 1, '2027-05'), 0.075);
near(tfMonthlyFee(TF_DEFAULT, '2027-05'), 820); near(tfMonthlyFee(TF_DEFAULT, '2027-06'), (39.2 + 656) * 1.25);
near(tfSpotFor(TF_DEFAULT, tfMarginal(TF_DEFAULT, 0.77, '2027-07'), '2027-07'), 0.77);
near(tfMarginal({ ...TF_DEFAULT, discUntil: '' }, 1, '2030-01'), tfMarginal(TF_DEFAULT, 1));   // empty end date = never ends
assert.strictEqual(tfClean({ discUntil: 'junk' }).discUntil, '2027-05-31'); assert.strictEqual(tfClean({ discUntil: '' }).discUntil, ''); assert.strictEqual(tfClean({ feeUntil: '2028-02-29' }).feeUntil, '2028-02-29');
// current month partly known: 6 of 30 days at 3.0 blended with seasonal 1.0 (band 0.5-1.5) -> weight 0.2
o = elOutlook({ 11: { mean: 1, lo: 0.5, hi: 1.5, n: 3 }, 12: { mean: 2, lo: 1, hi: 3, n: 3 } }, '2026-11', 2, { ym: '2026-11', mean: 3, days: 6 });
near(o[0].mean, 0.2 * 3 + 0.8 * 1); near(o[0].low, 0.6 + 0.4); near(o[0].high, 0.6 + 1.2); assert.strictEqual(o[0].known, 6); assert.strictEqual(o[0].dim, 30); near(o[1].mean, 2); assert.strictEqual(o[1].known, undefined);
near(elOutlook({ 11: { mean: 1, lo: 1, hi: 1, n: 1 } }, '2026-11', 1, { ym: '2026-10', mean: 9, days: 5 })[0].mean, 1);   // partial for another month: ignored
console.log('tariff: all tests passed');
