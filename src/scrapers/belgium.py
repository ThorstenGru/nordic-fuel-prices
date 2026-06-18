from ._anwb import ANWBScraper


class BelgiumScraper(ANWBScraper):
    COUNTRY    = "BE"
    ISO3       = "BEL"
    BBOX       = (49.50, 2.50, 51.50, 6.40)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90
