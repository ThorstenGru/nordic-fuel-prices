from ._anwb import ANWBScraper


class LithuaniaScraper(ANWBScraper):
    COUNTRY    = "LT"
    ISO3       = "LTU"
    BBOX       = (53.90, 20.95, 56.45, 26.83)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.85
