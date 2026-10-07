"""North Macedonia: ANWB station list + ERC legal maximum prices for stations without a price.

The cap is a LEGAL MAXIMUM retail price (Energy and Water Services Regulatory Commission, RKE/ERC,
decision on the highest retail prices of petroleum derivatives), NOT a price observed at a station:
retailers may sell below it. It is only used to fill price buckets (95, 98, diesel) for which ANWB has
no price, and those prices are flagged basis='regulated_max' by the merge engine. ANWB station prices
are never overridden.

Source: ERC only (official regulator). nafta.hr/cijene-goriva-makedonija was checked on 2026-10-07 and its
MK figures were WRONG versus the RKE decision (diesel 104.5 vs 97 MKD) - it must NOT be used for MK.
When ERC is unreachable (HTTP 403 from GitHub runners) NO cap is published and ANWB is returned unchanged.
ERC homepage block "AKTUELNI CENI" (official, current, MKD/L). The block
carries no date, so the effective date is the date of the newest "Odluka za ceni na ND" decision listed
on the same page (filename prefix YYYY.MM.DD) - a conservative (never too new) date. No cap is produced
when the figures are missing, implausible (MKD 50-190/L) or the date is older than 30 days.
"""
import re
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import aiohttp

from ._anwb import ANWBScraper
try:
    from merge_engine import SourceResult, MergeConfig, merge_sources
except ImportError:   # package-style import (src not on sys.path)
    from ..merge_engine import SourceResult, MergeConfig, merge_sources

ERC_URL = "https://www.erc.org.mk/"
UA = "EuroFuelPrices/1.0 (+https://eurofuelprices.com)"
CAP_BAND = (50.0, 190.0)       # MKD per litre
CAP_MAX_AGE_DAYS = 30
# The ECB publishes no MKD rate, so ANWB prices for MK stay in EUR (ANWB delivers EUR). To keep one
# currency per station the MKD cap is expressed in the currency of the ANWB prices using the National Bank's
# de-facto peg (denar held at ~61.5 per EUR; ANWB 95 ~1.60 EUR vs ERC 98.5 MKD confirms it). The MKD
# figure is kept in 'cap_original'.
MKD_PER_EUR = 61.5

# Row label as published (Cyrillic, escaped) -> (fuel_type, octane)
_SUPER = "ЕУРОСУПЕР"      # EUROSUPER
_DIESEL = "ЕУРОДИЗЕЛ"     # EURODIESEL
_BS = "БС"                                                    # BS
_ROWS = [
    (_SUPER + r"\s*" + _BS + r"\s*-\s*95", "95", 95),
    (_SUPER + r"\s*" + _BS + r"\s*-\s*98", "98", 98),
    (_DIESEL + r"\s*" + _BS, "DIESEL", None),
]
_UNIT = "ден/л"                                     # den/l


def parse_erc_homepage(html: str) -> Dict[str, Any]:
    """Return {'prices': {(fuel_type, octane): float}, 'date': date|None, 'decision_url': str|None}."""
    m = re.search(r"id=[\"']CeniLista[\"'].*?</table>", html, re.S)
    block = re.sub(r"<[^>]+>", "|", m.group(0)) if m else ""
    block = re.sub(r"\s+", " ", block)
    prices: Dict[tuple, float] = {}
    for pat, ft, octane in _ROWS:
        pm = re.search(pat + r"[^0-9]*?\|\s*([0-9]+(?:[.,][0-9]+)?)\s*" + _UNIT, block)
        if pm:
            prices[(ft, octane)] = float(pm.group(1).replace(",", "."))
    # newest "decision on maximum retail prices" link on the page -> effective date from the filename
    date = None
    url = None
    for lm in re.finditer(r"href=['\"]([^'\"]*?(20\d\d)\.(\d\d)\.(\d\d)[^'\"]*?Odluka[^'\"]*?ND[^'\"]*?\.pdf)['\"]",
                          html, re.I):
        try:
            d = datetime(int(lm.group(2)), int(lm.group(3)), int(lm.group(4))).date()
        except ValueError:
            continue
        if date is None or d > date:
            date, url = d, urllib.parse.urljoin(ERC_URL, urllib.parse.quote(lm.group(1), safe="/:%"))
    return {"prices": prices, "date": date, "decision_url": url}


def validate_cap(parsed: Dict[str, Any], today=None) -> Optional[str]:
    """Return an error string if the parsed cap must NOT be used, else None."""
    today = today or datetime.now(timezone.utc).date()
    pr = parsed.get("prices") or {}
    if ("DIESEL", None) not in pr or ("95", 95) not in pr:
        return "diesel and/or 95 missing"
    for k, v in pr.items():
        if not CAP_BAND[0] <= v <= CAP_BAND[1]:
            return f"{k} {v} outside plausibility band {CAP_BAND}"
    d = parsed.get("date")
    if d is None:
        return "no effective date found"
    if (today - d) > timedelta(days=CAP_MAX_AGE_DAYS) or d > today + timedelta(days=1):
        return f"effective date {d} not within {CAP_MAX_AGE_DAYS} days"
    return None


class NorthMacedoniaScraper(ANWBScraper):
    COUNTRY    = "MK"
    ISO3       = "MKD"
    CURRENCY   = "MKD"
    BBOX       = (40.85, 20.44, 42.37, 23.04)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90
    merge_report: Dict[str, Any] = {}
    cap_info: Dict[str, Any] = {}

    async def _fetch_cap(self) -> Optional[Dict[str, Any]]:
        try:
            async with self.session.get(ERC_URL, headers={"User-Agent": UA},
                                        timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                parsed = parse_erc_homepage(await resp.text())
        except Exception as e:
            print(f"[MK] ERC unreachable - no cap ({type(e).__name__}: {e})")
            return None
        err = validate_cap(parsed)
        if err:
            print(f"[MK] ERC cap not used: {err}")
            return None
        return parsed

    def build_cap_result(self, anwb: List[Dict[str, Any]], cap: Dict[str, Any]) -> SourceResult:
        d = cap["date"]
        ts = datetime(d.year, d.month, d.day, tzinfo=timezone.utc).isoformat()
        cur_counts: Dict[str, int] = {}
        for s in anwb:
            for p in s.get("prices") or []:
                cur_counts[p.get("currency")] = cur_counts.get(p.get("currency"), 0) + 1
        cur = max(cur_counts, key=cur_counts.get) if cur_counts else self.CURRENCY
        stations = []
        for s in anwb:
            c = {k: s.get(k) for k in ("id", "country", "name", "brand", "address", "city", "lat", "lon")}
            c["source"] = "regulator_cap"
            c["confidence"] = self.CONFIDENCE
            prices = []
            for (ft, octane), price in cap["prices"].items():
                e = self.price_entry(ft, price, "L", updated_at=ts, octane=octane)
                if cur == "EUR":
                    e["price"], e["currency"] = round(price / MKD_PER_EUR, 3), "EUR"
                    e["cap_original"] = {"price": price, "currency": "MKD", "mkd_per_eur": MKD_PER_EUR}
                prices.append(e)
            c["prices"] = prices
            stations.append(c)
        return SourceResult("regulator_cap", "ERC legal maximum price", stations, 20, "regulated_cap", cur)

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        anwb = await super().fetch_stations()
        try:
            cap = await self._fetch_cap()
        except Exception as e:
            print(f"[MK] ERC cap fetch failed: {type(e).__name__}: {e}")
            cap = None
        if not cap or not anwb:
            return anwb
        results = [SourceResult("anwb", "ANWB", anwb, 9, "aggregator", self.CURRENCY),
                   self.build_cap_result(anwb, cap)]
        merged, report = merge_sources(results, MergeConfig(country="MK"))
        self.merge_report = report
        # The page does not state the date the prices are valid FROM; the decision link filename carries the
        # decision date (2026.10.05), the prices apply from the next day (RKE: effective 2026-10-06 00:01).
        # We publish the filename date (conservative, never too new).
        self.cap_info = {"prices": {k[0] + (str(k[1]) if k[1] else ""): v for k, v in cap["prices"].items()},
                         "date": cap["date"].isoformat(), "date_basis": "decision_filename",
                         "source": "erc.org.mk", "url": ERC_URL, "decision_url": cap["decision_url"]}
        print(f"[MK] ERC legal-maximum fill: {report['regulated_fills']} price buckets (effective {cap['date']})"
              f" | final={report['final_station_count']} priced={report['priced_station_count']}")
        return merged
