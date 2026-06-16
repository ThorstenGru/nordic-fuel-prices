from typing import List, Dict, Any
from .base import BaseScraper

# Finland: polttoaine.net has no public JSON API.
# TODO: find replacement — candidates:
#   - https://github.com/Grenguar/fuel-api-finland-serverless (unofficial wrapper)
#   - Neste / ST1 / ABC chain APIs
#   - EU Oil Bulletin (weekly country averages only, not station-level)


class FinlandScraper(BaseScraper):
    COUNTRY = "FI"
    CURRENCY = "EUR"
    SOURCE = "polttoaine.net"
    CONFIDENCE = 0.70

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        print("[FI] Skipping — no public station-level API found yet")
        return []
