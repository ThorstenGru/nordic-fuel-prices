from typing import List, Dict, Any
from .base import BaseScraper

# Norway: no public station-level fuel price API available (as of 2026-06).
# Investigated and ruled out:
#   - Drivstoffappen (api.drivstoffappen.no) — went private in 2024
#   - Circle K EU API (api.circlek.com/eu/prices/v1/fuel/countries/NO) — "App not allowed"
#   - Circle K NO website (circlek.no) — geo-blocked outside Norway
#   - ST1 Norway (st1.no) — JavaScript SPA, no discoverable API
#   - Uno-X Norway (unox.no) — JavaScript SPA
#   - YX Energy (yx.no/drivstoffpriser) — 404
#   - Shell GeoApp (shellpumpepriser.geoapp.me) — DK only
#   - drivstoffpriser.no — WordPress blog, no API
#   - bensinpriser.no — gone (HTTP 410)
# Norway has no mandatory price reporting law (unlike Denmark since Jan 2026).
# TODO: revisit if a new aggregator emerges or Norway passes price-transparency legislation


class NorwayScraper(BaseScraper):
    COUNTRY = "NO"
    CURRENCY = "NOK"
    SOURCE = "none"
    CONFIDENCE = 0.0

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        print("[NO] Skipping — no public station-level API available")
        return []
