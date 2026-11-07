"""Where would a 'low undated price vs dated consensus' guard trigger? dated = timestamp known and <= 36 h old."""
import json, os, sys, collections, statistics as S
from datetime import datetime, timezone

D = sys.argv[1]; FLOOR = float(sys.argv[2]) if len(sys.argv) > 2 else 0.92
meta = json.load(open(os.path.join(D, 'meta.json'), encoding='utf-8'))
now = datetime.fromisoformat(meta['fetched_at'])
PETROL = ('E10', 'E5', '95', '98')

def bucket(p):
    ft = p.get('fuel_type')
    if ft in PETROL:
        o = p.get('octane') or (98 if ft == '98' else 95)
        return 'P98' if o >= 97 else 'P95'
    return ft

def dated(p):
    ts = p.get('updated_at')
    if not ts: return False
    t = datetime.fromisoformat(ts.replace('Z', '+00:00'))
    if t.tzinfo is None: t = t.replace(tzinfo=timezone.utc)
    return (now - t).total_seconds() / 3600 <= 36

print(f'floor = {FLOOR} x dated median (needs >= 20 dated prices). Only rows where the guard would trigger are shown.')
print(f"{'CC':3} {'fuel':7} {'dated n':>8} {'dated med':>9} {'undated n':>9} {'undated med':>11} {'undated below floor':>20}  {'% of undated':>12}")
for c in meta['countries']:
    cc = c['country']
    d, u = collections.defaultdict(list), collections.defaultdict(list)
    for s in json.load(open(os.path.join(D, cc.lower() + '.json'), encoding='utf-8'))['stations']:
        for p in s.get('prices', []):
            if p.get('plausible') is False or p.get('basis') == 'regulated_max' or not p.get('price'): continue
            b = bucket(p)
            if b not in ('P95', 'P98', 'DIESEL'): continue
            (d if dated(p) else u)[b].append(p['price'])
    for b in ('P95', 'P98', 'DIESEL'):
        if len(d[b]) < 20 or not u[b]: continue
        m = S.median(d[b]); below = sum(1 for v in u[b] if v < m * FLOOR)
        if below:
            print(f"{cc:3} {b:7} {len(d[b]):8} {m:9.3f} {len(u[b]):9} {S.median(u[b]):11.3f} {below:20} {100*below/len(u[b]):11.1f}%")
