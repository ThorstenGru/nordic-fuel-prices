"""Luxembourg: ANWB station list + Ministry of the Economy legal maximum prices for unpriced buckets.

Luxembourg fixes ONE maximum retail price per fuel for the whole country. That is a LEGAL MAXIMUM, NOT a
price observed at a station (stations may sell below it). It only fills price buckets (95, 98, diesel)
for which ANWB has no price; the merge engine flags them basis='regulated_max' and never overrides an
ANWB station price.

Source: STATEC/LUSTAT SDMX API (open data, CC0, also listed on data.public.lu), series
DSD_PRIX_ESSENCE@DF_E5301 (SP95, SP98) and @DF_E5302 (DIE): "Maxima motor petrol/diesel prices", EUR/L,
newest observation per series with its date. Fallback: spritpreise.lu (republishes the same ministry
maxima with a "valid since" date). No cap when missing, outside EUR 0.8-3.0/L, or older than 30 days.
"""
import asyncio
import csv
import io
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import aiohttp

from ._anwb import ANWBScraper
try:
    from merge_engine import SourceResult, MergeConfig, merge_sources
except ImportError:   # package-style import (src not on sys.path)
    from ..merge_engine import SourceResult, MergeConfig, merge_sources

UA = "EuroFuelPrices/1.0 (+https://eurofuelprices.com)"
LUSTAT = "https://lustat.statec.lu/rest/data/LU1,DSD_PRIX_ESSENCE@DF_{df},1.0/all?lastNObservations=1&format=csv"
SPRITPREISE_URL = "https://www.spritpreise.lu/fr"
CAP_BAND = (0.8, 3.0)
CAP_MAX_AGE_DAYS = 30
_CODES = {"SP95": ("95", 95), "SP98": ("98", 98), "DIE": ("DIESEL", None)}


def parse_lustat_csv(text: str) -> Dict[tuple, Any]:
    """CSV rows -> {(fuel_type, octane): (price, date)} keeping the newest observation per series."""
    out: Dict[tuple, Any] = {}
    for row in csv.DictReader(io.StringIO(text)):
        key = _CODES.get((row.get("MOTOR_ENERGY") or "").strip())
        try:
            price = float(row["OBS_VALUE"])
            d = datetime.strptime(row["TIME_PERIOD"][:10], "%Y-%m-%d").date()
        except (KeyError, ValueError, TypeError):
            continue
        if key and (key not in out or d > out[key][1]):
            out[key] = (price, d)
    return out


def parse_spritpreise(html: str) -> Dict[tuple, Any]:
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    dm = re.search(r"en vigueur depuis le (\d\d)/(\d\d)/(\d{4})", t)
    if not dm:
        return {}
    d = datetime(int(dm.group(3)), int(dm.group(2)), int(dm.group(1))).date()
    out = {}
    for label, key in (("Diesel", ("DIESEL", None)), (r"Super 95 \(E10\)", ("95", 95)), (r"Super 98", ("98", 98))):
        m = re.search(label + r" ([0-9]),([0-9]{3}) €", t)
        if m:
            out[key] = (float(m.group(1) + "." + m.group(2)), d)
    return out


def validate_cap(series: Dict[tuple, Any], today=None) -> Optional[str]:
    today = today or datetime.now(timezone.utc).date()
    if ("DIESEL", None) not in series or ("95", 95) not in series:
        return "diesel and/or 95 missing"
    for k, (p, d) in series.items():
        if not CAP_BAND[0] <= p <= CAP_BAND[1]:
            return f"{k} {p} outside plausibility band {CAP_BAND}"
        if (today - d) > timedelta(days=CAP_MAX_AGE_DAYS) or d > today + timedelta(days=1):
            return f"{k} effective date {d} not within {CAP_MAX_AGE_DAYS} days"
    return None


class LuxembourgScraper(ANWBScraper):
    COUNTRY    = "LU"
    ISO3       = "LUX"
    BBOX       = (49.44, 5.73, 50.18, 6.53)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90
    merge_report: Dict[str, Any] = {}
    cap_info: Dict[str, Any] = {}

    async def _get(self, url: str) -> str:
        async with self.session.get(url, headers={"User-Agent": UA},
                                    timeout=aiohttp.ClientTimeout(total=30)) as r:
            if r.status != 200:
                raise RuntimeError(f"HTTP {r.status} {url}")
            return await r.text()

    async def _fetch_cap(self) -> Optional[Dict[str, Any]]:
        series: Dict[tuple, Any] = {}
        src_url = "https://lustat.statec.lu/rest/data/LU1,DSD_PRIX_ESSENCE@DF_E5301|DF_E5302"
        try:
            for df in ("E5301", "E5302"):
                series.update(parse_lustat_csv(await self._get(LUSTAT.format(df=df))))
                await asyncio.sleep(1)
            err = validate_cap(series)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        if err:
            print(f"[LU] LUSTAT cap not used ({err}); trying spritpreise.lu")
            try:
                series = parse_spritpreise(await self._get(SPRITPREISE_URL))
                err = validate_cap(series)
                src_url = SPRITPREISE_URL
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
            if err:
                print(f"[LU] cap not used: {err}")
                return None
        return {"series": series, "url": src_url}

    def build_cap_result(self, anwb: List[Dict[str, Any]], cap: Dict[str, Any]) -> SourceResult:
        stations = []
        for s in anwb:
            c = {k: s.get(k) for k in ("id", "country", "name", "brand", "address", "city", "lat", "lon")}
            c["source"] = "regulator_cap"
            c["confidence"] = self.CONFIDENCE
            c["prices"] = [self.price_entry(
                ft, price, "L", octane=octane,
                updated_at=datetime(d.year, d.month, d.day, tzinfo=timezone.utc).isoformat())
                for (ft, octane), (price, d) in cap["series"].items()]
            stations.append(c)
        return SourceResult("regulator_cap", "Luxembourg Ministry of the Economy maximum price", stations, 20,
                            "regulated_cap", self.CURRENCY)

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        anwb = await super().fetch_stations()
        try:
            cap = await self._fetch_cap()
        except Exception as e:
            print(f"[LU] cap fetch failed: {type(e).__name__}: {e}")
            cap = None
        if not cap or not anwb:
            return anwb
        results = [SourceResult("anwb", "ANWB", anwb, 9, "aggregator", self.CURRENCY),
                   self.build_cap_result(anwb, cap)]
        merged, report = merge_sources(results, MergeConfig(country="LU"))
        self.merge_report = report
        self.cap_info = {"prices": {k[0] + (str(k[1]) if k[1] else ""): v[0] for k, v in cap["series"].items()},
                         "dates": {k[0]: v[1].isoformat() for k, v in cap["series"].items()}, "url": cap["url"]}
        print(f"[LU] legal-maximum fill: {report['regulated_fills']} price buckets"
              f" | final={report['final_station_count']} priced={report['priced_station_count']}")
        return merged
