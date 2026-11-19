"""The Pirate Bay, via API JSON pública (apibay.org)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from ..models import MediaType, TorrentFile, TorrentResult, UploaderStatus
from .base import SiteAdapter, build_magnet

API = "https://apibay.org"
EMPTY_HASH = "0" * 40

# Categorias do TPB: 1xx áudio, 2xx vídeo, 603 imagens.
QUERY_CAT = {MediaType.AUDIO: "100", MediaType.VIDEO: "200", MediaType.IMAGE: "603"}


def category_to_media(cat: str | int) -> MediaType | None:
    c = int(cat or 0)
    if 100 <= c < 200:
        return MediaType.AUDIO
    if 200 <= c < 300:
        return MediaType.VIDEO
    if c == 603:
        return MediaType.IMAGE
    return None  # software, jogos, adulto, etc. ficam de fora


STATUS = {"vip": UploaderStatus.VIP, "trusted": UploaderStatus.TRUSTED,
          "helper": UploaderStatus.TRUSTED, "moderator": UploaderStatus.TRUSTED,
          "supermod": UploaderStatus.TRUSTED, "admin": UploaderStatus.TRUSTED,
          "member": UploaderStatus.MEMBER}


def parse_search(items: list[dict]) -> list[tuple[str, TorrentResult]]:
    out = []
    for it in items:
        if it.get("info_hash", EMPTY_HASH) == EMPTY_HASH:
            continue  # "No results returned"
        media = category_to_media(it.get("category", 0))
        if media is None:
            continue
        h = it["info_hash"].lower()
        added = None
        if str(it.get("added", "")).isdigit():
            added = datetime.fromtimestamp(int(it["added"]), tz=timezone.utc)
        r = TorrentResult(
            source="The Pirate Bay",
            title=it["name"],
            media_type=media,
            size=int(it.get("size") or 0),
            seeders=int(it.get("seeders") or 0),
            leechers=int(it.get("leechers") or 0),
            uploader=it.get("username"),
            uploader_status=STATUS.get(str(it.get("status", "")).lower(),
                                       UploaderStatus.UNKNOWN),
            added=added,
            info_hash=h,
            magnet=build_magnet(h, it["name"]),
            page_url=f"https://thepiratebay.org/description.php?id={it['id']}",
        )
        out.append((str(it["id"]), r))
    return out


def parse_files(items: list[dict]) -> list[TorrentFile]:
    files = []
    for f in items:
        name = f.get("name", [""])
        size = f.get("size", [0])
        name = name[0] if isinstance(name, list) else name
        size = size[0] if isinstance(size, list) else size
        if name == "Filelist not found":
            continue
        files.append(TorrentFile(name=name, size=int(size or 0)))
    return files


class PirateBayAdapter(SiteAdapter):
    name = "The Pirate Bay"

    async def search(self, query, media):
        cat = QUERY_CAT[media] if media else "100,200,603"
        resp = await self.client.get(f"{API}/q.php", params={"q": query, "cat": cat})
        resp.raise_for_status()
        pairs = parse_search(resp.json())
        pairs.sort(key=lambda p: p[1].seeders or 0, reverse=True)

        async def load_files(tid, r):
            try:
                fr = await self.client.get(f"{API}/f.php", params={"id": tid})
                fr.raise_for_status()
                r.files = parse_files(fr.json())
            except Exception:
                r.files = None

        await asyncio.gather(*(load_files(t, r) for t, r in pairs[: self.inspect_top]))
        return [r for _, r in pairs]
