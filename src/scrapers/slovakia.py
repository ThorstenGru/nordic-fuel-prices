from ._anwb import ANWBScraper


class SlovakiaScraper(ANWBScraper):
    COUNTRY    = "SK"
    ISO3       = "SVK"
    BBOX       = (47.73, 16.84, 49.62, 22.57)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.85
