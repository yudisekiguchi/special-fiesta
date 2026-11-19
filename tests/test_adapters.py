import json
from pathlib import Path

import httpx
import pytest

from app.adapters import piratebay, x1337, internet_archive
from app.models import MediaType, UploaderStatus

FIX = Path(__file__).parent / "fixtures"

TPB_SEARCH = [
    {"id": "1", "name": "Artist - Album [MP3 320]", "info_hash": "A" * 40, "leechers": "4",
     "seeders": "80", "num_files": "10", "size": "123456789", "username": "bob",
     "added": "1500000000", "status": "vip", "category": "101", "imdb": ""},
    {"id": "2", "name": "Some Game", "info_hash": "B" * 40, "leechers": "1", "seeders": "999",
     "num_files": "1", "size": "1", "username": "x", "added": "1500000000", "status": "member",
     "category": "401", "imdb": ""},
]
TPB_FILES = [{"name": ["01.mp3"], "size": [5000000]}, {"name": ["cover.jpg"], "size": [1000]}]


def test_tpb_parse_filters_non_media():
    pairs = piratebay.parse_search(TPB_SEARCH)
    assert len(pairs) == 1
    r = pairs[0][1]
    assert r.media_type == MediaType.AUDIO and r.uploader_status == UploaderStatus.VIP
    assert r.magnet.startswith("magnet:?xt=urn:btih:" + "a" * 40)


def test_tpb_no_results():
    assert piratebay.parse_search([{"id": "0", "name": "No results returned", "info_hash": "0" * 40}]) == []


@pytest.mark.anyio
async def test_tpb_adapter_with_mock_transport():
    def handler(req):
        if req.url.path == "/q.php":
            return httpx.Response(200, json=TPB_SEARCH)
        return httpx.Response(200, json=TPB_FILES)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        res = await piratebay.PirateBayAdapter(c).search("album", None)
    assert len(res) == 1 and [f.name for f in res[0].files] == ["01.mp3", "cover.jpg"]


def test_1337x_parse_search():
    rs = x1337.parse_search((FIX / "1337x_search.html").read_text(), "https://1337x.to", MediaType.AUDIO)
    assert len(rs) == 2
    assert rs[0].seeders == 1234 and rs[0].uploader_status == UploaderStatus.VIP
    assert 400 * 1024**2 < rs[0].size < 420 * 1024**2
    assert rs[1].uploader_status == UploaderStatus.MEMBER and rs[1].seeders == 0


def test_1337x_parse_detail():
    magnet, h, files = x1337.parse_detail((FIX / "1337x_detail.html").read_text())
    assert h == "aabbccddeeff00112233445566778899aabbccdd"
    assert [f.name for f in files] == ["01 - Intro.flac", "cover.jpg"]


def test_archive_parse():
    data = {"response": {"docs": [
        {"identifier": "beethoven9", "title": "Symphony No. 9", "mediatype": "audio",
         "item_size": 300000000, "publicdate": "2012-01-01T00:00:00Z"},
        {"identifier": "abook", "title": "A text", "mediatype": "texts"}]}}
    rs = internet_archive.parse_search(data)
    assert len(rs) == 1 and rs[0].official_source
    assert rs[0].torrent_url.endswith("/beethoven9/beethoven9_archive.torrent")
