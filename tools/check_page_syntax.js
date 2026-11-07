// Syntax check of every inline <script> in the shipped pages (a broken index.html would otherwise deploy as a blank map).  node tools/check_page_syntax.js
const fs = require('fs'), vm = require('vm'), path = require('path');
let bad = 0, n = 0;
for (const f of ['index.html', 'about.html', 'admin.html']) {
  const html = fs.readFileSync(path.join(__dirname, '..', 'web', f), 'utf8').replace(/<!--[\s\S]*?-->/g, '');   // comments may mention <script>
  for (const m of html.matchAll(/<script(?![^>]*\bsrc=)([^>]*)>([\s\S]*?)<\/script>/g)) {
    if (/type=["']?(application\/ld\+json|module)/.test(m[1]) || !m[2].trim()) continue;
    n++;
    try { new vm.Script(m[2], { filename: f }); } catch (e) { bad++; console.error(`${f}: ${e.message}`); }
  }
}
if (bad) { console.error(`${bad} inline script(s) do not parse`); process.exit(1); }
console.log(`page syntax ok: ${n} inline scripts`);
