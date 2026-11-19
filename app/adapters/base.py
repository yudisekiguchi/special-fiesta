"""Interface comum para cada site. Para adicionar um site novo, crie um
módulo nesta pasta com uma subclasse de SiteAdapter e registre em
app/adapters/__init__.py."""
from __future__ import annotations

from abc import ABC, abstractmethod
from urllib.parse import quote

import httpx

from ..models import MediaType, TorrentResult

USER_AGENT = ("Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:130.0) "
              "Gecko/20100101 Firefox/130.0")

PUBLIC_TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://exodus.desync.com:6969/announce",
]


def build_magnet(info_hash: str, name: str) -> str:
    trackers = "".join(f"&tr={quote(t, safe='')}" for t in PUBLIC_TRACKERS)
    return f"magnet:?xt=urn:btih:{info_hash}&dn={quote(name)}{trackers}"


class SiteAdapter(ABC):
    name: str = "base"
    #: Quantos resultados do topo terão a lista de arquivos verificada
    #: (cada verificação é uma requisição extra ao site).
    inspect_top: int = 8

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    @abstractmethod
    async def search(self, query: str, media: MediaType | None) -> list[TorrentResult]:
        """Busca e retorna resultados já filtrados para áudio/vídeo/imagem."""
