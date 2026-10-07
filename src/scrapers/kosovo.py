"""Kosovo - ANWB stations + regulated MAXIMUM retail prices (gap fill).

IMPORTANT: the cap prices are a LEGAL MAXIMUM set by MINTI (Ministry of Industry, Entrepreneurship
and Trade; daily ceiling decision for diesel, petrol and LPG), NOT a measured station price. Most
stations charge at or just below it. Stations without an ANWB price get the cap, labelled
``basis: "regulated_max"`` by merge_engine; an ANWB price is never overridden.

Cap source (official): MINTI news posts "Cmimet maksimale te lejuara per derivatet e naftes, dates
DD.MM.YYYY" found through the site search on https://minti.rks-gov.net/ . The post text carries
Dizel / Benzine / Gas in EUR per litre. We publish a cap ONLY when the newest such post is within
the last 30 days and every value is plausible. As of 2026-10-07 the newest post on the site is
07.04.2026 (daily publication stopped), so no cap is produced and ANWB stations stay unchanged -
the code starts filling again by itself if MINTI resumes posting.
"""
import asyncio
import html as _html
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import aiohttp

from ._anwb import ANWBScraper
from .montenegro import merge_with_cap, CAP_UA, MAX_AGE_DAYS, PETROL_BAND, LPG_BAND

MINTI_BASE = "https://minti.rks-gov.net"
SEARCH_URLS = (MINTI_BASE + "/?s=%C3%A7mimet+maksimale", MINTI_BASE + "/?s=derivatet")
_POST_RE = re.compile(r'https://minti\.rks-gov\.net/news/cmimet-maksimale-te-lejuara-per-derivatet-'
                      r'e-naftes-dates-(\d{2})-(\d{2})-(\d{4})/')


def newest_post_url(search_html: str) -> Optional[tuple]:
    """(date, url) of the newest dated MINTI price post in a search-result page, or None."""
    best = None
    for m in _POST_RE.finditer(search_html):
        try:
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            continue
        if best is None or d > best[0]:
            best = (d, m.group(0))
    return best


def parse_post(raw_html: str, post_date: date, today: Optional[date] = None) -> Optional[Dict[str, Any]]:
    today = today or date.today()
    if post_date > today + timedelta(days=1) or (today - post_date).days > MAX_AGE_DAYS:
        return None
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw_html)
    t = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", t)))

    def val(label: str) -> Optional[float]:
        m = re.search(label + r"[^0-9]{0,40}?(\d[.,]\d{1,3})\s*(?:€|euro|EUR)", t, re.I)
        return float(m.group(1).replace(",", ".")) if m else None

    found = {"DIESEL": val(r"produktit\s+Dizel"), "95": val(r"produktit\s+Benzin[eë]"),
             "LPG": val(r"produktit\s+Gas")}
    prices = {}
    for k, v in found.items():
        if v is None:
            continue
        lo, hi = LPG_BAND if k == "LPG" else PETROL_BAND
        if not (lo <= v <= hi):
            return None
        prices[k] = v
    if "DIESEL" not in prices or "95" not in prices:
        return None
    return {"date": post_date.isoformat(), "valid_until": None, "prices": prices}


class KosovoScraper(ANWBScraper):
    COUNTRY    = "XK"
    ISO3       = "XKX"   # ISO 3166-1 alpha-3 used by EU/ANWB for Kosovo
    BBOX       = (41.85, 20.01, 43.27, 21.79)
    SOURCE     = "anwb.nl (ANWB POI API) + MINTI regulated max prices"
    CONFIDENCE = 0.90
    merge_report: Dict[str, Any] = {}

    async def _get(self, url: str) -> Optional[str]:
        async with self.session.get(url, headers={"User-Agent": CAP_UA},
                                    timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                print(f"[XK] {url} HTTP {resp.status}")
                return None
            return await resp.text()

    async def _fetch_cap(self) -> Optional[Dict[str, Any]]:
        try:
            best = None
            for u in SEARCH_URLS:
                page = await self._get(u)
                await asyncio.sleep(1)
                found = newest_post_url(page) if page else None
                if found and (best is None or found[0] > best[0]):
                    best = found
            if best is None:
                print("[XK] no MINTI price post found - no cap")
                return None
            if (date.today() - best[0]).days > MAX_AGE_DAYS:
                print(f"[XK] newest MINTI price post is {best[0]} (stale) - no cap")
                return None
            post = await self._get(best[1])
            cap = parse_post(post, best[0]) if post else None
            if cap is None:
                print("[XK] MINTI post unparseable or implausible - no cap")
            return cap
        except Exception as e:
            print(f"[XK] cap fetch failed: {e} - no cap")
            return None

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        anwb = await super().fetch_stations()
        cap = await self._fetch_cap()
        merged, report = merge_with_cap(self.COUNTRY, anwb, cap)
        self.merge_report = report
        if cap:
            print(f"[XK] regulated cap {cap['date']} {cap['prices']}: regulated_fills="
                  f"{report.get('regulated_fills')} priced {report.get('priced_station_count')}/{len(merged)}")
        return merged
