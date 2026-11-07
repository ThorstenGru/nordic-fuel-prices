"""How many prices sit deep below the country median (dated or not)? Candidates for 'never wins a headline claim'."""
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

print(f"{'CC':3} {'fuel':7} {'n':>6} {'median':>8} {'<0.85':>6} {'<0.80':>6} {'<0.75':>6} {'<0.70':>6}   lowest 3 (price, src)")
tot = collections.Counter()
for c in meta['countries']:
    cc = c['country']
    rows = collections.defaultdict(list)
    for s in json.load(open(os.path.join(D, cc.lower() + '.json'), encoding='utf-8'))['stations']:
        for p in s.get('prices', []):
            if p.get('plausible') is False or p.get('basis') == 'regulated_max' or not p.get('price'): continue
            b = bucket(p)
            if b in ('P95', 'DIESEL'): rows[b].append((p['price'], p.get('source'), bool(p.get('updated_at'))))
    for b, v in rows.items():
        if len(v) < 40: continue
        m = S.median(x[0] for x in v)
        c85, c80, c75, c70 = (sum(1 for x in v if x[0] < m * f) for f in (.85, .80, .75, .70))
        for k, n in (('85', c85), ('80', c80), ('75', c75), ('70', c70)): tot[k] += n
        if c80 >= 3:
            low = sorted(v)[:3]
            print(f"{cc:3} {b:7} {len(v):6} {m:8.3f} {c85:6} {c80:6} {c75:6} {c70:6}   {[(round(x[0], 2), x[1], 'dated' if x[2] else 'undated') for x in low]}")
print('totals below x*median:', dict(tot))
