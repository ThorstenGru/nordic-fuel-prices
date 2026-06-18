from ._anwb import ANWBScraper


class EstoniaScraper(ANWBScraper):
    COUNTRY    = "EE"
    ISO3       = "EST"
    BBOX       = (57.52, 21.83, 59.68, 28.21)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.85
