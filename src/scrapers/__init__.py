from .sweden import SwedenScraper
from .norway import NorwayScraper
from .denmark import DenmarkScraper
from .finland import FinlandScraper
from .austria import AustriaScraper
from .france import FranceScraper
from .spain import SpainScraper
from .italy import ItalyScraper
from .germany import GermanyScraper
from .portugal import PortugalScraper
from .iceland import IcelandScraper
from .croatia import CroatiaScraper
from .slovenia import SloveniaScraper
from .romania import RomaniaScraper
from .netherlands import NetherlandsScraper
from .belgium import BelgiumScraper
from .luxembourg import LuxembourgScraper
from .switzerland import SwitzerlandScraper
from .poland import PolandScraper
from .hungary import HungaryScraper
from .czechia import CzechiaScraper
from .slovakia import SlovakiaScraper
from .estonia import EstoniaScraper
from .latvia import LatviaScraper
from .lithuania import LithuaniaScraper
# Balkans / South-East Europe
from .greece import GreeceScraper
from .bulgaria import BulgariaScraper
from .serbia import SerbiaScraper
from .montenegro import MontenegroScraper
from .north_macedonia import NorthMacedoniaScraper
from .albania import AlbaniaScraper
from .bosnia import BosniaHerzegovinaScraper
from .kosovo import KosovoScraper
# Small / micro states
from .andorra import AndorraScraper
from .moldova import MoldovaScraper
from .malta import MaltaScraper
from .cyprus import CyprusScraper
from .liechtenstein import LiechtensteinScraper

ALL_SCRAPERS = [
    # Nordic
    SwedenScraper,
    NorwayScraper,
    DenmarkScraper,
    FinlandScraper,
    IcelandScraper,
    # Western Europe
    GermanyScraper,
    FranceScraper,
    SpainScraper,
    AndorraScraper,
    PortugalScraper,
    NetherlandsScraper,
    BelgiumScraper,
    LuxembourgScraper,
    SwitzerlandScraper,
    LiechtensteinScraper,
    # Central Europe
    AustriaScraper,
    CzechiaScraper,
    SlovakiaScraper,
    PolandScraper,
    HungaryScraper,
    # Southern Europe
    ItalyScraper,
    MaltaScraper,
    SloveniaScraper,
    CroatiaScraper,
    BosniaHerzegovinaScraper,
    MontenegroScraper,
    SerbiaScraper,
    KosovoScraper,
    NorthMacedoniaScraper,
    AlbaniaScraper,
    GreeceScraper,
    CyprusScraper,
    # Eastern Europe
    EstoniaScraper,
    LatviaScraper,
    LithuaniaScraper,
    RomaniaScraper,
    BulgariaScraper,
    MoldovaScraper,
]
