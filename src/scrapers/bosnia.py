from ._anwb import ANWBScraper


class BosniaHerzegovinaScraper(ANWBScraper):
    COUNTRY    = "BA"
    ISO3       = "BIH"
    CURRENCY   = "BAM"
    BBOX       = (42.55, 15.72, 45.28, 19.62)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90
