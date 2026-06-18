from ._anwb import ANWBScraper


class MontenegroScraper(ANWBScraper):
    COUNTRY    = "ME"
    ISO3       = "MNE"
    BBOX       = (41.87, 18.43, 43.57, 20.36)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90
