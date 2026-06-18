from ._anwb import ANWBScraper


class NorthMacedoniaScraper(ANWBScraper):
    COUNTRY    = "MK"
    ISO3       = "MKD"
    CURRENCY   = "MKD"
    BBOX       = (40.85, 20.44, 42.37, 23.04)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90
