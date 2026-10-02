from ._anwb import ANWBScraper


class IrelandScraper(ANWBScraper):
    COUNTRY    = "IE"
    ISO3       = "IRL"
    CURRENCY   = "EUR"
    BBOX       = (51.3,-10.7,55.5,-5.3)
    SOURCE     = "anwb.nl (ANWB POI API) — interim, no official feed connected"
    CONFIDENCE = 0.80
