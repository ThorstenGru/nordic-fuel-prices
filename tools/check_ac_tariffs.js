// Validates web/ac_tariffs.json and flags stale entries (> 90 days).  node tools/check_ac_tariffs.js [--today YYYY-MM-DD]
const fs = require('fs');
const f = JSON.parse(fs.readFileSync(__dirname + '/../web/ac_tariffs.json', 'utf8'));
const ai = process.argv.indexOf('--today');
const today = new Date(ai > 0 ? process.argv[ai + 1] : new Date().toISOString().slice(0, 10));
const errs = [], stale = [], ids = new Set();
const num = v => typeof v === 'number' && isFinite(v) && v >= 0;
const nn = v => v === null || num(v);
if (!Array.isArray(f.entries) || !f.entries.length) errs.push('entries missing');
for (const e of f.entries || []) {
  const w = m => errs.push(`${e.id || '?'}: ${m}`);
  for (const k of ['id', 'name', 'operator', 'notes', 'source', 'seen_on', 'confidence']) if (typeof e[k] !== 'string' || !e[k]) w(`missing ${k}`);
  if (ids.has(e.id)) w('duplicate id'); ids.add(e.id);
  if (e.check_operator !== true) w('check_operator must be true');
  if (!/^https?:\/\//.test(e.source || '')) w('source not a URL');
  if (!Array.isArray(e.countries) || !e.countries.length || e.countries.some(c => !/^[A-Z]{2}$/.test(c))) w('countries must be ISO-2 list');
  const m = e.match;
  if (!m || !Array.isArray(m.ocm_names) || !m.ocm_names.length || !Array.isArray(m.nobil_names)) w('match.ocm_names (non-empty) / nobil_names missing');
  const a = e.ac;
  if (a !== null) {
    if (!a || typeof a !== 'object') w('ac must be object or null');
    else {
      if (typeof a.currency !== 'string' || !a.currency) w('ac.currency');
      if (!nn(a.adhoc_kwh) || !nn(a.adhoc_kwh_max) || !nn(a.member_kwh) || !nn(a.start_fee)) w('bad ac number');
      if (a.adhoc_kwh === null && a.member_kwh === null) w('ac has no figures, use null');
      if (num(a.adhoc_kwh) && num(a.adhoc_kwh_max) && a.adhoc_kwh > a.adhoc_kwh_max) w('adhoc min > max');
      if (a.member_kwh !== null && typeof a.member_label !== 'string') w('member_kwh needs member_label');
      if (typeof a.basis !== 'string' || !a.basis) w('ac.basis missing');
      if (typeof a.subscription_needed_for_member !== 'boolean') w('subscription_needed_for_member boolean');
      if (![true, false, null].includes(a.app_required_adhoc)) w('app_required_adhoc true/false/null');
      const i = a.idle_fee;
      if (i !== null && !(i && num(i.amount) && i.currency === a.currency && typeof i.unit === 'string' && typeof i.label === 'string')) w('idle_fee needs amount, same currency, unit, label');
    }
    if (/not read|no body|not recorded/.test(e.confidence)) w('price given but confidence says not read');
  }
  const d = new Date(e.seen_on);
  if (isNaN(d)) w('bad seen_on'); else {
    if (d > today) w('seen_on in the future');
    const age = Math.floor((today - d) / 864e5);
    if (age > 90) stale.push(`${e.id}: ${age} days old`);
  }
}
if (stale.length) console.log('STALE (grey out, refresh):\n  ' + stale.join('\n  '));
if (errs.length) { console.error('AC_TARIFFS INVALID:\n  ' + errs.join('\n  ')); process.exit(1); }
console.log(`ac_tariffs.json ok: ${f.entries.length} entries, ${f.entries.filter(e => e.ac).length} priced, ${stale.length} stale`);
