from ._anwb import ANWBScraper


class CzechiaScraper(ANWBScraper):
    COUNTRY    = "CZ"
    ISO3       = "CZE"
    CURRENCY   = "CZK"
    BBOX       = (48.55, 12.10, 51.06, 18.87)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.85
