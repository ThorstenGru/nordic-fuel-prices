from ._anwb import ANWBScraper


class LatviaScraper(ANWBScraper):
    COUNTRY    = "LV"
    ISO3       = "LVA"
    BBOX       = (55.68, 20.97, 57.84, 28.24)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.85
