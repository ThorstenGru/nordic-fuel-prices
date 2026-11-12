import aiohttp
import asyncio
import csv
import math
import time
import io
from typing import List, Dict, Any
from .base import BaseScraper

# Italian mandatory fuel price reporting via MIMIT
# (Ministero delle Imprese e del Made in Italy)
# Two daily CSV files joined on idImpianto:
#   anagrafica — station registry with GPS coordinates
#   prezzo_alle_8 — 8 AM daily price snapshot
# Free, no API key required, ~20 000+ stations

REGISTRY_URL = "https://www.mimit.gov.it/images/exportCSV/anagrafica_impianti_attivi.csv"
PRICES_URL   = "https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv"

FUEL_MAP = {
    "Benzina":          ("E5",     "L"),   # standard unleaded = 95 RON
    "Gasolio":          ("DIESEL", "L"),
    "Gasolio BTZ":      ("DIESEL", "L"),
    "GPL":              ("LPG",    "L"),
    "Metano":           ("CNG",    "kg"),
    "HVO":              ("HVO100", "L"),
    "Bioetanolo E85":   ("E85",    "L"),
}


# Fallback: fuel-prices.eu republishes the same MIMIT data (IODL 2.0) and has given the owner written consent to use it.
# Its station endpoint returns at most 100 stations per call, so Italy is covered with a quadtree of circles. Polite by design:
# a User-Agent naming us, ~1.5 requests/s, one crawl a day (REFRESH_MINUTES), and give up early when the API misbehaves.
FPEU_API = "https://www.fuel-prices.eu/live/api.php"
FPEU_UA = "EuroFuelPrices/2.0 (+https://eurofuelprices.com)"
FPEU_SOURCE = "fuel-prices.eu (MIMIT data, IODL 2.0)"
FPEU_FUELS = {                       # their key -> (fuel_type, unit, octane); lng is not shown in the app
    "diesel": ("DIESEL", "L", None), "sp95": ("E5", "L", 95), "sp98": ("98", "L", 98),
    "gpl": ("LPG", "L", None), "cng": ("CNG", "kg", None),
}
FPEU_CAP = 100                       # their per-call limit: a full answer means "split this circle"
FPEU_MIN_RADIUS_KM = 1.2
FPEU_BUDGET_S = 25 * 60              # a partial crawl is worse than none: past this, keep the last good data
FPEU_GAP_S = 0.6


def fpeu_cells():
    """Coarse cover of Italy (0.6 x 0.8 degree cells -> circles of ~47 km that contain each cell)."""
    out = []
    lat = 35.4
    while lat < 47.2:
        lon = 6.6
        while lon < 18.9:
            clat, clon = lat + 0.3, lon + 0.4
            out.append((clat, clon, math.hypot(0.3 * 111.2, 0.4 * 111.2 * math.cos(math.radians(clat)))))
            lon += 0.8
        lat += 0.6
    return out


def fpeu_split(lat, lon, radius):
    """Four child circles of half the radius that together contain the parent's square."""
    dlat = radius / 2 / math.sqrt(2) / 111.2
    dlon = dlat / math.cos(math.radians(lat))
    return [(lat + a * dlat, lon + b * dlon, radius / 2) for a in (-1, 1) for b in (-1, 1)]


class ItalyScraper(BaseScraper):
    COUNTRY = "IT"
    CURRENCY = "EUR"
    SOURCE = "mimit.gov.it"
    CONFIDENCE = 0.90
    GRADE = "B"             # statutory duty (update on every change) but published as a daily CSV snapshot
    TIMEOUT_S = 1800        # the fuel-prices.eu fallback crawl needs ~17 min (main.py default is 15 min)
    REFRESH_MINUTES = 1380  # MIMIT publishes once a day (~08:00); also keeps the fuel-prices.eu fallback crawl to once a day

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        registry_text, prices_text = await asyncio.gather(
            self._fetch_csv(REGISTRY_URL),
            self._fetch_csv(PRICES_URL),
        )
        if not registry_text or not prices_text:
            print("[IT] MIMIT not reachable - trying fuel-prices.eu (same data, with their consent)")
            return await self._fetch_fpeu()

        # Parse station registry
        # Columns: idImpianto|Gestore|Bandiera|Tipo Impianto|Nome Impianto|Indirizzo|Comune|Provincia|Latitudine|Longitudine
        # The registry CSV may also start with a metadata line ("Estrazione del YYYY-MM-DD") before the header
        registry_lines = registry_text.splitlines()
        reg_header_idx = next(
            (i for i, line in enumerate(registry_lines) if line.startswith("idImpianto")),
            None,
        )
        registry_body = "\n".join(registry_lines[reg_header_idx:]) if reg_header_idx is not None else registry_text
        stations: Dict[str, Dict] = {}
        reader = csv.DictReader(io.StringIO(registry_body), delimiter="|")
        for row in reader:
            sid = (row.get("idImpianto") or "").strip()
            if not sid:
                continue
            try:
                lat = float((row.get("Latitudine") or "0").replace(",", "."))
                lon = float((row.get("Longitudine") or "0").replace(",", "."))
                if not (35 <= lat <= 48) or not (6 <= lon <= 19):
                    lat = lon = None
            except (ValueError, TypeError):
                lat = lon = None

            stations[sid] = {
                "id": f"it_{sid}",
                "country": "IT",
                "name": (row.get("Nome Impianto") or row.get("Gestore") or "").strip(),
                "brand": (row.get("Bandiera") or row.get("Gestore") or "").strip(),
                "address": (row.get("Indirizzo") or "").strip(),
                "city": (row.get("Comune") or "").strip(),
                "lat": lat,
                "lon": lon,
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices": [],
            }

        # Parse price file
        # Columns: idImpianto|descCarburante|prezzo|isSelf|dtComu
        # First line is a metadata line ("Estrazione del YYYY-MM-DD") before the header
        prices_lines = prices_text.splitlines()
        header_idx = next(
            (i for i, line in enumerate(prices_lines) if line.startswith("idImpianto")),
            None,
        )
        prices_body = "\n".join(prices_lines[header_idx:]) if header_idx is not None else prices_text
        # Each fuel can appear twice: isSelf=1 (self-service, cheaper) and isSelf=0 (served).
        # Prefer the self-service price; fall back to the served one.
        best: Dict[str, Dict[str, tuple]] = {}
        reader = csv.DictReader(io.StringIO(prices_body), delimiter="|")
        for row in reader:
            sid = (row.get("idImpianto") or "").strip()
            if sid not in stations:
                continue
            ft_info = FUEL_MAP.get((row.get("descCarburante") or "").strip())
            if not ft_info:
                continue
            ft, unit = ft_info
            try:
                price = float((row.get("prezzo") or "0").replace(",", "."))
            except (ValueError, TypeError):
                continue
            if price <= 0:
                continue
            is_self = (row.get("isSelf") or "").strip() == "1"
            prev = best.setdefault(sid, {}).get(ft)
            if prev is not None and (prev[0] or not is_self):
                continue                      # keep an existing self-service price / first served price
            entry = self.price_entry(ft, price, unit, updated_at=row.get("dtComu"), tz="Europe/Rome",
                                     octane=95 if ft == "E5" else None)
            best[sid][ft] = (is_self, entry)
        for sid, by_fuel in best.items():
            stations[sid]["prices"] = [e for _, e in by_fuel.values()]

        result = [s for s in stations.values() if s["prices"]]
        print(f"[IT] {len(result)} stations from mimit.gov.it")
        return result

    async def _fetch_csv(self, url: str) -> str:
        _HEADERS = {"User-Agent": FPEU_UA, "Accept": "text/csv,text/plain,*/*"}   # an honest client name, no browser disguise
        for attempt in range(3):
            t0 = time.monotonic()
            try:
                async with self.session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=90, sock_connect=15),   # blocked hosts fail fast, the fallback gets the time
                    headers=_HEADERS,
                ) as resp:
                    if resp.status != 200:
                        print(f"[IT] HTTP {resp.status} — {url}")
                        return ""
                    raw = await resp.read()
                    for enc in ("utf-8-sig", "latin-1", "cp1252"):
                        try:
                            return raw.decode(enc)
                        except UnicodeDecodeError:
                            continue
                    return raw.decode("latin-1", errors="replace")
            except Exception as e:
                msg = f"{type(e).__name__} after {time.monotonic() - t0:.0f}s (attempt {attempt + 1}/3): {e}"
                if attempt < 2:
                    print(f"[IT] {msg} — {url}")
                    await asyncio.sleep(4 * (attempt + 1))
                else:
                    print(f"[IT] giving up, {msg} — {url}")
        return ""

    async def _fpeu_query(self, lat: float, lon: float, radius: float):
        """One API call -> list of stations, or None when the API failed (3 tries)."""
        url = f"{FPEU_API}?action=stations&country=IT&lat={lat:.4f}&lng={lon:.4f}&radius={radius:.1f}&limit={FPEU_CAP}"
        for attempt in range(3):
            try:
                async with self.session.get(url, headers={"User-Agent": FPEU_UA}, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        d = await resp.json(content_type=None)
                        if d.get("ok"):
                            await asyncio.sleep(FPEU_GAP_S)
                            return (d.get("data") or {}).get("stations") or []
                    elif resp.status in (403, 429):
                        return None                       # they said no: stop, do not retry
            except Exception:  # noqa: BLE001 - a failed call is handled below
                pass
            await asyncio.sleep(3 * (attempt + 1))
        return None

    async def _fetch_fpeu(self) -> List[Dict[str, Any]]:
        t0, calls, fails = time.monotonic(), 0, 0
        found: Dict[Any, Dict] = {}
        todo = fpeu_cells()
        while todo:
            if time.monotonic() - t0 > FPEU_BUDGET_S or fails >= 5:
                print(f"[IT/fuel-prices.eu] giving up after {calls} calls ({fails} failed, {time.monotonic() - t0:.0f}s) - keeping last good data")
                return []
            lat, lon, rad = todo.pop()
            res = await self._fpeu_query(lat, lon, rad)
            calls += 1
            if res is None:
                fails += 1
                continue
            for st in res:
                found[st.get("id")] = st
            if len(res) >= FPEU_CAP and rad / 2 >= FPEU_MIN_RADIUS_KM:
                todo.extend(fpeu_split(lat, lon, rad))
        out = []
        for sid, st in found.items():
            try:
                lat, lon = float(st["lat"]), float(st["lng"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (35 <= lat <= 48) or not (6 <= lon <= 19):
                continue
            prices = []
            for key, (ft, unit, octane) in FPEU_FUELS.items():
                p = (st.get("prices") or {}).get(key) or {}
                try:
                    price = float(p["price"])
                except (KeyError, TypeError, ValueError):
                    continue
                if price > 0:
                    prices.append(self.price_entry(ft, price, unit, updated_at=p.get("ts"), octane=octane))
            if prices:
                out.append({"id": f"it_fp{sid}", "country": "IT", "name": (st.get("name") or "").strip(),
                            "brand": (st.get("brand") or "").strip(), "address": (st.get("address") or "").strip(),
                            "city": (st.get("city") or "").strip(), "lat": lat, "lon": lon,
                            "source": FPEU_SOURCE, "confidence": self.CONFIDENCE, "prices": prices})
        self.SOURCE = FPEU_SOURCE
        print(f"[IT/fuel-prices.eu] {len(out)} stations from {calls} calls in {time.monotonic() - t0:.0f}s")
        return out
