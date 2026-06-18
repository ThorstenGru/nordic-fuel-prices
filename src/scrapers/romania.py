import json
import aiohttp
from typing import List, Dict, Any, Optional
from .base import BaseScraper

# Romania: mandatory fuel price reporting via ANPC (National Consumer Protection Authority)
# Multiple possible endpoints tried in order:
#   1. peco-online.ro — popular aggregator, gets data from ANPC feed
#   2. carburanti.raa.ro — Registrul Auto Român (Romanian Auto Registry) API
#   3. ANPC preturi-carburanti — official government portal

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
}

# Map Romanian fuel type strings → internal types
_FUEL_KEYWORDS = [
    ("hvo",         "HVO100", "L"),
    ("e85",         "E85",    "L"),
    ("gpl",         "LPG",    "L"),
    ("gaz pet",     "LPG",    "L"),
    ("gaz nat",     "CNG",    "kg"),
    ("cng",         "CNG",    "kg"),
    ("premium 98",  "E5",     "L"),
    ("super 98",    "E5",     "L"),
    ("benzina 98",  "E5",     "L"),
    ("98",          "E5",     "L"),
    ("benzina",     "E5",     "L"),
    ("motorina",    "DIESEL", "L"),
    ("diesel",      "DIESEL", "L"),
]

_LAT_MIN, _LAT_MAX = 43.5, 48.4
_LON_MIN, _LON_MAX = 22.0, 30.2


def _map_fuel(name: str) -> Optional[tuple]:
    n = name.lower()
    for kw, ft, unit in _FUEL_KEYWORDS:
        if kw in n:
            return ft, unit
    return None


class RomaniaScraper(BaseScraper):
    COUNTRY = "RO"
    CURRENCY = "RON"
    SOURCE = "peco-online.ro"
    CONFIDENCE = 0.90

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        # Try each source in order — return on first success
        for method in (
            self._try_peco_online,
            self._try_peco_online_post,
            self._try_raa,
        ):
            stations = await method()
            if stations:
                print(f"[RO] {len(stations)} stations")
                return stations
        print("[RO] All endpoints returned 0 stations")
        return []

    async def _try_peco_online(self) -> List[Dict]:
        """peco-online.ro GET endpoint — tries several tip_carburant values."""
        for tip in ("", "0", "1"):
            params = {"action": "getStationsJson"}
            if tip:
                params["tip_carburant"] = tip
            try:
                async with self.session.get(
                    "https://www.peco-online.ro/index.php",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30),
                    headers=_BROWSER_HEADERS,
                ) as resp:
                    if resp.status != 200:
                        continue
                    text = await resp.text()
                    if not text or len(text) < 20:
                        continue
                    try:
                        raw = json.loads(text)
                    except Exception:
                        continue
                    items = self._unwrap(raw)
                    if items:
                        result = self._parse_items(items, "peco-online.ro")
                        if result:
                            return result
            except Exception:
                pass
        return []

    async def _try_peco_online_post(self) -> List[Dict]:
        """peco-online.ro POST with form data (AJAX-style request)."""
        for tip in ("", "0"):
            data = {"action": "getStationsJson"}
            if tip:
                data["tip_carburant"] = tip
            try:
                async with self.session.post(
                    "https://www.peco-online.ro/index.php",
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=30),
                    headers=_BROWSER_HEADERS,
                ) as resp:
                    if resp.status != 200:
                        continue
                    text = await resp.text()
                    if not text or len(text) < 20:
                        continue
                    try:
                        raw = json.loads(text)
                    except Exception:
                        continue
                    items = self._unwrap(raw)
                    if items:
                        result = self._parse_items(items, "peco-online.ro")
                        if result:
                            return result
            except Exception:
                pass
        return []

    async def _try_raa(self) -> List[Dict]:
        """Registrul Auto Român API."""
        for url in (
            "https://carburanti.raa.ro/api/statii",
            "https://carburanti.raa.ro/api/stations",
            "https://carburanti.raa.ro/api/v1/statii",
        ):
            try:
                async with self.session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=30),
                    headers={**_BROWSER_HEADERS, "Referer": "https://carburanti.raa.ro/"},
                ) as resp:
                    if resp.status != 200:
                        print(f"[RO] RAA HTTP {resp.status} — {url}")
                        continue
                    raw = await resp.json(content_type=None)
                    items = self._unwrap(raw)
                    if items:
                        result = self._parse_items(items, "raa.ro")
                        if result:
                            return result
            except Exception as e:
                print(f"[RO] RAA {e} — {url}")
        return []

    def _unwrap(self, raw) -> list:
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            return (
                raw.get("stations") or raw.get("statii") or
                raw.get("data") or raw.get("results") or
                raw.get("items") or []
            )
        return []

    def _parse_items(self, items: list, source: str) -> List[Dict]:
        stations = []
        for item in items:
            if not isinstance(item, dict):
                continue
            prices = self._parse_prices(item)
            if not prices:
                continue

            try:
                lat = float(item.get("lat") or item.get("latitude") or 0)
                lon = float(
                    item.get("lng") or item.get("lon") or
                    item.get("longitude") or item.get("long") or 0
                )
                if not (_LAT_MIN <= lat <= _LAT_MAX) or not (_LON_MIN <= lon <= _LON_MAX):
                    lat = lon = None
            except (ValueError, TypeError):
                lat = lon = None

            name = (
                item.get("station_name") or item.get("denumire") or
                item.get("name") or item.get("naziv") or ""
            ).strip()
            sid = item.get("id") or item.get("station_id") or len(stations)

            stations.append({
                "id": f"ro_{sid}",
                "country": "RO",
                "name": name,
                "brand": (item.get("brand") or item.get("marca") or name).strip(),
                "address": (item.get("adresa") or item.get("address") or "").strip(),
                "city": (
                    item.get("localitate") or item.get("oras") or
                    item.get("city") or item.get("town") or ""
                ).strip(),
                "lat": lat,
                "lon": lon,
                "source": source,
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })
        return stations

    def _parse_prices(self, item: dict) -> List[Dict]:
        prix = (
            item.get("carburanti") or item.get("prices") or
            item.get("preturi") or item.get("price_list") or []
        )
        seen: set = set()
        prices = []

        if isinstance(prix, list):
            for p in prix:
                if not isinstance(p, dict):
                    continue
                fname = (
                    p.get("fuel_type") or p.get("tip") or
                    p.get("tip_carburant") or p.get("name") or ""
                )
                val = p.get("price") or p.get("pret") or p.get("valoare")
                ft_info = _map_fuel(str(fname))
                if not ft_info or ft_info[0] in seen:
                    continue
                try:
                    price = float(str(val).replace(",", "."))
                except (ValueError, TypeError):
                    continue
                if price > 0:
                    prices.append(self.price_entry(ft_info[0], price, ft_info[1]))
                    seen.add(ft_info[0])

        elif isinstance(prix, dict):
            for fname, val in prix.items():
                ft_info = _map_fuel(fname)
                if not ft_info or ft_info[0] in seen:
                    continue
                try:
                    price = float(str(val).replace(",", "."))
                except (ValueError, TypeError):
                    continue
                if price > 0:
                    prices.append(self.price_entry(ft_info[0], price, ft_info[1]))
                    seen.add(ft_info[0])

        return prices
