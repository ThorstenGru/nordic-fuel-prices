// Validates web/fares.json and flags stale entries (> 90 days).  node tools/check_fares.js [--today YYYY-MM-DD]
const fs = require('fs');
const f = JSON.parse(fs.readFileSync(__dirname + '/../web/fares.json', 'utf8'));
const ai = process.argv.indexOf('--today');
const today = new Date(ai > 0 ? process.argv[ai + 1] : new Date().toISOString().slice(0, 10));
const KINDS = ['bridge', 'ferry', 'tunnel', 'vignette', 'toll-note'];
const errs = [], stale = [], ids = new Set();
const num = v => typeof v === 'number' && isFinite(v);
if (!Array.isArray(f.entries) || !f.entries.length) errs.push('entries missing');
for (const e of f.entries || []) {
  const w = m => errs.push(`${e.id || '?'}: ${m}`);
  for (const k of ['id', 'name', 'kind', 'conditions', 'source', 'seen_on', 'confidence']) if (typeof e[k] !== 'string' || !e[k]) w(`missing ${k}`);
  if (ids.has(e.id)) w('duplicate id'); ids.add(e.id);
  if (!KINDS.includes(e.kind)) w('bad kind ' + e.kind);
  if (e.check_operator !== true) w('check_operator must be true');
  if (!/^https?:\/\//.test(e.source || '')) w('source not a URL');
  if (!Array.isArray(e.countries) || !e.countries.length) w('countries missing');
  const m = e.match;
  if (!m || !Array.isArray(m.names) || !Array.isArray(m.endpoints)) w('match.names/endpoints missing');
  else for (const p of m.endpoints) if (!(Array.isArray(p) && num(p[0]) && num(p[1]) && Math.abs(p[0]) <= 90 && Math.abs(p[1]) <= 180)) w('bad endpoint');
  if (e.price !== null) {
    const p = e.price;
    if (!p || typeof p.currency !== 'string') w('price needs currency');
    else {
      if (p.min !== null && !num(p.min)) w('price.min'); if (p.max !== null && !num(p.max)) w('price.max');
      if (num(p.min) && num(p.max) && p.min > p.max) w('min > max');
      if (p.min === null && p.max === null) w('price has no figures, use null');
    }
    if (/not read|unconfirmed/.test(e.confidence)) w('price given but confidence says not read or unconfirmed');
    const tp = e.trip_price;
    if (tp === undefined) w('priced entry needs trip_price (a figure or null): min..max mixes products');
    else if (tp !== null && !(num(tp.amount) && tp.currency === p.currency && typeof tp.basis === 'string' && tp.basis)) w('trip_price needs amount, same currency and basis');
    else if (tp && ((num(p.min) && tp.amount < p.min) || (num(p.max) && tp.amount > p.max))) w('trip_price outside min..max');
  }
  const d = new Date(e.seen_on);
  if (isNaN(d)) w('bad seen_on'); else {
    if (d > today) w('seen_on in the future');
    const age = Math.floor((today - d) / 864e5);
    if (age > 90) stale.push(`${e.id}: ${age} days old`);
  }
}
if (stale.length) console.log('STALE (grey out, refresh):\n  ' + stale.join('\n  '));
if (errs.length) { console.error('FARES INVALID:\n  ' + errs.join('\n  ')); process.exit(1); }
console.log(`fares.json ok: ${f.entries.length} entries, ${f.entries.filter(e => e.price).length} priced, ${stale.length} stale`);
