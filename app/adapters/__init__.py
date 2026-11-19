from .internet_archive import InternetArchiveAdapter
from .piratebay import PirateBayAdapter
from .x1337 import X1337Adapter

# Registre aqui novos sites.
ADAPTERS = {
    "piratebay": PirateBayAdapter,
    "1337x": X1337Adapter,
    "archive": InternetArchiveAdapter,
}
