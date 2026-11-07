"""Structural checks on the cached live data (what the frontend relies on). Read-only."""
import json, os, re, sys, glob, collections, statistics as S
from datetime import datetime, timezone

D = sys.argv[1]
meta = json.load(open(os.path.join(D, 'meta.json'), encoding='utf-8'))
now = datetime.fromisoformat(meta['fetched_at'])
# frontend BBOX table, copied from web/index.html (stations outside it are skipped when the view does not touch the box)
src = open(sys.argv[2], encoding='utf-8').read()
bb = {}
for m in re.finditer(r"([A-Z]{2}):\[\[(-?[\d.]+),(-?[\d.]+)\],\[(-?[\d.]+),(-?[\d.]+)\]\]", src[src.index('const BBOX'):src.index('const CB')]):
    bb[m.group(1)] = tuple(map(float, m.groups()[1:]))

allst, ids = [], collections.Counter()
rows = []
for c in meta['countries']:
    cc = c['country']
    d = json.load(open(os.path.join(D, cc.lower() + '.json'), encoding='utf-8'))
    st = d['stations']
    b = bb.get(cc)
    n = len(st); priced = sum(1 for s in st if s.get('prices'))
    bad_pref = sum(1 for s in st if str(s['id'])[:2].upper() != cc)
    nolat = sum(1 for s in st if not s.get('lat') or not s.get('lon'))
    outbox = 0
    if b:
        for s in st:
            la, lo = s.get('lat'), s.get('lon')
            if la and lo and not (b[0] <= la <= b[2] and b[1] <= lo <= b[3]):
                outbox += 1
    swapped = sum(1 for s in st if s.get('lat') and s.get('lon') and abs(s['lat']) > 90)
    nonnum = nonpos = naive_ts = future_ts = old36 = tot_ts = 0
    cur = collections.Counter(); unit = collections.Counter(); ft = collections.Counter()
    for s in st:
        ids[s['id']] += 1
        for p in s.get('prices', []):
            cur[p.get('currency')] += 1; unit[p.get('unit')] += 1; ft[p.get('fuel_type')] += 1
            v = p.get('price')
            if not isinstance(v, (int, float)) or v != v: nonnum += 1
            elif v <= 0: nonpos += 1
            ts = p.get('updated_at')
            if ts:
                tot_ts += 1
                if not re.search(r'(Z|[+-]\d\d:?\d\d)$', ts): naive_ts += 1
                try:
                    t = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    if t.tzinfo is None: t = t.replace(tzinfo=timezone.utc)
                    age = (now - t).total_seconds() / 3600
                    if age < -0.1: future_ts += 1
                    if age > 36: old36 += 1
                except Exception: naive_ts += 1
    rows.append((cc, n, priced, bad_pref, nolat, outbox, swapped, nonnum, nonpos, naive_ts, future_ts, tot_ts, old36, dict(cur), dict(unit)))

print(f"{'CC':3} {'stn':>6} {'priced':>6} {'idPfx!':>6} {'noLL':>5} {'outBBOX':>7} {'|lat|>90':>8} {'nonNum':>6} {'<=0':>4} {'naiveTS':>7} {'future':>6} {'ts>0':>6} {'>36h':>6}  currency / units")
for r in rows:
    print(f"{r[0]:3} {r[1]:6} {r[2]:6} {r[3]:6} {r[4]:5} {r[5]:7} {r[6]:8} {r[7]:6} {r[8]:4} {r[9]:7} {r[10]:6} {r[11]:6} {r[12]:6}  {r[13]} {r[14]}")
dups = [k for k, v in ids.items() if v > 1]
print('\nduplicate station ids across all files:', len(dups), dups[:5])
print('total stations:', sum(r[1] for r in rows), ' priced:', sum(r[2] for r in rows))
