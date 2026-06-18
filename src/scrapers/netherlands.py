from ._anwb import ANWBScraper


class NetherlandsScraper(ANWBScraper):
    COUNTRY    = "NL"
    ISO3       = "NLD"
    BBOX       = (50.75, 3.36, 53.55, 7.22)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90
