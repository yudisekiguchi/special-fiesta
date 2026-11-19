"""1337x, lendo o HTML. O site usa Cloudflare e muda de domínio com
frequência; se parar de funcionar, ajuste BASE_URLS."""
from __future__ import annotations

import asyncio
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from ..models import MediaType, TorrentFile, TorrentResult, UploaderStatus
from .base import SiteAdapter

BASE_URLS = ["https://1337x.to", "https://1337x.st", "https://x1337x.ws"]

# Busca por categoria do site. "Other" inclui a subcategoria de imagens;
# o que não for imagem é penalizado pela checagem de arquivos.
CATEGORIES = {MediaType.AUDIO: ["Music"], MediaType.VIDEO: ["Movies", "TV"],
              MediaType.IMAGE: ["Other"]}
UNITS = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}


def parse_size(text: str) -> int:
    m = re.search(r"([\d.,]+)\s*(TB|GB|MB|KB|B)", text, re.IGNORECASE)
    if not m:
        return 0
    return int(float(m.group(1).replace(",", "")) * UNITS[m.group(2).upper()])


def parse_search(html: str, base: str, media: MediaType) -> list[TorrentResult]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for row in soup.select("table.table-list tbody tr"):
        name_td = row.select_one("td.coll-1")
        if not name_td:
            continue
        links = name_td.find_all("a")
        link = next((a for a in links if a.get("href", "").startswith("/torrent/")), None)
        if not link:
            continue
        row_media = media
        size_td = row.select_one("td.coll-4")
        if size_td:
            for span in size_td.find_all("span"):
                span.decompose()
        uploader_td = row.select_one("td.coll-5")
        classes = uploader_td.get("class", []) if uploader_td else []
        if "vip" in classes:
            status = UploaderStatus.VIP
        elif "uploader" in classes or "trial-uploader" in classes:
            status = UploaderStatus.TRUSTED
        else:
            status = UploaderStatus.MEMBER
        out.append(TorrentResult(
            source="1337x",
            title=link.get_text(strip=True),
            media_type=row_media,
            size=parse_size(size_td.get_text(" ", strip=True) if size_td else ""),
            seeders=_int(row.select_one("td.coll-2")),
            leechers=_int(row.select_one("td.coll-3")),
            uploader=uploader_td.get_text(strip=True) if uploader_td else None,
            uploader_status=status,
            page_url=base + link["href"],
        ))
    return out


def _int(td) -> int | None:
    try:
        return int(td.get_text(strip=True).replace(",", ""))
    except (AttributeError, ValueError):
        return None


def parse_detail(html: str) -> tuple[str | None, str | None, list[TorrentFile]]:
    """Retorna (magnet, info_hash, arquivos)."""
    soup = BeautifulSoup(html, "html.parser")
    magnet_a = soup.find("a", href=re.compile(r"^magnet:\?"))
    magnet = magnet_a["href"] if magnet_a else None
    info_hash = None
    if magnet:
        m = re.search(r"btih:([0-9a-fA-F]{40})", magnet)
        info_hash = m.group(1).lower() if m else None
    files = []
    for li in soup.select("#files li, .file-content li"):
        text = li.get_text(" ", strip=True)
        m = re.match(r"(.+?)\s*\(([\d.,]+\s*(?:TB|GB|MB|KB|B))\)\s*$", text, re.IGNORECASE)
        if m:
            files.append(TorrentFile(name=m.group(1).strip(), size=parse_size(m.group(2))))
        elif text:
            files.append(TorrentFile(name=text, size=0))
    return magnet, info_hash, files


class X1337Adapter(SiteAdapter):
    name = "1337x"

    async def search(self, query, media):
        medias = [media] if media else [MediaType.AUDIO, MediaType.VIDEO]
        last_err = None
        for base in BASE_URLS:
            jobs = [(m, cat) for m in medias for cat in CATEGORIES[m]]
            pages = await asyncio.gather(
                *(self.client.get(f"{base}/category-search/{quote(query)}/{cat}/1/")
                  for _, cat in jobs), return_exceptions=True)
            results, ok = [], False
            for (m, _), resp in zip(jobs, pages):
                if isinstance(resp, Exception) or resp.status_code != 200:
                    last_err = resp if isinstance(resp, Exception) else f"HTTP {resp.status_code}"
                    continue
                ok = True
                results.extend(parse_search(resp.text, base, m))
            if not ok:
                continue  # tenta o próximo domínio
            results.sort(key=lambda r: r.seeders or 0, reverse=True)
            await asyncio.gather(*(self._detail(r) for r in results[: self.inspect_top]))
            return results
        raise RuntimeError(f"1337x indisponível (pode ser bloqueio do Cloudflare): {last_err}")

    async def _detail(self, r: TorrentResult):
        try:
            resp = await self.client.get(r.page_url)
            resp.raise_for_status()
            r.magnet, r.info_hash, files = parse_detail(resp.text)
            r.files = files or None
        except Exception:
            pass
