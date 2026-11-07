"""Per country and per source: price level by fuel bucket + impossible orderings (98 < 95, diesel absurdly far from 95)."""
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

def med(v): return S.median(v) if v else None

print('Per country/source medians in LOCAL currency. flag = P98<=P95 (impossible), or DIESEL/P95 outside 0.80..1.30')
print(f"{'CC':3} {'source':13} {'n95':>5} {'P95':>8} {'n98':>5} {'P98':>8} {'nD':>5} {'DIESEL':>8} {'98/95':>6} {'D/95':>6}  flag")
flags = []
for c in meta['countries']:
    cc = c['country']
    st = json.load(open(os.path.join(D, cc.lower() + '.json'), encoding='utf-8'))['stations']
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for s in st:
        for p in s.get('prices', []):
            if p.get('plausible') is False or p.get('basis') == 'regulated_max': continue
            by[p.get('source')][bucket(p)].append(p['price'])
    for src, b in sorted(by.items(), key=lambda kv: -sum(len(x) for x in kv[1].values())):
        n95, n98, nd = len(b['P95']), len(b['P98']), len(b['DIESEL'])
        if n95 + nd < 40: continue
        m95, m98, md = med(b['P95']), med(b['P98']), med(b['DIESEL'])
        r98 = (m98 / m95) if (m95 and m98 and n98 >= 10 and n95 >= 10) else None
        rd = (md / m95) if (m95 and md and n95 >= 10 and nd >= 10) else None
        fl = []
        if r98 is not None and r98 <= 1.0: fl.append('98<=95 IMPOSSIBLE')
        if rd is not None and not (0.80 <= rd <= 1.30): fl.append('diesel/95 odd')
        f = lambda x: f'{x:8.3f}' if x is not None else '       -'
        g = lambda x: f'{x:6.3f}' if x is not None else '     -'
        print(f"{cc:3} {str(src):13} {n95:5} {f(m95)} {n98:5} {f(m98)} {nd:5} {f(md)} {g(r98)} {g(rd)}  {' | '.join(fl)}")
        if fl: flags.append((cc, src, fl))
print('\nFLAGGED:', flags)
