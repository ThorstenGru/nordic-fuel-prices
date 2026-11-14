"""Static SEO pages per country: a hub (/<cc>/) and one page per town (/<cc>/<town>/).

Runs after ``main.py`` in the scrape workflow and writes plain, JS-free HTML into ``data/`` so the
pages are crawlable and fast. Targets local-intent queries ("bensinpriser Växjö", "Spritpreise
Wien", "prix carburant Lyon") — see docs/ROADMAP.md, experiment E3.

Countries (COUNTRIES below): SE, AT, FR, DE, CH, ES, PT, DK, NL, BE (nl at /be/, fr at /be-fr/, same data), PL,
IT (IT switches on by itself once data/it.json holds prices younger than 72 h). DE and CH are currently fed
by the unofficial ANWB API, which the roadmap flags as a licence / cease-and-desist risk; the owner
released them anyway (2026-10-06). Their pages say so in the footer. Kill switch: SEO_EXCLUDE_ANWB=1
skips every ANWB-fed country. When DE switches to Tankerkönig (roadmap D3) the footer attribution
switches to Tankerkönig automatically (it follows ``meta.source``).

Town model — two modes:
  * "places": stations are assigned to the nearest OSM town centre (src/seed/<cc>_places.json) when
              the feed has no usable city field (SE, AT).
  * "city":   stations are grouped by the feed's own city/commune name (FR, DE, CH).

Thin-content guard: a town page needs >= MIN_STATIONS stations and at least one fresh price (SE also
allows "nearest priced stations" as content). Timestamps are shown honestly — see ``ts_kind``:
  snapshot  the source's feed snapshot time (SE: one time for the whole county feed),
  fetched   OUR fetch time, because the source gives no price time (AT/DE/CH),
  price     the real per-price update time from the source (FR).

Usage:  python src/seo_pages.py   (reads data/<cc>.json; writes data/<cc>/**, data/sitemap-<cc>.xml,
        data/sitemap-seo.xml)
"""

import json
import math
import os
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
SEED_DIR = Path(__file__).parent / "seed"
SITE = "https://eurofuelprices.com"

MIN_STATIONS = 3          # below this a town page would be thin content -> no page
ASSIGN_RADIUS_KM = 12     # places mode: a station belongs to the nearest centre within this radius
CITY_SPREAD_KM = 25       # city mode: same-name stations further than this from the median are another town
NEARBY_PRICED_KM = 50     # fallback radius for "nearest priced stations"
MAX_PRICE_AGE_H = 72      # ignore prices older than this when the source gives a price time
EXCLUDE_ANWB = os.environ.get("SEO_EXCLUDE_ANWB") == "1"   # kill switch: skip countries fed by the unofficial ANWB API

from seo_text import COUNTRIES, MONTHS, TXT  # (country settings and page texts live in seo_text.py)


def slugify(name: str, lang: str) -> str:
    rep = {"sv": {"å": "a", "ä": "a", "ö": "o"}, "de": {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}, "fr": {"œ": "oe", "æ": "ae"}, "es": {}, "pt": {}, "nl": {}, "da": {"å": "aa", "ø": "oe", "æ": "ae"}, "it": {}, "pl": {"ł": "l"}}[lang]
    s = name.lower()
    for k, v in rep.items():
        s = s.replace(k, v)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(a))


def parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def to_local(dt: datetime, lang: str = "") -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return dt.astimezone(ZoneInfo("Europe/Lisbon" if lang == "pt" else "Europe/Paris"))   # CET/CEST: same as SE/DE/AT/CH/FR/ES/DK
    except Exception:
        return dt


def fmt_when(dt: Optional[datetime], lang: str) -> str:
    if not dt:
        return "–"
    d = to_local(dt, lang)
    dot = "." if lang == "de" else ""
    return f"{d.day}{dot} {MONTHS[lang][d.month - 1]} {d.hour:02d}:{d.minute:02d}"


def fmt_price(v: float, cfg: Dict) -> str:
    s = f"{v:.2f}" if cfg["currency"] in ("SEK", "PLN") else f"{v:.3f}"
    return s.replace(".", ",")


def money(v: float, cfg: Dict) -> str:
    return f"{fmt_price(v, cfg)} {cfg['sym']}"


# Petrol rows are matched by OCTANE bucket (same rule as web/index.html) so a 98 price is never
# shown under a 95 label. Row keys: "P95" = octane-95 bucket (E10, E5@95, generic 95), "P98" = octane >= 97,
# "E5_95" = fuel_type E5 at 95 octane; any other key is a plain fuel_type match (E10, DIESEL, LPG, E85 ...).
_PETROL = ("E10", "E5", "95", "98")


def octane_of(p: Dict[str, Any]) -> Optional[int]:
    if p.get("fuel_type") not in _PETROL:
        return None
    if p.get("octane"):
        try:
            return int(p["octane"])
        except (TypeError, ValueError):
            return None
    return 98 if p.get("fuel_type") == "98" else 95   # legacy: E10/E5/95 without octane = 95


def fuel_match(p: Dict[str, Any], key: str) -> bool:
    if key == "P95":
        return octane_of(p) == 95
    if key == "P98":
        o = octane_of(p)
        return o is not None and o >= 97
    if key == "E5_95":
        return p.get("fuel_type") == "E5" and octane_of(p) == 95
    if key == "E10":
        return p.get("fuel_type") == "E10"
    return p.get("fuel_type") == key


def fresh_price(station: Dict[str, Any], fuel: str, now: datetime, cfg: Dict) -> Optional[Tuple[float, Optional[datetime]]]:
    best = None
    for p in station.get("prices") or []:
        if not fuel_match(p, fuel) or p.get("currency") != cfg["currency"] or p.get("unit") != "L" or p.get("plausible") is False:
            continue
        try:
            price = float(p["price"])
        except (KeyError, TypeError, ValueError):
            continue
        when = parse_iso(p.get("updated_at"))
        if when and (now - when).total_seconds() > cfg.get("max_age_h", MAX_PRICE_AGE_H) * 3600:
            continue
        if price == cfg.get("_ceil", {}).get(fuel):   # a legal maximum shown as if it were a station price
            continue
        if best is None or price < best[0]:
            best = (price, when)
    return best


def has_price(s: Dict, now: datetime, cfg: Dict) -> bool:
    return any(fresh_price(s, f, now, cfg) for f, _ in cfg["fuels"])


TREND_BASE: Optional[str] = SITE   # where the previous publish lives (tests set None); gives "change since" without a database
TREND_DAYS = 8


def fmt_day(date_str: str, lang: str) -> str:
    y, m, d = (int(v) for v in date_str.split("-"))
    return f"{d}{'.' if lang == 'de' else ''} {MONTHS[lang][m - 1]}"


def load_trend(cc: str) -> Dict[str, Dict[str, Dict[str, float]]]:
    """{town slug: {YYYY-MM-DD: {fuel: median}}} from the last published /<cc>/trend.json; {} when unreachable."""
    if not TREND_BASE:
        return {}
    try:
        import urllib.request
        req = urllib.request.Request(f"{TREND_BASE}/{cc}/trend.json", headers={"User-Agent": "EuroFuelPrices-build (+https://eurofuelprices.com)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode("utf-8"))
        return d.get("d", {}) if d.get("v") == 1 else {}
    except Exception:   # noqa: BLE001 - no history is fine, the pages just show no change line
        return {}


def town_medians(rows: List[Tuple[Dict, float]], c: "Ctx") -> Dict[str, float]:
    out: Dict[str, float] = {}
    for f, _ in c.cfg["fuels"]:
        v = [fp[0] for s, _ in rows if (fp := fresh_price(s, f, c.now, c.cfg))]
        if v:
            out[f] = statistics.median(v)
    return out


def previous_medians(hist: Dict[str, Dict[str, float]], today: str) -> Optional[Tuple[str, Dict[str, float]]]:
    older = sorted(d for d in hist if d < today)
    return (older[-1], hist[older[-1]]) if older else None


# ── town model ───────────────────────────────────────────────────────────────

Town = Dict[str, Any]   # name, lat, lon, pop, rows [(station, km)], slug


def towns_from_places(stations: List[Dict], cc: str) -> List[Town]:
    places = json.loads((SEED_DIR / f"{cc}_places.json").read_text(encoding="utf-8"))
    towns = [dict(name=p["name"], lat=p["lat"], lon=p["lon"], pop=p.get("pop", 0), rows=[]) for p in places]
    for s in stations:
        try:
            lat, lon = float(s["lat"]), float(s["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        best, best_d = None, 1e9
        for t in towns:
            if abs(t["lat"] - lat) > 0.5 or abs(t["lon"] - lon) > 1.0:
                continue
            d = haversine_km(lat, lon, t["lat"], t["lon"])
            if d < best_d:
                best, best_d = t, d
        if best is not None and best_d <= ASSIGN_RADIUS_KM:
            best["rows"].append((s, best_d))
    return [t for t in towns if t["rows"]]


def clean_city(name: str, lang: str = "") -> str:
    n = re.sub(r"\s+", " ", (name or "").strip())
    if lang == "da":   # Danish postal districts: "Aarhus C", "København SV", "Aalborg Øst" are one town for searchers
        n = re.sub(r"\s+(C|N|V|S|Ø|SV|SØ|NV|NØ|Syd|Nord|Øst|Vest|Sv|Sø|Nv|Nø)$", "", n)
    n = re.sub(r"\s+\d{1,2}(er|e|ème)?\s*(arrondissement)?$", "", n, flags=re.I)   # "Paris 15e" -> "Paris"
    if n.isupper() or n.islower():
        n = n.title()
    return n


def towns_from_city(stations: List[Dict], lang: str) -> List[Town]:
    groups: Dict[str, List[Dict]] = defaultdict(list)
    spelling: Dict[str, Counter] = defaultdict(Counter)
    for s in stations:
        c = clean_city(s.get("city") or "", lang)
        if not c or "lat" not in s:
            continue
        key = slugify(c, lang)                       # "Zürich" and "Zuerich" are one town
        groups[key].append(s)
        spelling[key][c] += 1
    towns: List[Town] = []
    for key, sts in groups.items():
        name = max(spelling[key].items(), key=lambda kv: (kv[1], not kv[0].isascii()))[0]   # tie -> spelling with diacritics
        remaining = sts
        for _ in range(3):               # split same-name towns that are far apart
            if not remaining:
                break
            clat = statistics.median(float(s["lat"]) for s in remaining)
            clon = statistics.median(float(s["lon"]) for s in remaining)
            near = [(s, haversine_km(clat, clon, float(s["lat"]), float(s["lon"]))) for s in remaining]
            here = [(s, d) for s, d in near if d <= CITY_SPREAD_KM]
            remaining = [s for s, d in near if d > CITY_SPREAD_KM]
            if here:
                towns.append(dict(name=name, lat=clat, lon=clon, pop=0, rows=here))
    return towns


def assign_slugs(towns: List[Town], lang: str, near_word: str) -> None:
    """Unique slugs; same-name towns get '<name> (near <biggest other town>)' so titles stay distinct."""
    towns.sort(key=lambda t: (-len(t["rows"]), -t["pop"], t["name"]))
    seen: Dict[str, int] = Counter()
    for t in towns:
        base = slugify(t["name"], lang) or "ort"
        seen[base] += 1
        t["base"] = base
        t["clash"] = seen[base] > 1
    clashing = {t["base"] for t in towns if t["clash"]}
    used: set = set()
    for t in towns:
        slug, display = t["base"], t["name"]
        if t["base"] in clashing and (t["clash"] or any(o is not t and o["base"] == t["base"] and o["clash"] for o in towns)):
            if t["clash"]:
                anchor = next((o for o in towns if o["base"] != t["base"]
                               and haversine_km(t["lat"], t["lon"], o["lat"], o["lon"]) <= 150), None)
                if anchor:
                    display = f"{t['name']} ({near_word} {anchor['name']})"
                    slug = f"{t['base']}-{slugify(anchor['name'], lang)}"
        n = 2
        while slug in used:
            slug = f"{t['base']}-{n}"
            n += 1
        used.add(slug)
        t["slug"], t["display"] = slug, display


# ── HTML ─────────────────────────────────────────────────────────────────────

CSS = """
*, *::before, *::after { box-sizing:border-box; }
body { margin:0 auto; max-width:760px; padding:0 16px 60px;  line-height:1.6; font-size:16px; }
header { padding:20px 0 8px; display:flex; align-items:center; justify-content:space-between; gap:10px; }
.logo { font-size:1.1rem; font-weight:500; color:var(--text); text-decoration:none; }
.back { font-size:.82rem; color:var(--blue); text-decoration:none; border:1px solid var(--border); border-radius:12px; padding:7px 14px; background:var(--surf); white-space:nowrap; }
nav.crumbs { font-size:.82rem; color:var(--text3); margin:6px 0 0; }
nav.crumbs a { color:var(--text2); }
h1 { font-size:1.6rem; font-weight:600; line-height:1.25; margin:14px 0 8px; }
h2 { font-size:1.12rem; font-weight:600; margin:30px 0 10px; }
p { margin:0 0 12px; }
.lede { color:var(--text2); }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin:18px 0; }
.card { background:var(--surf); border:1px solid var(--border); border-radius:14px; padding:12px 14px; }
.card .k { font-size:.78rem; color:var(--text2); }
.card .v { font-size:1.45rem; font-weight:600; color:var(--green); }
.card .s { font-size:.78rem; color:var(--text2); }
.tw { overflow-x:auto; background:var(--surf); border:1px solid var(--border); border-radius:14px; }
table { border-collapse:collapse; width:100%; font-size:.9rem; }
th, td { text-align:left; padding:9px 12px; border-top:1px solid var(--border); white-space:nowrap; }
th { border-top:0; font-size:.76rem; color:var(--text2); font-weight:500; }
td.p { font-variant-numeric:tabular-nums; }
td.n { white-space:normal; min-width:150px; }
h3 { font-size:1rem; font-weight:600; margin:18px 0 4px; }
.range { position:relative; height:6px; background:var(--border); border-radius:3px; margin:10px 0 4px; }
.range b { position:absolute; top:0; height:6px; background:var(--green); border-radius:3px; min-width:4px; }
.range i { position:absolute; top:-3px; width:2px; height:12px; background:var(--text2); }
.sub { display:block; font-size:.76rem; color:var(--text3); }
.note { font-size:.84rem; color:var(--text2); background:var(--surf); border:1px solid var(--border); border-radius:12px; padding:10px 14px; }
ul.links { list-style:none; padding:0; margin:0; display:flex; flex-wrap:wrap; gap:8px; }
ul.links a { display:inline-block; padding:6px 12px; border:1px solid var(--border); border-radius:999px; background:var(--surf); color:var(--blue); text-decoration:none; font-size:.88rem; }
a { color:var(--blue); }
footer { margin-top:40px; padding-top:14px; border-top:1px solid var(--border); color:var(--text3); font-size:.8rem; }
"""


def page(cfg: Dict, title: str, desc: str, canonical: str, h1: str, body: str, jsonld: List[Dict],
         crumbs: str, modified: str, foot: str) -> str:
    x = TXT[cfg["lang"]]
    ld = "\n".join('<script type="application/ld+json">' + json.dumps(o, ensure_ascii=False).replace("</", "<\\/") + '</script>' for o in jsonld)   # a name containing </script> must not end the block
    return f"""<!DOCTYPE html>
<html lang="{cfg['lang']}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)} | EuroFuelPrices</title>
<meta name="description" content="{escape(desc)}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:locale" content="{x['locale']}">
<meta property="og:site_name" content="EuroFuelPrices">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{SITE}/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' https://static.cloudflareinsights.com; connect-src 'self' https://cloudflareinsights.com https://static.cloudflareinsights.com; style-src 'self' 'unsafe-inline'; img-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none';">
<meta name="theme-color" content="#E9EEF3" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0E1A29" media="(prefers-color-scheme: dark)">
<link rel="icon" type="image/svg+xml" href="/icon.svg">
<link rel="stylesheet" href="/theme.css">
{ld}
<style>{CSS}</style>
<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token": "4266c1f5c19845839b3163f64446320f"}}'></script>
</head>
<body>
<header><a class="logo" href="/"><img src="/icon.svg" alt="" width="22" height="22" style="vertical-align:-4px"> EuroFuelPrices</a><a class="back" href="/">{escape(x['map'])}</a></header>
{crumbs}
<h1>{escape(h1)}</h1>
{body}
<footer>
<p>{foot}</p>
<p>{escape(x['foot_upd'])}: {escape(modified)}. · <a href="https://www.facebook.com/eurofuelprices" rel="me noopener">Facebook</a></p>
</footer>
</body>
</html>
"""


def crumbs_html(lang: str, items: List[Tuple[str, Optional[str]]]) -> str:
    parts = [f'<a href="{u}">{escape(n)}</a>' if u else escape(n) for n, u in items]
    return f'<nav class="crumbs" aria-label="{escape(TXT[lang]["crumbs"])}">' + " › ".join(parts) + "</nav>"


def breadcrumb_ld(items: List[Tuple[str, str]]) -> Dict:
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(items)]}


def station_label(s: Dict) -> Tuple[str, str]:
    name = (s.get("brand") or s.get("name") or "").strip() or "Station"
    street = (s.get("address") or "").strip()
    city = (s.get("city") or "").strip()
    if name.lower().startswith("station-service") and street:     # FR feed has no brand: "Station-service · Lyon"
        name, street = (street.title() if street.isupper() else street), ""
    addr = ", ".join(x for x in [street, city] if x)
    return name, addr


class Ctx:
    def __init__(self, cc: str, cfg: Dict, now: datetime, fetched: datetime, national: Dict[str, float]):
        self.cc, self.cfg, self.now, self.fetched, self.national = cc, cfg, now, fetched, national
        self.x = TXT[cfg["lang"]]
        self.lang = cfg["lang"]


def row_time(s: Dict, fuels: List[str], c: Ctx) -> str:
    kind = c.cfg["ts_kind"]
    newest = None
    for f in fuels:
        fp = fresh_price(s, f, c.now, c.cfg)
        if fp and fp[1] and (newest is None or fp[1] > newest):
            newest = fp[1]
    if newest is None and kind == "fetched" and any(fresh_price(s, f, c.now, c.cfg) for f in fuels):
        newest = c.fetched
    return fmt_when(newest, c.lang)


def station_table(rows: List[Tuple[Dict, float]], c: Ctx, show_town: Optional[Dict[str, str]] = None) -> str:
    cfg, x = c.cfg, c.x
    present = [f for f, _ in cfg["fuels"] if any(fresh_price(s, f, c.now, cfg) for s, _ in rows)] or list(cfg["cheapest"])
    label = dict(cfg["fuels"])

    def sort_key(r):
        s, d = r
        fp = fresh_price(s, cfg["cheapest"][0], c.now, cfg) or fresh_price(s, "DIESEL", c.now, cfg)
        return (0, fp[0], d) if fp else (1, 0.0, d)

    head = "".join(f"<th>{escape(label[f])}</th>" for f in present)
    body = []
    for s, d in sorted(rows, key=sort_key):
        name, addr = station_label(s)
        sub = addr or (x["km_from"].format(d=f"{d:.0f}") if d >= 1 else x["central"])
        if show_town and s.get("id") in show_town:
            sub = f"{show_town[s['id']]} · {x['km'].format(d=f'{d:.0f}')}"
        cells = "".join(
            f'<td class="p">{fmt_price(fp[0], cfg)}</td>' if (fp := fresh_price(s, f, c.now, cfg)) else '<td class="p">–</td>'
            for f in present)
        body.append(f'<tr><td class="n">{escape(name)}<span class="sub">{escape(sub)}</span></td>{cells}'
                    f'<td>{row_time(s, present, c)}</td></tr>')
    return (f'<div class="tw"><table><thead><tr><th>{escape(x["th_station"])}</th>{head}'
            f'<th>{escape(x["th_when"][cfg["ts_kind"]])}</th></tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def summary_cards(rows: List[Tuple[Dict, float]], c: Ctx, prev: Optional[Tuple[str, Dict[str, float]]] = None,
                  now_med: Optional[Dict[str, float]] = None) -> str:
    cfg, x = c.cfg, c.x
    cards = []
    for f, label in cfg["fuels"]:
        vals = [(fp[0], s) for s, _ in rows if (fp := fresh_price(s, f, c.now, cfg))]
        if not vals:
            continue
        low, st = min(vals, key=lambda v: v[0])
        diff = ""
        if f in c.national and abs(low - c.national[f]) >= 0.005:
            dd = low - c.national[f]
            amount = f"{'+' if dd >= 0 else '−'}{fmt_price(abs(dd), cfg)}"
            diff = " · " + x["vs"].format(d=amount, sym=cfg["sym"], nation=cfg.get("nation", ""))
        prices = [v[0] for v in vals]
        hi = max(prices)
        nat = c.national.get(f)
        lo_s, hi_s = min(low, nat if nat else low), max(hi, nat if nat else hi)
        extra = ""
        if hi_s - lo_s >= 0.005:   # range of this town, tick = national median; the numbers below say the same in text
            pos = lambda v: 100 * (v - lo_s) / (hi_s - lo_s)   # noqa: E731
            tick = f'<i style="left:{pos(nat):.1f}%"></i>' if nat else ""
            extra = (f'<div class="range" aria-hidden="true"><b style="left:{pos(low):.1f}%;width:{max(pos(hi) - pos(low), 0):.1f}%"></b>{tick}</div>'
                     f'<div class="s">{escape(fmt_price(low, cfg))}–{escape(fmt_price(hi, cfg))} {escape(cfg["sym"])}</div>')
        if prev and now_med and f in now_med and f in prev[1] and abs(now_med[f] - prev[1][f]) >= 0.0005:
            dd = now_med[f] - prev[1][f]
            amount = f"{'+' if dd > 0 else '−'}{fmt_price(abs(dd), cfg)}"
            extra += f'<div class="s">{escape(x["chg"].format(when=fmt_day(prev[0], c.lang), d=amount, u=cfg["sym"] + "/L"))}</div>'
        cards.append(f'<div class="card"><div class="k">{escape(x["cheapest"].format(f=label))}</div>'
                     f'<div class="v">{escape(money(low, cfg))}</div><div class="s">{escape(station_label(st)[0])}{escape(diff)}</div>{extra}</div>')
    return f'<div class="cards">{"".join(cards)}</div>' if cards else ""


def faq_items(c: Ctx, disp: str, rows: List[Tuple[Dict, float]], priced_rows: List[Tuple[Dict, float]], modified: str) -> List[Tuple[str, str]]:
    """Questions people search for, answered from this page's own numbers (also emitted as FAQPage markup)."""
    cfg, x = c.cfg, c.x
    u = cfg["sym"] + "/L"
    fuel = cfg["cheapest"][1]
    label = dict(cfg["fuels"]).get(fuel, fuel)
    cands = [(fp[0], s) for s, _ in priced_rows if (fp := fresh_price(s, fuel, c.now, cfg))]
    out: List[Tuple[str, str]] = []
    if cands:
        low, st = min(cands, key=lambda v: v[0])
        out.append((x["q1"].format(fuel=label, town=disp), x["a1"].format(fuel=label, town=disp, p=fmt_price(low, cfg), u=u, station=" – ".join(p for p in station_label(st) if p))))
        if fuel in c.national:
            out.append((x["q2"].format(town=disp), x["a2"].format(fuel=label, town=disp, p=fmt_price(low, cfg), u=u, nation=x["nat"], n=fmt_price(c.national[fuel], cfg))))
    out.append((x["q3"].format(town=disp), x["a3"].format(town=disp, total=len(rows), n=len(priced_rows))))
    out.append((x["q4"], x["a4"].format(checked=modified, foot=x["foot_ts"][cfg["ts_kind"]])))
    return out


def footer_html(c: Ctx, unofficial: bool = False) -> str:
    cfg, x = c.cfg, c.x
    src_line = x["foot_unofficial"] if unofficial else x["foot_src"].format(src=cfg["src"])
    parts = [escape(src_line), escape(x["foot_ts"][cfg["ts_kind"]]),
             f'<a href="/about.html">{escape(x["foot_grades"])}</a>.']
    if cfg.get("acc_line"):
        parts.append(escape(cfg["acc_line"]))
    if cfg.get("credit"):
        parts.append('Data: <a href="https://www.fuel-prices.eu/" rel="noopener">fuel-prices.eu</a>, CC BY 4.0.')
    if cfg["osm"]:
        parts.append(f'{escape(x["foot_osm"])} <a href="https://www.openstreetmap.org/copyright">{escape(x["foot_osm_who"])}</a>.')
    return " ".join(parts)


# ── build one country ────────────────────────────────────────────────────────

def build_country(cc: str, cfg: Dict, now: datetime) -> Optional[List[Tuple[str, str]]]:
    f = DATA_DIR / f"{cfg.get('data', cc)}.json"
    if not f.exists():
        print(f"seo_pages[{cc}]: {f.name} missing - skipped")
        return None
    doc = json.loads(f.read_text(encoding="utf-8"))
    meta, stations = doc.get("meta") or {}, doc.get("stations") or []
    src_name = (meta.get("source") or "").lower()
    unofficial = "anwb" in src_name and "+" not in src_name   # merged feeds (DK) name their own sources
    if unofficial and EXCLUDE_ANWB:
        print(f"seo_pages[{cc}]: excluded by SEO_EXCLUDE_ANWB (source {meta.get('source')!r})")
        return None
    if meta.get("status") == "stale":   # keep the pages (a 404 on every indexed URL is worse): build them from the last data, no age filter; they show the real fetch date
        print(f"seo_pages[{cc}]: source stale - pages kept with the last data and fetch date")
        cfg = dict(cfg, max_age_h=10 ** 6)
    if cfg.get("acc"):   # measured accuracy of the unofficial feed against the official one (written by scrapers/germany.py)
        try:
            a = json.loads((DATA_DIR / cfg["acc"]).read_text(encoding="utf-8")).get("summary") or {}
            if a.get("n", 0) >= 500:
                de = lambda v: f"{v:g}".replace(".", ",")   # noqa: E731
                cfg = dict(cfg, acc_line=f"Genauigkeit: Verglichen mit dem amtlichen MTS-K-Preis stimmt der ANWB-Preis bei {de(a['within_1ct_pct'])} % von {a['n']} Stichproben "
                                         f"auf 1 Cent genau (letzte {a['days']} Tage); 90 % der Stichproben liegen innerhalb von {de(a['abs_p90_ct'])} Cent.")
        except (OSError, ValueError, KeyError):
            pass
    if "fuel-prices.eu" in src_name:   # credit required by their licence page: "Data: fuel-prices.eu", linked
        cfg = dict(cfg, credit=True)
    lang, x = cfg["lang"], TXT[cfg["lang"]]
    fetched = parse_iso(meta.get("fetched_at")) or now
    c = Ctx(cc, cfg, now, fetched, {})
    cfg["_ceil"] = {}
    if cfg.get("ceiling_share"):   # BE: most stations in the ANWB feed carry the government maximum price (one identical value for >= half of them), not their own
        for fuel, _ in cfg["fuels"]:
            vals = [fp[0] for s in stations if (fp := fresh_price(s, fuel, now, cfg))]
            top = Counter(vals).most_common(1)
            if vals and top[0][1] / len(vals) >= cfg["ceiling_share"]:
                cfg["_ceil"][fuel] = top[0][0]
    for fuel, _ in cfg["fuels"]:
        vals = [fp[0] for s in stations if (fp := fresh_price(s, fuel, now, cfg))]
        if len(vals) >= 5:
            c.national[fuel] = statistics.median(vals)

    trend = load_trend(cc)
    today_s = now.date().isoformat()
    towns = towns_from_places(stations, cc) if cfg["mode"] == "places" else towns_from_city(stations, lang)
    towns = [t for t in towns if len(t["rows"]) >= MIN_STATIONS]
    priced_all = [(s, t) for t in towns for s, _ in t["rows"] if has_price(s, now, cfg)]
    if cfg["fallback_nearby"]:
        pass
    else:
        towns = [t for t in towns if any(has_price(s, now, cfg) for s, _ in t["rows"])]
    if not towns:
        print(f"seo_pages[{cc}]: no eligible towns - skipped")
        return None
    assign_slugs(towns, lang, x["near"])
    town_of = {s["id"]: t["name"] for t in towns for s, _ in t["rows"]}

    out = DATA_DIR / cc
    out.mkdir(parents=True, exist_ok=True)
    lastmod = fetched.date().isoformat()
    modified = fmt_when(fetched, lang)
    hub_url = f"{SITE}/{cc}/"
    foot = footer_html(c, unofficial)
    urls = [(hub_url, lastmod)]
    hub_rows = []
    town_lows: List[Tuple[str, str, int, Optional[float], Optional[float]]] = []

    trend_out: Dict[str, Dict[str, Dict[str, float]]] = {}
    for t in sorted(towns, key=lambda t: t["name"]):
        name, disp, slug, rows = t["name"], t["display"], t["slug"], t["rows"]
        canonical = f"{SITE}/{cc}/{slug}/"
        priced_rows = [(s, d) for s, d in rows if has_price(s, now, cfg)]
        body = []
        if priced_rows:
            body.append(f'<p class="lede">{escape(x["lede"].format(n=len(priced_rows), total=len(rows), town=disp))}</p>')
            med = town_medians(priced_rows, c)
            newest = max((fp[1] for s, _ in priced_rows for f, _l in cfg["fuels"] if (fp := fresh_price(s, f, now, cfg)) and fp[1]), default=None)
            trust = f'{x["checked"]} {modified}' + (f' · {x["latest"]} {fmt_when(newest, lang)}' if newest else "")
            body.append(f'<p class="note">{escape(trust)}</p>')
            body.append(summary_cards(rows, c, previous_medians(trend.get(slug, {}), today_s), med))
            body.append(f"<h2>{escape(x['h_stations'].format(town=disp))}</h2>")
            body.append(station_table(rows, c))
            trend_out[slug] = {**{d: v for d, v in trend.get(slug, {}).items() if d != today_s}, today_s: {f: round(v, 4) for f, v in med.items()}}
            u = cfg["sym"] + "/L"
            lows = {k: min((fp[0] for s, _ in priced_rows if (fp := fresh_price(s, k, now, cfg))), default=None) for k in ("P95", "DIESEL")}
            title = (x["t_dp"].format(town=disp, d=fmt_price(lows["DIESEL"], cfg), p=fmt_price(lows["P95"], cfg), u=u)
                     if lows["P95"] is not None and lows["DIESEL"] is not None else x["t_priced"].format(town=disp))
            faq = faq_items(c, disp, rows, priced_rows, modified)
            if faq:
                body.append(f"<h2>{escape(x['faq_h'])}</h2>" + "".join(f"<h3>{escape(q)}</h3><p>{escape(a)}</p>" for q, a in faq))
            desc = x["d_priced"].format(town=disp, n=len(priced_rows))
            low = min((fp[0] for s, _ in priced_rows if (fp := fresh_price(s, cfg["cheapest"][0], now, cfg))), default=None)
            hub_rows.append((disp, slug, low))
            town_lows.append((disp, slug, len(priced_rows),
                              min((fp[0] for s, _ in priced_rows if (fp := fresh_price(s, "P95", now, cfg))), default=None),
                              min((fp[0] for s, _ in priced_rows if (fp := fresh_price(s, "DIESEL", now, cfg))), default=None)))
        else:
            near = sorted(((s, haversine_km(t["lat"], t["lon"], float(s["lat"]), float(s["lon"]))) for s, _ in priced_all),
                          key=lambda r: r[1])
            near = [r for r in near if r[1] <= NEARBY_PRICED_KM][:6]
            if not near:
                continue
            body.append(f'<p class="lede">{escape(x["lede_none"].format(total=len(rows), town=disp))}</p>')
            body.append(f"<h2>{escape(x['h_near_priced'])}</h2>")
            body.append(summary_cards(near, c))
            body.append(station_table(near, c, show_town=town_of))
            body.append(f"<h2>{escape(x['h_stations'].format(town=disp))}</h2>")
            body.append(station_table(rows, c))
            body.append(f'<p class="note">{escape(x["note_none"])}</p>')
            title = x["t_none"].format(town=disp)
            desc = x["d_none"].format(town=disp)
            hub_rows.append((disp, slug, None))

        nb = sorted((o for o in towns if o is not t),
                    key=lambda o: haversine_km(t["lat"], t["lon"], o["lat"], o["lon"]))[:8]
        if nb:
            links = "".join(
                f'<li><a href="/{cc}/{o["slug"]}/">{escape(o["display"])}</a> <span class="sub" style="display:inline">'
                f'{haversine_km(t["lat"], t["lon"], o["lat"], o["lon"]):.0f} km · {len(o["rows"])} {escape(x["stns"])}</span></li>' for o in nb)
            body.append(f"<h2>{escape(x['h_nearby'])}</h2><ul class=\"links\">{links}</ul>")

        stations_ld = [{"@type": "GasStation", "name": station_label(s)[0],
                        "geo": {"@type": "GeoCoordinates", "latitude": s["lat"], "longitude": s["lon"]},
                        "address": {"@type": "PostalAddress", "addressLocality": name, "addressCountry": cfg.get("iso", cc.upper())}}
                       for s, _ in rows[:20]]
        ld = [breadcrumb_ld([(x["home"], SITE + "/"), (cfg["hub"], hub_url), (disp, canonical)]),
              {"@context": "https://schema.org", "@type": "ItemList", "name": x["h_stations"].format(town=disp),
               "itemListElement": [{"@type": "ListItem", "position": k + 1, "item": it} for k, it in enumerate(stations_ld)]}]
        if priced_rows and faq:
            ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]})
        d = out / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(
            page(cfg, title, desc, canonical, x["h1"].format(town=disp), "\n".join(body), ld,
                 crumbs_html(lang, [(x["home"], "/"), (cfg["hub"], hub_url), (disp, None)]), modified, foot),
            encoding="utf-8")
        urls.append((canonical, lastmod))

    rk = cfg.get("rank")
    if rk and town_lows:
        def tbl(idx: int) -> str:
            rows_ = sorted((t for t in town_lows if t[idx] is not None), key=lambda t: t[idx])[:30]
            tr = "".join(f'<tr><td>{i}</td><td class="n"><a href="/{cc}/{t[1]}/">{escape(t[0])}</a></td>'
                         f'<td class="p">{escape(money(t[idx], cfg))}</td><td>{t[2]}</td></tr>' for i, t in enumerate(rows_, 1))
            return f'<div class="tw"><table><thead><tr><th>#</th><th>{rk["col"]}</th><th>{cfg["sym"]}/L</th><th>{rk["n"]}</th></tr></thead><tbody>{tr}</tbody></table></div>'
        rurl = f"{SITE}/{cc}/{rk['slug']}/"
        rbody = (f'<p class="lede">{escape(rk["lede"].format(min=MIN_STATIONS))}</p>'
                 f'<h2>{escape(rk["h95"])}</h2>{tbl(3)}<h2>{escape(rk["hdi"])}</h2>{tbl(4)}')
        write_page = page(cfg, rk["title"], rk["desc"], rurl, rk["h1"], rbody,
                          [breadcrumb_ld([(x["home"], SITE + "/"), (cfg["hub"], hub_url), (rk["h1"], rurl)])],
                          crumbs_html(lang, [(x["home"], "/"), (cfg["hub"], hub_url), (rk["h1"], None)]), modified, foot)
        (out / rk["slug"]).mkdir(parents=True, exist_ok=True)
        (out / rk["slug"] / "index.html").write_text(write_page, encoding="utf-8")
        urls.append((rurl, lastmod))

    # hub
    top = []
    labels = dict(cfg["fuels"])
    for fuel in cfg["cheapest"]:
        cheapest = sorted(((fp[0], s) for s in stations if (fp := fresh_price(s, fuel, now, cfg))), key=lambda r: r[0])[:10]
        if cheapest:
            li = "".join(f'<tr><td class="n">{escape(station_label(s)[0])}<span class="sub">{escape(town_of.get(s["id"]) or s.get("city") or "")}</span></td>'
                         f'<td class="p">{escape(money(pr, cfg))}</td></tr>' for pr, s in cheapest)
            top.append(f"<h2>{escape((cfg.get('h_cheapest') or x['h_cheapest']).format(f=labels[fuel]))}</h2><div class=\"tw\"><table><tbody>{li}</tbody></table></div>")
    by_letter: Dict[str, List[str]] = defaultdict(list)
    for disp, slug, low in sorted(hub_rows, key=lambda r: r[0]):
        extra = f' <span class="sub" style="display:inline">{escape(money(low, cfg))}</span>' if low else ""
        by_letter[disp[0].upper()].append(f'<li><a href="/{cc}/{slug}/">{escape(disp)}</a>{extra}</li>')
    towns_html = "".join(f'<h2>{escape(l)}</h2><ul class="links">{"".join(v)}</ul>' for l, v in sorted(by_letter.items()))
    rank_link = f'<p><a href="/{cc}/{cfg["rank"]["slug"]}/">{escape(cfg["rank"]["h1"])} →</a></p>' if cfg.get("rank") and town_lows else ""
    hub_body = f'<p class="lede">{(cfg.get("hub_lede") or x["hub_lede"]).format(n=len(hub_rows))}</p>' + rank_link + "".join(top) + f"<h2>{escape(x['h_find'])}</h2>{towns_html}"
    (out / "index.html").write_text(
        page(cfg, cfg["hub_title"], (cfg.get("hub_desc") or x["hub_desc"]).format(n=len(hub_rows)), hub_url, cfg["hub"], hub_body,
             [breadcrumb_ld([(x["home"], SITE + "/"), (cfg["hub"], hub_url)])],
             crumbs_html(lang, [(x["home"], "/"), (cfg["hub"], None)]), modified, foot),
        encoding="utf-8")

    cutoff = sorted({d for h in trend_out.values() for d in h})[-TREND_DAYS:]
    (out / "trend.json").write_text(json.dumps({"v": 1, "d": {k: {d: v for d, v in h.items() if d in cutoff} for k, h in trend_out.items()}},
                                               separators=(",", ":")), encoding="utf-8")
    write_sitemap(DATA_DIR / f"sitemap-{cc}.xml", urls)
    print(f"seo_pages[{cc}]: {len(urls) - 1} town pages + hub ({len(priced_all)} priced stations)")
    return urls


def write_sitemap(path: Path, urls: List[Tuple[str, str]]) -> None:
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"  <url><loc>{u}</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq></url>" for u, lm in urls]
    sm.append("</urlset>")
    path.write_text("\n".join(sm) + "\n", encoding="utf-8")


def link_alternates(dir_a: Path, dir_b: Path, lang_a: str, lang_b: str, base_a: str, base_b: str) -> int:
    """hreflang pairs for the two Belgian page sets (/be/ Dutch, /be-fr/ French, same stations): only for pages that exist in BOTH sets
    (hub and the towns whose slug is the same), each page also pointing at itself, x-default = the Dutch page."""
    n = 0
    pages = [("", "")] + [(p.name + "/", p.name + "/") for p in dir_a.iterdir() if p.is_dir() and (dir_b / p.name / "index.html").exists()]
    for sub, _ in pages:
        fa, fb = dir_a / sub / "index.html", dir_b / sub / "index.html"
        if not (fa.exists() and fb.exists()):
            continue
        ua, ub = base_a + sub, base_b + sub
        tags = "".join(f'<link rel="alternate" hreflang="{hl}" href="{u}">' + chr(10) for hl, u in ((lang_a, ua), (lang_b, ub), ("x-default", ua)))
        for fp in (fa, fb):
            h = fp.read_text(encoding="utf-8")
            if "hreflang=" in h:
                continue
            h = h.replace('<meta property="og:type"', tags + '<meta property="og:type"', 1)
            fp.write_text(h, encoding="utf-8")
            n += 1
    return n


def main() -> int:
    now = datetime.now(timezone.utc)
    built = []
    for cc, cfg in COUNTRIES.items():
        try:
            if build_country(cc, cfg, now):
                built.append(cc)
        except Exception as e:   # one country must never break the deploy
            print(f"seo_pages[{cc}]: FAILED {type(e).__name__}: {e}", file=sys.stderr)
    if "be" in built and "be-fr" in built:
        link_alternates(DATA_DIR / "be", DATA_DIR / "be-fr", "nl-BE", "fr-BE", f"{SITE}/be/", f"{SITE}/be-fr/")
    idx = ['<?xml version="1.0" encoding="UTF-8"?>', '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    idx += [f"  <sitemap><loc>{SITE}/sitemap-{cc}.xml</loc></sitemap>" for cc in built]
    idx.append("</sitemapindex>")
    (DATA_DIR / "sitemap-seo.xml").write_text("\n".join(idx) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
