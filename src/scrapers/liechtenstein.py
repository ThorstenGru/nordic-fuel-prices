from ._anwb import ANWBScraper


class LiechtensteinScraper(ANWBScraper):
    COUNTRY    = "LI"
    ISO3       = "LIE"
    BBOX       = (47.05, 9.47, 47.27, 9.64)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90
