"""Static SEO pages per country: a hub (/<cc>/) and one page per town (/<cc>/<town>/).

Runs after ``main.py`` in the scrape workflow and writes plain, JS-free HTML into ``data/`` so the
pages are crawlable and fast. Targets local-intent queries ("bensinpriser Växjö", "Spritpreise
Wien", "prix carburant Lyon") — see docs/ROADMAP.md, experiment E3.

Countries (COUNTRIES below): SE (sv), AT (de), FR (fr), DE (de), CH (de). DE and CH are currently fed
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

COUNTRIES: Dict[str, Dict[str, Any]] = {
    "se": dict(lang="sv", currency="SEK", sym="kr", mode="places", ts_kind="snapshot", fallback_nearby=True,
               hub="Bensinpriser Sverige", hub_title="Bensinpriser Sverige idag – billigaste bensin & diesel",
               fuels=[("P95", "Bensin 95"), ("P98", "Bensin 98"), ("DIESEL", "Diesel"), ("E85", "E85")],
               cheapest=("P95", "DIESEL"), src="bensinpriser.nu", osm=True),
    "at": dict(lang="de", currency="EUR", sym="€", mode="places", ts_kind="fetched", fallback_nearby=False,
               hub="Spritpreise Österreich", hub_title="Spritpreise Österreich aktuell – günstig tanken",
               fuels=[("P95", "Super 95"), ("DIESEL", "Diesel"), ("LPG", "Autogas (LPG)")],
               cheapest=("P95", "DIESEL"), src="E-Control Spritpreisrechner", osm=True,
               nation="Österreich-Median"),
    "de": dict(lang="de", currency="EUR", sym="€", mode="city", ts_kind="fetched", fallback_nearby=False,
               hub="Spritpreise Deutschland", hub_title="Spritpreise Deutschland aktuell – günstig tanken",
               fuels=[("E10", "Super E10"), ("E5_95", "Super E5"), ("DIESEL", "Diesel"), ("LPG", "Autogas (LPG)")],
               cheapest=("E10", "DIESEL"), src="Tankerkönig / MTS-K", osm=False, nation="Deutschland-Median"),
    "ch": dict(lang="de", currency="CHF", sym="CHF", mode="city", ts_kind="fetched", fallback_nearby=False,
               hub="Benzinpreise Schweiz", hub_title="Benzinpreise Schweiz aktuell – günstig tanken",
               fuels=[("E10", "Bleifrei 95 (E10)"), ("E5_95", "Bleifrei 95 (E5)"), ("P98", "Bleifrei 98"), ("DIESEL", "Diesel"), ("LPG", "Autogas (LPG)")],
               cheapest=("E10", "DIESEL"), src="Community", osm=False, nation="Schweiz-Median"),
    "fr": dict(lang="fr", currency="EUR", sym="€", mode="city", ts_kind="price", fallback_nearby=False, max_age_h=336,
               hub="Prix des carburants en France", hub_title="Prix des carburants en France – le moins cher aujourd’hui",
               fuels=[("E10", "SP95-E10"), ("E5_95", "SP95 (E5)"), ("P98", "SP98"), ("DIESEL", "Gazole"), ("E85", "E85 (superéthanol)"), ("LPG", "GPLc")],
               cheapest=("E10", "DIESEL"), src="prix-carburants.gouv.fr (data.economie.gouv.fr)", osm=False,
               nation="médiane nationale"),
    "es": dict(lang="es", currency="EUR", sym="€", mode="city", ts_kind="snapshot", fallback_nearby=False,
               hub="Precios de gasolineras en España", hub_title="Precio gasolina y gasóleo hoy en España – gasolineras más baratas",
               fuels=[("P95", "Gasolina 95"), ("P98", "Gasolina 98"), ("DIESEL", "Gasóleo A"), ("CNG", "GNC")],
               cheapest=("P95", "DIESEL"), src="Ministerio para la Transición Ecológica (geoportalgasolineras.es)", osm=False,
               nation="mediana nacional"),
    "pt": dict(lang="pt", currency="EUR", sym="€", mode="city", ts_kind="price", fallback_nearby=False, max_age_h=168,
               hub="Preços dos combustíveis em Portugal", hub_title="Preços dos combustíveis em Portugal hoje – gasolina e gasóleo mais baratos",
               fuels=[("P95", "Gasolina 95"), ("DIESEL", "Gasóleo"), ("LPG", "GPL Auto")],
               cheapest=("P95", "DIESEL"), src="DGEG – Direção-Geral de Energia e Geologia", osm=False,
               nation="mediana nacional"),
    "dk": dict(lang="da", currency="DKK", sym="kr", mode="city", ts_kind="price", fallback_nearby=False,
               hub="Benzinpriser Danmark", hub_title="Benzinpriser Danmark i dag – billigste benzin og diesel",
               fuels=[("P95", "Benzin 95"), ("P98", "Benzin 98"), ("DIESEL", "Diesel")],
               cheapest=("P95", "DIESEL"), src="OK, Q8, Shell og Go’on (åbne API’er)", osm=False,
               nation="landsmedian"),
}

MONTHS = {
    "sv": ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"],
    "de": ["Jan.", "Feb.", "Mär.", "Apr.", "Mai", "Jun.", "Jul.", "Aug.", "Sep.", "Okt.", "Nov.", "Dez."],
    "fr": ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
    "es": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
    "pt": ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"],
    "da": ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"],
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
foot_unofficial="Källa: ANWB-data (inofficiell tredjepartskälla). Priserna kan avvika – kontrollera vid pump.", foot_grades="Så graderar vi datakällor", foot_osm="Stationsplatser och ortnamn ©", foot_osm_who="OpenStreetMap-bidragsgivare",
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
        foot_unofficial="Quelle: ANWB-Daten (inoffizielle Drittquelle, nicht amtlich; Preise ggf. umgerechnet). Preise können erheblich abweichen – bitte vor Ort prüfen.",
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
        foot_unofficial="Source : données ANWB (source tierce non officielle). Les prix peuvent différer – vérifiez en station.",
        foot_grades="Comment nous évaluons les sources", foot_osm="Noms de lieux ©", foot_osm_who="contributeurs d’OpenStreetMap",
        foot_upd="Dernière mise à jour", ad=""),
    "es": dict(
        locale="es_ES", home="Inicio", map="Abrir el mapa →", crumbs="Ruta de navegación",
        cheapest="Más barato: {f}", vs="{d} {sym} frente a la {nation}",
        lede="Precios actuales en {n} de {total} gasolineras de {town} y alrededores, de más barata a más cara.",
        lede_none="", h_stations="Gasolineras en {town}", h_near_priced="", h_nearby="Precios en localidades cercanas",
        h1="Precio de la gasolina en {town}", t_priced="Gasolina y gasóleo en {town} hoy – precios",
        t_none="", d_priced="Gasolina y gasóleo más baratos en {town}: compara los precios de {n} gasolineras, actualizados a diario.",
        d_none="", th_station="Gasolinera", km_from="a unos {d} km del centro", central="centro", km="a unos {d} km", near="cerca de",
        note_none="", hub_lede="Precios de gasolineras en {n} localidades de España. Elige tu localidad para ver la gasolina y el gasóleo más baratos cerca de ti, o abre el <a href=\"/\">mapa en directo</a>.",
        h_cheapest="Más barato en España: {f}", h_find="Encuentra tu localidad",
        hub_desc="Compara el precio de la gasolina y el gasóleo en {n} localidades de España.",
        th_when={"snapshot": "Datos de la fuente", "fetched": "Consultado", "price": "Actualizado"},
        foot_ts={"snapshot": "La hora es la de los datos de la fuente (actualización diaria), no el momento en que cambió el precio en la gasolinera.",
                 "fetched": "La hora es la de nuestra consulta; la fuente no indica la hora del precio.",
                 "price": "La hora es la del último cambio de precio según la fuente."},
        foot_src="Fuente: {src}. Los precios pueden diferir en la gasolinera: compruébalos en el surtidor.",
        foot_unofficial="Fuente: datos de ANWB (fuente de terceros no oficial). Los precios pueden diferir: compruébalos en el surtidor.",
        foot_grades="Cómo valoramos las fuentes", foot_osm="Nombres de lugares ©", foot_osm_who="colaboradores de OpenStreetMap",
        foot_upd="Última actualización", ad=""),
    "pt": dict(
        locale="pt_PT", home="Início", map="Abrir o mapa →", crumbs="Caminho",
        cheapest="Mais barato: {f}", vs="{d} {sym} face à {nation}",
        lede="Preços atuais em {n} de {total} postos de abastecimento em {town} e arredores, do mais barato ao mais caro.",
        lede_none="", h_stations="Postos de abastecimento em {town}", h_near_priced="", h_nearby="Preços em localidades próximas",
        h1="Preços dos combustíveis em {town}", t_priced="Gasolina e gasóleo em {town} hoje – preços",
        t_none="", d_priced="Gasolina e gasóleo mais baratos em {town}: compare os preços de {n} postos de abastecimento.",
        d_none="", th_station="Posto", km_from="a cerca de {d} km do centro", central="centro", km="a cerca de {d} km", near="perto de",
        note_none="", hub_lede="Preços dos combustíveis em {n} localidades de Portugal. Escolha a sua localidade para ver a gasolina e o gasóleo mais baratos perto de si, ou abra o <a href=\"/\">mapa em direto</a>.",
        h_cheapest="Mais barato em Portugal: {f}", h_find="Encontre a sua localidade",
        hub_desc="Compare os preços da gasolina e do gasóleo em {n} localidades de Portugal.",
        th_when={"snapshot": "Dados da fonte", "fetched": "Consultado", "price": "Atualizado"},
        foot_ts={"snapshot": "A hora é a dos dados da fonte, não o momento em que o preço mudou no posto.",
                 "fetched": "A hora é a da nossa consulta; a fonte não indica a hora do preço.",
                 "price": "A hora é a da última alteração do preço segundo a fonte."},
        foot_src="Fonte: {src}. Os preços podem diferir no posto: confirme na bomba.",
        foot_unofficial="Fonte: dados ANWB (fonte de terceiros não oficial). Os preços podem diferir: confirme na bomba.",
        foot_grades="Como avaliamos as fontes", foot_osm="Nomes de locais ©", foot_osm_who="colaboradores do OpenStreetMap",
        foot_upd="Última atualização", ad=""),
    "da": dict(
        locale="da_DK", home="Forside", map="Åbn kortet →", crumbs="Brødkrummer",
        cheapest="Billigste {f}", vs="{d} {sym} mod {nation}",
        lede="Aktuelle priser ved {n} af {total} tankstationer i og omkring {town}, billigste først.",
        lede_none="", h_stations="Tankstationer i {town}", h_near_priced="", h_nearby="Priser i nærliggende byer",
        h1="Benzinpriser i {town}", t_priced="Benzinpriser {town} i dag – benzin og diesel",
        t_none="", d_priced="Billigste benzin og diesel i {town}: sammenlign priserne på {n} tankstationer.",
        d_none="", th_station="Station", km_from="ca. {d} km fra centrum", central="centralt", km="ca. {d} km", near="ved",
        note_none="", hub_lede="Benzinpriser og tankstationer i {n} byer i Danmark. Vælg din by for at se billigste benzin og diesel i nærheden – eller åbn <a href=\"/\">live-kortet</a>.",
        h_cheapest="Billigste {f} i Danmark lige nu", h_find="Find din by",
        hub_desc="Sammenlign benzin- og dieselpriser i {n} danske byer – opdateres løbende.",
        th_when={"snapshot": "Kildedata", "fetched": "Hentet", "price": "Opdateret"},
        foot_ts={"snapshot": "Tiden er kildedataens tidspunkt, ikke hvornår prisen blev ændret på stationen.",
                 "fetched": "Tiden er hvornår vi hentede prisen; kilden oplyser ikke et pristidspunkt.",
                 "price": "Tiden er den seneste prisændring ifølge kilden; – betyder, at kilden ikke oplyser tid."},
        foot_src="Kilder: {src}. Priserne kan afvige – tjek altid ved pumpen.",
        foot_unofficial="Kilde: ANWB-data (uofficiel tredjepartskilde). Priserne kan afvige – tjek ved pumpen.",
        foot_grades="Sådan vurderer vi kilderne", foot_osm="Stednavne ©", foot_osm_who="OpenStreetMap-bidragsydere",
        foot_upd="Senest opdateret", ad=""),
}


# ── helpers ──────────────────────────────────────────────────────────────────

def slugify(name: str, lang: str) -> str:
    rep = {"sv": {"å": "a", "ä": "a", "ö": "o"}, "de": {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}, "fr": {"œ": "oe", "æ": "ae"}, "es": {}, "pt": {}, "da": {"å": "aa", "ø": "oe", "æ": "ae"}}[lang]
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
    s = f"{v:.2f}" if cfg["currency"] in ("SEK",) else f"{v:.3f}"
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


def footer_html(c: Ctx, unofficial: bool = False) -> str:
    cfg, x = c.cfg, c.x
    src_line = x["foot_unofficial"] if unofficial else x["foot_src"].format(src=cfg["src"])
    parts = [escape(src_line), escape(x["foot_ts"][cfg["ts_kind"]]),
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
    src_name = (meta.get("source") or "").lower()
    unofficial = "anwb" in src_name and "+" not in src_name   # merged feeds (DK) name their own sources
    if unofficial and EXCLUDE_ANWB:
        print(f"seo_pages[{cc}]: excluded by SEO_EXCLUDE_ANWB (source {meta.get('source')!r})")
        return None
    if meta.get("status") == "stale":   # keep the pages (a 404 on every indexed URL is worse); they show the real fetch date and fresh_price drops timestamped prices older than 72 h
        print(f"seo_pages[{cc}]: source stale - pages kept with the last fetch date")
    lang, x = cfg["lang"], TXT[cfg["lang"]]
    fetched = parse_iso(meta.get("fetched_at")) or now
    c = Ctx(cc, cfg, now, fetched, {})
    for fuel, _ in cfg["fuels"]:
        vals = [fp[0] for s in stations if (fp := fresh_price(s, fuel, now, cfg))]
        if len(vals) >= 5:
            c.national[fuel] = statistics.median(vals)

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
