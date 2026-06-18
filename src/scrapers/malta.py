from ._anwb import ANWBScraper


class MaltaScraper(ANWBScraper):
    COUNTRY    = "MT"
    ISO3       = "MLT"
    BBOX       = (35.78, 14.18, 36.08, 14.58)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90
