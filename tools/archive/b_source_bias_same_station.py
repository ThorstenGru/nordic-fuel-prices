"""Source-vs-source bias on the SAME station+fuel (uses the merge engine's per-price `alt` list), plus SE deep-dive."""
import json, os, sys, collections, statistics as S

D = sys.argv[1]
meta = json.load(open(os.path.join(D, 'meta.json'), encoding='utf-8'))
PETROL = ('E10', 'E5', '95', '98')

def bucket(p):
    ft = p.get('fuel_type')
    if ft in PETROL:
        o = p.get('octane') or (98 if ft == '98' else 95)
        return 'P98' if o >= 97 else 'P95'
    return ft

pairs = collections.defaultdict(list)       # (cc, bucket, primary, alt) -> [alt/primary ratio]
for c in meta['countries']:
    cc = c['country']
    for s in json.load(open(os.path.join(D, cc.lower() + '.json'), encoding='utf-8'))['stations']:
        for p in s.get('prices', []):
            for a in p.get('alt', []) or []:
                if p['price'] > 0 and a.get('price', 0) > 0:
                    pairs[(cc, bucket(p), p.get('source'), a.get('source'))].append(a['price'] / p['price'])

print('Same station + same fuel, two sources: alt/primary price ratio (1.000 = they agree)')
print(f"{'CC':3} {'fuel':7} {'primary':13} {'alt':13} {'n':>5} {'median':>7} {'p10':>6} {'p90':>6}")
for k, v in sorted(pairs.items(), key=lambda kv: -len(kv[1])):
    if len(v) < 20: continue
    v = sorted(v); q = lambda f: v[min(len(v) - 1, int(f * len(v)))]
    flag = '  <-- biased' if abs(S.median(v) - 1) > 0.04 else ''
    print(f"{k[0]:3} {k[1]:7} {str(k[2]):13} {str(k[3]):13} {len(v):5} {S.median(v):7.3f} {q(.1):6.3f} {q(.9):6.3f}{flag}")

# ---- Sweden deep dive: where does each 95 / diesel price come from, and what level is it? ----
se = json.load(open(os.path.join(D, 'se.json'), encoding='utf-8'))['stations']
lvl = collections.defaultdict(list)
for s in se:
    for p in s.get('prices', []):
        lvl[(bucket(p), p.get('source'))].append(p['price'])
print('\nSweden price level by fuel bucket and source (SEK/L):')
for k in sorted(lvl):
    v = sorted(lvl[k])
    print(f"  {k[0]:7} {str(k[1]):13} n={len(v):5} median={S.median(v):7.2f} p10={v[int(.1*len(v))]:7.2f} p90={v[int(.9*len(v))]:7.2f} min={v[0]:6.2f} max={v[-1]:6.2f}")

# stations that have BOTH bensinpriser and anwb for 95 (agreement test)
both = []
for s in se:
    srcs = {}
    for p in s.get('prices', []):
        if bucket(p) == 'P95': srcs.setdefault(p.get('source'), []).append(p['price'])
        for a in p.get('alt', []) or []:
            if bucket(p) == 'P95': srcs.setdefault(a.get('source'), []).append(a['price'])
    if 'bensinpriser' in srcs and 'anwb' in srcs:
        both.append((min(srcs['bensinpriser']), min(srcs['anwb'])))
if both:
    d = [b - a for a, b in both]
    print(f"\nSE stations with a 95 from BOTH sources: {len(both)}  anwb - bensinpriser: median {S.median(d):+.2f} kr  (p10 {sorted(d)[int(.1*len(d))]:+.2f}, p90 {sorted(d)[int(.9*len(d))]:+.2f})")

# the 10 cheapest SE 95 prices overall, and who says so
rows = []
for s in se:
    for p in s.get('prices', []):
        if bucket(p) == 'P95' and p.get('plausible') is not False:
            rows.append((p['price'], s.get('name'), s.get('city'), p.get('source'), p.get('updated_at'), s['id']))
rows.sort()
print('\nCheapest 12 SE 95-octane prices in the data (what "Cheapest here" would surface):')
for r in rows[:12]: print('  ', r)
print('Priciest 5:'); [print('  ', r) for r in rows[-5:]]
