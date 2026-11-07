// Tests for the plan-as-a-link functions in web/index.html (SH-PURE block): round trip of every field, versions, damaged links, limits.  node tools/test_share.js
const fs = require('fs'), assert = require('assert');
const src = fs.readFileSync(__dirname + '/../web/index.html', 'utf8');
const m = src.match(/\/\/ SH-PURE-BEGIN[^\n]*\n([\s\S]*?)\/\/ SH-PURE-END/); assert(m, 'pure block not found');
const F = new Function(m[1] + '; return { shNorm, shEncode, shDecode, SH_MAX, SH_VER };')();

const full = { f: { la: 55.6049, lo: 13.0038, n: 'Malmö, Sweden' }, t: { la: 53.5511, lo: 9.9937, n: 'Hamburg Hbf' }, w: 5, k: 'D', fp: 50, bp: 0, r: 7.5, s: 110, v: 40, d: 1, h: 1, a: { p: 3.5, c: 'SEK' } };
const rt = s => { const h = F.shEncode(s); assert(h, 'encodes'); const d = F.shDecode(h); assert.strictEqual(d.st, 'ok'); return d.state; };

// every assumption field survives the round trip (ABRP's shared links lost them)
assert.deepStrictEqual(rt(full), full);
for (const [k, v] of Object.entries({ w: 2, k: 'P', fp: 25, bp: 100, r: null, s: null, v: 0, d: 0, h: 0, a: null })) assert.deepStrictEqual(rt({ ...full, [k]: v })[k], v, k);
assert.deepStrictEqual(rt({ ...full, r: 0 }).r, 0);                                   // zero reserve is not 'default'
assert.deepStrictEqual(rt({ ...full, bp: 0, fp: 0 }), { ...full, bp: 0, fp: 0 });
for (const w of [2, 3, 5]) assert.strictEqual(rt({ ...full, w }).w, w);
for (const k of ['P', 'D']) assert.strictEqual(rt({ ...full, k }).k, k);
for (const s of [null, 90, 110, 130]) assert.strictEqual(rt({ ...full, s }).s, s);
for (const a of [null, { p: 0.25, c: 'EUR' }, { p: 12.9, c: 'DKK' }]) assert.deepStrictEqual(rt({ ...full, a }).a, a);
// non-ASCII names, quotes and emoji-free unicode survive; the link itself is ASCII only and short
const odd = { ...full, f: { la: -33.8688, lo: 151.2093, n: 'Tåby "Å" & Ö ü / ñ 東京' } };
assert.deepStrictEqual(rt(odd), odd);
const h = F.shEncode(full); assert(/^#p1=[A-Za-z0-9_-]+$/.test(h)); assert(h.length < 400, h.length);
assert(/^#p1=[\x21-\x7e]+$/.test(F.shEncode(odd)));
// coordinates are rounded to 4 decimals (about 11 m)
assert.strictEqual(rt({ ...full, f: { la: 55.604912345, lo: 13.003876, n: 'x' } }).f.la, 55.6049);
// empty name -> the coordinates as text (the planner needs a non-empty name)
assert.strictEqual(rt({ ...full, t: { la: 1, lo: 2, n: '  ' } }).t.n, '1, 2');
// name capped at 80 characters, control characters removed
assert.strictEqual(rt({ ...full, t: { la: 1, lo: 2, n: 'a'.repeat(300) } }).t.n.length, 80);
assert.strictEqual(rt({ ...full, t: { la: 1, lo: 2, n: 'a\nb\u0000c' } }).t.n, 'a b c');
// a longest-case link stays within the cap
assert(F.shEncode({ ...full, f: { la: 1, lo: 2, n: '東'.repeat(200) }, t: { la: 1, lo: 2, n: '東'.repeat(200) } }).length <= F.SH_MAX);

// decoding works with or without the leading '#', and the hash of other features is left alone
assert.strictEqual(F.shDecode(h.slice(1)).st, 'ok');
for (const x of ['', '#', '#stations', '#pump', '#p1x', '#page=2', '#about', null, undefined, 42]) assert.strictEqual(F.shDecode(x).st, 'none', String(x));

// unknown versions: a status, not an exception
assert.deepStrictEqual(F.shDecode('#p2=' + h.slice(4)), { st: 'ver', v: 2 });
assert.deepStrictEqual(F.shDecode('#p0=abc'), { st: 'ver', v: 0 });
assert.deepStrictEqual(F.shDecode('#p99='), { st: 'ver', v: 99 });

// damaged links
const bad = ['#p1', '#p1=', '#p1=!!!', '#p1=a', '#p1=AAAA', '#p1=' + h.slice(4, 30), '#p1=' + h.slice(4) + '%00', '#p1=' + 'A'.repeat(F.SH_MAX + 1), '#p1=' + h.slice(4) + '&x=1', '#p1=%E2%82', '#p1=/+/+',
  '#p1=' + Buffer.from('null').toString('base64url'), '#p1=' + Buffer.from('[]').toString('base64url'), '#p1=' + Buffer.from('{}').toString('base64url'), '#p1=' + Buffer.from('{"f":1}').toString('base64url'),
  '#p1=' + Buffer.from([0xff, 0xfe, 0xfd]).toString('base64url')];                // invalid UTF-8
for (const x of bad) assert.strictEqual(F.shDecode(x).st, 'bad', x.slice(0, 40));
// out-of-range or wrong-typed fields are damage, never clamped silently
const enc = o => '#p1=' + Buffer.from(JSON.stringify(o)).toString('base64url');
const j = { f: full.f, t: full.t, w: 3, k: 'P', fp: 50, bp: 50, v: 0 };
assert.strictEqual(F.shDecode(enc(j)).st, 'ok');
for (const o of [{ w: 4 }, { k: 'X' }, { fp: 101 }, { fp: -1 }, { fp: '50' }, { bp: null }, { v: 5000 }, { r: 500 }, { r: 'x' }, { s: 10 }, { s: 999 }, { a: { p: 1, c: 'sek' } }, { a: { p: -1, c: 'SEK' } }, { a: { p: 1 } }, { a: 5 },
  { f: { la: 91, lo: 0, n: 'x' } }, { t: { la: 0, lo: 181, n: 'x' } }, { f: null }, { t: { la: 'a', lo: 0, n: 'x' } }]) assert.strictEqual(F.shDecode(enc({ ...j, ...o })).st, 'bad', JSON.stringify(o));
// unknown extra fields are ignored (forward compatible within a version)
assert.deepStrictEqual(Object.keys(F.shDecode(enc({ ...j, zzz: 1 })).state).sort(), Object.keys(F.shNorm(j)).sort());
// a missing optional field is the default
assert.deepStrictEqual(F.shDecode(enc(j)).state, { ...F.shNorm(j), r: null, s: null, d: 0, h: 0, a: null });
// encoding an invalid state gives null, never a half link
assert.strictEqual(F.shEncode({ ...full, w: 9 }), null); assert.strictEqual(F.shEncode(null), null); assert.strictEqual(F.shEncode({}), null);
// the link never carries fields outside the allowed list (home tariff, car profile ...)
const leak = F.shEncode({ ...full, elec: 1.23, home: 'Storgatan 1', car: { cons: 7 } });
assert.deepStrictEqual(Object.keys(JSON.parse(Buffer.from(leak.slice(4), 'base64url').toString())).sort(), ['a', 'bp', 'd', 'f', 'fp', 'h', 'k', 'r', 's', 't', 'v', 'w']);
console.log('test_share: all passed');
