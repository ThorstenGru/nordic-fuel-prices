"""Model-free consistency test: on ONE station, 98-octane must never be cheaper than 95-octane, and E85 must be clearly
cheaper than 95. Violations mean a mislabelled/misbucketed price slot. Also: how many stations are driven by such prices."""
import json, os, sys, collections

D = sys.argv[1]
meta = json.load(open(os.path.join(D, 'meta.json'), encoding='utf-8'))
PETROL = ('E10', 'E5', '95', '98')

def bucket(p):
    ft = p.get('fuel_type')
    if ft in PETROL:
        o = p.get('octane') or (98 if ft == '98' else 95)
        return 'P98' if o >= 97 else 'P95'
    return ft

print(f"{'CC':3} {'stations w/ 95+98':>17} {'98<95':>6} {'rate':>6}   {'stations w/ 95+E85':>18} {'E85>=95':>8}   by source of the 95 on violating stations")
for c in meta['countries']:
    cc = c['country']
    n_both = n_viol = n_e85 = n_e85v = 0
    srcs = collections.Counter()
    ex = None
    for s in json.load(open(os.path.join(D, cc.lower() + '.json'), encoding='utf-8'))['stations']:
        b = collections.defaultdict(list)
        for p in s.get('prices', []):
            if p.get('plausible') is False or p.get('basis') == 'regulated_max': continue
            b[bucket(p)].append((p['price'], p.get('source')))
        if b['P95'] and b['P98']:
            n_both += 1
            lo95, lo98 = min(b['P95']), min(b['P98'])
            if lo98[0] < lo95[0] - 0.0005:
                n_viol += 1; srcs[f"95:{lo95[1]} 98:{lo98[1]}"] += 1
                ex = ex or (s['id'], lo95, lo98)
        if b['P95'] and b['E85']:
            n_e85 += 1
            if min(b['E85'])[0] >= min(b['P95'])[0] - 0.0005: n_e85v += 1
    if n_both >= 10 or n_e85 >= 10:
        rate = f"{100 * n_viol / n_both:5.1f}%" if n_both else '     -'
        print(f"{cc:3} {n_both:17} {n_viol:6} {rate}   {n_e85:18} {n_e85v:8}   {dict(srcs.most_common(3))} {('ex ' + str(ex)) if ex and n_viol / max(1, n_both) > .1 else ''}")
