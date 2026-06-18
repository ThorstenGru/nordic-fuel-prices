from ._anwb import ANWBScraper


class HungaryScraper(ANWBScraper):
    COUNTRY    = "HU"
    ISO3       = "HUN"
    CURRENCY   = "HUF"
    BBOX       = (45.70, 16.10, 48.60, 22.90)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.85
