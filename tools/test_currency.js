// Tests for the pure currency functions in web/index.html (between CUR-PURE-BEGIN and CUR-PURE-END).  node tools/test_currency.js
const fs = require('fs'), assert = require('assert');
const src = fs.readFileSync(__dirname + '/../web/index.html', 'utf8');
const m = src.match(/\/\/ CUR-PURE-BEGIN[^\n]*\n([\s\S]*?)\/\/ CUR-PURE-END/); assert(m, 'pure block not found');
const { cardClamp, curPerEur, toEur, curShow, curDec } = new Function(m[1] + '; return { cardClamp, curPerEur, toEur, curShow, curDec };')();
const near = (a, b, e = 1e-9) => assert(Math.abs(a - b) <= e, `${a} != ${b}`);
const R = { SEK: 10.99, PLN: 4.2, CHF: 0.93, CZK: 24.3 };

// ECB: units per EUR; 15.43 SEK -> about 1.40 EUR
near(toEur(15.43, 'SEK', R, 0), 15.43 / 10.99); near(toEur(15.43, 'SEK', R, 0), 1.404, 0.001);
near(toEur(6.09, 'PLN', R, 0), 1.45, 0.001);
// card surcharge applies to foreign currencies only, never to EUR
near(toEur(15.43, 'SEK', R, 2), 15.43 / 10.99 * 1.02);
assert.strictEqual(toEur(1.65, 'EUR', R, 5), 1.65);
// missing rate -> null, never a guess
assert.strictEqual(toEur(1, 'ISK', R, 0), null); assert.strictEqual(curPerEur(null, 'SEK'), null); assert.strictEqual(curPerEur(R, 'EUR'), 1);
assert.strictEqual(curPerEur({ SEK: 0 }, 'SEK'), null); assert.strictEqual(curPerEur({ SEK: -3 }, 'SEK'), null);
// card input is clamped and tolerant: comma decimals, junk, negatives, huge
assert.strictEqual(cardClamp('1,5'), 1.5); assert.strictEqual(cardClamp('abc'), 0); assert.strictEqual(cardClamp(-2), 0);
assert.strictEqual(cardClamp(99), 10); assert.strictEqual(cardClamp(''), 0); assert.strictEqual(cardClamp(null), 0);
// Local | EUR switch
assert.deepStrictEqual(curShow(15.43, 'SEK', 'local', R, 2), { v: 15.43, cur: 'SEK' });
let s = curShow(15.43, 'SEK', 'eur', R, 0); assert.strictEqual(s.cur, 'EUR'); near(s.v, 1.404, 0.001);
assert.deepStrictEqual(curShow(1.65, 'EUR', 'eur', R, 3), { v: 1.65, cur: 'EUR' });      // euro countries unchanged in both modes
assert.deepStrictEqual(curShow(1.65, 'EUR', 'local', R, 3), { v: 1.65, cur: 'EUR' });
assert.deepStrictEqual(curShow(100, 'ISK', 'eur', R, 0), { v: 100, cur: 'ISK' });         // no rate: stays local and says so
// ranking in EUR puts a cheap-looking big number where it belongs: 620 HUF/L is not dearer than 15 SEK/L
const H = { ...R, HUF: 395 };
assert(toEur(620, 'HUF', H, 0) < toEur(15.43, 'SEK', H, 0) * 1.2);
// decimals: pumps price EUR/GBP in 3 decimals natively; converted amounts and other currencies 2
assert.strictEqual(curDec('EUR', true), 3); assert.strictEqual(curDec('GBP', true), 3); assert.strictEqual(curDec('EUR', false), 2); assert.strictEqual(curDec('SEK', true), 2);

// trip currency: one currency for the whole trip: the one most countries use (tie: the start country); unknown rate or EUR switch -> EUR
{ const m2 = src.match(/\/\/ CURTRIP-PURE-BEGIN[^\n]*\n([\s\S]*?)\/\/ CURTRIP-PURE-END/); assert(m2, 'curtrip block not found');
  const curForTrip = new Function(m2[1] + '; return curForTrip;')();
  const cur = { SE: 'SEK', DK: 'DKK', DE: 'EUR', PL: 'PLN' }, f = (ccs, mode = 'local', ok = () => true) => curForTrip(ccs, c => cur[c], mode, ok);
  assert.strictEqual(f(['SE']), 'SEK'); assert.strictEqual(f(['SE', 'SE']), 'SEK'); assert.strictEqual(f(['DE']), 'EUR');
  assert.strictEqual(f(['SE', 'DK']), 'SEK'); assert.strictEqual(f(['DK', 'SE']), 'DKK'); assert.strictEqual(f(['SE', 'DE']), 'SEK'); assert.strictEqual(f(['DE', 'DK', 'DK']), 'DKK'); assert.strictEqual(f([]), 'EUR');
  assert.strictEqual(f(['SE'], 'eur'), 'EUR'); assert.strictEqual(f(['PL'], 'local', () => false), 'EUR'); }
console.log('test_currency: ok');
