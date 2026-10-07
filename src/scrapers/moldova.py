import json
import math
import aiohttp
from typing import List, Dict, Any, Optional
from .base import BaseScraper

# Moldova: ANRE (National Energy Regulatory Agency) e-Carburanti public API.
#   GET /public/         -> JSON list of all registered stations (incl. inactive ones)
#   GET /public/plafon/  -> {"date": "...", "b_pc": <petrol cap>, "m_pc": <diesel cap>} (MDL/L)
#
# Per-station fields used: station_status (1 = active; 0 / 4 = inactive/suspended), gasoline,
# diesel, gpl (MDL per litre, null when not sold), x/y (EPSG:3857 metres), station_name,
# fullstreet/addrnum/bua/lev1/lev2 (address). There is no brand field and no price timestamp.
# Petrol is standard 95 -> E5, diesel -> DIESEL, gpl -> LPG.
# The daily cap is only used as a sanity bound / for logging, never as a station price.

API_URL = "https://api.ecarburanti.anre.md/public/"
CAP_URL = "https://api.ecarburanti.anre.md/public/plafon/"

_ACTIVE_STATUS = 1
_R = 6378137.0

# MDL/L plausibility bands (cap ~34-36 MDL; LPG ~15-20)
_BANDS = {
    "E5":     (20.0, 60.0),
    "DIESEL": (20.0, 60.0),
    "LPG":    (8.0, 40.0),
}
_FIELDS = (("gasoline", "E5"), ("diesel", "DIESEL"), ("gpl", "LPG"))

_LAT_MIN, _LAT_MAX = 45.4, 48.6
_LON_MIN, _LON_MAX = 26.5, 30.3

# normalised station_name -> display brand
_BRANDS = {
    "LUKOIL": "Lukoil", "ROMPETROL": "Rompetrol", "VENTO": "Vento", "PETROM": "Petrom",
    "BEMOL": "Bemol", "NOW OIL": "Now Oil", "E-GAZ": "E-Gaz", "FOX PETROL": "Fox Petrol",
    "BASAPETROL": "Basapetrol", "TLX": "TLX", "AVANTE": "Avante", "PETROCUB": "Petrocub",
    "GLORIA-QVARC": "Gloria-Qvarc",
}


def _mercator_to_wgs84(x: float, y: float):
    lon = math.degrees(x / _R)
    lat = math.degrees(math.atan(math.sinh(y / _R)))
    return lat, lon


def _decode(raw: bytes) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return json.loads(text)


def _price(v: Any) -> Optional[float]:
    try:
        return float(str(v).replace(",", "."))
    except (ValueError, TypeError):
        return None


class MoldovaScraper(BaseScraper):
    COUNTRY    = "MD"
    CURRENCY   = "MDL"
    SOURCE     = "ANRE e-Carburanti (api.ecarburanti.anre.md)"
    CONFIDENCE = 1.0
    # Official regulator register, but periodic submissions with no price timestamps and most
    # prices simply equal the daily regulated cap -> B.
    GRADE      = "B"

    async def _get(self, url: str) -> Any:
        async with self.session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=60),
            headers={"User-Agent": "Mozilla/5.0 (compatible; EuroFuelPrices/1.0)",
                     "Accept": "application/json"},
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"[MD] ANRE HTTP {resp.status} for {url}")
            return _decode(await resp.read())

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        data = await self._get(API_URL)
        if not isinstance(data, list) or not data:
            raise RuntimeError(f"[MD] Unexpected ANRE payload: {type(data)}")

        cap = None
        try:
            cap = await self._get(CAP_URL)
        except Exception as e:
            print(f"[MD] cap endpoint unavailable: {e}")

        stations: List[Dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict) or item.get("station_status") != _ACTIVE_STATUS:
                continue
            try:
                lat, lon = _mercator_to_wgs84(float(item["x"]), float(item["y"]))
            except (KeyError, ValueError, TypeError):
                continue
            if not (_LAT_MIN <= lat <= _LAT_MAX and _LON_MIN <= lon <= _LON_MAX):
                continue

            prices = []
            for field, ft in _FIELDS:
                p = _price(item.get(field))
                lo, hi = _BANDS[ft]
                if p is not None and lo <= p <= hi:
                    prices.append(self.price_entry(ft, round(p, 2), "L", octane=95 if ft == "E5" else None))
            if not prices:
                continue

            name = (item.get("station_name") or "").strip()
            brand = _BRANDS.get(name.upper(), name)
            street = (item.get("fullstreet") or "").strip()
            num = str(item.get("addrnum") or "").strip()
            city = (item.get("bua") or item.get("lev1") or "").strip()
            if city.lower() == "extravilan":
                city = (item.get("lev1") or "").strip()

            stations.append({
                "id":         f"md_{item.get('idno', '')}_{len(stations)}",
                "country":    "MD",
                "name":       name,
                "brand":      brand,
                "address":    f"{street} {num}".strip(),
                "city":       city,
                "lat":        round(lat, 6),
                "lon":        round(lon, 6),
                "source":     self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices":     prices,
            })

        if not stations:
            raise RuntimeError("[MD] ANRE returned no usable active stations")
        print(f"[MD] {len(stations)} stations from ANRE e-Carburanti (cap: {cap})")
        return stations
