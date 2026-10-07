import aiohttp
import asyncio
import os
import re
from typing import List, Dict, Any, Tuple
from .base import BaseScraper
try:
    from merge_engine import SourceResult, MergeConfig, merge_sources
except ImportError:   # package-style import (src not on sys.path)
    from ..merge_engine import SourceResult, MergeConfig, merge_sources
from ._anwb import ANWBScraper
from . import geocoder as _geo

# Free, no-auth APIs mandated by Danish law from Jan 2026
SHELL_URL = "https://shellpumpepriser.geoapp.me/v1/prices"
Q8_URL = "https://beta.q8.dk/Station/GetStationPrices?page=1&pageSize=2000"
OK_URL = "https://mobility-prices.ok.dk/api/v1/fuel-prices"
GOON_URL = "https://goon.nu/wp-json/goon/v1/pump-prices"   # Bearer key from env GOON_API_KEY (never hardcode)
DK_TZ = "Europe/Copenhagen"   # Shell/Q8/OK/Go'on deliver naive or local timestamps

# OK: product_name (lower-case) -> fuel_type. 'Oktan 100' is a premium grade without a site fuel type.
OK_FUEL_MAP = {"blyfri 95": "E10", "svovlfri diesel": "DIESEL"}


class _DKAnwb(ANWBScraper):
    """ANWB coverage for Denmark: Circle K, Uno-X, Go'On, Oil! etc."""
    COUNTRY    = "DK"
    ISO3       = "DNK"
    CURRENCY   = "DKK"
    BBOX       = (54.80, 8.00, 57.80, 15.20)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90

# Shell: (fuelType, octane) → fuel_type
SHELL_FUEL_MAP = {
    ("Autobenzin", "95"):  "E10",
    ("Autobenzin", "98"):  "E5",
    ("Autodiesel", None):  "DIESEL",
    ("Autodiesel", ""):    "DIESEL",
}

# Q8/F24: product name keywords → fuel_type
Q8_FUEL_MAP = [
    ("95 E10",    "E10"),
    ("95 Extra",  "E5"),
    ("95",        "E10"),   # fallback
    ("Diesel Extra", "DIESEL"),
    ("Diesel",    "DIESEL"),
    ("HVO",       "HVO100"),
    ("Gas",       "LPG"),
]


class DenmarkScraper(BaseScraper):
    COUNTRY = "DK"
    CURRENCY = "DKK"
    SOURCE = "ok+shell+q8+goon+anwb.nl open APIs"
    CONFIDENCE = 1.0  # Mandatory government reporting
    merge_report: Dict[str, Any] = {}

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        # (id, display name, priority, kind, coroutine); a failing/skipped source never blanks the country
        specs = [
            ("ok",    "OK",     1, "company",    self._fetch_ok()),
            ("shell", "Shell",  2, "company",    self._fetch_shell()),
            ("q8",    "Q8",     3, "company",    self._fetch_q8()),
            ("goon",  "Go'on",  4, "company",    self._fetch_goon()),
            ("anwb",  "ANWB",   9, "aggregator", _DKAnwb(self.session).fetch_stations()),
        ]
        fetched = await asyncio.gather(*(s[4] for s in specs), return_exceptions=True)

        results: List[SourceResult] = []
        for (sid, name, prio, kind, _), res in zip(specs, fetched):
            if isinstance(res, BaseException):
                err = f"{type(res).__name__}: {res}"
                print(f"[DK/{sid}] FAILED: {err}")
                results.append(SourceResult(sid, name, [], prio, kind, self.CURRENCY, ok=False, error=err))
            elif not res:
                err = ("GOON_API_KEY not set" if sid == "goon" and not os.environ.get("GOON_API_KEY", "").strip()
                       else "returned 0 stations")
                print(f"[DK/{sid}] {err}")
                results.append(SourceResult(sid, name, [], prio, kind, self.CURRENCY, ok=False, error=err))
            else:
                results.append(SourceResult(sid, name, res, prio, kind, self.CURRENCY))

        if not any(r.ok for r in results):
            raise RuntimeError("DK: all sub-sources failed or returned nothing")

        merged, report = merge_sources(results, MergeConfig(country="DK"))
        self.merge_report = report
        print("[DK] merged: " + ", ".join(f"{k}={v['stations_in']}" for k, v in report["sources"].items())
              + f" | final={report['final_station_count']} priced={report['priced_station_count']}"
              + f" matched={report['matched_pairs']} conflicts={report['conflicts']}"
              + f" outliers={report['outliers_dropped']}")
        return merged

    # -- OK (open JSON, GPS, per-station timestamp) ---------------------------
    async def _fetch_ok(self) -> List[Dict]:
        async with self.session.get(OK_URL, timeout=aiohttp.ClientTimeout(total=30),
                                    headers={"Accept": "application/json"}) as resp:
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}")
            data = await resp.json(content_type=None)
        stations = []
        for item in (data or {}).get("items", []):
            c = item.get("coordinates") or {}
            try:
                lat, lon = float(c.get("latitude")), float(c.get("longitude"))
            except (TypeError, ValueError):
                lat = lon = None
            ts = item.get("last_updated_time")
            prices = []
            for p in item.get("prices", []):
                ft = OK_FUEL_MAP.get((p.get("product_name") or "").strip().lower())
                oct_ = 95 if ft == "E10" else None
                try:
                    price = float(p.get("price"))
                except (TypeError, ValueError):
                    continue
                if ft and price > 0:
                    prices.append(self.price_entry(ft, price, "L", updated_at=ts, tz=DK_TZ, octane=oct_))
            if not prices:
                continue
            city = item.get("city", "") or ""
            stations.append({
                "id": f"dk_ok_{item.get('facility_number', '')}",
                "country": "DK",
                "name": f"OK {city}".strip(),
                "address": f"{item.get('street', '') or ''} {item.get('house_number', '') or ''}".strip(),
                "city": city,
                "postal_code": str(item.get("postal_code", "") or ""),
                "brand": "OK",
                "lat": lat,
                "lon": lon,
                "source": "mobility-prices.ok.dk",
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })
        return stations

    # -- Go'on (Bearer key from env) ------------------------------------------
    async def _fetch_goon(self) -> List[Dict]:
        key = os.environ.get("GOON_API_KEY", "").strip()
        if not key:
            print("[DK/goon] GOON_API_KEY not set - skipping Go'on source")
            return []
        async with self.session.get(
            GOON_URL, timeout=aiohttp.ClientTimeout(total=30),
            headers={"Accept": "application/json", "Authorization": f"Bearer {key}"},
        ) as resp:
            if resp.status != 200:
                body = (await resp.text())[:150].replace(key, "***")
                raise RuntimeError(f"HTTP {resp.status} {body}")   # 401/403 bad key, 429 = >1 req/30 s
            data = await resp.json(content_type=None)
        stations = []
        for item in (data or {}).get("stations", []):
            c = item.get("coordinates") or {}
            try:
                lat, lon = float(c.get("latitude")), float(c.get("longitude"))
            except (TypeError, ValueError):
                lat = lon = None
            prices = []
            for p in item.get("prices", []):
                ft = self._map_goon_fuel(p.get("fuelType") or "", p.get("octane"))
                try:
                    price = float(p.get("price"))
                except (TypeError, ValueError):
                    continue
                if ft and price > 0:
                    prices.append(self.price_entry(ft, price, "L", updated_at=p.get("lastUpdated"), tz=DK_TZ,
                                                   octane=95 if ft == "E10" else None))
            if not prices:
                continue
            city = item.get("city", "") or ""
            stations.append({
                "id": f"dk_goon_{item.get('stationId', '')}",
                "country": "DK",
                "name": f"Go'on {city}".strip(),
                "address": f"{item.get('street', '') or ''} {item.get('houseNumber', '') or ''}".strip(),
                "city": city,
                "postal_code": str(item.get("postalCode", "") or ""),
                "brand": "Go'on",
                "lat": lat,
                "lon": lon,
                "source": "goon.nu",
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })
        return stations

    @staticmethod
    def _map_goon_fuel(fuel_type: str, octane):
        ft = fuel_type.lower()
        if ft == "autodiesel":
            return "DIESEL"
        if ft == "autobenzin" and str(octane) == "95":
            return "E10"
        return None   # 92 octane etc. have no matching fuel type on the site

    async def _fetch_shell(self) -> List[Dict]:
        try:
            async with self.session.get(
                SHELL_URL, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                if resp.status != 200:
                    print(f"[DK/Shell] HTTP {resp.status}")
                    return []
                data = await resp.json(content_type=None)
        except Exception as e:
            print(f"[DK/Shell] {e}")
            return []

        stations = []
        for item in data:
            coords = item.get("coordinates", {})
            try:
                lat = float(coords.get("latitude", 0)) or None
                lon = float(coords.get("longitude", 0)) or None
            except (TypeError, ValueError):
                lat = lon = None

            prices = []
            for p in item.get("prices", []):
                ft = self._map_shell_fuel(
                    p.get("fuelType", ""), p.get("octane") or ""
                )
                if not ft:
                    continue
                try:
                    price = float(p["price"])
                except (KeyError, TypeError, ValueError):
                    continue
                if price > 0:
                    oct_ = None
                    if ft == "E10":
                        oct_ = 95
                    elif ft == "E5":
                        oct_ = 98 if str(p.get("octane") or "") == "98" else 95
                    prices.append(self.price_entry(ft, price, "L", updated_at=p.get("lastUpdated"), tz=DK_TZ,
                                                   octane=oct_))

            if not prices:
                continue

            stations.append({
                "id": f"dk_shell_{item.get('stationId', '')}",
                "country": "DK",
                "name": f"Shell {item.get('city', '')}".strip(),
                "address": f"{item.get('street', '')} {item.get('houseNumber', '') or ''}".strip(),
                "city": item.get("city", ""),
                "postal_code": item.get("postalCode", ""),
                "brand": "Shell",
                "lat": lat,
                "lon": lon,
                "source": "shellpumpepriser.geoapp.me",
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })

        return stations

    async def _fetch_q8(self) -> List[Dict]:
        try:
            async with self.session.get(
                Q8_URL,
                timeout=aiohttp.ClientTimeout(total=20),
                headers={"Accept": "application/json"},
            ) as resp:
                if resp.status != 200:
                    print(f"[DK/Q8] HTTP {resp.status}")
                    return []
                data = await resp.json(content_type=None)
        except Exception as e:
            print(f"[DK/Q8] {e}")
            return []

        raw = data.get("data", {}).get("stationsPrices", [])
        stations = []
        for item in raw:
            prices = []
            for p in item.get("products", []):
                ft = self._map_q8_fuel(p.get("productName", ""))
                if not ft:
                    continue
                try:
                    price = float(p["price"])
                except (KeyError, TypeError, ValueError):
                    continue
                if price > 0:
                    # Q8 petrol names state 95 ("95 E10", "95 Extra", "95")
                    prices.append(self.price_entry(ft, price, "L", updated_at=p.get("priceChangeDate"), tz=DK_TZ,
                                                   octane=95 if ft in ("E10", "E5") else None))

            if not prices:
                continue

            city, postal, street = self._parse_q8_address(item.get("address", ""))
            stations.append({
                "id": f"dk_q8_{item.get('stationId', '')}",
                "country": "DK",
                "name": item.get("stationName", ""),
                "address": item.get("address", ""),
                "city": city,
                "postal_code": postal,
                "geo_street": street,   # extracted street component for geocoding
                "brand": item.get("stationName", ""),
                "lat": None,  # Q8 API doesn't include coordinates
                "lon": None,
                "source": "beta.q8.dk",
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })

        await _geo.apply_geocoding(
            stations, "DK", self.session,
            key_fn=lambda s: s["id"],
            query_fn=lambda s: (s.get("city", ""), s.get("geo_street", ""), s.get("postal_code", "")),
        )

        for s in stations:
            s.pop("geo_street", None)

        return stations

    def _map_shell_fuel(self, fuel_type: str, octane: str) -> str | None:
        key = (fuel_type, octane if octane else None)
        ft = SHELL_FUEL_MAP.get(key)
        if not ft:
            # Try without octane
            ft = SHELL_FUEL_MAP.get((fuel_type, None))
        return ft

    def _map_q8_fuel(self, product_name: str) -> str | None:
        name = product_name.lower()
        for keyword, ft in Q8_FUEL_MAP:
            if keyword.lower() in name:
                return ft
        return None

    def _parse_q8_address(self, address: str) -> Tuple[str, str, str]:
        """Parse Q8 address string → (city, postal, street).

        Format: "Street [Number] City PostalCode Danmark"
        e.g. "Dronningemaen 34 Svendborg 5700 Danmark"
        → city="Svendborg", postal="5700", street="Dronningemaen 34"
        """
        match = re.search(r'(\d{4})', address)
        postal = match.group(1) if match else ""
        street = ""
        if match:
            before_postal = address[:match.start()].strip()
            words = before_postal.split()
            city = words[-1] if words else ""
            street = " ".join(words[:-1]) if len(words) > 1 else ""
        else:
            city = ""
        return city, postal, street
