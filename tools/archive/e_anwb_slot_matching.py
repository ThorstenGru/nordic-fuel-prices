"""For stations priced by ANWB AND another source: which fuel slot of the other source does each ANWB price equal (to 0.5 %)?
A mislabelled slot shows up as ANWB 'P98' == other source's 'P95'."""
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

print('ANWB slot -> which slot of ANOTHER source on the SAME station has (almost) the same price')
print(f"{'CC':3} {'ANWB slot':9} {'pairs':>6} {'=P95':>6} {'=P98':>6} {'=DIESEL':>7} {'=E85':>5} {'none':>5}   comment")
for c in meta['countries']:
    cc = c['country']
    conf = collections.defaultdict(collections.Counter)
    for s in json.load(open(os.path.join(D, cc.lower() + '.json'), encoding='utf-8'))['stations']:
        # collect every (source, bucket, price) incl. alternatives
        obs = []
        for p in s.get('prices', []):
            obs.append((p.get('source'), bucket(p), p['price']))
            for a in p.get('alt', []) or []:
                obs.append((a.get('source'), bucket(p), a['price']))
        anwb = [(b, v) for src, b, v in obs if src == 'anwb']
        other = [(src, b, v) for src, b, v in obs if src not in (None, 'anwb')]
        if not anwb or not other: continue
        for b, v in set(anwb):
            if b not in ('P95', 'P98'): continue
            hit = [ob for _, ob, ov in other if abs(ov - v) <= 0.005 * v]
            conf[b]['pairs'] += 1
            if not hit: conf[b]['none'] += 1
            for h in set(hit): conf[b][h] += 1
    for b in ('P95', 'P98'):
        x = conf[b]
        if x['pairs'] >= 15:
            note = ''
            if b == 'P98' and x['P95'] > x['P98']: note = '<-- ANWB "98" is really the other source\'s 95'
            if b == 'P95' and x['P98'] > x['P95']: note = '<-- ANWB "95" is really the other source\'s 98'
            print(f"{cc:3} {b:9} {x['pairs']:6} {x['P95']:6} {x['P98']:6} {x['DIESEL']:7} {x['E85']:5} {x['none']:5}   {note}")
