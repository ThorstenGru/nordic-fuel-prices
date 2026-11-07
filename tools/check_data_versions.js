// web/vehicles.json and web/fares.json are fetched as ?v=<N> and the service worker serves a versioned URL cache-first, so an edit without a
// bump never reaches returning visitors. index.html records a content hash next to each version constant; this check fails when they differ.
// The hash is taken over the text with LF line endings, so a Windows checkout (CRLF) and CI (LF) agree.
//   node tools/check_data_versions.js         check (CI)
//   node tools/check_data_versions.js --fix   after editing a data file: bump the version and record the new hash
const fs = require('fs'), crypto = require('crypto'), path = require('path');
const root = path.join(__dirname, '..', 'web'), fix = process.argv.includes('--fix');
const hashOf = file => crypto.createHash('sha256').update(fs.readFileSync(path.join(root, file), 'utf8').split('\r\n').join('\n')).digest('hex').slice(0, 10);
let html = fs.readFileSync(path.join(root, 'index.html'), 'utf8'), bad = 0, changed = false;
for (const [file, konst] of [['vehicles.json', 'VEH_V'], ['fares.json', 'FARES_V']]) {
  const hash = hashOf(file);
  const re = new RegExp(`(const ${konst} = )(\\d+)(;\\s*// data-hash:${file.replace('.', '\\.')}=)([0-9a-f]{10})`);
  const m = html.match(re);
  if (!m) { console.error(`${konst}: no "data-hash:${file}=" marker next to the constant in index.html`); bad++; continue; }
  if (m[4] === hash) continue;
  if (fix) { html = html.replace(re, `$1${+m[2] + 1}$3${hash}`); changed = true; console.log(`${file}: ${konst} ${m[2]} -> ${+m[2] + 1}`); }
  else { console.error(`${file} changed (hash ${m[4]} -> ${hash}) but ${konst} was not bumped. Run: node tools/check_data_versions.js --fix`); bad++; }
}
if (changed) fs.writeFileSync(path.join(root, 'index.html'), html);
if (bad) process.exit(1);
console.log('data versions ok');
