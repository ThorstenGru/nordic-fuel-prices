from typing import List, Dict, Any
from .base import BaseScraper

# Norway: Drivstoffappen public API was shut down (private key required as of 2024).
# TODO: find replacement — candidates:
#   - https://web.drivstoffpriser.net/ (scraping required, no public API)
#   - Official Norwegian petroleum board data (Ptil) — country averages only
#   - Circle K / Uno-X / YX individual chain APIs


class NorwayScraper(BaseScraper):
    COUNTRY = "NO"
    CURRENCY = "NOK"
    SOURCE = "drivstoffappen.no"
    CONFIDENCE = 1.0

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        print("[NO] Skipping — no public station-level API available yet")
        return []
