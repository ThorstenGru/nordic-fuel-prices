from ._anwb import ANWBScraper


class KosovoScraper(ANWBScraper):
    COUNTRY    = "XK"
    ISO3       = "XKX"   # ISO 3166-1 alpha-3 used by EU/ANWB for Kosovo
    BBOX       = (41.85, 20.01, 43.27, 21.79)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90
