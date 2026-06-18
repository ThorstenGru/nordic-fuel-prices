from ._anwb import ANWBScraper


class PolandScraper(ANWBScraper):
    COUNTRY    = "PL"
    ISO3       = "POL"
    BBOX       = (49.00, 14.10, 54.90, 24.10)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.85
