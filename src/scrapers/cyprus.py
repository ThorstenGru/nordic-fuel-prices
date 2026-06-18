from ._anwb import ANWBScraper


class CyprusScraper(ANWBScraper):
    COUNTRY    = "CY"
    ISO3       = "CYP"
    BBOX       = (34.63, 32.26, 35.71, 34.59)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90
