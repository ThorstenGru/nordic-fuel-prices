"""
Spain.

Primary: MITECO/MINETUR "Geoportal Gasolineras" REST feed (GRADE A — statutory: every station must
report a price BEFORE it takes effect; Orden ITC/2308/2007). ~11.5k priced stations with GPS.
The ministry resets connections coming from many cloud/datacentre IPs (it does so for GitHub
Actions), so we try both official hostnames and, if both stay unreachable, fall back to the
ANWB feed (adaptively tiled; GRADE C) so Spain is never empty. A long-term fix for the datacentre
block is a relay (e.g. a Cloudflare Worker or an EU self-hosted runner) — see docs/DATA_SOURCES_AUDIT.md.
"""

import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import aiohttp

from .base import BaseScraper, iso_utc
from ._anwb import ANWBScraper


class _ESAnwb(ANWBScraper):
    COUNTRY    = "ES"
    ISO3       = "ESP"
    BBOX       = (27.5, -18.3, 43.9, 4.4)       # mainland + Balearics + Canaries
    TILE_STEP  = 2.0
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.85


HOSTS = [
    "https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/",
    "https://energia.serviciosmin.gob.es/ServiciosRestCarburantes/PreciosCarburantes/EstacionesTerrestres/",
]

# Spanish field name → (internal fuel_type, unit)
FUEL_FIELDS = {
    "Precio Gasoleo A":                      ("DIESEL", "L"),
    "Precio Gasolina 95 E5":                 ("E5",     "L"),
    "Precio Gasolina 95 E10":                ("E10",    "L"),
    "Precio Gasolina 98 E5":                 ("E5",     "L"),  # premium 98 (deduped below)
    "Precio Gases licuados del petroleo":    ("LPG",    "L"),
    "Precio Gas Natural Comprimido":         ("CNG",    "kg"),
    "Precio Bioetanol":                      ("E85",    "L"),
    "Precio Hidrogeno":                      ("H2",     "kg"),
}


def _file_time(fecha: Optional[str]) -> Optional[str]:
    """'Fecha' is dd/mm/yyyy HH:MM:SS in Spanish local time (whole-file generation time)."""
    if not fecha:
        return None
    try:
        from zoneinfo import ZoneInfo
        dt = datetime.strptime(fecha.strip(), "%d/%m/%Y %H:%M:%S").replace(tzinfo=ZoneInfo("Europe/Madrid"))
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


class SpainScraper(BaseScraper):
    COUNTRY    = "ES"
    CURRENCY   = "EUR"
    SOURCE     = "minetur.gob.es"
    CONFIDENCE = 0.95
    GRADE      = "A"

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        data = None
        for attempt in range(4):
            url = HOSTS[attempt % len(HOSTS)]
            try:
                async with self.session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=90),
                    headers={
                        "Accept": "application/json",
                        "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                                       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
                    },
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        break
                    print(f"[ES] HTTP {resp.status} from {url.split('/')[2]} (attempt {attempt + 1})")
            except Exception as e:
                print(f"[ES] {url.split('/')[2]}: {e} (attempt {attempt + 1})")
            await asyncio.sleep(4 * (attempt + 1))

        if not isinstance(data, dict) or not data.get("ListaEESSPrecio"):
            print("[ES] MINETUR unreachable (datacentre block) — falling back to ANWB (tiled)")
            self.SOURCE = "anwb.nl (ANWB POI API) — MINETUR unreachable"
            self.CONFIDENCE = 0.85
            self.GRADE = "C"
            return await _ESAnwb(self.session).fetch_stations()

        as_of = _file_time(data.get("Fecha"))
        stations = []
        for s in data["ListaEESSPrecio"]:
            prices, seen = [], set()
            for field, (ft, unit) in FUEL_FIELDS.items():
                val_str = (s.get(field) or "").strip()
                if not val_str or ft in seen:
                    continue
                try:
                    price = float(val_str.replace(",", "."))
                except ValueError:
                    continue
                if price > 0:
                    prices.append(self.price_entry(ft, price, unit, updated_at=as_of))
                    seen.add(ft)

            try:
                lat = float((s.get("Latitud") or "0").replace(",", "."))
                lon = float((s.get("Longitud (WGS84)") or "0").replace(",", "."))
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180) or (lat == 0 and lon == 0):
                    lat = lon = None
            except (ValueError, TypeError):
                lat = lon = None

            stations.append({
                "id": f"es_{s.get('IDEESS', '')}",
                "country": "ES",
                "name": s.get("Rótulo", ""),
                "brand": s.get("Rótulo", ""),
                "address": s.get("Dirección", ""),
                "city": s.get("Municipio", ""),
                "lat": lat,
                "lon": lon,
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })

        priced = sum(1 for s in stations if s["prices"])
        print(f"[ES] {len(stations)} stations ({priced} priced) from minetur.gob.es")
        return stations
