from ._anwb import ANWBScraper


class MoldovaScraper(ANWBScraper):
    COUNTRY    = "MD"
    ISO3       = "MDA"
    BBOX       = (45.47, 26.62, 48.49, 30.14)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90
