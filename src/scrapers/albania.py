from ._anwb import ANWBScraper


class AlbaniaScraper(ANWBScraper):
    COUNTRY    = "AL"
    ISO3       = "ALB"
    CURRENCY   = "ALL"
    BBOX       = (39.63, 19.27, 42.68, 21.06)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90
