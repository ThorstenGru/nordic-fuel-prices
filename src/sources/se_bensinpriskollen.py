"""
Sweden - bensinpriskollen.se (crowdsourced per-station prices, CANDIDATE source, grade D).

Endpoints (server-rendered HTML, no JSON API; /api/ is Disallowed in robots.txt and NOT used):
  https://bensinpriskollen.se/sitemap.xml            -> ~290 municipality pages (/<kommun>/)
  https://bensinpriskollen.se/<kommun>/              -> table of stations with 95 price + age ("21 h", "2 d")
  https://bensinpriskollen.se/station/<slug>/        -> 95 / Diesel / 98 / Etanol price + age per station
Only prices reported in the last 7 days are shown (site FAQ). Coordinates are NOT published
(JSON-LD has latitude/longitude = 0), so stations are SNAPPED onto an existing reference list
(default: the live https://eurofuelprices.com/se.json) by brand + street + house number.
Unmatched stations are dropped (counted in `last_stats`) - we never invent coordinates.

Licence/ToS: no licence or API terms published; operator Hojjo Sverige AB (Kungalv). The data is
user-submitted. Treat as "scrape with permission pending": ask the operator for written OK /
attribution wording before production use. robots.txt allows everything except /api/ and /admin/.
Rate limit used here: <= 1 request/s, honest User-Agent. Full crawl = ~290 city pages
+ one page per matched station (~25 min at 1 req/s); city pages alone (95 only) ~5 min.
Refresh recommendation: every 6 h is plenty (page cache is 60 min, data is crowd-paced).
updated_at is derived from the relative age text (now - age), hence approximate (+-1 h / +-1 d).
"""

import asyncio
import html as _html
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

BASE = "https://bensinpriskollen.se"
REFERENCE_URL = "https://eurofuelprices.com/se.json"
UA = "EuroFuelPrices/1.0 (+https://eurofuelprices.com)"
SOURCE = "bensinpriskollen.se"
_NON_CITY = {"", "lan", "rakna-ut-bensinkostnad", "nyheter", "guider", "dieselpris", "98-oktan",
             "etanol", "station", "hvo100", "om", "integritet", "cookies", "kontakt", "app"}

last_stats: Dict[str, Any] = {}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def _fix_mojibake(s: str) -> str:
    try:
        return s.encode("cp1252").decode("utf-8")
    except Exception:
        return s


_BRANDS = {"okq8": "OKQ8", "circle k": "Circle K", "preem": "Preem", "st1": "St1", "ingo": "Ingo",
           "qstar": "Qstar", "tanka": "Tanka", "gulf": "Gulf", "din x": "din-X", "dinx": "din-X",
           "shell": "Shell", "best": "Best", "pump": "Pump", "costco": "Costco"}


def _brand_key(b: str) -> str:
    n = _norm(b)
    for k, v in _BRANDS.items():
        if n.startswith(k):
            return _norm(v)
    return n


_STREET_RE = re.compile(r"^(.*?[a-z]+)\s+(\d+)\s*([a-z]?)\b")


def _street_key(addr: str) -> Optional[str]:
    """'Spanga Avestagatan 71' -> 'avestagatan 71' (last street-like word + number)."""
    n = _norm(addr)
    m = re.search(r"([a-z]+(?:gatan|vagen|gata|vag|leden|stigen|torget|allen|vagen|gard|vallen|backen|plan|stan|v)?)\s+(\d+)", n)
    if not m:
        return None
    return f"{m.group(1)} {m.group(2)}"


def _age(text: str, now: datetime) -> Optional[str]:
    m = re.search(r"(\d+)\s*(min|h|d|dag|dagar|tim)", text or "")
    if not m:
        return None
    n, u = int(m.group(1)), m.group(2)
    delta = timedelta(minutes=n) if u == "min" else timedelta(hours=n) if u in ("h", "tim") else timedelta(days=n)
    return (now - delta).replace(microsecond=0).isoformat()


def parse_city_page(t: str, now: datetime) -> List[Dict[str, Any]]:
    out = []
    for m in re.finditer(r'<tr id="station-[^"]+".*?</tr>', t, re.S):
        row = m.group(0)
        href = re.search(r'href="(/station/[^"]+/)"', row)
        spans = re.findall(r'<span class="(?:ml-2 text-xs|block text-xs)[^>]*>([^<]*)</span>', row)
        price = re.search(r'tabular-nums[^>]*>([0-9]+(?:\.[0-9]+)?)</span>', row)
        age = re.search(r'(\d+\s*(?:min|h|d))\s*</span></td></tr>$', row)
        if not (href and price and len(spans) >= 2):
            continue
        out.append({"url": href.group(1), "brand": _html.unescape(spans[0]), "street": _html.unescape(spans[1]),
                    "p95": float(price.group(1)), "age95": age.group(1) if age else ""})
    return out


def parse_station_page(t: str) -> Dict[str, Tuple[float, str]]:
    """-> {'95': (price, ageText), 'diesel': ..., '98': ...} from the 'Priser idag' table."""
    txt = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", _html.unescape(txt))
    i = txt.find("Bränsle Pris kr/l Uppdaterad")
    seg = txt[i:i + 400] if i >= 0 else ""
    res = {}
    for key, label in (("95", "Bensin 95"), ("DIESEL", "Diesel"), ("98", "98-oktan"), ("98", "Bensin 98")):
        m = re.search(re.escape(label) + r" (\d+\.\d+) (\d+ ?(?:min|h|d|dagar|dag|timmar) ?(?:sedan)?)", seg)
        if m and key not in res:
            res[key] = (float(m.group(1)), m.group(2))
    return res


async def _get(session, url: str, delay: float = 1.0) -> Optional[str]:
    await asyncio.sleep(delay)
    try:
        async with session.get(url, headers={"User-Agent": UA}, timeout=30) as r:
            if r.status != 200:
                return None
            return await r.text(encoding="utf-8")
    except Exception:
        return None


async def _load_reference(session) -> List[Dict[str, Any]]:
    async with session.get(REFERENCE_URL, headers={"User-Agent": UA}, timeout=60) as r:
        data = await r.json(content_type=None)
    return data["stations"]


def _build_index(ref: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    idx: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for s in ref:
        sk = _street_key(_fix_mojibake(s.get("address", "")) if "Ã" in s.get("address", "") else s.get("address", ""))
        if sk:
            idx.setdefault((_brand_key(s.get("brand") or s.get("name", "")), sk), s)
    return idx


async def fetch(session, reference: Optional[List[Dict[str, Any]]] = None, station_pages: bool = True,
                max_cities: Optional[int] = None) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    ref = reference if reference is not None else await _load_reference(session)
    idx = _build_index(ref)
    sm = await _get(session, BASE + "/sitemap.xml", 0) or ""
    cities = []
    for u in re.findall(r"<loc>([^<]+)</loc>", sm):
        seg = u.replace(BASE, "").strip("/")
        if "/" not in seg and seg not in _NON_CITY:
            cities.append(seg)
    cities = sorted(set(cities))[:max_cities]
    rows: List[Dict[str, Any]] = []
    seen = set()
    for c in cities:
        t = await _get(session, f"{BASE}/{c}/")
        for r in parse_city_page(t or "", now):
            if r["url"] not in seen:
                seen.add(r["url"]); r["city"] = c; rows.append(r)
    stats = {"cities": len(cities), "stations_seen": len(rows), "matched": 0, "unmatched": 0}
    out = []
    for r in rows:
        sk = _street_key(r["street"])
        ref_s = idx.get((_brand_key(r["brand"]), sk)) if sk else None
        if not ref_s:
            stats["unmatched"] += 1
            continue
        stats["matched"] += 1
        prices = {"95": (r["p95"], r["age95"])}
        if station_pages:
            t = await _get(session, BASE + r["url"])
            if t:
                prices.update(parse_station_page(t))
        pl = []
        for k, (p, age) in prices.items():
            if k == "95":
                pl.append({"fuel_type": "95", "octane": 95, "price": p})
            elif k == "98":
                pl.append({"fuel_type": "98", "octane": 98, "price": p})
            else:
                pl.append({"fuel_type": "DIESEL", "price": p})
            pl[-1].update({"currency": "SEK", "unit": "L", "updated_at": _age(age, now), "source": SOURCE})
        out.append({"id": "se_bpk_" + r["url"].strip("/").split("/")[-1], "country": "SE",
                    "name": ref_s.get("name") or r["brand"], "brand": ref_s.get("brand") or r["brand"],
                    "address": r["street"], "city": ref_s.get("city") or r["city"],
                    "lat": ref_s["lat"], "lon": ref_s["lon"], "source": SOURCE, "confidence": 0.5,
                    "ref_id": ref_s.get("id"), "prices": pl})
    last_stats.clear(); last_stats.update(stats)
    return out
