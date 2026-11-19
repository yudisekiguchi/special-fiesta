"""Motor de pontuação de confiança.

Não existe garantia de segurança sem escanear o arquivo baixado. Aqui
combinamos sinais conhecidos para classificar cada resultado em:
  green  -> aparenta ser confiável
  yellow -> atenção, verifique antes
  red    -> evite
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone

from .models import MediaType, TorrentResult, UploaderStatus

KB, MB, GB = 1024, 1024**2, 1024**3

# Executáveis/scripts: nunca deveriam estar num torrent de música, vídeo ou imagem.
DANGEROUS_EXT = {
    ".exe", ".scr", ".bat", ".cmd", ".com", ".msi", ".lnk", ".vbs", ".vbe",
    ".js", ".jse", ".jar", ".ps1", ".psm1", ".apk", ".pif", ".hta", ".wsf",
    ".dll", ".cpl", ".reg", ".sh", ".run", ".bin", ".appimage", ".deb", ".dmg",
}
# Compactados podem esconder conteúdo ou exigir "senha num site".
ARCHIVE_EXT = {".zip", ".rar", ".7z", ".tar", ".gz", ".iso"}
# Arquivos de acompanhamento normais.
HARMLESS_EXTRA_EXT = {".txt", ".nfo", ".sfv", ".md5", ".cue", ".log", ".m3u",
                      ".m3u8", ".srt", ".sub", ".idx", ".ass", ".jpg", ".jpeg",
                      ".png", ".url"}

MEDIA_EXT = {
    MediaType.AUDIO: {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav",
                      ".wma", ".alac", ".ape", ".aiff"},
    MediaType.VIDEO: {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".webm",
                      ".ts", ".mpg", ".mpeg", ".flv"},
    MediaType.IMAGE: {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif",
                      ".tiff", ".raw", ".cr2", ".nef", ".heic", ".psd"},
}

SUSPICIOUS_WORDS = re.compile(
    r"\b(password|senha|codec|keygen|crack|setup|install(er)?|activator|"
    r"patch|serial|loader|free[\s_-]?download)\b",
    re.IGNORECASE,
)

# Faixas de tamanho plausíveis (total do torrent).
SIZE_RANGES = {
    MediaType.AUDIO: (1 * MB, 30 * GB),
    MediaType.VIDEO: (50 * MB, 120 * GB),
    MediaType.IMAGE: (20 * KB, 50 * GB),
}


MEDIA_PT = {MediaType.AUDIO: "música", MediaType.VIDEO: "vídeo", MediaType.IMAGE: "imagem"}


def _ext(name: str) -> str:
    return os.path.splitext(name.lower().strip())[1]


def _add(result: TorrentResult, points: int, kind: str, text: str) -> None:
    result.reasons.append({"points": points, "kind": kind, "text": text})


def score(result: TorrentResult, now: datetime | None = None) -> TorrentResult:
    now = now or datetime.now(timezone.utc)
    result.reasons = []
    critical = False
    pts = 50  # ponto de partida neutro

    # --- Nome do torrent ---
    title_ext = _ext(result.title)
    if title_ext in DANGEROUS_EXT:
        pts -= 60
        critical = True
        _add(result, -60, "danger", f"O nome termina em {title_ext} (executável)")
    m = SUSPICIOUS_WORDS.search(result.title)
    if m:
        pts -= 25
        _add(result, -25, "warn", f'Nome contém termo suspeito: "{m.group(0)}"')

    # --- Lista de arquivos ---
    if result.files is None:
        _add(result, 0, "info", "Lista de arquivos não verificada")
    elif not result.files:
        pts -= 10
        _add(result, -10, "warn", "Torrent sem lista de arquivos")
    else:
        exts = [_ext(f.name) for f in result.files]
        bad = sorted({e for e in exts if e in DANGEROUS_EXT})
        archives = sorted({e for e in exts if e in ARCHIVE_EXT})
        expected = MEDIA_EXT[result.media_type]
        media_count = sum(1 for e in exts if e in expected)
        unknown = sorted({e for e in exts if e and e not in expected
                          and e not in HARMLESS_EXTRA_EXT
                          and e not in DANGEROUS_EXT and e not in ARCHIVE_EXT})
        if bad:
            pts -= 70
            critical = True
            _add(result, -70, "danger",
                 f"Contém arquivos executáveis: {', '.join(bad)}")
        if archives:
            pts -= 20
            _add(result, -20, "warn",
                 f"Contém arquivos compactados ({', '.join(archives)}): "
                 "podem esconder conteúdo ou pedir senha")
        if media_count == 0:
            pts -= 30
            _add(result, -30, "warn",
                 f"Nenhum arquivo de {MEDIA_PT[result.media_type]} reconhecido")
        else:
            pts += 10
            _add(result, +10, "good",
                 f"{media_count} arquivo(s) de {MEDIA_PT[result.media_type]} com extensão esperada")
        if unknown:
            pts -= 5
            _add(result, -5, "info", f"Extensões incomuns: {', '.join(unknown[:6])}")

    # --- Tamanho ---
    lo, hi = SIZE_RANGES[result.media_type]
    if result.size and result.size < lo:
        pts -= 30
        _add(result, -30, "warn", "Tamanho pequeno demais para o tipo de mídia")
    elif result.size and result.size > hi:
        pts -= 10
        _add(result, -10, "info", "Tamanho muito grande para o tipo de mídia")

    # --- Fonte oficial ---
    if result.official_source:
        pts += 35
        _add(result, +35, "good", "Fonte oficial/curada (acervo público)")

    # --- Seeders ---
    s = result.seeders
    if s is not None:
        if s == 0:
            pts -= 20
            _add(result, -20, "warn", "Nenhum seeder (provavelmente morto ou falso)")
        elif s < 5:
            pts -= 5
            _add(result, -5, "info", f"Poucos seeders ({s})")
        elif s >= 500:
            pts += 20
            _add(result, +20, "good", f"Muito compartilhado ({s} seeders)")
        elif s >= 50:
            pts += 12
            _add(result, +12, "good", f"Bem compartilhado ({s} seeders)")
        else:
            pts += 5
            _add(result, +5, "good", f"{s} seeders")
        # Muitos leechers e quase nenhum seeder é padrão de torrent isca.
        if result.leechers and s < 3 and result.leechers > 50:
            pts -= 10
            _add(result, -10, "warn", "Muitos baixando e quase ninguém compartilhando")

    # --- Uploader ---
    if result.uploader_status == UploaderStatus.VIP:
        pts += 20
        _add(result, +20, "good", f"Uploader VIP ({result.uploader})")
    elif result.uploader_status == UploaderStatus.TRUSTED:
        pts += 15
        _add(result, +15, "good", f"Uploader confiável ({result.uploader})")
    elif result.uploader_status == UploaderStatus.MEMBER:
        _add(result, 0, "info", "Uploader sem selo de confiança")

    # --- Idade ---
    if result.added:
        added = result.added if result.added.tzinfo else result.added.replace(tzinfo=timezone.utc)
        days = (now - added).days
        if days < 2 and result.uploader_status not in (UploaderStatus.VIP, UploaderStatus.TRUSTED):
            pts -= 5
            _add(result, -5, "info", "Publicado há menos de 2 dias por uploader sem selo")
        elif days > 365 and (s or 0) >= 10:
            pts += 5
            _add(result, +5, "good", "Torrent antigo e ainda ativo")

    # --- Presença em várias fontes ---
    if result.also_on:
        bonus = min(10 * len(result.also_on), 20)
        pts += bonus
        _add(result, +bonus, "good", f"Mesmo hash também em: {', '.join(result.also_on)}")

    pts = max(0, min(100, pts))
    result.score = pts
    if critical or pts < 40:
        result.level = "red"
    elif pts >= 70:
        result.level = "green"
    else:
        result.level = "yellow"
    return result


def merge_duplicates(results: list[TorrentResult]) -> list[TorrentResult]:
    """Agrupa resultados com o mesmo info_hash, mantendo o mais completo."""
    by_hash: dict[str, TorrentResult] = {}
    out: list[TorrentResult] = []
    for r in results:
        h = (r.info_hash or "").lower()
        if not h:
            out.append(r)
            continue
        if h not in by_hash:
            by_hash[h] = r
            out.append(r)
            continue
        keep = by_hash[h]
        if r.source != keep.source and r.source not in keep.also_on:
            keep.also_on.append(r.source)
        if keep.files is None and r.files is not None:
            keep.files = r.files
        if (r.seeders or 0) > (keep.seeders or 0):
            keep.seeders, keep.leechers = r.seeders, r.leechers
    return out
