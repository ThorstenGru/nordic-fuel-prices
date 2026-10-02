from ._anwb import ANWBScraper


class SanMarinoScraper(ANWBScraper):
    COUNTRY    = "SM"
    ISO3       = "SMR"
    CURRENCY   = "EUR"
    BBOX       = (43.88,12.40,43.99,12.52)
    SOURCE     = "anwb.nl (ANWB POI API) — interim, no official feed connected"
    CONFIDENCE = 0.80
