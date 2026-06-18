from ._anwb import ANWBScraper


class AndorraScraper(ANWBScraper):
    COUNTRY    = "AD"
    ISO3       = "AND"
    # Andorra is tiny (~468 km²) but has notably cheap fuel (low tax),
    # making it a popular refuelling stop on trans-Pyrenean routes.
    BBOX       = (42.43, 1.41, 42.66, 1.79)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90
