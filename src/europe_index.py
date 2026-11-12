"""Europe fuel price index + border-comparison pages + open aggregate data.

Runs after ``seo_pages.py`` in the scrape workflow. Reads ``data/meta.json`` (per-country EUR medians,
``stats_eur``) and writes, into ``data/``:
  europe/index.html                      ranking of countries (petrol 95 / diesel) + weekly change + border gaps
  europe/<a>-vs-<b>/index.html           one page per border pair ("Fuel prices Sweden vs Denmark")
  open-data/national-averages.{json,csv} the same numbers as downloadable data (attribution requested)
  index_history.json                     one snapshot per day (read back from the live site, appended here)
  sitemap-europe.xml                     and an entry for it in sitemap-seo.xml

Only country MEDIANS are published here (never raw station rows). A country is listed only when its
status is "ok", its data is < 36 h old and it has >= MIN_N priced stations for that fuel. Every row shows
the source grade so a grade-D/C median is never presented as equal to an official one.
"""

import csv
import io
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from seo_pages import CSS, DATA_DIR, SITE, breadcrumb_ld, write_sitemap  # noqa: E402

MIN_N = 30
MAX_AGE_H = 36
HISTORY_URL = SITE + "/index_history.json"
HISTORY_DAYS = 400
FUELS = [("p95", "Petrol 95"), ("diesel", "Diesel")]
FILL_L = 50

NAMES = {
    "AD": "Andorra", "AL": "Albania", "AT": "Austria", "BA": "Bosnia and Herzegovina", "BE": "Belgium",
    "BG": "Bulgaria", "CH": "Switzerland", "CY": "Cyprus", "CZ": "Czechia", "DE": "Germany", "DK": "Denmark",
    "EE": "Estonia", "ES": "Spain", "FI": "Finland", "FR": "France", "GB": "United Kingdom", "GR": "Greece",
    "HR": "Croatia", "HU": "Hungary", "IE": "Ireland", "IS": "Iceland", "IT": "Italy", "LI": "Liechtenstein",
    "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia", "MC": "Monaco", "MD": "Moldova", "ME": "Montenegro",
    "MK": "North Macedonia", "MT": "Malta", "NL": "Netherlands", "NO": "Norway", "PL": "Poland", "PT": "Portugal",
    "RO": "Romania", "RS": "Serbia", "SE": "Sweden", "SI": "Slovenia", "SK": "Slovakia", "SM": "San Marino",
    "XK": "Kosovo",
}
# Real land/short-sea borders where people actually fill up across the line.
BORDER_PAIRS = [("SE", "DK"), ("DK", "DE"), ("NO", "SE"), ("DE", "PL"), ("DE", "NL"), ("DE", "AT"), ("DE", "CZ"),
                ("DE", "FR"), ("DE", "LU"), ("DE", "CH"), ("FR", "ES"), ("FR", "BE"), ("ES", "PT"), ("AT", "CZ"),
                ("AT", "SI"), ("FI", "EE"), ("IT", "SI"), ("IT", "CH"), ("HU", "SK"), ("PL", "CZ"),
                ("BE", "NL"), ("BE", "LU"), ("BE", "DE"), ("FR", "LU"), ("FR", "CH"), ("FR", "IT"), ("AT", "CH"), ("AT", "IT"),
                ("AT", "SK"), ("AT", "HU"), ("PL", "SK"), ("PL", "LT"), ("LT", "LV"), ("LV", "EE"), ("FI", "SE"), ("FI", "NO"),
                ("HR", "SI"), ("HR", "HU"), ("RO", "HU"), ("BG", "RO"), ("GR", "BG"), ("ES", "AD"), ("FR", "AD")]


def slug(cc: str) -> str:
    return NAMES[cc].lower().replace(" ", "-")


def pair_slug(a: str, b: str) -> str:
    return f"fuel-prices-{slug(a)}-vs-{slug(b)}"


def parse_iso(s: Optional[str]) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat((s or "").replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def eligible(meta: Dict[str, Any], now: datetime) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """{cc: {fuel: {"median", "n", "grade", "source"}}} for countries that pass the trust filter."""
    out: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for c in meta.get("countries") or []:
        cc = (c.get("country") or "").upper()
        if cc not in NAMES or c.get("status") != "ok":
            continue
        fetched = parse_iso(c.get("fetched_at"))
        if not fetched or now - fetched > timedelta(hours=MAX_AGE_H):
            continue
        st = c.get("stats_eur") or {}
        for fuel, _ in FUELS:
            s = st.get(fuel) or {}
            if s.get("n", 0) >= MIN_N and s.get("median"):
                out.setdefault(cc, {})[fuel] = dict(median=round(float(s["median"]), 3), n=int(s["n"]),
                                                    grade=c.get("grade") or "?", source=c.get("source") or "")
    return out


def load_history() -> List[Dict[str, Any]]:
    try:
        with urllib.request.urlopen(HISTORY_URL, timeout=20) as r:
            h = json.loads(r.read().decode("utf-8"))
        return h if isinstance(h, list) else []
    except Exception as e:   # first run, offline test, 404: start empty
        print(f"europe_index: no history ({type(e).__name__})")
        return []


def update_history(hist: List[Dict[str, Any]], elig: Dict[str, Any], today: str) -> List[Dict[str, Any]]:
    snap = {"date": today, **{f: {cc: v[f]["median"] for cc, v in elig.items() if f in v} for f, _ in FUELS}}
    hist = [h for h in hist if h.get("date") != today] + [snap]
    return sorted(hist, key=lambda h: h["date"])[-HISTORY_DAYS:]


def change_7d_value(hist: List[Dict[str, Any]], today: str, fuel: str, cc: str, now_val: float) -> Optional[float]:
    t = datetime.fromisoformat(today)
    best = None
    for h in hist:
        age = (t - datetime.fromisoformat(h["date"])).days
        if 5 <= age <= 10 and cc in (h.get(fuel) or {}):
            if best is None or abs(age - 7) < abs(best[0] - 7):
                best = (age, h[fuel][cc])
    return None if best is None else round(now_val - best[1], 3)


def eur(v: float) -> str:
    return f"{v:.3f}"



def pil_font(size: int, bold: bool = True):
    """DejaVu (Linux runner) or Arial (Windows), else Pillow's built-in font. Shared by the share cards and the weekly video."""
    from PIL import ImageFont
    for name in (("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"), "arialbd.ttf" if bold else "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def make_card(path: Path, title: str, line1: str, line2: str = "") -> bool:
    """1200x630 share picture for og:image. Returns False (and writes nothing) if Pillow/fonts are unavailable."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False

    font = pil_font

    img = Image.new("RGB", (1200, 630), "#0E1A29")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 18, 630], fill="#0B8F6E")

    def wrap(text: str, f, width: int) -> List[str]:
        lines, cur = [], ""
        for w in text.split():
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f) <= width or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = w
        return lines + [cur] if cur else lines

    y = 70
    for ln in wrap(title, font(62), 1040)[:3]:
        d.text((80, y), ln, font=font(62), fill="#F8FAFC")
        y += 78
    y = max(y + 20, 330)
    for ln in wrap(line1, font(44), 1040)[:2]:
        d.text((80, y), ln, font=font(44), fill="#5EEAD4")
        y += 58
    if line2:
        d.text((80, y + 8), line2, font=font(34, False), fill="#9FB0C0")
    d.text((80, 548), "eurofuelprices.com", font=font(38), fill="#E9EEF3")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)
    return True


def head(title: str, desc: str, canonical: str, ld: List[Dict], lang: str = "en", locale: str = "en_GB",
         back: str = "Open the live map →", alts: str = "", image: str = "") -> str:
    lds = "\n".join('<script type="application/ld+json">' + json.dumps(o, ensure_ascii=False).replace("</", "<\\/") + "</script>" for o in ld)
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)} | EuroFuelPrices</title>
<meta name="description" content="{escape(desc)}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:locale" content="{locale}">
{alts}
<meta property="og:site_name" content="EuroFuelPrices">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{image or SITE + "/og-image.png"}">
<meta name="twitter:card" content="summary_large_image">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' https://static.cloudflareinsights.com; connect-src 'self' https://cloudflareinsights.com https://static.cloudflareinsights.com; style-src 'self' 'unsafe-inline'; img-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none';">
<meta name="theme-color" content="#E9EEF3" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0E1A29" media="(prefers-color-scheme: dark)">
<link rel="icon" type="image/svg+xml" href="/icon.svg">
<link rel="stylesheet" href="/theme.css">
{lds}
<style>{CSS} td.up {{ color:var(--red,#b3261e); }} td.dn {{ color:var(--green); }} .grade {{ font-size:.72rem; border:1px solid var(--border); border-radius:6px; padding:1px 6px; color:var(--text2); }}</style>
<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token": "4266c1f5c19845839b3163f64446320f"}}'></script>
</head>
<body>
<header><a class="logo" href="/"><img src="/icon.svg" alt="" width="22" height="22" style="vertical-align:-4px"> EuroFuelPrices</a><a class="back" href="/">{back}</a></header>
"""


def foot(updated: str) -> str:
    return (f'<footer><p>Figures are the <strong>median station price</strong> in each country, converted to euro at the ECB rate. '
            f'Source grades: A/B official, C unofficial or merged, D community — <a href="/about.html">how we grade sources</a>. '
            f'Countries with fewer than {MIN_N} priced stations, a failed feed or data older than {MAX_AGE_H} h are left out. '
            f'Prices are indicative; check at the pump.</p><p>Last updated: {escape(updated)} UTC. '
            f'Free to reuse with a link to eurofuelprices.com — <a href="/open-data/national-averages.json">JSON</a> · '
            f'<a href="/open-data/national-averages.csv">CSV</a> · <a href="/embed.html">free widget</a> · <a href="https://www.facebook.com/eurofuelprices" rel="me noopener">Facebook</a>.</p></footer>\n</body>\n</html>\n')


def crumbs(items: List[Tuple[str, Optional[str]]]) -> str:
    parts = [f'<a href="{u}">{escape(n)}</a>' if u else escape(n) for n, u in items]
    return '<nav class="crumbs" aria-label="Breadcrumbs">' + " › ".join(parts) + "</nav>\n"


def ranking_table(elig, fuel: str, hist, today: str) -> str:
    rows = sorted(((v[fuel]["median"], cc) for cc, v in elig.items() if fuel in v))
    out = []
    for i, (m, cc) in enumerate(rows, 1):
        d = change_7d_value(hist, today, fuel, cc, m)
        chg = "<td>–</td>" if d is None else f'<td class="{"up" if d > 0 else "dn"}">{d:+.3f}</td>'
        v = elig[cc][fuel]
        out.append(f'<tr><td>{i}</td><td class="n">{escape(NAMES[cc])}</td><td class="p">{eur(m)}</td>{chg}'
                   f'<td>{v["n"]}</td><td><span class="grade">{escape(str(v["grade"]))}</span></td></tr>')
    return ('<div class="tw"><table><thead><tr><th>#</th><th>Country</th><th>€/L (median)</th><th>7-day change</th>'
            '<th>Stations</th><th>Grade</th></tr></thead><tbody>' + "".join(out) + "</tbody></table></div>")


def pair_rows(elig, a: str, b: str):
    rows = []
    for fuel, label in FUELS:
        if fuel in elig.get(a, {}) and fuel in elig.get(b, {}):
            va, vb = elig[a][fuel]["median"], elig[b][fuel]["median"]
            rows.append((label, va, vb, vb - va))
    return rows


def pair_sentence(a: str, b: str, rows) -> str:
    bits = []
    for label, va, vb, d in rows:
        cheaper, dearer = (a, b) if d > 0 else (b, a)
        bits.append(f"{label.lower()} is about €{abs(d):.2f} per litre cheaper in {NAMES[cheaper]} than in {NAMES[dearer]} "
                    f"(€{abs(d) * FILL_L:.2f} on a {FILL_L} L fill-up)")
    return "On the median station, " + " and ".join(bits) + "." if bits else ""


def build_index(elig, hist, today: str, updated: str, image: str = "") -> str:
    url = f"{SITE}/europe/"
    title = "European Fuel Prices Today – Cheapest & Most Expensive Countries"
    n = len(elig)
    cheap95 = min(((v["p95"]["median"], cc) for cc, v in elig.items() if "p95" in v), default=None)
    dear95 = max(((v["p95"]["median"], cc) for cc, v in elig.items() if "p95" in v), default=None)
    desc = (f"Petrol and diesel prices in {n} European countries ranked from cheapest to most expensive, with 7-day change "
            f"and border-region comparisons. Updated daily.")
    cards = ""
    if cheap95 and dear95:
        cards = (f'<div class="cards"><div class="card"><div class="k">Cheapest petrol 95</div><div class="v">€{eur(cheap95[0])}</div><div class="s">{escape(NAMES[cheap95[1]])}</div></div>'
                 f'<div class="card"><div class="k">Most expensive petrol 95</div><div class="v">€{eur(dear95[0])}</div><div class="s">{escape(NAMES[dear95[1]])}</div></div></div>')
    pairs = [(a, b) for a, b in BORDER_PAIRS if pair_rows(elig, a, b)]
    pl = "".join(f'<li><a href="/europe/{pair_slug(a, b)}/">{escape(NAMES[a])} vs {escape(NAMES[b])}</a></li>' for a, b in pairs)
    body = (crumbs([("Home", "/"), ("Europe fuel price index", None)]) + "<h1>European fuel prices today</h1>"
            f'<p class="lede">Median petrol and diesel prices across {n} European countries, from the live station data on EuroFuelPrices. '
            f'Sorted cheapest first; the 7-day change appears once a week of history exists.</p>{cards}'
            f"<h2>Petrol 95 — cheapest to most expensive</h2>{ranking_table(elig, 'p95', hist, today)}"
            f"<h2>Diesel — cheapest to most expensive</h2>{ranking_table(elig, 'diesel', hist, today)}"
            + (f'<h2>Is it cheaper across the border?</h2><ul class="links">{pl}</ul>' if pl else "")
            + '<p class="note">These are country medians, not the price at a specific station. Open the <a href="/">live map</a> to find the cheapest pump near you.</p>')
    ld = [breadcrumb_ld([("Home", SITE + "/"), ("Europe fuel price index", url)]),
          {"@context": "https://schema.org", "@type": "Dataset", "name": "European fuel prices by country (median, EUR per litre)",
           "description": desc, "url": url, "creator": {"@type": "Organization", "name": "EuroFuelPrices", "url": SITE},
           "dateModified": updated[:10], "isAccessibleForFree": True,
           "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": SITE + "/open-data/national-averages.json"},
                            {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": SITE + "/open-data/national-averages.csv"}]}]
    alts = "\n".join([f'<link rel="alternate" hreflang="en" href="{SITE}/europe/">'] +
                     [f'<link rel="alternate" hreflang="{l}" href="{SITE}/europe/{l}/">' for l in LANG_TXT] +
                     [f'<link rel="alternate" hreflang="x-default" href="{SITE}/europe/">'])
    return head(title, desc, url, ld, alts=alts, image=image) + body + foot(updated)


# ── translated index pages (/europe/sv|de|da/) ─────────────────────────────────
def _names(spec: str) -> Dict[str, str]:
    return dict(x.split("=", 1) for x in spec.split(";"))


LANG_TXT = {
    "sv": dict(locale="sv_SE", back="Öppna live-kartan →", home="Hem", crumb="Bensinpriser i Europa",
               title="Bensinpriser i Europa idag – billigaste och dyraste länderna",
               desc="Bensin- och dieselpriser i {n} europeiska länder, rankade från billigast till dyrast. Uppdateras dagligen.",
               h1="Bensinpriser i Europa idag",
               lede="Medianpris för bensin och diesel i {n} europeiska länder, från live-data på EuroFuelPrices. Billigast först; förändring över 7 dagar visas när en vecka historik finns.",
               h95="Bensin 95 – billigast till dyrast", hdi="Diesel – billigast till dyrast", hb="Är det billigare över gränsen?",
               cheap="Billigaste bensin 95", dear="Dyraste bensin 95", c="Land", m="€/L (median)", ch="Ändring 7 dagar", st="Stationer", g="Klass",
               note='Det här är medianpriser per land, inte priset vid en viss station. Öppna <a href="/">live-kartan</a> för att hitta billigaste macken nära dig.',
               foot=("Siffrorna är <strong>medianpriset</strong> per land, omräknat till euro enligt ECB:s kurs. Källklasser: A/B officiell, C inofficiell eller sammanslagen, D community — "
                     '<a href="/about.html">så graderar vi källor</a>. Länder med färre än {min_n} stationer med pris, ett fel i källan eller data äldre än {age} h utelämnas. Priserna är vägledande; kontrollera vid pumpen.'),
               upd="Senast uppdaterad", reuse="Fri att återanvända med länk till eurofuelprices.com", widget="gratis widget",
               names="AD=Andorra;AL=Albanien;AT=Österrike;BA=Bosnien och Hercegovina;BE=Belgien;BG=Bulgarien;CH=Schweiz;CY=Cypern;CZ=Tjeckien;DE=Tyskland;DK=Danmark;EE=Estland;ES=Spanien;FI=Finland;FR=Frankrike;GB=Storbritannien;GR=Grekland;HR=Kroatien;HU=Ungern;IE=Irland;IS=Island;IT=Italien;LI=Liechtenstein;LT=Litauen;LU=Luxemburg;LV=Lettland;MC=Monaco;MD=Moldavien;ME=Montenegro;MK=Nordmakedonien;MT=Malta;NL=Nederländerna;NO=Norge;PL=Polen;PT=Portugal;RO=Rumänien;RS=Serbien;SE=Sverige;SI=Slovenien;SK=Slovakien;SM=San Marino;XK=Kosovo"),
    "de": dict(locale="de_DE", back="Zur Live-Karte →", home="Startseite", crumb="Spritpreise in Europa",
               title="Spritpreise in Europa heute – günstigste und teuerste Länder",
               desc="Benzin- und Dieselpreise in {n} europäischen Ländern, vom günstigsten zum teuersten Land. Täglich aktualisiert.",
               h1="Spritpreise in Europa heute",
               lede="Mediane Benzin- und Dieselpreise in {n} europäischen Ländern, aus den Live-Daten von EuroFuelPrices. Günstigste zuerst; die 7-Tage-Änderung erscheint, sobald eine Woche Verlauf vorliegt.",
               h95="Super 95 – günstigste bis teuerste", hdi="Diesel – günstigste bis teuerste", hb="Lohnt sich das Tanken im Nachbarland?",
               cheap="Günstigstes Super 95", dear="Teuerstes Super 95", c="Land", m="€/L (Median)", ch="Änderung 7 Tage", st="Tankstellen", g="Klasse",
               note='Dies sind Medianpreise je Land, nicht der Preis an einer bestimmten Tankstelle. Auf der <a href="/">Live-Karte</a> finden Sie die günstigste Tankstelle in Ihrer Nähe.',
               foot=("Die Werte sind der <strong>Medianpreis</strong> je Land, zum EZB-Kurs in Euro umgerechnet. Quellenklassen: A/B amtlich, C inoffiziell oder zusammengeführt, D Community — "
                     '<a href="/about.html">so bewerten wir Quellen</a>. Länder mit weniger als {min_n} Tankstellen mit Preis, ausgefallener Quelle oder Daten älter als {age} h werden weggelassen. Preise sind Richtwerte; bitte vor Ort prüfen.'),
               upd="Zuletzt aktualisiert", reuse="Frei nutzbar mit Link auf eurofuelprices.com", widget="kostenloses Widget",
               names="AD=Andorra;AL=Albanien;AT=Österreich;BA=Bosnien und Herzegowina;BE=Belgien;BG=Bulgarien;CH=Schweiz;CY=Zypern;CZ=Tschechien;DE=Deutschland;DK=Dänemark;EE=Estland;ES=Spanien;FI=Finnland;FR=Frankreich;GB=Vereinigtes Königreich;GR=Griechenland;HR=Kroatien;HU=Ungarn;IE=Irland;IS=Island;IT=Italien;LI=Liechtenstein;LT=Litauen;LU=Luxemburg;LV=Lettland;MC=Monaco;MD=Moldau;ME=Montenegro;MK=Nordmazedonien;MT=Malta;NL=Niederlande;NO=Norwegen;PL=Polen;PT=Portugal;RO=Rumänien;RS=Serbien;SE=Schweden;SI=Slowenien;SK=Slowakei;SM=San Marino;XK=Kosovo"),
    "da": dict(locale="da_DK", back="Åbn live-kortet →", home="Forside", crumb="Benzinpriser i Europa",
               title="Benzinpriser i Europa i dag – billigste og dyreste lande",
               desc="Benzin- og dieselpriser i {n} europæiske lande, rangeret fra billigste til dyreste. Opdateres dagligt.",
               h1="Benzinpriser i Europa i dag",
               lede="Medianpriser for benzin og diesel i {n} europæiske lande, fra live-data på EuroFuelPrices. Billigste først; ændringen over 7 dage vises, når der er en uges historik.",
               h95="Benzin 95 – billigste til dyreste", hdi="Diesel – billigste til dyreste", hb="Er det billigere på den anden side af grænsen?",
               cheap="Billigste benzin 95", dear="Dyreste benzin 95", c="Land", m="€/L (median)", ch="Ændring 7 dage", st="Stationer", g="Klasse",
               note='Det er medianpriser pr. land, ikke prisen på en bestemt station. Åbn <a href="/">live-kortet</a> for at finde den billigste station i nærheden.',
               foot=("Tallene er <strong>medianprisen</strong> pr. land, omregnet til euro efter ECB-kursen. Kildeklasser: A/B officiel, C uofficiel eller sammenlagt, D community — "
                     '<a href="/about.html">sådan vurderer vi kilder</a>. Lande med under {min_n} stationer med pris, en fejlet kilde eller data ældre end {age} t udelades. Priserne er vejledende; tjek ved pumpen.'),
               upd="Senest opdateret", reuse="Frit at genbruge med link til eurofuelprices.com", widget="gratis widget",
               names="AD=Andorra;AL=Albanien;AT=Østrig;BA=Bosnien-Hercegovina;BE=Belgien;BG=Bulgarien;CH=Schweiz;CY=Cypern;CZ=Tjekkiet;DE=Tyskland;DK=Danmark;EE=Estland;ES=Spanien;FI=Finland;FR=Frankrig;GB=Storbritannien;GR=Grækenland;HR=Kroatien;HU=Ungarn;IE=Irland;IS=Island;IT=Italien;LI=Liechtenstein;LT=Litauen;LU=Luxembourg;LV=Letland;MC=Monaco;MD=Moldova;ME=Montenegro;MK=Nordmakedonien;MT=Malta;NL=Holland;NO=Norge;PL=Polen;PT=Portugal;RO=Rumænien;RS=Serbien;SE=Sverige;SI=Slovenien;SK=Slovakiet;SM=San Marino;XK=Kosovo"),
}


def build_index_lang(lang: str, elig, hist, today: str, updated: str) -> str:
    x = LANG_TXT[lang]
    nm = _names(x["names"])
    url = f"{SITE}/europe/{lang}/"
    n = len(elig)

    def table(fuel: str) -> str:
        rows = sorted(((v[fuel]["median"], cc) for cc, v in elig.items() if fuel in v))
        out = []
        for i, (m, cc) in enumerate(rows, 1):
            d = change_7d_value(hist, today, fuel, cc, m)
            chg = "<td>–</td>" if d is None else f'<td class="{"up" if d > 0 else "dn"}">{d:+.3f}</td>'
            v = elig[cc][fuel]
            out.append(f'<tr><td>{i}</td><td class="n">{escape(nm.get(cc, NAMES[cc]))}</td><td class="p">{eur(m)}</td>{chg}'
                       f'<td>{v["n"]}</td><td><span class="grade">{escape(str(v["grade"]))}</span></td></tr>')
        return (f'<div class="tw"><table><thead><tr><th>#</th><th>{x["c"]}</th><th>{x["m"]}</th><th>{x["ch"]}</th><th>{x["st"]}</th><th>{x["g"]}</th></tr></thead>'
                f'<tbody>{"".join(out)}</tbody></table></div>')

    lo = min(((v["p95"]["median"], cc) for cc, v in elig.items() if "p95" in v), default=None)
    hi = max(((v["p95"]["median"], cc) for cc, v in elig.items() if "p95" in v), default=None)
    cards = ""
    if lo and hi:
        cards = (f'<div class="cards"><div class="card"><div class="k">{x["cheap"]}</div><div class="v">€{eur(lo[0])}</div><div class="s">{escape(nm.get(lo[1], NAMES[lo[1]]))}</div></div>'
                 f'<div class="card"><div class="k">{x["dear"]}</div><div class="v">€{eur(hi[0])}</div><div class="s">{escape(nm.get(hi[1], NAMES[hi[1]]))}</div></div></div>')
    pairs = [(a, b) for a, b in BORDER_PAIRS if pair_rows(elig, a, b)]
    pl = "".join(f'<li><a href="/europe/{pair_slug(a, b)}/">{escape(nm.get(a, NAMES[a]))} – {escape(nm.get(b, NAMES[b]))}</a></li>' for a, b in pairs)
    body = (crumbs([(x["home"], "/"), (x["crumb"], None)]) + f"<h1>{x['h1']}</h1>"
            f'<p class="lede">{x["lede"].format(n=n)}</p>{cards}<h2>{x["h95"]}</h2>{table("p95")}<h2>{x["hdi"]}</h2>{table("diesel")}'
            + (f'<h2>{x["hb"]}</h2><ul class="links">{pl}</ul>' if pl else "") + f'<p class="note">{x["note"]}</p>')
    alts = "\n".join([f'<link rel="alternate" hreflang="en" href="{SITE}/europe/">'] +
                     [f'<link rel="alternate" hreflang="{l}" href="{SITE}/europe/{l}/">' for l in LANG_TXT])
    ld = [breadcrumb_ld([(x["home"], SITE + "/"), (x["crumb"], url)])]
    foot_html = (f'<footer><p>{x["foot"].format(min_n=MIN_N, age=MAX_AGE_H)}</p><p>{x["upd"]}: {escape(updated)} UTC. {x["reuse"]} — '
                 f'<a href="/open-data/national-averages.json">JSON</a> · <a href="/open-data/national-averages.csv">CSV</a> · <a href="/embed.html">{x["widget"]}</a> · <a href="https://www.facebook.com/eurofuelprices" rel="me noopener">Facebook</a>.</p></footer>\n</body>\n</html>\n')
    return head(x["title"], x["desc"].format(n=n), url, ld, lang=lang, locale=x["locale"], back=x["back"], alts=alts) + body + foot_html


def build_pair(a: str, b: str, elig, updated: str, image: str = "") -> str:
    rows = pair_rows(elig, a, b)
    url = f"{SITE}/europe/{pair_slug(a, b)}/"
    na, nb = NAMES[a], NAMES[b]
    title = f"Fuel prices {na} vs {nb} – is it cheaper across the border?"
    desc = f"Petrol and diesel prices in {na} compared with {nb} today. " + pair_sentence(a, b, rows)
    trs = "".join(f'<tr><td class="n">{label}</td><td class="p">{eur(va)}</td><td class="p">{eur(vb)}</td>'
                  f'<td class="p">{vb - va:+.3f}</td><td class="p">{abs(vb - va) * FILL_L:.2f}</td></tr>' for label, va, vb, _ in rows)
    body = (crumbs([("Home", "/"), ("Europe fuel price index", "/europe/"), (f"{na} vs {nb}", None)])
            + f"<h1>Fuel prices: {escape(na)} vs {escape(nb)}</h1><p class=\"lede\">{escape(pair_sentence(a, b, rows))}</p>"
            f'<div class="tw"><table><thead><tr><th>Fuel</th><th>{escape(na)} €/L</th><th>{escape(nb)} €/L</th><th>Difference (B − A)</th>'
            f'<th>{FILL_L} L fill-up gap (€)</th></tr></thead><tbody>{trs}</tbody></table></div>'
            f'<p class="note">Before you drive over the border just for fuel, weigh the extra distance: a 40 km detour in a car using 7 L/100 km burns about 2.8 L. '
            f'Medians are country-wide; border-region prices can differ — check the <a href="/">live map</a> for the stations you would actually use.</p>'
            f'<h2>More comparisons</h2><ul class="links"><li><a href="/europe/">All European countries</a></li></ul>')
    ld = [breadcrumb_ld([("Home", SITE + "/"), ("Europe fuel price index", SITE + "/europe/"), (f"{na} vs {nb}", url)])]
    return head(title, desc, url, ld, image=image) + body + foot(updated)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(data_dir: Path = DATA_DIR) -> int:
    now = datetime.now(timezone.utc)
    meta_f = data_dir / "meta.json"
    if not meta_f.exists():
        print("europe_index: meta.json missing - skipped")
        return 0
    meta = json.loads(meta_f.read_text(encoding="utf-8"))
    elig = eligible(meta, now)
    if len(elig) < 8:
        print(f"europe_index: only {len(elig)} eligible countries - skipped (keeps the previous page)")
        return 0
    today, updated = now.date().isoformat(), now.strftime("%Y-%m-%d %H:%M")
    hist = update_history(load_history(), elig, today)
    write(data_dir / "index_history.json", json.dumps(hist, separators=(",", ":")))

    lo = min(((v["p95"]["median"], cc) for cc, v in elig.items() if "p95" in v), default=None)
    hi = max(((v["p95"]["median"], cc) for cc, v in elig.items() if "p95" in v), default=None)
    img = ""
    if lo and hi and make_card(data_dir / "og" / "europe.png", "European fuel prices today",
                               f"Cheapest petrol 95: {NAMES[lo[1]]} €{lo[0]:.3f}/L", f"Most expensive: {NAMES[hi[1]]} €{hi[0]:.3f}/L"):
        img = SITE + "/og/europe.png"
    write(data_dir / "europe" / "index.html", build_index(elig, hist, today, updated, img))
    urls = [(SITE + "/europe/", today)]
    for lang in LANG_TXT:
        write(data_dir / "europe" / lang / "index.html", build_index_lang(lang, elig, hist, today, updated))
        urls.append((f"{SITE}/europe/{lang}/", today))
    for a, b in BORDER_PAIRS:
        if pair_rows(elig, a, b):
            rows = pair_rows(elig, a, b)
            pimg = ""
            best = max(rows, key=lambda r: abs(r[3]))
            cheaper = NAMES[a] if best[3] > 0 else NAMES[b]
            if make_card(data_dir / "og" / f"{pair_slug(a, b)}.png", f"Fuel prices: {NAMES[a]} vs {NAMES[b]}",
                         f"{best[0]} is €{abs(best[3]):.2f}/L cheaper in {cheaper}", f"= €{abs(best[3]) * FILL_L:.2f} on a {FILL_L} L fill-up"):
                pimg = f"{SITE}/og/{pair_slug(a, b)}.png"
            write(data_dir / "europe" / pair_slug(a, b) / "index.html", build_pair(a, b, elig, updated, pimg))
            urls.append((f"{SITE}/europe/{pair_slug(a, b)}/", today))
    write_sitemap(data_dir / "sitemap-europe.xml", urls)

    sm = data_dir / "sitemap-seo.xml"
    if sm.exists():
        t = sm.read_text(encoding="utf-8")
        if "sitemap-europe.xml" not in t:
            sm.write_text(t.replace("</sitemapindex>", f"  <sitemap><loc>{SITE}/sitemap-europe.xml</loc></sitemap>\n</sitemapindex>"), encoding="utf-8")

    rows = [dict(country=cc, name=NAMES[cc], fuel=f, median_eur_per_litre=v[f]["median"], stations=v[f]["n"], source_grade=v[f]["grade"])
            for cc, v in sorted(elig.items()) for f, _ in FUELS if f in v]
    doc = {"updated": updated + "Z", "unit": "EUR per litre (median station price, converted at the ECB rate)",
           "attribution": "EuroFuelPrices (https://eurofuelprices.com) - free to reuse with a link", "rows": rows}
    write(data_dir / "open-data" / "national-averages.json", json.dumps(doc, ensure_ascii=False, indent=1))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    write(data_dir / "open-data" / "national-averages.csv", buf.getvalue())
    print(f"europe_index: {len(elig)} countries, {len(urls) - 1} border pages")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else DATA_DIR))
