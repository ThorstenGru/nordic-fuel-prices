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
SUPPORTED = ["de", "at", "ch", "dk", "se", "no", "fi", "fr", "es", "pt", "nl", "be", "pl", "it"]   # DACH and the Nordics first (Iceland has no city field). be = Dutch names; French names are tried as be-fr (same data file)
CITIES = [("de", "Hamburg"), ("de", "Berlin"), ("de", "München"), ("de", "Köln"), ("de", "Flensburg"), ("de", "Frankfurt am Main"),
          ("dk", "København"), ("dk", "Aarhus"), ("dk", "Aalborg"), ("dk", "Odense"),
          ("se", "Stockholm"), ("se", "Göteborg"), ("se", "Malmö"), ("se", "Uppsala"), ("se", "Linköping"), ("ch", "Zürich"), ("ch", "Basel"), ("ch", "Bern"),
          ("at", "Wien"), ("at", "Graz"), ("at", "Salzburg"), ("at", "Linz"), ("at", "Innsbruck"),
          ("no", "Oslo"), ("no", "Bergen"), ("no", "Trondheim"), ("no", "Stavanger"), ("fi", "Helsinki"), ("fi", "Tampere"), ("fi", "Turku"), ("fi", "Oulu"),
          ("fr", "Paris"), ("fr", "Lyon"), ("fr", "Marseille"), ("fr", "Strasbourg"),
          ("es", "Madrid"), ("es", "Barcelona"), ("es", "Valencia"), ("es", "Sevilla"),
          ("pt", "Lisboa"), ("pt", "Porto"), ("nl", "Amsterdam"), ("nl", "Rotterdam"), ("nl", "Utrecht"),
          ("be", "Antwerpen"), ("be", "Gent"), ("pl", "Warszawa"), ("pl", "Kraków"), ("pl", "Wrocław"), ("pl", "Gdańsk"), ("it", "Roma"), ("it", "Milano"), ("it", "Napoli"), ("it", "Torino")]
COUNTRY_WORDS = {n.lower(): c for c, n in NAMES.items()}
COUNTRY_WORDS.update({"deutschland": "DE", "österreich": "AT", "oesterreich": "AT", "schweiz": "CH", "suisse": "CH", "españa": "ES", "espana": "ES",
                      "danmark": "DK", "nederland": "NL", "holland": "NL", "italia": "IT", "sverige": "SE", "norge": "NO",
                      "polska": "PL", "suomi": "FI", "finnland": "FI", "noreg": "NO", "norwegen": "NO", "schweden": "SE", "dänemark": "DK", "danemark": "DK", "belgië": "BE", "belgie": "BE", "belgique": "BE"})


# Reply language (2026-11-16): the bot answers in the language of the comment. The language is read from the country word the person wrote
# in their own language ("Wien, Österreich" -> German); an English country name or no country gives English. Unknown languages fall back to English.
NATIVE_WORDS = {
    "de": ["deutschland", "österreich", "oesterreich", "schweiz", "schweden", "dänemark", "norwegen", "finnland", "frankreich", "spanien", "italien", "polen", "niederlande", "belgien"],
    "sv": ["sverige"], "da": ["danmark"], "nb": ["norge", "noreg"], "fi": ["suomi"], "es": ["españa", "espana"], "nl": ["nederland", "belgië", "belgie"],
    "fr": ["suisse", "belgique", "danemark"],
}
REPLY = {
    "en": dict(lead="Here are the cheapest stations within {km} km of {town}:", p95="Petrol 95", diesel="Diesel", ok="Prices as listed on our map; check at the pump.",
               est="Estimates from community reports, not official prices; check at the pump.", chain="* the same price at many stations of this chain, probably its list price.",
               more="More:", another="Another town? Just comment it."),
    "de": dict(lead="Hier sind die günstigsten Tankstellen im Umkreis von {km} km um {town}:", p95="Benzin 95", diesel="Diesel", ok="Preise wie auf unserer Karte; bitte an der Zapfsäule prüfen.",
               est="Schätzungen aus Community-Meldungen, keine amtlichen Preise; bitte an der Zapfsäule prüfen.", chain="* derselbe Preis an vielen Stationen dieser Kette, vermutlich der Listenpreis.",
               more="Mehr:", another="Anderer Ort? Einfach kommentieren."),
    "sv": dict(lead="Här är de billigaste stationerna inom {km} km från {town}:", p95="Bensin 95", diesel="Diesel", ok="Priser som på vår karta; kontrollera vid pumpen.",
               est="Uppskattningar från användarrapporter, inte officiella priser; kontrollera vid pumpen.", chain="* samma pris på många stationer i kedjan, troligen listpriset.",
               more="Mer:", another="En annan ort? Kommentera bara."),
    "da": dict(lead="Her er de billigste tankstationer inden for {km} km fra {town}:", p95="Benzin 95", diesel="Diesel", ok="Priser som på vores kort; tjek ved pumpen.",
               est="Skøn fra brugerrapporter, ikke officielle priser; tjek ved pumpen.", chain="* samme pris på mange stationer i kæden, sandsynligvis listeprisen.",
               more="Mere:", another="En anden by? Skriv den bare."),
    "nb": dict(lead="Her er de billigste stasjonene innen {km} km fra {town}:", p95="Bensin 95", diesel="Diesel", ok="Priser som på kartet vårt; sjekk ved pumpen.",
               est="Anslag fra brukerrapporter, ikke offisielle priser; sjekk ved pumpen.", chain="* samme pris på mange stasjoner i kjeden, trolig listeprisen.",
               more="Mer:", another="Et annet sted? Bare kommenter."),
    "fi": dict(lead="Halvimmat asemat {km} km säteellä paikasta {town}:", p95="Bensiini 95", diesel="Diesel", ok="Hinnat kuten kartallamme; tarkista pumpulta.",
               est="Arvioita käyttäjäilmoituksista, ei virallisia hintoja; tarkista pumpulta.", chain="* sama hinta monella ketjun asemalla, luultavasti listahinta.",
               more="Lisää:", another="Toinen paikkakunta? Kommentoi vain."),
    "fr": dict(lead="Voici les stations les moins chères dans un rayon de {km} km autour de {town} :", p95="Sans plomb 95", diesel="Gazole", ok="Prix comme sur notre carte ; vérifiez à la pompe.",
               est="Estimations issues de signalements d’utilisateurs, pas des prix officiels ; vérifiez à la pompe.", chain="* même prix dans de nombreuses stations de cette enseigne, probablement le prix catalogue.",
               more="Plus :", another="Une autre ville ? Commentez-la."),
    "es": dict(lead="Estas son las gasolineras más baratas en {km} km alrededor de {town}:", p95="Gasolina 95", diesel="Diésel", ok="Precios como en nuestro mapa; comprueba en el surtidor.",
               est="Estimaciones de avisos de usuarios, no precios oficiales; comprueba en el surtidor.", chain="* el mismo precio en muchas estaciones de esta cadena, probablemente su precio de lista.",
               more="Más:", another="¿Otra localidad? Solo coméntala."),
    "nl": dict(lead="Dit zijn de goedkoopste tankstations binnen {km} km van {town}:", p95="Euro 95", diesel="Diesel", ok="Prijzen zoals op onze kaart; controleer bij de pomp.",
               est="Schattingen uit meldingen van gebruikers, geen officiële prijzen; controleer bij de pomp.", chain="* dezelfde prijs bij veel stations van deze keten, waarschijnlijk de lijstprijs.",
               more="Meer:", another="Een andere plaats? Reageer maar."),
}


def comment_lang(text):
    """Language code (a key of REPLY) for a comment: the language of the country word the person used; English otherwise."""
    words = {w.strip().lower() for w in re.split(r"[,/]", text or "") if w.strip()}
    for lang, native in NATIVE_WORDS.items():
        if words & set(native):
            return lang
    return "en"



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


def format_lines(cc, found, lang="en"):
    cfg = sp.COUNTRIES[cc]
    lines = []
    R = REPLY.get(lang) or REPLY["en"]
    for fuel, label in (("P95", R["p95"]), ("DIESEL", R["diesel"])):
        rows = found.get(fuel) or []
        if rows:
            items = "; ".join(f"{i}) {sp.station_label(s)[0]}, {sp.station_label(s)[1] or '-'} {sp.money(p, cfg)}{'*' if s.get('chain_price') else ''}" for i, (p, s) in enumerate(rows, 1))
            lines.append(f"{label}: {items}")
    return lines


def local_text(cc, town, found, lead, grade="C", lang="en"):
    R = REPLY.get(lang) or REPLY["en"]
    url = SITE + "/" if sp.COUNTRIES[cc].get("bot_only") else f"{SITE}/{cc}/{town['slug']}/"   # bot-only countries have no town page: the live map
    chain = any(s.get("chain_price") for rows in found.values() for _, s in rows)
    note = R["est"] if grade == "D" else R["ok"]
    if chain:
        note = R["chain"] + " " + note
    return f"{lead}\n" + "\n".join(format_lines(cc, found, lang)) + f"\n{note} {R['more']} {url}"


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
    recent = {r.get("key") for r in used if str(r.get("format", "")).startswith("spotlight") and (today - datetime.fromisoformat(r["date"]).date()).days < days}
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


def answer_for(name, cc, fetch, now=None, grades=None, cache=None, lang="en"):
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
    R = REPLY.get(lang) or REPLY["en"]
    return local_text(c, town, found, R["lead"].format(km=RADIUS_KM, town=town["name"]), (grades or {}).get(g, "C"), lang) + chr(10) + R["another"]
