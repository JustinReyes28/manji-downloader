"""Integration tests: streaming download through the Phase 3 mock server."""

from __future__ import annotations

import threading
from pathlib import Path

import httpx
import pytest

from manji.domain import Category, MediaItem, MediaVariant
from manji.download.downloader import Downloader, DownloadOutcome, temp_path_for
from manji.errors import ChallengeDetectedError, DownloadError
from manji.organize.filenames import FilenameContext, build_destination
from manji.organize.sidecars import write_episode_sidecar
from tests.conftest import TEST_USER_AGENT, build_client, load_fixture
from tests.helpers import MockSite

pytestmark = [pytest.mark.integration, pytest.mark.compliance]

PAYLOAD = bytes(range(256)) * 400  # 102_400 bytes


def _mount_media(site: MockSite, path: str = "/media/ep-01.mkv", payload: bytes = PAYLOAD) -> None:
    site.static(
        path,
        body=payload,
        headers={
            "Content-Type": "video/x-matroska",
            "Content-Length": str(len(payload)),
            "ETag": '"v1"',
            "Accept-Ranges": "bytes",
        },
    )


def test_download_success_writes_atomic_file(mock_json_site: MockSite, tmp_path: Path) -> None:
    _mount_media(mock_json_site)
    client = build_client(mock_json_site.base_url)
    try:
        result = Downloader(client).download(
            "https://mock-json.test/media/ep-01.mkv", tmp_path / "ep-01.mkv"
        )
    finally:
        client.close()

    assert result.outcome is DownloadOutcome.DOWNLOADED
    assert result.destination.read_bytes() == PAYLOAD
    assert not temp_path_for(result.destination).exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_download_resumes_from_partial_temp(mock_json_site: MockSite, tmp_path: Path) -> None:
    _mount_media(mock_json_site)
    destination = tmp_path / "ep-01.mkv"
    temp = temp_path_for(destination)
    temp.write_bytes(PAYLOAD[:50_000])

    from manji.download.downloader import ResumeState
    from manji.fs import atomic_write_json

    atomic_write_json(
        destination.with_name(destination.name + ".resume.json"),
        ResumeState(url="https://mock-json.test/media/ep-01.mkv", etag='"v1"').to_dict(),
    )

    client = build_client(mock_json_site.base_url)
    try:
        result = Downloader(client).download("https://mock-json.test/media/ep-01.mkv", destination)
    finally:
        client.close()

    assert result.outcome is DownloadOutcome.RESUMED
    assert result.resumed_from == 50_000
    assert destination.read_bytes() == PAYLOAD


def test_download_through_mock_html_site(mock_html_site: MockSite, tmp_path: Path) -> None:
    _mount_media(mock_html_site, "/media/ova-01.mkv", b"html-site-payload")
    client = build_client(mock_html_site.base_url)
    try:
        result = Downloader(client).download(
            "https://mock-html.test/media/ova-01.mkv", tmp_path / "ova-01.mkv"
        )
    finally:
        client.close()

    assert result.destination.read_bytes() == b"html-site-payload"


def test_download_checks_robots_before_streaming(mock_json_site: MockSite, tmp_path: Path) -> None:
    client = build_client(mock_json_site.base_url)
    try:
        with pytest.raises(Exception, match="disallows"):
            Downloader(client).download(
                "https://mock-json.test/private/ep-01.mkv", tmp_path / "ep-01.mkv"
            )
    finally:
        client.close()

    assert mock_json_site.hits("/private/ep-01.mkv") == 0
    assert not (tmp_path / "ep-01.mkv").exists()


def test_download_stops_on_challenge(mock_json_site: MockSite, tmp_path: Path) -> None:
    mock_json_site.static(
        "/media/ep-01.mkv",
        status=403,
        body=load_fixture("mock_json", "challenge.html"),
        headers={"Content-Type": "text/html"},
    )
    client = build_client(mock_json_site.base_url)
    try:
        with pytest.raises(ChallengeDetectedError, match="browser"):
            Downloader(client).download(
                "https://mock-json.test/media/ep-01.mkv", tmp_path / "ep-01.mkv"
            )
    finally:
        client.close()

    assert mock_json_site.hits("/media/ep-01.mkv") == 1
    assert not (tmp_path / "ep-01.mkv").exists()


def test_download_respects_domain_delay(mock_json_site: MockSite, tmp_path: Path) -> None:
    from manji.net.limiter import FakeClock

    _mount_media(mock_json_site)
    clock = FakeClock()
    client = build_client(mock_json_site.base_url, clock=clock, delay=1.5)
    try:
        Downloader(client).download("https://mock-json.test/media/ep-01.mkv", tmp_path / "a.mkv")
        Downloader(client).download("https://mock-json.test/media/ep-01.mkv", tmp_path / "b.mkv")
    finally:
        client.close()
    assert 1.5 in clock.sleeps


def test_download_with_sidecar_and_template(mock_json_site: MockSite, tmp_path: Path) -> None:
    _mount_media(mock_json_site)
    item = MediaItem(
        id="ep-01", number=1, title="Episode 01", url="https://mock-json.test/media/ep-01.mkv"
    )
    variant = MediaVariant(
        id="ep-01-1080p-mkv",
        quality="1080p",
        container="mkv",
        size_bytes=len(PAYLOAD),
        uploaded_at=None,
        download_count=0,
        url="https://mock-json.test/media/ep-01.mkv",
    )
    from manji.domain import SeriesCatalog

    catalog = SeriesCatalog(
        title="Example Mock Series",
        site_id="mock_json",
        source_url="https://mock-json.test/series/example",
        episodes=(item,),
    )
    context = FilenameContext.build(catalog, Category.EPISODES, item, variant)
    template = (
        "{series_title}/{category}/{series_title} - Episode {episode_number} [{quality}].{ext}"
    )
    destination = build_destination(tmp_path, template, context)
    assert destination.name == "Example Mock Series - Episode 01 [1080p].mkv"

    client = build_client(mock_json_site.base_url)
    try:
        Downloader(client).download(item.url, destination)
    finally:
        client.close()

    write_episode_sidecar(
        destination.parent,
        Category.EPISODES,
        item,
        variant,
        site_id=catalog.site_id,
        source_url=catalog.source_url,
    )

    assert destination.exists()
    assert (destination.parent / "episode.yaml").exists()
    assert destination.parent.parent.name == "Example Mock Series"


def test_cancel_then_resume_integration(mock_json_site: MockSite, tmp_path: Path) -> None:
    _mount_media(mock_json_site)
    destination = tmp_path / "ep-01.mkv"
    stop = threading.Event()

    class Interrupting(httpx.SyncByteStream):
        def __iter__(self):
            yield PAYLOAD[:40_000]
            stop.set()
            yield PAYLOAD[40_000:]

        def close(self) -> None:
            return None

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, stream=Interrupting(), headers={"Content-Length": str(len(PAYLOAD))}
        )

    from manji.net.client import ClientSettings, CompliantClient
    from manji.net.limiter import FakeClock

    def wrapped(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\n")
        return handler(request)

    client = CompliantClient(
        ClientSettings(user_agent=TEST_USER_AGENT, timeout_seconds=5.0, max_retries=0),
        transport=httpx.MockTransport(wrapped),
        clock=FakeClock(),
    )
    try:
        with pytest.raises(DownloadError, match="cancelled"):
            Downloader(client).download(
                "https://mock-json.test/media/ep-01.mkv", destination, stop_event=stop
            )
    finally:
        client.close()

    assert temp_path_for(destination).exists()
    assert not destination.exists()

    client = build_client(mock_json_site.base_url)
    try:
        result = Downloader(client).download("https://mock-json.test/media/ep-01.mkv", destination)
    finally:
        client.close()

    assert destination.read_bytes() == PAYLOAD
    assert result.outcome in {DownloadOutcome.RESUMED, DownloadOutcome.DOWNLOADED}
