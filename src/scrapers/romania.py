import asyncio
import re
import json
import aiohttp
from typing import List, Dict, Any, Optional
from .base import BaseScraper

# Romania: peco-online.ro — server-side rendered map with embedded JSON
# Fuel price data from ANPC mandatory price reporting
# ~1200+ stations with GPS, prices in RON/L
#
# Strategy: POST index.php per county × fuel type, parse embedded JSON.
# Response embeds: var rezultate = JSON.parse('[["Brand",lat,lon,"City","Address",price], ...]')

BASE_URL = "https://www.peco-online.ro/index.php"

# All 42 Romanian counties (judete) + Ilfov
_COUNTIES = [
    "Alba", "Arad", "Arges", "Bacau", "Bihor", "Bistrita-Nasaud",
    "Botosani", "Braila", "Brasov", "Buzau", "Calarasi", "Cluj",
    "Constanta", "Covasna", "Dambovita", "Dolj", "Galati", "Giurgiu",
    "Gorj", "Harghita", "Hunedoara", "Ialomita", "Iasi", "Ilfov",
    "Maramures", "Mehedinti", "Mures", "Neamt", "Olt", "Prahova",
    "Salaj", "Satu Mare", "Sibiu", "Suceava", "Teleorman", "Timis",
    "Tulcea", "Vaslui", "Valcea", "Vrancea", "Bucuresti",
]

# Station chains with reported prices (send all as retele[] to include everyone)
_RETELE = [
    "Gazprom", "Lukoil", "Mol", "OMV", "Petrom", "Rompetrol", "Socar",
    "ALD", "BLKOil", "CellyRo", "Dacma", "DHR", "Metropoli", "Ozana",
    "Petrolium", "Petromar", "RST", "TEAutohof", "VhExtraOil", "FuelOne",
]

# Fuel types to query → internal fuel_type
_FUELS = {
    "Benzina_Regular":  ("E5",     "L"),
    "Motorina_Regular": ("DIESEL", "L"),
    "GPL":              ("LPG",    "L"),
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": "https://www.peco-online.ro/index.php",
    "Origin": "https://www.peco-online.ro",
}

# peco-online throttles bursts (replies turn into ``JSON.parse('null')``); ~2 s spacing works.
_PACE_S = 2.0
_NULL_BACKOFF_S = 12.0

_LAT_MIN, _LAT_MAX = 43.5, 48.4
_LON_MIN, _LON_MAX = 22.0, 30.2

_REZULTATE_RE = re.compile(r"var rezultate\s*=\s*JSON\.parse\('(\[.*?\])'\)", re.DOTALL)

# Since ~Oct 2026 the site only answers POSTs that carry a signed token which the page embeds
# (``locationTokenPayload = {...}``). Without it the reply is ``JSON.parse('null')`` = 0 stations.
_TOKEN_RE = re.compile(r"locationTokenPayload\s*=\s*(\{.*?\})\s*;?\s*\n", re.DOTALL)


class RomaniaScraper(BaseScraper):
    COUNTRY = "RO"
    CURRENCY = "RON"
    SOURCE = "peco-online.ro"
    CONFIDENCE = 0.90
    REFRESH_MINUTES = 30
    # peco-online throttles bursts, so one full pass (41 counties x 3 fuels at ~2 s) takes far longer
    # than a CI run should. Instead every run refreshes ONE rotating quarter of the counties and
    # merges it into the previously published RO file; a full cycle takes ~NSLICES runs.
    NSLICES = 4
    WALL_CLOCK_CAP_S = 200

    async def _load_previous(self) -> Dict[str, dict]:
        """Previously published RO stations (live site), keyed like the fresh ones."""
        from .geocoder import resolve_pages_base
        prev: Dict[str, dict] = {}
        try:
            base = await resolve_pages_base(self.session)
            async with self.session.get(f"{base}/ro.json", timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return prev
                data = await resp.json(content_type=None)
        except Exception as e:
            print(f"[RO] previous data not available: {e!r}")
            return prev
        for st in (data.get("stations") if isinstance(data, dict) else None) or []:
            try:
                key = f"{st['brand']}|{round(st['lat'], 4)}|{round(st['lon'], 4)}"
                st["_prices"] = {
                    p["fuel_type"]: (p["price"], p.get("unit", "L"))
                    for p in st.get("prices", []) if p.get("price", 0) > 0
                }
                st.pop("prices", None)
                prev[key] = st
            except (KeyError, TypeError):
                continue
        return prev

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        import hashlib
        import time
        # station_key -> station dict with a "_prices" {fuel_type: (price, unit)} scratch field
        stations_by_key: Dict[str, dict] = await self._load_previous()
        n_prev = len(stations_by_key)
        self._token: Optional[dict] = None
        self._null_replies = 0
        self._requests = 0

        cycle = int(time.time() // (self.REFRESH_MINUTES * 60)) % self.NSLICES
        counties = _COUNTIES[cycle::self.NSLICES]
        t0 = time.monotonic()
        done = 0
        for county in counties:
            if time.monotonic() - t0 > self.WALL_CLOCK_CAP_S:
                print(f"[RO] wall-clock cap hit after {done}/{len(counties)} counties")
                break
            for fuel_key, (ft, unit) in _FUELS.items():
                entries = await self._fetch_county(county, fuel_key)
                for brand, lat, lon, city, address, price in entries:
                    key = f"{brand}|{round(lat, 4)}|{round(lon, 4)}"
                    st = stations_by_key.get(key)
                    if st is None:
                        st = stations_by_key[key] = {
                            "id":         "ro_" + hashlib.md5(key.encode()).hexdigest()[:10],
                            "country":    "RO",
                            "name":       brand,
                            "brand":      brand,
                            "address":    address,
                            "city":       city,
                            "lat":        lat,
                            "lon":        lon,
                            "source":     self.SOURCE,
                            "confidence": self.CONFIDENCE,
                            "_prices":    {},
                        }
                    st["_prices"][ft] = (price, unit)       # refreshed value replaces the old one
                await asyncio.sleep(_PACE_S)   # bursts get throttled -> JSON.parse('null')
            done += 1
        print(f"[RO] slice {cycle + 1}/{self.NSLICES}: {done}/{len(counties)} counties refreshed, "
              f"{n_prev} stations carried over")

        # Convert to final format
        result = []
        for s in stations_by_key.values():
            prices = [
                self.price_entry(ft, pr, unit, octane=95 if ft == "E5" else None)   # Benzina_Regular = 95
                for ft, (pr, unit) in s.pop("_prices").items()
                if pr > 0
            ]
            if prices:
                s["prices"] = prices
                result.append(s)

        print(f"[RO] {len(result)} stations from peco-online.ro "
              f"({self._requests} requests, {self._null_replies} empty/null replies)")
        if not result:
            raise RuntimeError(
                f"peco-online.ro returned no stations ({self._requests} requests, "
                f"{self._null_replies} null replies) - token scheme or markup probably changed")
        return result

    async def _get_token(self, force: bool = False) -> Optional[dict]:
        """GET the page once (sets the session cookie) and read the signed token it embeds."""
        import time
        tok = self._token
        if tok and not force and int(tok.get("expires", 0)) - time.time() > 60:
            return tok
        try:
            async with self.session.get(
                BASE_URL, timeout=aiohttp.ClientTimeout(total=20),
                headers={k: v for k, v in _HEADERS.items() if k != "Content-Type"},
            ) as resp:
                if resp.status != 200:
                    print(f"[RO] token GET -> HTTP {resp.status}")
                    return None
                html = await resp.text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"[RO] token GET failed: {e!r}")
            return None
        m = _TOKEN_RE.search(html)
        if not m:
            print("[RO] locationTokenPayload not found in page")
            return None
        try:
            self._token = json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            print("[RO] locationTokenPayload not valid JSON")
            return None
        return self._token

    async def _fetch_county(self, county: str, carburant: str, _retry: bool = True) -> list:
        tok = await self._get_token()
        if not tok:
            return []
        post_data = {
            "carburant": carburant,
            "locatie": "Judet",
            "nume_locatie": county,
            "req_action": tok.get("action", ""),
            "req_expires": tok.get("expires", ""),
            "req_nonce": tok.get("nonce", ""),
            "req_token": tok.get("token", ""),
        }
        self._requests += 1
        # Add all station chain checkboxes
        retele_str = "&".join(f"retele[]={r}" for r in _RETELE)
        form_body = "&".join(f"{k}={v}" for k, v in post_data.items()) + "&" + retele_str

        try:
            async with self.session.post(
                BASE_URL,
                data=form_body,
                timeout=aiohttp.ClientTimeout(total=20),
                headers=_HEADERS,
            ) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        # The nonce is single-use: every reply carries the token for the NEXT request. Without a
        # fresh one, the next POST would come back as ``JSON.parse('null')``.
        self._token = None
        tm = _TOKEN_RE.search(html)
        if tm:
            try:
                self._token = json.loads(tm.group(1))
            except (json.JSONDecodeError, ValueError):
                self._token = None

        m = _REZULTATE_RE.search(html)
        if not m:
            self._null_replies += 1
            if _retry:
                await asyncio.sleep(_NULL_BACKOFF_S)
                self._token = None          # force a fresh page GET (new cookie + token)
                return await self._fetch_county(county, carburant, _retry=False)
            return []

        try:
            raw = json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            return []

        entries = []
        for item in raw:
            if not isinstance(item, list) or len(item) < 6:
                continue
            brand = str(item[0]).strip()
            try:
                lat = float(item[1])
                lon = float(item[2])
            except (TypeError, ValueError):
                continue
            if not (_LAT_MIN <= lat <= _LAT_MAX) or not (_LON_MIN <= lon <= _LON_MAX):
                continue
            city = str(item[3]).strip()
            address = str(item[4]).strip()
            try:
                price = float(item[5])
            except (TypeError, ValueError):
                continue
            if price > 0:
                entries.append((brand, lat, lon, city, address, price))

        return entries
