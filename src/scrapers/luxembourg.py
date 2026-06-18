from ._anwb import ANWBScraper


class LuxembourgScraper(ANWBScraper):
    COUNTRY    = "LU"
    ISO3       = "LUX"
    BBOX       = (49.44, 5.73, 50.18, 6.53)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90
