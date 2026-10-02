from ._anwb import ANWBScraper


class UnitedKingdomScraper(ANWBScraper):
    COUNTRY    = "GB"
    ISO3       = "GBR"
    CURRENCY   = "GBP"
    BBOX       = (49.8,-8.7,60.9,1.9)
    TILE_STEP  = 3.0
    SOURCE     = "anwb.nl (ANWB POI API) — interim, no official feed connected"
    CONFIDENCE = 0.80
