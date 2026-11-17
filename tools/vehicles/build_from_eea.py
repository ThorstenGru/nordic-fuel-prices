"""Build web/vehicles_eea.json: the 100 best-selling models per kind from the EEA register of new passenger cars.

Input : data/eea/co2cars_2024Fv30_top.json (grouped rows from Discodata table CO2Emission.latest.co2cars_2024Fv30,
        year 2024, final data; kinds: petrol = Ft petrol + Fm M, diesel = Ft diesel + Fm M, hev = Fm H (incl. mild hybrids),
        phev = Fm P). Each row: Mk, Cn, Ft, Fm, regs, fc_l100, wh_km, co2_g_km (sums/averages over the EU register).
Output: one entry per make+model. Stdlib only.
Not in the register (so left empty, never invented): tank size, electric range, battery size.
For PHEV the register's Fc and Z are weighted (utility-factor) WLTP values, NOT charge-sustaining consumption, so they go
into cons_wltp_weighted / ev_kwh100 only; cons_l100 stays None for plug-in hybrids.
"""
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "data" / "eea" / "co2cars_2024Fv30_top.json"
OUT = ROOT / "web" / "vehicles_eea.json"
KINDS = ("petrol", "diesel", "hev", "phev")
TOP = 100
CREDIT = "European Environment Agency, CO2 monitoring of new passenger cars (Reg. (EU) 2019/631), 2024 final data"


def make_name(mk):
    mk = mk.upper().replace("VOLKSWAGEN VW", "VOLKSWAGEN").strip()
    return {"BMW": "BMW", "MG": "MG", "DS": "DS", "KIA": "Kia", "SEAT": "SEAT", "CUPRA": "Cupra", "MINI": "MINI"}.get(mk, mk.title())


def model_name(mk, cn):
    cn = re.sub(r"\s+", " ", cn.strip())
    if cn.upper().startswith(mk.upper() + " "):          # "TOYOTA YARIS CROSS" -> "Yaris Cross"
        cn = cn[len(mk) + 1:]
    # only plain long words are title-cased: XC60, T-Roc, X1 XDRIVE25E keep their codes
    return " ".join(w.title() if w.isalpha() and len(w) > 3 else w for w in cn.split(" ")) if cn.isupper() else cn


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def build(src):
    out = {}
    for kind in KINDS:
        agg = collections.defaultdict(lambda: {"regs": 0, "fc": 0.0, "fcn": 0, "wh": 0.0, "whn": 0, "co2": 0.0, "co2n": 0})
        for r in src.get(kind, []):
            key = (make_name(r["Mk"]), model_name(r["Mk"], r["Cn"]))
            a, n = agg[key], r["regs"]
            a["regs"] += n
            for f, col in (("fc", "fc_l100"), ("wh", "wh_km"), ("co2", "co2_g_km")):
                if r.get(col) is not None:
                    a[f] += n * r[col]
                    a[f + "n"] += n
        rows = []
        for (mk, mo), a in sorted(agg.items(), key=lambda kv: -kv[1]["regs"])[:TOP]:
            w = lambda f: round(a[f] / a[f + "n"], 2) if a[f + "n"] else None
            fc = w("fc")
            wh = w("wh")
            rows.append({
                "id": f"eea-{kind}-{slug(mk)}-{slug(mo)}", "make": mk, "model": mo, "type": kind, "rank": len(rows) + 1,
                "registrations_2024": a["regs"],
                "cons_l100": None if kind == "phev" else fc,
                "cons_wltp_weighted": fc if kind == "phev" else None,
                "ev_kwh100": round(wh / 10, 1) if (kind == "phev" and wh) else None,
                "co2_g_km": w("co2"), "tank_l": None, "range_km": None, "battery_kwh": None,
                "source": "EEA 2024",
            })
        out[kind] = rows
    return out


def validate(out):
    errs = []
    for kind, rows in out.items():
        if len(rows) < TOP:
            errs.append(f"{kind}: only {len(rows)} models")
        for r in rows:
            c = r["cons_l100"]
            if c is not None and not 2.0 <= c <= 16.0:
                errs.append(f"{r['id']}: cons_l100 {c} outside 2..16")
    return errs


def main():
    out = build(json.loads(SRC.read_text(encoding="utf-8")))
    errs = validate(out)
    if errs:
        print("\n".join(errs))
        sys.exit(1)
    doc = {"version": 1, "source": CREDIT, "note": "Model-level averages weighted by registrations; no tank size or electric range in the register. HEV includes mild hybrids. For PHEV the consumption figures are weighted WLTP values, not charge-sustaining.", "categories": out}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print({k: len(v) for k, v in out.items()}, OUT.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
