"""Modelos de dados compartilhados entre adaptadores, pontuação e API."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional


class MediaType(str, Enum):
    AUDIO = "audio"
    VIDEO = "video"
    IMAGE = "image"


class UploaderStatus(str, Enum):
    VIP = "vip"          # selo mais alto do site
    TRUSTED = "trusted"  # uploader confiável/verificado
    MEMBER = "member"    # usuário comum
    UNKNOWN = "unknown"


@dataclass
class TorrentFile:
    name: str
    size: int  # bytes


@dataclass
class TorrentResult:
    source: str
    title: str
    media_type: MediaType
    size: int  # bytes
    seeders: Optional[int] = None
    leechers: Optional[int] = None
    uploader: Optional[str] = None
    uploader_status: UploaderStatus = UploaderStatus.UNKNOWN
    added: Optional[datetime] = None
    info_hash: Optional[str] = None
    magnet: Optional[str] = None
    torrent_url: Optional[str] = None
    page_url: Optional[str] = None
    files: Optional[list[TorrentFile]] = None  # None = lista não verificada
    official_source: bool = False  # ex.: Internet Archive (acervo curado)

    # Preenchidos pelo motor de pontuação
    score: int = 0
    level: str = "red"
    reasons: list[dict] = field(default_factory=list)
    also_on: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["media_type"] = self.media_type.value
        d["uploader_status"] = self.uploader_status.value
        d["added"] = self.added.isoformat() if self.added else None
        return d
