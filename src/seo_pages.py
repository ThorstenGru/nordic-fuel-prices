"""Static SEO pages per country: a hub (/<cc>/) and one page per town (/<cc>/<town>/).

Runs after ``main.py`` in the scrape workflow and writes plain, JS-free HTML into ``data/`` so the
pages are crawlable and fast. Targets local-intent queries ("bensinpriser Växjö", "Spritpreise
Wien", "prix carburant Lyon") — see docs/ROADMAP.md, experiment E3.

Countries (COUNTRIES below): SE (sv), AT (de), FR (fr) are live; DE and CH (de) are built but GATED:
their feed currently comes from the unofficial ANWB API, which the roadmap flags as a licence /
cease-and-desist risk. A country whose ``meta.source`` mentions "anwb" is skipped unless
SEO_INCLUDE_GATED=1 (local testing). The moment DE switches to a licensed source (Tankerkönig key,
roadmap D3) its pages build automatically.

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
INCLUDE_GATED = os.environ.get("SEO_INCLUDE_GATED") == "1"

COUNTRIES: Dict[str, Dict[str, Any]] = {
    "se": dict(lang="sv", currency="SEK", sym="kr", mode="places", ts_kind="snapshot", fallback_nearby=True,
               hub="Bensinpriser Sverige", hub_title="Bensinpriser Sverige idag – billigaste bensin & diesel",
               fuels=[("E10", "Bensin 95"), ("E5", "Bensin 98"), ("DIESEL", "Diesel"), ("E85", "E85")],
               cheapest=("E10", "DIESEL"), src="bensinpriser.nu", osm=True),
    "at": dict(lang="de", currency="EUR", sym="€", mode="places", ts_kind="fetched", fallback_nearby=False,
               hub="Spritpreise Österreich", hub_title="Spritpreise Österreich aktuell – günstig tanken",
               fuels=[("E5", "Super 95"), ("DIESEL", "Diesel"), ("LPG", "Autogas (LPG)")],
               cheapest=("E5", "DIESEL"), src="E-Control Spritpreisrechner", osm=True,
               nation="Österreich-Median"),
    "de": dict(lang="de", currency="EUR", sym="€", mode="city", ts_kind="fetched", fallback_nearby=False,
               hub="Spritpreise Deutschland", hub_title="Spritpreise Deutschland aktuell – günstig tanken",
               fuels=[("E10", "Super E10"), ("E5", "Super E5"), ("DIESEL", "Diesel"), ("LPG", "Autogas (LPG)")],
               cheapest=("E10", "DIESEL"), src="Tankerkönig / MTS-K", osm=False, nation="Deutschland-Median"),
    "ch": dict(lang="de", currency="CHF", sym="CHF", mode="city", ts_kind="fetched", fallback_nearby=False,
               hub="Benzinpreise Schweiz", hub_title="Benzinpreise Schweiz aktuell – günstig tanken",
               fuels=[("E10", "Bleifrei 95 (E10)"), ("E5", "Bleifrei 95/98 (E5)"), ("DIESEL", "Diesel"), ("LPG", "Autogas (LPG)")],
               cheapest=("E10", "DIESEL"), src="Community", osm=False, nation="Schweiz-Median"),
    "fr": dict(lang="fr", currency="EUR", sym="€", mode="city", ts_kind="price", fallback_nearby=False, max_age_h=336,
               hub="Prix des carburants en France", hub_title="Prix des carburants en France – le moins cher aujourd’hui",
               fuels=[("E10", "SP95-E10"), ("E5", "SP95 / SP98 (E5)"), ("DIESEL", "Gazole"), ("E85", "E85 (superéthanol)"), ("LPG", "GPLc")],
               cheapest=("E10", "DIESEL"), src="prix-carburants.gouv.fr (data.economie.gouv.fr)", osm=False,
               nation="médiane nationale"),
}

MONTHS = {
    "sv": ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"],
    "de": ["Jan.", "Feb.", "Mär.", "Apr.", "Mai", "Jun.", "Jul.", "Aug.", "Sep.", "Okt.", "Nov.", "Dez."],
    "fr": ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
}

TXT: Dict[str, Dict[str, str]] = {
    "sv": dict(
        locale="sv_SE", home="Hem", map="Öppna kartan →", crumbs="Brödsmulor",
        cheapest="Billigaste {f}", vs="{d} kr mot riksmedian",
        lede="Aktuella priser vid {n} av {total} bensinstationer i och runt {town}, med billigast först. Priserna rapporteras av användare och stationsägare.",
        lede_none="Vi känner till {total} bensinstationer i och runt {town}, men ingen har rapporterat ett aktuellt pris ännu. Här är stationerna och de närmaste stationerna med rapporterade priser.",
        h_stations="Bensinstationer i {town}", h_near_priced="Närmaste stationer med rapporterade priser",
        h_nearby="Bensinpriser i närliggande orter", h1="Bensinpriser i {town}",
        t_priced="Bensinpriser {town} idag – bensin & diesel", t_none="Bensinstationer i {town} – priser i närheten",
        d_priced="Billigaste bensin och diesel i {town} idag. Jämför priser på {n} stationer – uppdateras löpande.",
        d_none="Bensinstationer i {town}: adresser och närmaste rapporterade bensin- och dieselpriser.",
        th_station="Station", km_from="ca {d} km från centrum", central="centralt", km="ca {d} km", near="nära",
        note_none="Bensinpriser i Sverige saknar lagstadgad rapportering, så täckningen bygger på frivilliga rapporter. Hjälp gärna till genom att rapportera pris på bensinpriser.nu.",
        hub_lede="Bensinpriser och bensinstationer i {n} orter i Sverige. Välj din ort för billigaste bensin, diesel och E85 i närheten – eller öppna <a href=\"/\">live-kartan</a>.",
        h_cheapest="Billigaste {f} i Sverige just nu", h_find="Hitta din ort",
        hub_desc="Jämför bensinpriser i {n} svenska orter. Billigaste bensin 95, diesel och E85 – uppdateras löpande.",
        th_when={"snapshot": "Källdata", "fetched": "Hämtad", "price": "Uppdaterad"},
        foot_ts={"snapshot": "Tiden i tabellen är när källans data senast uppdaterades – inte när priset ändrades vid stationen.",
                 "fetched": "Tiden är när vi hämtade priset; källan anger ingen pristid.",
                 "price": "Tiden är när priset senast ändrades enligt källan."},
        foot_src="Priser rapporteras av användare och stationsägare via bensinpriser.nu (källklass D, community) och kan vara inaktuella – kontrollera alltid vid pump.",
        foot_grades="Så graderar vi datakällor", foot_osm="Stationsplatser och ortnamn ©", foot_osm_who="OpenStreetMap-bidragsgivare",
        foot_upd="Senast uppdaterad", ad="Priser", dash_crumb="Brödsmulor"),
    "de": dict(
        locale="de_DE", home="Startseite", map="Zur Karte →", crumbs="Brotkrumen",
        cheapest="Günstigster {f}", vs="{d} {sym} ggü. {nation}",
        lede="Aktuelle Spritpreise an {n} von {total} Tankstellen in und um {town} – die günstigsten zuerst.",
        lede_none="", h_stations="Tankstellen in {town}", h_near_priced="", h_nearby="Spritpreise in der Umgebung",
        h1="Spritpreise in {town}", t_priced="Spritpreise {town} aktuell – Benzin & Diesel",
        t_none="", d_priced="Günstigster Sprit in {town}: aktuelle Benzin- und Dieselpreise an {n} Tankstellen im Vergleich.",
        d_none="", th_station="Tankstelle", km_from="ca. {d} km vom Zentrum", central="zentral", km="ca. {d} km", near="bei",
        note_none="", hub_lede="Spritpreise und Tankstellen in {n} Orten. Wählen Sie Ihren Ort für die günstigsten Preise für Benzin und Diesel in der Nähe – oder öffnen Sie die <a href=\"/\">Live-Karte</a>.",
        h_cheapest="Günstigster {f} – aktuell", h_find="Ort finden",
        hub_desc="Spritpreise im Vergleich: aktuelle Benzin- und Dieselpreise in {n} Orten.",
        th_when={"snapshot": "Quelldaten", "fetched": "Abgerufen", "price": "Aktualisiert"},
        foot_ts={"snapshot": "Die Zeit ist der Stand der Quelldaten – nicht der Zeitpunkt der Preisänderung an der Tankstelle.",
                 "fetched": "Die Zeit ist der Zeitpunkt unseres Abrufs; die Quelle liefert keinen Preiszeitpunkt.",
                 "price": "Die Zeit ist die letzte Preisänderung laut Quelle."},
        foot_src="Quelle: {src}. Preise können abweichen – bitte vor Ort prüfen.",
        foot_grades="So bewerten wir Datenquellen", foot_osm="Ortsnamen ©", foot_osm_who="OpenStreetMap-Mitwirkende",
        foot_upd="Zuletzt aktualisiert", ad=""),
    "fr": dict(
        locale="fr_FR", home="Accueil", map="Ouvrir la carte →", crumbs="Fil d’Ariane",
        cheapest="{f} le moins cher", vs="{d} {sym} vs {nation}",
        lede="Prix actuels dans {n} stations-service sur {total} à {town} et aux alentours, les moins chères en premier.",
        lede_none="", h_stations="Stations-service à {town}", h_near_priced="", h_nearby="Prix des carburants à proximité",
        h1="Prix des carburants à {town}", t_priced="Prix carburant {town} aujourd’hui – gazole, SP95-E10",
        t_none="", d_priced="Carburant le moins cher à {town} : comparez les prix du gazole et du SP95-E10 dans {n} stations-service.",
        d_none="", th_station="Station", km_from="à env. {d} km du centre", central="centre", km="à env. {d} km", near="près de",
        note_none="", hub_lede="Prix des carburants et stations-service dans {n} communes. Choisissez votre commune pour trouver le gazole et l’essence les moins chers près de chez vous – ou ouvrez la <a href=\"/\">carte en direct</a>.",
        h_cheapest="{f} le moins cher en France", h_find="Trouver votre commune",
        hub_desc="Comparez les prix des carburants dans {n} communes françaises : gazole, SP95-E10, SP98, E85, GPL.",
        th_when={"snapshot": "Données source", "fetched": "Relevé", "price": "Mis à jour"},
        foot_ts={"snapshot": "L’heure indique la mise à jour des données de la source, pas le moment où le prix a changé en station.",
                 "fetched": "L’heure est celle de notre relevé ; la source ne fournit pas d’horodatage du prix.",
                 "price": "L’heure est celle de la dernière modification du prix selon la source."},
        foot_src="Source : {src}, données ouvertes sous Licence Ouverte 2.0 (Etalab). Les prix peuvent différer en station.",
        foot_grades="Comment nous évaluons les sources", foot_osm="Noms de lieux ©", foot_osm_who="contributeurs d’OpenStreetMap",
        foot_upd="Dernière mise à jour", ad=""),
}


# ── helpers ──────────────────────────────────────────────────────────────────

def slugify(name: str, lang: str) -> str:
    rep = {"sv": {"å": "a", "ä": "a", "ö": "o"}, "de": {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}, "fr": {"œ": "oe", "æ": "ae"}}[lang]
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


def to_local(dt: datetime) -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return dt.astimezone(ZoneInfo("Europe/Paris"))   # CET/CEST: same as SE/DE/AT/CH/FR
    except Exception:
        return dt


def fmt_when(dt: Optional[datetime], lang: str) -> str:
    if not dt:
        return "–"
    d = to_local(dt)
    dot = "." if lang == "de" else ""
    return f"{d.day}{dot} {MONTHS[lang][d.month - 1]} {d.hour:02d}:{d.minute:02d}"


def fmt_price(v: float, cfg: Dict) -> str:
    s = f"{v:.2f}" if cfg["currency"] in ("SEK",) else f"{v:.3f}"
    return s.replace(".", ",")


def money(v: float, cfg: Dict) -> str:
    return f"{fmt_price(v, cfg)} {cfg['sym']}"


def fresh_price(station: Dict[str, Any], fuel: str, now: datetime, cfg: Dict) -> Optional[Tuple[float, Optional[datetime]]]:
    best = None
    for p in station.get("prices") or []:
        if p.get("fuel_type") != fuel or p.get("currency") != cfg["currency"] or p.get("unit") != "L":
            continue
        try:
            price = float(p["price"])
        except (KeyError, TypeError, ValueError):
            continue
        when = parse_iso(p.get("updated_at"))
        if when and (now - when).total_seconds() > cfg.get("max_age_h", MAX_PRICE_AGE_H) * 3600:
            continue
        if best is None or price < best[0]:
            best = (price, when)
    return best


def has_price(s: Dict, now: datetime, cfg: Dict) -> bool:
    return any(fresh_price(s, f, now, cfg) for f, _ in cfg["fuels"])


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


def clean_city(name: str) -> str:
    n = re.sub(r"\s+", " ", (name or "").strip())
    n = re.sub(r"\s+\d{1,2}(er|e|ème)?\s*(arrondissement)?$", "", n, flags=re.I)   # "Paris 15e" -> "Paris"
    if n.isupper() or n.islower():
        n = n.title()
    return n


def towns_from_city(stations: List[Dict]) -> List[Town]:
    groups: Dict[str, List[Dict]] = defaultdict(list)
    spelling: Dict[str, Counter] = defaultdict(Counter)
    for s in stations:
        c = clean_city(s.get("city") or "")
        if not c or "lat" not in s:
            continue
        key = unicodedata.normalize("NFKC", c).casefold()
        groups[key].append(s)
        spelling[key][c] += 1
    towns: List[Town] = []
    for key, sts in groups.items():
        name = spelling[key].most_common(1)[0][0]
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
:root { --bg:#F4F5F7; --surf:#FFFFFF; --border:#E6E8EB; --text:#16181D; --text2:#6B7280; --text3:#9AA1AC; --blue:#0F766E; --green:#16A34A; }
@media (prefers-color-scheme: dark) { :root { --bg:#12151A; --surf:#1B1F26; --border:#2A2F38; --text:#ECEEF1; --text2:#A0A7B3; --text3:#7B8390; --blue:#4FD1C5; --green:#4ADE80; } }
*, *::before, *::after { box-sizing:border-box; }
body { margin:0 auto; max-width:760px; padding:0 16px 60px; font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:var(--bg); color:var(--text); line-height:1.6; font-size:16px; }
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
    ld = "\n".join(f'<script type="application/ld+json">{json.dumps(o, ensure_ascii=False)}</script>' for o in jsonld)
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
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none';">
<link rel="icon" type="image/svg+xml" href="/icon.svg">
{ld}
<style>{CSS}</style>
</head>
<body>
<header><a class="logo" href="/">⛽ EuroFuelPrices</a><a class="back" href="/">{escape(x['map'])}</a></header>
{crumbs}
<h1>{escape(h1)}</h1>
{body}
<footer>
<p>{foot}</p>
<p>{escape(x['foot_upd'])}: {escape(modified)}.</p>
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
    name = (s.get("brand") or s.get("name") or "").strip() or "⛽"
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


def summary_cards(rows: List[Tuple[Dict, float]], c: Ctx) -> str:
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
        cards.append(f'<div class="card"><div class="k">{escape(x["cheapest"].format(f=label))}</div>'
                     f'<div class="v">{escape(money(low, cfg))}</div><div class="s">{escape(station_label(st)[0])}{escape(diff)}</div></div>')
    return f'<div class="cards">{"".join(cards)}</div>' if cards else ""


def footer_html(c: Ctx) -> str:
    cfg, x = c.cfg, c.x
    parts = [escape(x["foot_src"].format(src=cfg["src"])), escape(x["foot_ts"][cfg["ts_kind"]]),
             f'<a href="/about.html">{escape(x["foot_grades"])}</a>.']
    if cfg["osm"]:
        parts.append(f'{escape(x["foot_osm"])} <a href="https://www.openstreetmap.org/copyright">{escape(x["foot_osm_who"])}</a>.')
    return " ".join(parts)


# ── build one country ────────────────────────────────────────────────────────

def build_country(cc: str, cfg: Dict, now: datetime) -> Optional[List[Tuple[str, str]]]:
    f = DATA_DIR / f"{cc}.json"
    if not f.exists():
        print(f"seo_pages[{cc}]: {f.name} missing - skipped")
        return None
    doc = json.loads(f.read_text(encoding="utf-8"))
    meta, stations = doc.get("meta") or {}, doc.get("stations") or []
    if "anwb" in (meta.get("source") or "").lower() and not INCLUDE_GATED:
        print(f"seo_pages[{cc}]: GATED (source {meta.get('source')!r} is unofficial) - skipped")
        return None
    if meta.get("status") == "stale":
        print(f"seo_pages[{cc}]: source stale - skipped")
        return None
    lang, x = cfg["lang"], TXT[cfg["lang"]]
    fetched = parse_iso(meta.get("fetched_at")) or now
    c = Ctx(cc, cfg, now, fetched, {})
    for fuel, _ in cfg["fuels"]:
        vals = [fp[0] for s in stations if (fp := fresh_price(s, fuel, now, cfg))]
        if len(vals) >= 5:
            c.national[fuel] = statistics.median(vals)

    towns = towns_from_places(stations, cc) if cfg["mode"] == "places" else towns_from_city(stations)
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
    foot = footer_html(c)
    urls = [(hub_url, lastmod)]
    hub_rows = []

    for t in sorted(towns, key=lambda t: t["name"]):
        name, disp, slug, rows = t["name"], t["display"], t["slug"], t["rows"]
        canonical = f"{SITE}/{cc}/{slug}/"
        priced_rows = [(s, d) for s, d in rows if has_price(s, now, cfg)]
        body = []
        if priced_rows:
            body.append(f'<p class="lede">{escape(x["lede"].format(n=len(priced_rows), total=len(rows), town=disp))}</p>')
            body.append(summary_cards(rows, c))
            body.append(f"<h2>{escape(x['h_stations'].format(town=disp))}</h2>")
            body.append(station_table(rows, c))
            title = x["t_priced"].format(town=disp)
            desc = x["d_priced"].format(town=disp, n=len(priced_rows))
            low = min((fp[0] for s, _ in priced_rows if (fp := fresh_price(s, cfg["cheapest"][0], now, cfg))), default=None)
            hub_rows.append((disp, slug, low))
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
            links = "".join(f'<li><a href="/{cc}/{o["slug"]}/">{escape(o["display"])}</a></li>' for o in nb)
            body.append(f"<h2>{escape(x['h_nearby'])}</h2><ul class=\"links\">{links}</ul>")

        stations_ld = [{"@type": "GasStation", "name": station_label(s)[0],
                        "geo": {"@type": "GeoCoordinates", "latitude": s["lat"], "longitude": s["lon"]},
                        "address": {"@type": "PostalAddress", "addressLocality": name, "addressCountry": cc.upper()}}
                       for s, _ in rows[:20]]
        ld = [breadcrumb_ld([(x["home"], SITE + "/"), (cfg["hub"], hub_url), (disp, canonical)]),
              {"@context": "https://schema.org", "@type": "ItemList", "name": x["h_stations"].format(town=disp),
               "itemListElement": [{"@type": "ListItem", "position": k + 1, "item": it} for k, it in enumerate(stations_ld)]}]
        d = out / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(
            page(cfg, title, desc, canonical, x["h1"].format(town=disp), "\n".join(body), ld,
                 crumbs_html(lang, [(x["home"], "/"), (cfg["hub"], hub_url), (disp, None)]), modified, foot),
            encoding="utf-8")
        urls.append((canonical, lastmod))

    # hub
    top = []
    labels = dict(cfg["fuels"])
    for fuel in cfg["cheapest"]:
        cheapest = sorted(((fp[0], s) for s in stations if (fp := fresh_price(s, fuel, now, cfg))), key=lambda r: r[0])[:10]
        if cheapest:
            li = "".join(f'<tr><td class="n">{escape(station_label(s)[0])}<span class="sub">{escape(town_of.get(s["id"]) or s.get("city") or "")}</span></td>'
                         f'<td class="p">{escape(money(pr, cfg))}</td></tr>' for pr, s in cheapest)
            top.append(f"<h2>{escape(x['h_cheapest'].format(f=labels[fuel]))}</h2><div class=\"tw\"><table><tbody>{li}</tbody></table></div>")
    by_letter: Dict[str, List[str]] = defaultdict(list)
    for disp, slug, low in sorted(hub_rows, key=lambda r: r[0]):
        extra = f' <span class="sub" style="display:inline">{escape(money(low, cfg))}</span>' if low else ""
        by_letter[disp[0].upper()].append(f'<li><a href="/{cc}/{slug}/">{escape(disp)}</a>{extra}</li>')
    towns_html = "".join(f'<h2>{escape(l)}</h2><ul class="links">{"".join(v)}</ul>' for l, v in sorted(by_letter.items()))
    hub_body = f'<p class="lede">{x["hub_lede"].format(n=len(hub_rows))}</p>' + "".join(top) + f"<h2>{escape(x['h_find'])}</h2>{towns_html}"
    (out / "index.html").write_text(
        page(cfg, cfg["hub_title"], x["hub_desc"].format(n=len(hub_rows)), hub_url, cfg["hub"], hub_body,
             [breadcrumb_ld([(x["home"], SITE + "/"), (cfg["hub"], hub_url)])],
             crumbs_html(lang, [(x["home"], "/"), (cfg["hub"], None)]), modified, foot),
        encoding="utf-8")

    write_sitemap(DATA_DIR / f"sitemap-{cc}.xml", urls)
    print(f"seo_pages[{cc}]: {len(urls) - 1} town pages + hub ({len(priced_all)} priced stations)")
    return urls


def write_sitemap(path: Path, urls: List[Tuple[str, str]]) -> None:
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"  <url><loc>{u}</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq></url>" for u, lm in urls]
    sm.append("</urlset>")
    path.write_text("\n".join(sm) + "\n", encoding="utf-8")


def main() -> int:
    now = datetime.now(timezone.utc)
    built = []
    for cc, cfg in COUNTRIES.items():
        try:
            if build_country(cc, cfg, now):
                built.append(cc)
        except Exception as e:   # one country must never break the deploy
            print(f"seo_pages[{cc}]: FAILED {type(e).__name__}: {e}", file=sys.stderr)
    idx = ['<?xml version="1.0" encoding="UTF-8"?>', '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    idx += [f"  <sitemap><loc>{SITE}/sitemap-{cc}.xml</loc></sitemap>" for cc in built]
    idx.append("</sitemapindex>")
    (DATA_DIR / "sitemap-seo.xml").write_text("\n".join(idx) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
