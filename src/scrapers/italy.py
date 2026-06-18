import aiohttp
import asyncio
import csv
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
    "Benzina":          ("E5",     "L"),
    "Gasolio":          ("DIESEL", "L"),
    "Gasolio BTZ":      ("DIESEL", "L"),
    "GPL":              ("LPG",    "L"),
    "Metano":           ("CNG",    "kg"),
    "HVO":              ("HVO100", "L"),
    "Bioetanolo E85":   ("E85",    "L"),
}


class ItalyScraper(BaseScraper):
    COUNTRY = "IT"
    CURRENCY = "EUR"
    SOURCE = "mimit.gov.it"
    CONFIDENCE = 0.90

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        registry_text, prices_text = await asyncio.gather(
            self._fetch_csv(REGISTRY_URL),
            self._fetch_csv(PRICES_URL),
        )
        if not registry_text or not prices_text:
            return []

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
        seen: Dict[str, set] = {}
        reader = csv.DictReader(io.StringIO(prices_body), delimiter="|")
        for row in reader:
            sid = (row.get("idImpianto") or "").strip()
            if sid not in stations:
                continue
            fuel_name = (row.get("descCarburante") or "").strip()
            ft_info = FUEL_MAP.get(fuel_name)
            if not ft_info:
                continue
            ft, unit = ft_info
            if sid not in seen:
                seen[sid] = set()
            if ft in seen[sid]:
                continue
            try:
                price = float((row.get("prezzo") or "0").replace(",", "."))
            except (ValueError, TypeError):
                continue
            if price > 0:
                stations[sid]["prices"].append(self.price_entry(ft, price, unit))
                seen[sid].add(ft)

        result = [s for s in stations.values() if s["prices"]]
        print(f"[IT] {len(result)} stations from mimit.gov.it")
        return result

    async def _fetch_csv(self, url: str) -> str:
        _HEADERS = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/csv,text/plain,*/*",
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
            "Referer": "https://www.mimit.gov.it/",
        }
        for attempt in range(3):
            try:
                async with self.session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=90),
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
                if attempt < 2:
                    await asyncio.sleep(4 * (attempt + 1))
                else:
                    print(f"[IT] {e} — {url}")
        return ""
