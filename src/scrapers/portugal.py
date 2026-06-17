import aiohttp
import asyncio
from typing import List, Dict, Any
from .base import BaseScraper

# Portuguese mandatory fuel price reporting via DGEG
# (Direção-Geral de Energia e Geologia)
# Free, no API key required, ~4 000+ stations with GPS

BASE_URL = "https://precoscombustiveis.dgeg.gov.pt/api/PrecoComb/PesquisarPostos"

FUEL_IDS: Dict[int, tuple] = {
    2101: ("DIESEL", "L"),   # Gasóleo simples
    3201: ("E5",     "L"),   # Gasolina simples 95
    3400: ("E5",     "L"),   # Gasolina simples 98 (maps to E5 — best available)
    1120: ("LPG",    "L"),   # GPL Auto
}

LAT_MIN, LAT_MAX = 36.0, 43.0
LON_MIN, LON_MAX = -10.0, -5.5


class PortugalScraper(BaseScraper):
    COUNTRY = "PT"
    CURRENCY = "EUR"
    SOURCE = "dgeg.gov.pt"
    CONFIDENCE = 1.0

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        sem = asyncio.Semaphore(4)
        tasks = [self._fetch_fuel(fid, sem) for fid in FUEL_IDS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        merged: Dict[str, Dict] = {}
        for result in results:
            if isinstance(result, Exception) or not result:
                continue
            for s in result:
                sid = s["id"]
                if sid not in merged:
                    merged[sid] = s
                else:
                    existing = {p["fuel_type"] for p in merged[sid]["prices"]}
                    for p in s["prices"]:
                        if p["fuel_type"] not in existing:
                            merged[sid]["prices"].append(p)

        stations = list(merged.values())
        print(f"[PT] {len(stations)} stations from dgeg.gov.pt")
        return stations

    async def _fetch_fuel(self, fuel_id: int, sem: asyncio.Semaphore) -> List[Dict]:
        params = {"idsTiposComb": fuel_id, "qtdPorPagina": 9999, "pagina": 1}
        async with sem:
            try:
                async with self.session.get(
                    BASE_URL, params=params,
                    timeout=aiohttp.ClientTimeout(total=60),
                    headers={"Accept": "application/json"},
                ) as resp:
                    if resp.status != 200:
                        print(f"[PT] HTTP {resp.status} fuel={fuel_id}")
                        return []
                    data = await resp.json(content_type=None)
            except Exception as e:
                print(f"[PT] fuel={fuel_id}: {e}")
                return []

        if not data.get("status"):
            return []

        ft, unit = FUEL_IDS[fuel_id]
        result = []
        for s in data.get("resultado", []):
            try:
                lat = float(s.get("Latitude") or 0)
                lon = float(s.get("Longitude") or 0)
                if not (LAT_MIN <= lat <= LAT_MAX) or not (LON_MIN <= lon <= LON_MAX):
                    lat = lon = None
            except (ValueError, TypeError):
                lat = lon = None

            price_raw = str(s.get("Preco") or "").replace("€", "").replace(",", ".").strip()
            try:
                price = float(price_raw)
            except ValueError:
                continue
            if price <= 0:
                continue

            result.append({
                "id": f"pt_{s.get('Id', '')}",
                "country": "PT",
                "name": (s.get("Nome") or "").strip(),
                "brand": (s.get("Marca") or "").strip(),
                "address": (s.get("Morada") or "").strip(),
                "city": (s.get("Municipio") or "").strip(),
                "lat": lat,
                "lon": lon,
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices": [self.price_entry(ft, price, unit)],
            })
        return result
