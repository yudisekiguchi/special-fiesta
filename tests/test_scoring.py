from datetime import datetime, timedelta, timezone

from app.models import MediaType, TorrentFile, TorrentResult, UploaderStatus
from app.scoring import GB, MB, merge_duplicates, score

NOW = datetime(2026, 11, 19, tzinfo=timezone.utc)


def mk(**kw):
    base = dict(source="X", title="Artist - Album (2010) [FLAC]", media_type=MediaType.AUDIO,
                size=400 * MB, seeders=120, leechers=10, uploader="joe",
                uploader_status=UploaderStatus.TRUSTED, added=NOW - timedelta(days=800),
                files=[TorrentFile("01 - Song.flac", 30 * MB), TorrentFile("cover.jpg", 1 * MB)])
    base.update(kw)
    return score(TorrentResult(**base), now=NOW)


def test_good_album_is_green():
    r = mk()
    assert r.level == "green" and r.score >= 70


def test_executable_forces_red():
    r = mk(files=[TorrentFile("01 - Song.mp3", 5 * MB), TorrentFile("Player.exe", 2 * MB)],
           uploader_status=UploaderStatus.VIP, seeders=5000)
    assert r.level == "red"
    assert any(x["kind"] == "danger" for x in r.reasons)


def test_executable_in_title_is_red():
    assert mk(title="Movie 2026 1080p.mp4.exe", media_type=MediaType.VIDEO, files=None).level == "red"


def test_tiny_video_with_codec_word_is_red():
    r = mk(title="New Movie 2026 1080p + codec", media_type=MediaType.VIDEO, size=2 * MB,
           files=None, seeders=0, uploader_status=UploaderStatus.MEMBER,
           added=NOW - timedelta(hours=5))
    assert r.level == "red"


def test_password_archive_is_not_green():
    r = mk(files=[TorrentFile("album.rar", 300 * MB), TorrentFile("password.txt", 1)],
           uploader_status=UploaderStatus.MEMBER, seeders=20)
    assert r.level != "green"


def test_unverified_files_member_is_yellow():
    r = mk(files=None, uploader_status=UploaderStatus.MEMBER, seeders=30,
           title="Some Show S01E01 720p", media_type=MediaType.VIDEO, size=1 * GB)
    assert r.level == "yellow"


def test_official_source_is_green():
    r = mk(seeders=None, leechers=None, uploader_status=UploaderStatus.UNKNOWN,
           files=None, official_source=True)
    assert r.level == "green"


def test_merge_duplicates():
    a = TorrentResult(source="A", title="t", media_type=MediaType.AUDIO, size=1, info_hash="ab" * 20, seeders=3)
    b = TorrentResult(source="B", title="t", media_type=MediaType.AUDIO, size=1, info_hash="AB" * 20, seeders=9,
                      files=[TorrentFile("x.mp3", 1)])
    out = merge_duplicates([a, b])
    assert len(out) == 1 and out[0].also_on == ["B"] and out[0].seeders == 9 and out[0].files
