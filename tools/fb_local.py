"""Local posts: "cheapest stations within 10 km of <town>" from our own station data.

Aggregate only: the town comes from a rotating list of big towns, from the Page's aggregate follower-city insight, or from a town a
person typed into a comment on our "comment your town" post. Nothing about individuals is looked up or stored.
Countries with source grade D (community estimates) are included but always marked as estimates; prices follow the same freshness rules as the website pages.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import seo_pages as sp  # noqa: E402
from europe_index import NAMES  # noqa: E402

SITE = "https://eurofuelprices.com"
RADIUS_KM = 10
TOP_N = 3
# countries with their own town pages and a source grade we are willing to quote
SUPPORTED = ["de", "ch", "fr", "es", "pt", "dk", "nl", "se", "be", "pl", "it"]   # AT has no city field in its feed. be = Dutch names; French names are tried as be-fr (same data file)
CITIES = [("de", "Hamburg"), ("de", "Berlin"), ("de", "München"), ("de", "Köln"), ("de", "Flensburg"), ("de", "Frankfurt am Main"),
          ("dk", "København"), ("dk", "Aarhus"), ("dk", "Aalborg"), ("dk", "Odense"),
          ("se", "Stockholm"), ("se", "Göteborg"), ("se", "Malmö"), ("se", "Uppsala"), ("se", "Linköping"), ("ch", "Zürich"), ("ch", "Basel"), ("ch", "Bern"),
          ("fr", "Paris"), ("fr", "Lyon"), ("fr", "Marseille"), ("fr", "Strasbourg"),
          ("es", "Madrid"), ("es", "Barcelona"), ("es", "Valencia"), ("es", "Sevilla"),
          ("pt", "Lisboa"), ("pt", "Porto"), ("nl", "Amsterdam"), ("nl", "Rotterdam"), ("nl", "Utrecht"),
          ("be", "Antwerpen"), ("be", "Gent"), ("pl", "Warszawa"), ("pl", "Kraków"), ("pl", "Wrocław"), ("pl", "Gdańsk"), ("it", "Roma"), ("it", "Milano"), ("it", "Napoli"), ("it", "Torino")]
COUNTRY_WORDS = {n.lower(): c for c, n in NAMES.items()}
COUNTRY_WORDS.update({"deutschland": "DE", "österreich": "AT", "oesterreich": "AT", "schweiz": "CH", "suisse": "CH", "españa": "ES", "espana": "ES",
                      "danmark": "DK", "nederland": "NL", "holland": "NL", "italia": "IT", "sverige": "SE", "norge": "NO",
                      "polska": "PL", "belgië": "BE", "belgie": "BE", "belgique": "BE"})


def load_stations(c, fetch, cache=None):
    """Station list of a page-country (be-fr reads be.json). One download per file per run when a cache dict is passed."""
    f = sp.COUNTRIES[c].get("data", c)
    if cache is not None and f in cache:
        return cache[f]
    raw = fetch(f"{SITE}/{f}.json", timeout=120)
    out = json.loads(raw)["stations"] if raw else []
    if cache is not None:
        cache[f] = out
    return out


def km(lat1, lon1, lat2, lon2):
    return sp.haversine_km(lat1, lon1, lat2, lon2)


def find_town(stations, cc, name):
    """Town record (name, lat, lon, rows) for `name` in this country's station list, matched like the website's town pages."""
    cfg = sp.COUNTRIES[cc]
    slug = sp.slugify(sp.clean_city(name, cfg["lang"]), cfg["lang"])
    towns = [t for t in sp.towns_from_city(stations, cfg["lang"]) if len(t["rows"]) >= sp.MIN_STATIONS]
    sp.assign_slugs(towns, cfg["lang"], sp.TXT[cfg["lang"]]["near"])
    for t in sorted(towns, key=lambda t: -len(t["rows"])):
        if t["slug"] == slug or t["base"] == slug:
            return t
    return None


def cheapest_near(stations, cc, town, now=None, radius=RADIUS_KM, top=TOP_N):
    """{fuel_key: [(price, station), ...]} for P95 and DIESEL within `radius` km of the town centre, cheapest first."""
    cfg = sp.COUNTRIES[cc]
    now = now or datetime.now(timezone.utc)
    out = {}
    for fuel in ("P95", "DIESEL"):
        rows = []
        for s in stations:
            try:
                if km(town["lat"], town["lon"], float(s["lat"]), float(s["lon"])) > radius:
                    continue
            except (KeyError, TypeError, ValueError):
                continue
            fp = sp.fresh_price(s, fuel, now, cfg)
            if fp:
                rows.append((fp[0], s))
        out[fuel] = sorted(rows, key=lambda r: r[0])[:top]
    return out


def format_lines(cc, found):
    cfg = sp.COUNTRIES[cc]
    lines = []
    for fuel, label in (("P95", "Petrol 95"), ("DIESEL", "Diesel")):
        rows = found.get(fuel) or []
        if rows:
            items = "; ".join(f"{i}) {sp.station_label(s)[0]}, {sp.station_label(s)[1] or '-'} {sp.money(p, cfg)}" for i, (p, s) in enumerate(rows, 1))
            lines.append(f"{label}: {items}")
    return lines


def local_text(cc, town, found, lead, grade="C"):
    url = f"{SITE}/{cc}/{town['slug']}/"
    note = ("Estimates from community reports, not official prices; check at the pump." if grade == "D"
            else "Prices as listed on our map; check at the pump.")
    return f"{lead}\n" + "\n".join(format_lines(cc, found)) + f"\n{note} More: {url}"


def usable(found):
    return len(found.get("P95") or []) >= 2 and len(found.get("DIESEL") or []) >= 2


def spotlight(fetch, used, today, audience=None, days=30):
    """(text, key) for a rotating town (or a town where our followers are, in aggregate), None if nothing usable."""
    grades = {}
    try:
        meta = json.loads(fetch(SITE + "/meta.json"))
        grades = {c["country"].lower(): c.get("grade") for c in meta.get("countries", [])}
    except Exception:
        return None
    recent = {r.get("key") for r in used if r.get("format") == "spotlight" and (today - datetime.fromisoformat(r["date"]).date()).days < days}
    candidates = []
    for place in (audience or {}):                       # "City, Region, Country" -> aggregate follower cities, biggest first
        parts = [p.strip() for p in place.split(",")]
        cc = COUNTRY_WORDS.get(parts[-1].lower(), "").lower()
        if cc in SUPPORTED and parts[0]:
            candidates.append((cc, parts[0]))
    candidates += [c for c in CITIES if c not in candidates]
    cache = {}
    for cc, name in candidates:
        key = f"{cc}-{sp.slugify(name, sp.COUNTRIES[cc]['lang'])}"
        if key in recent or grades.get(cc) not in ("A", "B", "C", "D"):
            continue
        stations = load_stations(cc, fetch, cache)
        town = find_town(stations, cc, name)
        if not town:
            continue
        found = cheapest_near(stations, cc, town)
        if usable(found):
            return local_text(cc, town, found, f"Cheapest fuel within {RADIUS_KM} km of {town['name']} today:", grades.get(cc)), key
    return None


def match_comment(text, supported=SUPPORTED):
    """Split a comment like 'Hamburg, Germany' into (name, cc or None). Returns None for text that is clearly not a town."""
    t = re.sub(r"[^\w\s,/.\-]", " ", text or "").strip()
    if not t or len(t) > 60 or len(t.split()) > 6:
        return None
    parts = [p.strip() for p in re.split(r"[,/]", t) if p.strip()]
    cc = None
    if len(parts) >= 2 and parts[-1].lower() in COUNTRY_WORDS:
        cc = COUNTRY_WORDS[parts[-1].lower()].lower()
        parts = parts[:-1]
    name = parts[0] if parts else ""
    if cc and cc not in supported:
        return None
    return (name, cc) if name else None


def answer_for(name, cc, fetch, now=None, grades=None, cache=None):
    """Reply text for a comment, or None if the town cannot be found uniquely in a supported country."""
    options = [cc] if cc else SUPPORTED
    hits = []
    for c in options:
        for v in ([c, "be-fr"] if c == "be" else [c]):         # Belgium: Dutch names first, then French names on the same data
            stations = load_stations(v, fetch, cache)
            town = find_town(stations, v, name) if stations else None
            if town:
                hits.append((v, town, stations))
                break
    if len(hits) != 1:
        return None
    c, town, stations = hits[0]
    found = cheapest_near(stations, c, town, now)
    if not usable(found):
        return None
    if grades is None:
        try:
            grades = {x["country"].lower(): x.get("grade") for x in json.loads(fetch(SITE + "/meta.json")).get("countries", [])}
        except Exception:
            grades = {}
    g = sp.COUNTRIES[c].get("data", c)
    if grades and grades.get(g) not in ("A", "B", "C", "D"):
        return None                                          # no usable source grade: say nothing rather than guess
    return local_text(c, town, found, f"Here are the cheapest stations within {RADIUS_KM} km of {town['name']}:", (grades or {}).get(g, "C"))
