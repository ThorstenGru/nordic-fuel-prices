import aiohttp
import asyncio
import math
import os
import re
from typing import List, Dict, Any, Tuple
from .base import BaseScraper
from ._anwb import ANWBScraper
from . import geocoder as _geo

# Free, no-auth APIs mandated by Danish law from Jan 2026
SHELL_URL = "https://shellpumpepriser.geoapp.me/v1/prices"
Q8_URL = "https://beta.q8.dk/Station/GetStationPrices?page=1&pageSize=2000"
OK_URL = "https://mobility-prices.ok.dk/api/v1/fuel-prices"
GOON_URL = "https://goon.nu/wp-json/goon/v1/pump-prices"   # Bearer key from env GOON_API_KEY (never hardcode)
DK_TZ = "Europe/Copenhagen"   # Shell/Q8/OK/Go'on deliver naive or local timestamps

# Duplicate suppression: same canonical brand AND within this distance => same station
MERGE_RADIUS_M = 100.0
# Source priority for filling prices (official / brand-direct first, ANWB aggregator last)
SOURCE_PRIORITY = ["ok", "shell", "q8", "goon", "anwb"]

# Canonical brand detection: (regex on lower-cased name/brand, canonical brand)
BRAND_PATTERNS = [
    (re.compile(r"\bshell\b"), "shell"),
    (re.compile(r"\bq8\b"), "q8"),
    (re.compile(r"\bf24\b"), "f24"),
    (re.compile(r"^ok\b|\bok\s*(benzin|tank|plus)\b"), "ok"),
    (re.compile(r"circle\s*k"), "circlek"),
    (re.compile(r"\buno[\s-]*x\b"), "unox"),
    (re.compile(r"go['\u2019` ]?on\b"), "goon"),
    (re.compile(r"^oil!?(\s|$)|\boil!"), "oil"),
    (re.compile(r"\bingo\b"), "ingo"),
]

# OK: product_name (lower-case) -> fuel_type. 'Oktan 100' is a premium grade without a site fuel type.
OK_FUEL_MAP = {"blyfri 95": "E10", "svovlfri diesel": "DIESEL"}


def canonical_brand(*names: str):
    """Return canonical chain id, or None when unknown (unknown brands are never merged)."""
    for n in names:
        low = (n or "").lower().strip()
        if not low:
            continue
        for rx, brand in BRAND_PATTERNS:
            if rx.search(low):
                return brand
    return None


def _dist_m(a_lat, a_lon, b_lat, b_lon) -> float:
    dlat = (b_lat - a_lat) * 111_320.0
    dlon = (b_lon - a_lon) * 111_320.0 * math.cos(math.radians((a_lat + b_lat) / 2))
    return math.hypot(dlat, dlon)


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

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        names = ["ok", "shell", "q8", "goon", "anwb"]
        tasks = [self._fetch_ok(), self._fetch_shell(), self._fetch_q8(),
                 self._fetch_goon(), _DKAnwb(self.session).fetch_stations()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        by_source: Dict[str, List[Dict]] = {}
        for name, res in zip(names, results):
            if isinstance(res, BaseException):
                print(f"[DK/{name}] FAILED: {type(res).__name__}: {res}")
                continue
            if not res:
                print(f"[DK/{name}] returned 0 stations")
                continue
            by_source[name] = res
        if not by_source:
            raise RuntimeError("DK: all sub-sources failed or returned nothing")

        raw_total = sum(len(v) for v in by_source.values())
        merged = self._merge(by_source)
        print("[DK] sources: " + ", ".join(f"{k}={len(v)}" for k, v in by_source.items())
              + f" | before dedupe={raw_total} after={len(merged)} (merged {raw_total - len(merged)})")
        return merged

    # -- merge / dedupe ------------------------------------------------------
    def _merge(self, by_source: Dict[str, List[Dict]]) -> List[Dict]:
        """Conservative cross-source dedupe.

        Two stations from different sources are the same only when the brand is known and equal,
        both have coordinates within MERGE_RADIUS_M, and the match is mutually unique (each is the
        only candidate of the other). Anything ambiguous stays separate. Prices are filled per fuel
        type by SOURCE_PRIORITY; nothing is averaged. Each price carries 'source'; each station
        carries a 'sources' list.
        """
        kept: List[Dict] = []
        for src in SOURCE_PRIORITY:
            batch = by_source.get(src)
            if not batch:
                continue
            for st in batch:
                st["_brand"] = canonical_brand(st.get("brand"), st.get("name"))
                for p in st.get("prices", []):
                    p["source"] = src
                st["sources"] = [src]

            fwd: Dict[int, List[int]] = {}
            rev: Dict[int, List[int]] = {}
            for i, st in enumerate(batch):
                if not st["_brand"] or st.get("lat") is None or st.get("lon") is None:
                    continue
                for j, k in enumerate(kept):
                    if k["_brand"] != st["_brand"] or k.get("lat") is None or k.get("lon") is None:
                        continue
                    if abs(k["lat"] - st["lat"]) > 0.002 or abs(k["lon"] - st["lon"]) > 0.004:
                        continue
                    if _dist_m(k["lat"], k["lon"], st["lat"], st["lon"]) <= MERGE_RADIUS_M:
                        fwd.setdefault(i, []).append(j)
                        rev.setdefault(j, []).append(i)

            add: List[Dict] = []
            for i, st in enumerate(batch):
                cands = fwd.get(i, [])
                if len(cands) == 1 and len(rev.get(cands[0], [])) == 1:
                    k = kept[cands[0]]
                    have = {p["fuel_type"] for p in k["prices"]}
                    for p in st.get("prices", []):
                        if p["fuel_type"] not in have:
                            k["prices"].append(p)
                            have.add(p["fuel_type"])
                    k["sources"].append(src)
                else:
                    add.append(st)
            kept.extend(add)

        for k in kept:
            k.pop("_brand", None)
        return kept

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
                try:
                    price = float(p.get("price"))
                except (TypeError, ValueError):
                    continue
                if ft and price > 0:
                    prices.append(self.price_entry(ft, price, "L", updated_at=ts, tz=DK_TZ))
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
                    prices.append(self.price_entry(ft, price, "L", updated_at=p.get("lastUpdated"), tz=DK_TZ))
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
                    prices.append(self.price_entry(ft, price, "L", updated_at=p.get("lastUpdated"), tz=DK_TZ))

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
                    prices.append(self.price_entry(ft, price, "L", updated_at=p.get("priceChangeDate"), tz=DK_TZ))

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
