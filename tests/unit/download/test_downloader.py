from __future__ import annotations

import threading
from pathlib import Path

import httpx
import pytest

from manji.config.models import ConflictResolution
from manji.download.downloader import (
    Downloader,
    DownloadOutcome,
    read_resume_state,
    resume_path_for,
    temp_path_for,
)
from manji.errors import DownloadError, HTTPError
from manji.net.client import ClientSettings, CompliantClient
from manji.net.limiter import FakeClock
from tests.conftest import TEST_USER_AGENT

pytestmark = pytest.mark.unit

PAYLOAD = b"0123456789" * 1000  # 10_000 bytes


def make_client(handler, *, max_retries: int = 0) -> CompliantClient:
    def wrapped(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\n")
        return handler(request)

    return CompliantClient(
        ClientSettings(
            user_agent=TEST_USER_AGENT,
            timeout_seconds=5.0,
            max_retries=max_retries,
            default_request_delay_seconds=0.0,
        ),
        transport=httpx.MockTransport(wrapped),
        clock=FakeClock(),
    )


def test_download_writes_file_and_removes_temp(tmp_path: Path) -> None:
    client = make_client(
        lambda request: httpx.Response(
            200, content=PAYLOAD, headers={"Content-Length": str(len(PAYLOAD))}
        )
    )
    try:
        result = Downloader(client).download("https://mock.test/m.mkv", tmp_path / "out.mkv")
    finally:
        client.close()

    assert result.outcome is DownloadOutcome.DOWNLOADED
    assert result.destination.read_bytes() == PAYLOAD
    assert result.bytes_written == len(PAYLOAD)
    assert result.total_bytes == len(PAYLOAD)
    assert not temp_path_for(result.destination).exists()
    assert not resume_path_for(result.destination).exists()


def test_content_length_mismatch_raises_and_keeps_temp(tmp_path: Path) -> None:
    client = make_client(
        lambda request: httpx.Response(200, content=b"short", headers={"Content-Length": "999"})
    )
    try:
        with pytest.raises(DownloadError, match="Size mismatch"):
            Downloader(client).download("https://mock.test/m.mkv", tmp_path / "out.mkv")
    finally:
        client.close()

    assert temp_path_for(tmp_path / "out.mkv").exists()
    assert not (tmp_path / "out.mkv").exists()


def test_expected_size_mismatch_is_detected(tmp_path: Path) -> None:
    client = make_client(lambda request: httpx.Response(200, content=b"12345"))
    try:
        with pytest.raises(DownloadError, match="Size mismatch"):
            Downloader(client).download(
                "https://mock.test/m.mkv", tmp_path / "out.mkv", expected_size=10
            )
    finally:
        client.close()


def test_cancellation_keeps_temp_and_metadata(tmp_path: Path) -> None:
    """A cancelled download keeps its temp file so a later run can resume."""

    stop = threading.Event()

    class Chunked(httpx.SyncByteStream):
        def __iter__(self):
            yield b"a" * 100
            stop.set()
            yield b"b" * 100

        def close(self) -> None:
            return None

    client = make_client(
        lambda request: httpx.Response(200, stream=Chunked(), headers={"Content-Length": "200"})
    )
    try:
        with pytest.raises(DownloadError, match="cancelled"):
            Downloader(client).download(
                "https://mock.test/m.mkv", tmp_path / "out.mkv", stop_event=stop
            )
    finally:
        client.close()

    temp = temp_path_for(tmp_path / "out.mkv")
    assert temp.exists(), "the temp file must survive cancellation for resume"
    assert not (tmp_path / "out.mkv").exists(), "a partial file must never be finalized"


def test_cancelled_download_resumes_later(tmp_path: Path) -> None:
    destination = tmp_path / "out.mkv"
    stop = threading.Event()

    class Chunked(httpx.SyncByteStream):
        def __iter__(self):
            yield b"a" * 100
            stop.set()
            yield b"b" * 100

        def close(self) -> None:
            return None

    client = make_client(
        lambda request: httpx.Response(200, stream=Chunked(), headers={"Content-Length": "200"})
    )
    try:
        with pytest.raises(DownloadError):
            Downloader(client).download(
                destination=destination, url="https://mock.test/m.mkv", stop_event=stop
            )
    finally:
        client.close()

    offset = temp_path_for(destination).stat().st_size
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update({key.lower(): value for key, value in request.headers.items()})
        return httpx.Response(
            206,
            content=b"z" * (200 - offset),
            headers={"Content-Range": f"bytes {offset}-199/200"},
        )

    client = make_client(handler)
    try:
        result = Downloader(client).download("https://mock.test/m.mkv", destination)
    finally:
        client.close()

    if offset:
        assert seen.get("range") == f"bytes={offset}-"
        assert result.outcome is DownloadOutcome.RESUMED
    else:
        assert result.outcome is DownloadOutcome.DOWNLOADED
    assert destination.stat().st_size == 200
    assert not temp_path_for(destination).exists()


def test_resume_from_partial_temp(tmp_path: Path) -> None:
    destination = tmp_path / "out.mkv"
    temp = temp_path_for(destination)
    temp.write_bytes(PAYLOAD[:4000])
    from manji.download.downloader import ResumeState
    from manji.fs import atomic_write_json

    atomic_write_json(
        resume_path_for(destination),
        ResumeState(url="https://mock.test/m.mkv").to_dict(),
    )

    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update({key.lower(): value for key, value in request.headers.items()})
        return httpx.Response(
            206,
            content=PAYLOAD[4000:],
            headers={
                "Content-Range": f"bytes 4000-{len(PAYLOAD) - 1}/{len(PAYLOAD)}",
                "Content-Length": str(len(PAYLOAD) - 4000),
                "ETag": '"abc"',
            },
        )

    client = make_client(handler)
    try:
        result = Downloader(client).download("https://mock.test/m.mkv", destination)
    finally:
        client.close()

    assert seen_headers.get("range") == "bytes=4000-"
    assert result.outcome is DownloadOutcome.RESUMED
    assert result.resumed_from == 4000
    assert destination.read_bytes() == PAYLOAD


def test_server_ignoring_range_restarts(tmp_path: Path) -> None:
    destination = tmp_path / "out.mkv"
    temp_path_for(destination).write_bytes(b"garbage-prefix")

    client = make_client(
        lambda request: httpx.Response(
            200, content=PAYLOAD, headers={"Content-Length": str(len(PAYLOAD))}
        )
    )
    try:
        result = Downloader(client).download("https://mock.test/m.mkv", destination)
    finally:
        client.close()

    assert result.outcome is DownloadOutcome.DOWNLOADED
    assert destination.read_bytes() == PAYLOAD


def test_416_with_complete_file_finalizes(tmp_path: Path) -> None:
    destination = tmp_path / "out.mkv"
    temp_path_for(destination).write_bytes(PAYLOAD)
    from manji.download.downloader import ResumeState
    from manji.fs import atomic_write_json

    atomic_write_json(
        resume_path_for(destination),
        ResumeState(url="https://mock.test/m.mkv", total_bytes=len(PAYLOAD)).to_dict(),
    )

    client = make_client(
        lambda request: httpx.Response(416, headers={"Content-Range": f"bytes */{len(PAYLOAD)}"})
    )
    try:
        with pytest.raises(DownloadError, match="already complete"):
            Downloader(client).download("https://mock.test/m.mkv", destination)
    finally:
        client.close()

    assert destination.read_bytes() == PAYLOAD


def test_416_without_complete_file_errors(tmp_path: Path) -> None:
    destination = tmp_path / "out.mkv"
    temp_path_for(destination).write_bytes(b"partial")

    client = make_client(lambda request: httpx.Response(416))
    try:
        with pytest.raises(DownloadError, match="416"):
            Downloader(client).download("https://mock.test/m.mkv", destination)
    finally:
        client.close()


@pytest.mark.parametrize(
    ("policy", "expected_outcome"),
    [
        (ConflictResolution.SKIP, DownloadOutcome.SKIPPED),
        (ConflictResolution.OVERWRITE, DownloadOutcome.DOWNLOADED),
        (ConflictResolution.RENAME, DownloadOutcome.RENAMED),
    ],
)
def test_conflict_policies(
    tmp_path: Path,
    policy: ConflictResolution,
    expected_outcome: DownloadOutcome,
) -> None:
    destination = tmp_path / "out.mkv"
    destination.write_bytes(b"existing")

    client = make_client(lambda request: httpx.Response(200, content=b"fresh"))
    try:
        result = Downloader(client, conflict_resolution=policy).download(
            "https://mock.test/m.mkv", destination
        )
    finally:
        client.close()

    assert result.outcome is expected_outcome
    if policy is ConflictResolution.SKIP:
        assert destination.read_bytes() == b"existing"
        assert result.bytes_written == 0
    elif policy is ConflictResolution.OVERWRITE:
        assert destination.read_bytes() == b"fresh"
    else:
        assert destination.read_bytes() == b"existing"
        assert result.destination.name == "out (1).mkv"
        assert result.destination.read_bytes() == b"fresh"


def test_rename_skips_existing_candidates(tmp_path: Path) -> None:
    (tmp_path / "out.mkv").write_bytes(b"a")
    (tmp_path / "out (1).mkv").write_bytes(b"b")

    client = make_client(lambda request: httpx.Response(200, content=b"fresh"))
    try:
        result = Downloader(client, conflict_resolution=ConflictResolution.RENAME).download(
            "https://mock.test/m.mkv", tmp_path / "out.mkv"
        )
    finally:
        client.close()

    assert result.destination.name == "out (2).mkv"


def test_resume_state_for_different_url_is_discarded(tmp_path: Path) -> None:
    destination = tmp_path / "out.mkv"
    temp_path_for(destination).write_bytes(b"stale")
    resume_path_for(destination).write_text(
        '{"version": "1.0", "url": "https://other.test/x.mkv"}', encoding="utf-8"
    )

    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update({key.lower(): value for key, value in request.headers.items()})
        return httpx.Response(200, content=b"fresh")

    client = make_client(handler)
    try:
        Downloader(client).download("https://mock.test/m.mkv", destination)
    finally:
        client.close()

    assert "range" not in seen
    assert destination.read_bytes() == b"fresh"


def test_unexpected_status_raises(tmp_path: Path) -> None:
    client = make_client(lambda request: httpx.Response(404))
    try:
        with pytest.raises(HTTPError, match="404"):
            Downloader(client).download("https://mock.test/m.mkv", tmp_path / "out.mkv")
    finally:
        client.close()


def test_resume_state_round_trip(tmp_path: Path) -> None:
    from manji.download.downloader import ResumeState

    state = ResumeState(
        url="https://mock.test/m.mkv",
        etag='"e"',
        last_modified="Wed, 01 May 2024 00:00:00 GMT",
        total_bytes=123,
    )
    payload = state.to_dict()
    restored = ResumeState.from_dict(payload)
    assert restored.etag == '"e"'
    assert restored.total_bytes == 123
    assert restored.updated_at is not None


def test_corrupt_resume_state_is_ignored(tmp_path: Path) -> None:
    destination = tmp_path / "out.mkv"
    resume_path_for(destination).write_text("not json", encoding="utf-8")
    assert read_resume_state(destination) is None
