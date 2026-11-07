// Text keys per language: which keys exist in English but have no text in sv / de / fr / es (they fall back to English).
//   node tools/i18n_dump.js                 summary
//   node tools/i18n_dump.js --missing de    JSON {key: english text} of the keys German is missing
// It runs the page script from the I18N declaration on, with a stub for the browser, so it needs no browser.
const fs = require('fs'), vm = require('vm'), path = require('path');

function loadI18N(rawHtml) {
  const html = (rawHtml || fs.readFileSync(path.join(__dirname, '..', 'web', 'index.html'), 'utf8')).replace(/<!--[\s\S]*?-->/g, '');
  const scripts = [...html.matchAll(/<script(?![^>]*\bsrc=)([^>]*)>([\s\S]*?)<\/script>/g)].filter(m => !/ld\+json|module/.test(m[1])).map(m => m[2]);
  const main = scripts.reduce((a, b) => (b.length > a.length ? b : a), '');
  const i = main.indexOf('const I18N');
  if (i < 0) throw new Error('const I18N not found');
  const stub = new Proxy(function () {}, { get: (_, k) => (k === Symbol.toPrimitive ? () => '' : stub), apply: () => stub, construct: () => stub });
  const ctx = vm.createContext({ document: stub, window: stub, localStorage: { getItem: () => null, setItem() {} }, navigator: { language: 'en' }, console, setTimeout, store: { get: (k, d) => d, set() {} } });
  try { vm.runInContext(main.slice(i), ctx, { timeout: 5000 }); } catch (e) { /* the script goes on into DOM code; I18N is already built by then */ }
  try { return vm.runInContext('I18N', ctx); } catch (e) { throw new Error('could not build I18N: ' + e.message); }
}
module.exports = { loadI18N };

if (require.main === module) {
  const out = loadI18N(), en = out.en, langs = ['sv', 'de', 'fr', 'es'];
  const missing = l => Object.keys(en).filter(k => !(k in (out[l] || {})));
  if (process.argv[2] === '--missing') {
    const l = process.argv[3], r = {}; for (const k of missing(l)) r[k] = en[k];
    console.log(JSON.stringify(r, null, 1));
  } else {
    console.log('en keys:', Object.keys(en).length);
    for (const l of langs) console.log(l, 'has', Object.keys(out[l] || {}).length, 'missing', missing(l).length);
  }
}
