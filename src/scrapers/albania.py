"""Albania - ANWB stations + the Transparency Board's retail MAXIMUM (gap fill).

The cap (Bordi i Transparencës, Ministry of Finance newsroom) is a legal ceiling for all stations in
a "special situation" period, not a measured pump price; it only fills buckets ANWB lacks, labelled
``basis: regulated_max``. financa.gov.al sits behind bot protection, so the decision is recorded in
``seed/al_cap.json`` (read on the primary page) and published for at most 14 days - the Board meets
irregularly and the series has been switched off before. ANWB delivers EUR (no ALL rate at the ECB),
so the lek cap is converted with the open.er-api.com daily rate (attribution: exchangerate-api.com);
the lek figure is kept in ``cap_original``.
"""
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

from ._anwb import ANWBScraper
from .montenegro import merge_with_cap

_SEED = Path(__file__).resolve().parent.parent / "seed" / "al_cap.json"
_FX_URL = "https://open.er-api.com/v6/latest/EUR"
CAP_MAX_AGE_DAYS = 14
LEK_PER_EUR_BAND = (70.0, 130.0)


def cap_age_ok(cap: dict, today: Optional[date] = None) -> Optional[str]:
    today = today or datetime.now(timezone.utc).date()
    age = (today - date.fromisoformat(cap["decision_date"])).days
    if age > CAP_MAX_AGE_DAYS or age < -1:
        return f"decision is {age} days old"
    return None


def to_eur_cap(cap: dict, rate: float) -> Dict[str, Any]:
    prices = {k: round(v / rate, 3) for k, v in cap["retail_max_lek"].items()}
    return {"date": cap["decision_date"], "valid_until": None, "prices": prices}


class AlbaniaScraper(ANWBScraper):
    COUNTRY    = "AL"
    ISO3       = "ALB"
    CURRENCY   = "ALL"
    BBOX       = (39.63, 19.27, 42.68, 21.06)
    SOURCE     = "anwb.nl (ANWB POI API) + Transparency Board maximum (financa.gov.al)"
    CONFIDENCE = 0.90
    merge_report: Dict[str, Any] = {}

    async def _fetch_cap(self) -> Optional[Dict[str, Any]]:
        try:
            cap = json.loads(_SEED.read_text(encoding="utf-8"))
            why = cap_age_ok(cap)
            if why:
                print(f"[AL] Board cap not published: {why}")
                return None
            async with self.session.get(_FX_URL, timeout=aiohttp.ClientTimeout(total=30)) as r:
                r.raise_for_status()
                rate = float((await r.json(content_type=None))["rates"]["ALL"])
            if not LEK_PER_EUR_BAND[0] <= rate <= LEK_PER_EUR_BAND[1]:
                print(f"[AL] implausible ALL rate {rate} - no cap")
                return None
            out = to_eur_cap(cap, rate)
            out["lek"], out["rate"] = cap["retail_max_lek"], rate
            return out
        except Exception as e:
            print(f"[AL] cap unavailable: {type(e).__name__}: {e}")
            return None

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        anwb = await super().fetch_stations()
        cap = await self._fetch_cap()
        merged, report = merge_with_cap(self.COUNTRY, anwb, cap)
        self.merge_report = report
        if cap:
            for s in merged:
                for p in s.get("prices", []):
                    if p.get("basis") == "regulated_max" and p.get("fuel_type") in cap["lek"]:
                        p["cap_original"] = {"price": cap["lek"][p["fuel_type"]], "currency": "ALL",
                                             "all_per_eur": cap["rate"]}
            print(f"[AL] Board cap {cap['date']}: regulated_fills={report.get('regulated_fills')} "
                  f"priced {report.get('priced_station_count')}/{len(merged)}")
        return merged
