// Add translations to web/index.html as one Object.assign(I18N.<lang>, {...}) block placed just before 'let lang = (function'.
//   node tools/i18n_apply.js <de|fr|es> <translations.json> --check    validate only
//   node tools/i18n_apply.js <de|fr|es> <translations.json>            validate and write (replaces an earlier block with the same marker)
// The JSON is {key: translated text}. Only keys that exist in English and are still missing in that language are written.
const fs = require('fs'), path = require('path');
const { loadI18N } = require('./i18n_dump.js');
const [lang, file] = [process.argv[2], process.argv[3]], check = process.argv.includes('--check');
if (!['de', 'fr', 'es'].includes(lang) || !file) { console.error('usage: node tools/i18n_apply.js <de|fr|es> <file.json> [--check]'); process.exit(2); }
const pHtml = path.join(__dirname, '..', 'web', 'index.html'), rawHtml = fs.readFileSync(pHtml, 'utf8');
const markerRe = new RegExp(String.raw`// I18N-${lang.toUpperCase()}-AUTO-BEGIN[\s\S]*?// I18N-${lang.toUpperCase()}-AUTO-END
`);
const tr = JSON.parse(fs.readFileSync(file, 'utf8')), I = loadI18N(rawHtml.replace(markerRe, '')), en = I.en, have = I[lang] || {};   // an earlier auto block does not count as translated: it is replaced
const ph = s => (String(s).match(/\{[a-zA-Z0-9_]+\}/g) || []).sort().join(','), tg = s => (String(s).match(/<\/?[a-zA-Z][^>]*>/g) || []).map(t => t.replace(/\s.*$/, '').replace('>', '')).sort().join(','), ent = s => (String(s).match(/&[a-z#0-9]+;/g) || []).sort().join(',');
const out = {}, problems = []; let skipped = 0;
for (const [k, v] of Object.entries(tr)) {
  if (!(k in en)) { problems.push(`${k}: not an English key`); continue; }
  if (k in have && !(have[k] === en[k])) { skipped++; continue; }          // already translated
  if (typeof v !== 'string' || !v.trim()) { problems.push(`${k}: empty or not text`); continue; }
  if (ph(v) !== ph(en[k])) problems.push(`${k}: placeholders [${ph(v)}] but English has [${ph(en[k])}]`);
  if (tg(v) !== tg(en[k])) problems.push(`${k}: tags [${tg(v)}] but English has [${tg(en[k])}]`);
  if (ent(v) !== ent(en[k])) problems.push(`${k}: entities [${ent(v)}] but English has [${ent(en[k])}]`);
  out[k] = v;
}
const missing = Object.keys(en).filter(k => !(k in have) && !(k in out));
console.log(`${lang}: ${Object.keys(out).length} to write, ${skipped} already translated, ${missing.length} English keys still without text`);
if (problems.length) { console.error(problems.slice(0, 60).join('\n')); console.error(`${problems.length} problem(s)`); process.exit(1); }
if (missing.length) console.log('still missing (first 20): ' + missing.slice(0, 20).join(', '));
if (check) process.exit(0);
const p = path.join(__dirname, '..', 'web', 'index.html');
let html = fs.readFileSync(p, 'utf8');
const marker = `// I18N-${lang.toUpperCase()}-AUTO`;
const block = `${marker}-BEGIN (tools/i18n_apply.js)\nObject.assign(I18N.${lang}, ${JSON.stringify(out, null, 1).replace(/<\/script/gi, '<\\/script')});\n${marker}-END\n`;
const re = new RegExp(`${marker}-BEGIN[\\s\\S]*?${marker}-END\\n`);
if (re.test(html)) html = html.replace(re, () => block);
else {
  const anchor = 'let lang = (function';
  const i = html.indexOf(anchor); if (i < 0) { console.error('anchor not found'); process.exit(1); }
  html = html.slice(0, i) + block + html.slice(i);
}
fs.writeFileSync(p, html);
console.log('written');
