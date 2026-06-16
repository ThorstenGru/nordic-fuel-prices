import aiohttp
import asyncio
import re
import urllib.parse
from typing import List, Dict, Any, Optional
from .base import BaseScraper

BASE_URL = "https://www.polttoaine.net"
ENCODING = "windows-1252"
CONCURRENCY = 10

# All slugs from the city/brand/road dropdown on polttoaine.net
SLUGS = [
    # Cities
    "A_hta_ri", "Alavus", "Espoo", "Eurajoki", "Forssa", "Ha_meenkyro_",
    "Ha_meenlinna", "Hanko", "Heinola", "Helsinki", "Hollola", "Ii", "Iitti",
    "Inari", "Joensuu", "Juva", "Jyva_skyla_", "Kaarina", "Kajaani",
    "Kangasala", "Karkkila", "Kemi", "Kemija_rvi", "Kempele", "Keuruu",
    "Kokkola", "Kontiolahti", "Kotka", "Kouvola", "Kuopio", "Kuortane",
    "Lahti", "Laitila", "Lappaja_rvi", "Lempa_a_la_", "Leppa_virta",
    "Lieto", "Liminka", "Liperi", "Lohja", "Loviisa", "Luuma_ki", "Muhos",
    "Mustasaari", "Naantali", "Nurmes", "Nurmija_rvi", "Oulu", "Outokumpu",
    "Padasjoki", "Pielavesi", "Pietarsaari", "Pirkkala", "Pori", "Pudasja_rvi",
    "Pyhta_a_", "Raasepori", "Raisio", "Rauma", "Riihima_ki", "Rusko",
    "Salo", "Savonlinna", "Savukoski", "Seina_joki", "Somero", "Tampere",
    "Tohmaja_rvi", "Turku", "Tuusula", "Ulvila", "Vaasa", "Valtimo",
    "Vantaa", "Varkaus", "Vihti", "Vimpeli", "Vo_yri-Maksamaa", "Ylivieska",
    # Helsinki ring roads
    "Keha_ I", "Keha_ III (E18)",
    # Brand pages (national coverage, deduped by station ID)
    "A24", "ABC", "Esso", "Futura", "Neste", "Neste_Oil", "Neste_Oil_Express",
    "Nex", "Ritoil", "Seo", "Shell", "ShellExpress", "St1", "Teboil",
    "Teboil_Express", "Ysi5",
    # Major roads (tie = road)
    "1-tie", "2-tie", "3-tie", "4-tie", "5-tie", "6-tie", "7-tie",
    "8-tie", "9-tie", "10-tie", "12-tie", "13-tie", "14-tie", "15-tie",
    "17-tie", "18-tie", "19-tie", "20-tie", "22-tie", "23-tie", "24-tie",
    "25-tie", "27-tie", "43-tie", "45-tie", "52-tie", "54-tie", "63-tie",
    "65-tie", "66-tie", "75-tie", "110-tie", "120-tie", "130-tie", "140-tie",
]

TABLE_RE = re.compile(r'<table class="e10">(.*?)</table>', re.DOTALL)
# Station rows have a leading space in the class: class=" bg1 E10"
ROW_RE = re.compile(r'<tr class=" bg[12] E10">(.*?)</tr>', re.DOTALL)
MAP_ID_RE = re.compile(r'cmd=map&(?:amp;)?id=(\d+)')
# Station name is text immediately after the closing </a> tag
NAME_RE = re.compile(r'</a>([^<]+)')
# Price cells have class containing "Hinnat"
HINNAT_RE = re.compile(r'<td[^>]*class="Hinnat[^"]*"[^>]*>([^<]+)</td>')
# Embedded Re85/E85 price in station name, e.g. "(Re85 1.649)"
RE85_RE = re.compile(r'\(Re85\s+([\d.]+)\)')


class FinlandScraper(BaseScraper):
    COUNTRY = "FI"
    CURRENCY = "EUR"
    SOURCE = "polttoaine.net"
    CONFIDENCE = 0.70  # Community-reported prices

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        sem = asyncio.Semaphore(CONCURRENCY)
        tasks = [self._fetch_slug(slug, sem) for slug in SLUGS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        seen: Dict[str, Dict] = {}
        for result in results:
            if isinstance(result, Exception) or not result:
                continue
            for station in result:
                sid = station["id"]
                if sid not in seen:
                    seen[sid] = station

        total = len(seen)
        print(f"[FI] {total} stations from polttoaine.net")
        return list(seen.values())

    async def _fetch_slug(self, slug: str, sem: asyncio.Semaphore) -> List[Dict]:
        url = f"{BASE_URL}/{urllib.parse.quote(slug, safe='_-()~')}"
        async with sem:
            try:
                async with self.session.get(
                    url, timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status != 200:
                        return []
                    raw = await resp.read()
                    html = raw.decode(ENCODING, errors="replace")
            except Exception as e:
                print(f"[FI/{slug}] {e}")
                return []
        return self._parse_stations(html, slug)

    def _parse_stations(self, html: str, slug: str) -> List[Dict]:
        m = TABLE_RE.search(html)
        if not m:
            return []

        stations = []
        for row_m in ROW_RE.finditer(m.group(1)):
            row = row_m.group(1)

            id_m = MAP_ID_RE.search(row)
            if not id_m:
                continue
            station_id = id_m.group(1)

            name_m = NAME_RE.search(row)
            if not name_m:
                continue
            raw_name = name_m.group(1).strip()

            # Extract optional embedded Re85/E85 price from name
            re85_price: Optional[float] = None
            re85_m = RE85_RE.search(raw_name)
            if re85_m:
                try:
                    re85_price = float(re85_m.group(1))
                except ValueError:
                    pass
                raw_name = RE85_RE.sub("", raw_name).strip()

            brand = raw_name.split(",")[0].strip() if "," in raw_name else raw_name
            address = raw_name.split(",", 1)[1].strip() if "," in raw_name else ""

            # Columns: 95E10 → E10, 98E → E5, Di → DIESEL
            cells = HINNAT_RE.findall(row)
            if len(cells) < 3:
                continue

            fuel_defs = [("E10", "L"), ("E5", "L"), ("DIESEL", "L")]
            prices = []
            for val, (ft, unit) in zip(cells[-3:], fuel_defs):
                val = val.strip()
                if val == "-" or not val:
                    continue
                try:
                    p = float(val.replace(",", "."))
                    if p > 0:
                        prices.append(self.price_entry(ft, p, unit))
                except ValueError:
                    pass

            if re85_price and re85_price > 0:
                prices.append(self.price_entry("E85", re85_price, "L"))

            if not prices:
                continue

            stations.append({
                "id": f"fi_{station_id}",
                "country": "FI",
                "name": raw_name,
                "brand": brand,
                "address": address,
                "city": slug,
                "lat": None,
                "lon": None,
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })

        return stations
