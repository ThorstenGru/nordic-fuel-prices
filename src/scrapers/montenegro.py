"""Montenegro - ANWB stations + regulated MAXIMUM retail prices (gap fill).

IMPORTANT: the cap prices are a LEGAL MAXIMUM set by the Ministry of Energy and Mining
(weekly decision under Uredba, Sl. list CG 23/2021), NOT a measured station price. Most stations
charge at or just below it. Stations that have no ANWB price get the cap, labelled
``basis: "regulated_max"`` by merge_engine; an ANWB price is never overridden.

Cap source: https://nafta.hr/cijene-goriva-crna-gora/ - republishes the ministry's official
figures with an "update date" and a validity end date (gov.me publishes each week under a new
article URL with no stable listing, so it is not scriptable). We publish a cap ONLY if the date is
within the last 30 days, the validity window has not expired and every value is plausible;
otherwise ANWB stations are returned unchanged.
"""
import asyncio
import copy
import html as _html
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp

from ._anwb import ANWBScraper
try:
    from merge_engine import SourceResult, MergeConfig, merge_sources
except ImportError:   # package-style import
    from ..merge_engine import SourceResult, MergeConfig, merge_sources

GOVME_LIST = "https://wapi.gov.me/v1/articles?title=cijene%20goriva"
GOVME_ARTICLE = "https://www.gov.me/clanak/{slug}"
CAP_URL = "https://nafta.hr/cijene-goriva-crna-gora/"   # fallback only: republisher, lags the ministry by ~1 week
CAP_UA = "EuroFuelPrices/1.0 (+https://eurofuelprices.com)"
MAX_AGE_DAYS = 30
PETROL_BAND = (0.8, 3.0)
LPG_BAND = (0.3, 1.5)


def _text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def parse_cap_page(raw_html: str, today: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """Return {'date': 'YYYY-MM-DD', 'valid_until': ..|None, 'prices': {'DIESEL':x,'95':x,'98':x,'LPG':x?}}
    or None when anything is missing, implausible or stale."""
    today = today or date.today()
    t = _text(raw_html)
    m = re.search(r"Datum a\w+uriranja:?\s*(\d{1,2})\.(\d{1,2})\.(\d{4})", t)
    if not m:
        return None
    try:
        eff = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None
    if eff > today + timedelta(days=1) or (today - eff).days > MAX_AGE_DAYS:
        return None
    until = None
    mu = re.search(r"vrijediti do\s*(\d{1,2})\.(\d{1,2})\.(\d{4})", t)
    if mu:
        try:
            until = date(int(mu.group(3)), int(mu.group(2)), int(mu.group(1)))
        except ValueError:
            until = None
        if until and until < today:
            return None

    def val(label: str) -> Optional[float]:
        mm = re.search(label + r"\s*(\d[.,]\d{1,3})\s*(?:€|EUR)?\s*/\s*L", t, re.I)
        return float(mm.group(1).replace(",", ".")) if mm else None

    found = {"DIESEL": val(r"Eurodizel"), "95": val(r"Benzin\s+BMB\s*95"),
             "98": val(r"Benzin\s+BMB\s*98"), "LPG": val(r"(?:Autoplin|LPG|UNP)")}
    prices = {}
    for k, v in found.items():
        if v is None:
            continue
        lo, hi = LPG_BAND if k == "LPG" else PETROL_BAND
        if not (lo <= v <= hi):
            return None          # one implausible figure poisons the whole page: publish nothing
        prices[k] = v
    if "DIESEL" not in prices or "95" not in prices:
        return None
    return {"date": eff.isoformat(), "valid_until": until.isoformat() if until else None, "prices": prices}


def parse_govme_article(raw_html: str, title: str, today: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """Parse a gov.me 'Nove cijene goriva od DD.MM.YYYY' article (primary source, Ministry of Energy)."""
    today = today or date.today()
    m = re.search(r"od\s+(\d{1,2})\.(\d{1,2})\.(\d{4})", title)
    if not m:
        return None
    try:
        eff = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None
    if eff > today + timedelta(days=2) or (today - eff).days > MAX_AGE_DAYS:
        return None
    t = _text(raw_html)

    def val(label: str) -> Optional[float]:
        mm = re.search(label + r"\s*:\s*(\d[.,]\d{1,3})\s*€\s*/\s*l", t, re.I)
        return float(mm.group(1).replace(",", ".")) if mm else None

    found = {"DIESEL": val(r"EURODIZEL"), "95": val(r"EUROSUPER\s*95"), "98": val(r"EUROSUPER\s*98")}
    prices = {}
    for k, v in found.items():
        if v is None:
            continue
        if not (PETROL_BAND[0] <= v <= PETROL_BAND[1]):
            return None
        prices[k] = v
    if "DIESEL" not in prices or "95" not in prices:
        return None
    return {"date": eff.isoformat(), "valid_until": None, "prices": prices}


def build_cap_stations(stations: List[dict], cap: Dict[str, Any], currency: str = "EUR") -> List[dict]:
    plist = []
    for k in ("95", "98", "DIESEL", "LPG"):
        if k not in cap["prices"]:
            continue
        e = {"fuel_type": k, "price": cap["prices"][k], "currency": currency, "unit": "L",
             "updated_at": cap["date"], "source": "regulator_cap"}
        if k in ("95", "98"):
            e["octane"] = int(k)
        plist.append(e)
    out = []
    for s in stations:
        c = copy.deepcopy({k: v for k, v in s.items() if k != "prices"})
        c["prices"] = [dict(p) for p in plist]
        out.append(c)
    return out


def merge_with_cap(country: str, anwb: List[dict], cap: Optional[Dict[str, Any]]):
    """ANWB + cap -> (stations, merge_report). Without a cap the ANWB list is returned unchanged."""
    if not cap or not anwb:
        return anwb, {}
    results = [
        SourceResult("anwb", "ANWB", anwb, 9, "aggregator", "EUR"),
        SourceResult("regulator_cap", "Regulated maximum price", build_cap_stations(anwb, cap),
                     20, "regulated_cap", "EUR"),
    ]
    merged, report = merge_sources(results, MergeConfig(country=country))
    # cap copies that could not be matched to their ANWB twin (ambiguous neighbours) must not
    # become extra stations
    merged = [s for s in merged if s.get("sources") != ["regulator_cap"]]
    return merged, report


class MontenegroScraper(ANWBScraper):
    COUNTRY    = "ME"
    ISO3       = "MNE"
    BBOX       = (41.87, 18.43, 43.57, 20.36)
    SOURCE     = "anwb.nl (ANWB POI API) + regulated max prices (gov.me, Ministry of Energy)"
    CONFIDENCE = 0.90
    merge_report: Dict[str, Any] = {}

    async def _fetch_govme(self) -> Optional[Dict[str, Any]]:
        hdr = {"User-Agent": CAP_UA}
        try:
            to = aiohttp.ClientTimeout(total=30)
            async with self.session.get(GOVME_LIST, headers=hdr, timeout=to) as r:
                if r.status != 200:
                    return None
                arts = (await r.json(content_type=None))["data"]["data"]
            for a in arts:
                title = a.get("title", "")
                if not re.match(r"\s*Nove cijene goriva od", title, re.I):
                    continue
                async with self.session.get(GOVME_ARTICLE.format(slug=a["slug"]), headers=hdr, timeout=to) as r:
                    if r.status != 200:
                        return None
                    return parse_govme_article(await r.text(errors="replace"), title)
        except Exception as e:
            print(f"[ME] gov.me fetch failed: {e}")
        return None

    async def _fetch_cap(self) -> Optional[Dict[str, Any]]:
        cap = await self._fetch_govme()
        if cap:
            return cap
        print("[ME] gov.me primary unavailable - falling back to nafta.hr")
        try:
            async with self.session.get(CAP_URL, headers={"User-Agent": CAP_UA},
                                        timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    print(f"[ME] cap page HTTP {resp.status} - no cap")
                    return None
                cap = parse_cap_page(await resp.text())
        except Exception as e:
            print(f"[ME] cap fetch failed: {e} - no cap")
            return None
        if cap is None:
            print("[ME] cap page unparseable, implausible or stale - no cap")
        return cap

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        anwb = await super().fetch_stations()
        cap = await self._fetch_cap()
        merged, report = merge_with_cap(self.COUNTRY, anwb, cap)
        self.merge_report = report
        if cap:
            print(f"[ME] regulated cap {cap['date']} {cap['prices']}: regulated_fills="
                  f"{report.get('regulated_fills')} priced {report.get('priced_station_count')}/{len(merged)}")
        return merged
