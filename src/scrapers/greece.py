from ._anwb import ANWBScraper


class GreeceScraper(ANWBScraper):
    COUNTRY    = "GR"
    ISO3       = "GRC"
    # Bbox covers Greek mainland + all major island groups (Crete, Rhodes, Corfu,
    # Lesbos, Dodecanese). Filter by ISO3=GRC excludes Turkish/Albanian border stations.
    BBOX       = (34.70, 19.30, 41.80, 29.70)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90
