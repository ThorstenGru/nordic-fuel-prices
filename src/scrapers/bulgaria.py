from ._anwb import ANWBScraper


class BulgariaScraper(ANWBScraper):
    COUNTRY    = "BG"
    ISO3       = "BGR"
    BBOX       = (41.23, 22.36, 44.22, 28.69)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90
