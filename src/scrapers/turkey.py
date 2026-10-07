from ._anwb import ANWBScraper


class TurkeyScraper(ANWBScraper):
    """Türkiye via ANWB. Verified 2026-10-07: prices are identical per brand within a city
    (distributors set province-level prices), so they are NOT per-station measurements."""
    COUNTRY    = "TR"
    ISO3       = "TUR"
    CURRENCY   = "TRY"
    BBOX       = (35.8, 25.6, 42.2, 44.9)
    TILE_STEP  = 2.0
    SOURCE     = "anwb.nl (ANWB POI API) — province-level distributor prices"
    CONFIDENCE = 0.80
