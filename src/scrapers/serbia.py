from ._anwb import ANWBScraper


class SerbiaScraper(ANWBScraper):
    COUNTRY    = "RS"
    ISO3       = "SRB"
    CURRENCY   = "RSD"
    BBOX       = (42.23, 18.84, 46.19, 23.01)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90
