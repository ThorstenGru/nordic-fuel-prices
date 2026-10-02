from ._anwb import ANWBScraper


class MonacoScraper(ANWBScraper):
    COUNTRY    = "MC"
    ISO3       = "MCO"
    CURRENCY   = "EUR"
    BBOX       = (43.72,7.40,43.76,7.45)
    SOURCE     = "anwb.nl (ANWB POI API) — interim, no official feed connected"
    CONFIDENCE = 0.80
