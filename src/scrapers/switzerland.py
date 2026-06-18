from ._anwb import ANWBScraper


class SwitzerlandScraper(ANWBScraper):
    COUNTRY    = "CH"
    ISO3       = "CHE"
    BBOX       = (45.80, 5.90, 47.80, 10.50)
    CURRENCY   = "CHF"
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.85
