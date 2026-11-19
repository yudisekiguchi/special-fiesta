"""Internet Archive (archive.org): acervo legal de domínio público e
Creative Commons, com .torrent oficial para cada item."""
from __future__ import annotations

from datetime import datetime

from ..models import MediaType, TorrentResult
from .base import SiteAdapter

SEARCH = "https://archive.org/advancedsearch.php"
MEDIATYPE = {MediaType.AUDIO: "audio", MediaType.VIDEO: "movies", MediaType.IMAGE: "image"}
REVERSE = {v: k for k, v in MEDIATYPE.items()}


def parse_search(data: dict) -> list[TorrentResult]:
    out = []
    for d in data.get("response", {}).get("docs", []):
        media = REVERSE.get(d.get("mediatype"))
        if media is None:
            continue
        ident = d["identifier"]
        title = d.get("title") or ident
        if isinstance(title, list):
            title = title[0]
        added = None
        if d.get("publicdate"):
            try:
                added = datetime.fromisoformat(d["publicdate"].replace("Z", "+00:00"))
            except ValueError:
                pass
        out.append(TorrentResult(
            source="Internet Archive",
            title=title,
            media_type=media,
            size=int(d.get("item_size") or 0),
            uploader=d.get("uploader") if isinstance(d.get("uploader"), str) else None,
            added=added,
            torrent_url=f"https://archive.org/download/{ident}/{ident}_archive.torrent",
            page_url=f"https://archive.org/details/{ident}",
            official_source=True,
        ))
    return out


class InternetArchiveAdapter(SiteAdapter):
    name = "Internet Archive"

    async def search(self, query, media):
        types = [MEDIATYPE[media]] if media else list(MEDIATYPE.values())
        q = f"({query}) AND mediatype:({' OR '.join(types)})"
        params = [("q", q), ("rows", "30"), ("output", "json"), ("sort[]", "downloads desc")]
        params += [("fl[]", f) for f in
                   ("identifier", "title", "mediatype", "item_size", "publicdate", "uploader")]
        resp = await self.client.get(SEARCH, params=params)
        resp.raise_for_status()
        return parse_search(resp.json())
