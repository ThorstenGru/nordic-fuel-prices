// Translations must carry exactly the placeholders and tags of the English text, or a sentence breaks at run time.  node tools/test_i18n.js
// A language may be missing keys (it falls back to English) but must never have a key English lacks, nor a different {placeholder} or <tag> set.
const assert = require('assert');
const { loadI18N } = require('./i18n_dump.js');
const I = loadI18N(), en = I.en;
const ph = s => (String(s).match(/\{[a-zA-Z0-9_]+\}/g) || []).sort().join(',');
const tg = s => (String(s).match(/<\/?[a-zA-Z][^>]*>/g) || []).map(t => t.replace(/\s.*$/, '').replace('>', '')).sort().join(',');
const ent = s => (String(s).match(/&[a-z#0-9]+;/g) || []).sort().join(',');
let bad = 0, n = 0;
for (const l of ['sv', 'de', 'fr', 'es']) {
  for (const [k, v] of Object.entries(I[l] || {})) {
    n++;
    if (!(k in en)) { console.error(`${l}.${k}: key not in English`); bad++; continue; }
    if (typeof v !== typeof en[k]) { console.error(`${l}.${k}: type differs`); bad++; continue; }
    if (typeof v !== 'string') continue;
    if (ph(v) !== ph(en[k])) { console.error(`${l}.${k}: placeholders ${ph(v)} != ${ph(en[k])}`); bad++; }
    if (tg(v) !== tg(en[k])) { console.error(`${l}.${k}: tags ${tg(v)} != ${tg(en[k])}`); bad++; }
    if (ent(v) !== ent(en[k])) { console.error(`${l}.${k}: entities differ`); bad++; }
    if (!v.trim()) { console.error(`${l}.${k}: empty`); bad++; }
  }
}
if (bad) { console.error(`${bad} translation problem(s)`); process.exit(1); }
console.log(`test_i18n: ok (${n} translated entries checked)`);
