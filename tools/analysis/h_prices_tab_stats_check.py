"""Does meta.json stats_eur (the Prices tab) match a recomputation from the raw country files? (EUR countries: exact; others: implied FX)"""
import json, os, sys, statistics as S

D = sys.argv[1]
meta = json.load(open(os.path.join(D, 'meta.json'), encoding='utf-8'))
PETROL = ('E10', 'E5', '95', '98')

def bucket(p):
    ft = p.get('fuel_type')
    if ft in PETROL:
        o = p.get('octane') or (98 if ft == '98' else 95)
        return 'P98' if o >= 97 else 'P95'
    return ft

print(f"{'CC':3} {'cur':4} {'key':6} {'n meta':>7} {'n mine':>7} {'median meta':>11} {'median mine':>11} {'implied FX':>10}  verdict")
bad = 0
for c in meta['countries']:
    cc, cur = c['country'], c.get('currency', 'EUR')
    se = c.get('stats_eur')
    if not se: continue
    st = json.load(open(os.path.join(D, cc.lower() + '.json'), encoding='utf-8'))['stations']
    for key, bk in (('p95', 'P95'), ('diesel', 'DIESEL')):
        if key not in se: continue
        v = []
        for s in st:
            best = None
            for p in s.get('prices', []):
                if p.get('plausible') is False or p.get('basis') == 'regulated_max' or not p.get('price'): continue
                if bucket(p) == bk and (best is None or p['price'] < best): best = p['price']
            if best is not None: v.append(best)
        if not v: continue
        mine = S.median(v); m = se[key]['median']
        fx = m / mine
        if cur == 'EUR':
            ok = abs(m - mine) <= 0.0015 and se[key]['n'] == len(v)
            verdict = 'OK' if ok else 'DIFFERS'
            if not ok: bad += 1
        else:
            verdict = f'FX {fx:.4f} EUR per {cur}'
        print(f"{cc:3} {cur:4} {key:6} {se[key]['n']:7} {len(v):7} {m:11.3f} {mine:11.3f} {fx:10.4f}  {verdict}")
print('EUR countries with a difference:', bad)
