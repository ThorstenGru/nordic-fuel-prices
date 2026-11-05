"""Merge tools/vehicles/{petrol,diesel,phev,hyundai}.json into web/vehicles.json.
Fails loudly (exit 1) on validation errors. Python stdlib only."""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent / "web" / "vehicles.json"
KEEP = ("id", "make", "model", "variant", "type", "hybrid", "rank", "tank_l", "cons_l100",
        "battery_kwh", "range_km", "ev_kwh100", "confidence", "source", "notes")
NOTE_MAX = 240


def load(name):
    return json.loads((HERE / f"{name}.json").read_text(encoding="utf-8"))["vehicles"]


def check_range(errs, v, field, lo, hi):
    x = v.get(field)
    if x is not None and not (isinstance(x, (int, float)) and lo <= x <= hi):
        errs.append(f"{v.get('id')}: {field}={x!r} outside {lo}..{hi}")


def validate(entries):
    errs, seen = [], {}
    for v in entries:
        for f in ("make", "model", "type", "id"):
            if not v.get(f):
                errs.append(f"{v.get('id') or v}: missing {f}")
        if v.get("id") in seen and seen[v["id"]] != v:
            errs.append(f"duplicate id with different content: {v['id']}")
        seen[v.get("id")] = v
        t = v.get("type")
        if t != "ev":
            check_range(errs, v, "tank_l", 25, 120) if t != "hydrogen" else None
        if t in ("petrol", "diesel"):
            check_range(errs, v, "cons_l100", 3.0, 14.0)
        if t == "phev":
            check_range(errs, v, "cons_l100", 3.5, 9.0)
        check_range(errs, v, "battery_kwh", 5, 130)
        check_range(errs, v, "range_km", 20, 800 if t != "hydrogen" else 1000)
        check_range(errs, v, "ev_kwh100", 10, 35)
    return errs


def slim(v):
    o = {k: v.get(k) for k in KEEP}
    if o["notes"] and len(o["notes"]) > NOTE_MAX:
        o["notes"] = o["notes"][:NOTE_MAX - 1].rstrip() + "\u2026"
    return o


def main():
    cats = {c: load(c) for c in ("petrol", "diesel", "phev")}
    hyundai = load("hyundai")
    errs = validate([v for l in cats.values() for v in l] + hyundai)
    # same id in a category list and the Hyundai list must be identical
    byid = {v["id"]: v for l in cats.values() for v in l}
    for h in hyundai:
        if h["id"] in byid and byid[h["id"]] != h:
            errs.append(f"{h['id']}: differs between category list and hyundai list")
    if errs:
        print("vehicles validation FAILED:\n  " + "\n  ".join(errs), file=sys.stderr)
        return 1
    key = lambda v: (v["rank"] is None, v["rank"] or 0)  # stable: unranked keep file order
    out = {"version": 1, "generated": "2026-11-05",
           "note": "Example values (typical WLTP figures). Please adjust to your car.",
           "categories": {c: [slim(v) for v in sorted(l, key=key)] for c, l in cats.items()},
           "hyundai": [slim(v) for v in hyundai]}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} " + ", ".join(f"{c}={len(l)}" for c, l in cats.items()) + f", hyundai={len(hyundai)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
