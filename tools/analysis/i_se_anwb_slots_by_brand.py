"""Sweden: ANWB petrol slots ('95','98') by brand: stations, median, distinct price values.
Brand-uniform pricing shows as 1 distinct value. Usage: python i_se_anwb_slots_by_brand.py <folder with se.json>"""
import json, os, sys, statistics, collections

D = sys.argv[1]
stations = json.load(open(os.path.join(D, 'se.json'), encoding='utf-8'))['stations']
data = collections.defaultdict(list)
for s in stations:
    for p in s.get('prices', []):
        if p.get('source') == 'anwb' and p.get('fuel_type') in ('95', '98', 'E10', 'E5'):
            slot = '98' if (p.get('octane') or 0) >= 97 or p['fuel_type'] == '98' else '95'
            data[(slot, s.get('brand') or '?')].append(p['price'])
print(f"{'slot':4} {'brand':20} {'n':>5} {'median':>7} {'distinct':>8}")
for (slot, brand), v in sorted(data.items(), key=lambda kv: (kv[0][0], -len(kv[1]))):
    print(f"{slot:4} {brand[:20]:20} {len(v):5} {statistics.median(v):7.2f} {len(set(v)):8}")
