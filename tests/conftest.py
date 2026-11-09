"""Shared fixtures for compliance HTTP tests."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from manji.net.client import ClientSettings, CompliantClient
from manji.net.limiter import FakeClock
from tests.helpers import HostRewriteTransport, MockSite
from tests.helpers.mock_site import running_site

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "adapters"
TEST_USER_AGENT = "ManjiDownloader/1.0 (+https://example.com/manji-downloader)"


def load_fixture(site: str, name: str) -> str:
    return (FIXTURES / site / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    from manji.adapters.registry import reset_registry

    reset_registry()
    yield
    reset_registry()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def mock_json_site() -> Iterator[MockSite]:
    with running_site() as site:
        site.static(
            "/robots.txt",
            body=load_fixture("mock_json", "robots.txt"),
            headers={"Content-Type": "text/plain"},
        )
        catalog = json.loads(load_fixture("mock_json", "catalog.json"))
        site.json("/series/example", catalog)
        variants = json.loads(load_fixture("mock_json", "variants.json"))
        for episode in range(1, 25):
            path = f"/series/example/episodes/{episode}"
            payload = {
                "item_id": f"ep-{episode:02d}",
                "variants": [
                    {
                        **variant,
                        "id": variant["id"].replace("ep-01", f"ep-{episode:02d}"),
                    }
                    for variant in variants["variants"]
                ],
            }
            site.json(path, payload)
        yield site


@pytest.fixture
def mock_html_site() -> Iterator[MockSite]:
    with running_site() as site:
        site.static(
            "/robots.txt",
            body=load_fixture("mock_html", "robots.txt"),
            headers={"Content-Type": "text/plain"},
        )
        site.static(
            "/series/example",
            body=load_fixture("mock_html", "catalog.html"),
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
        variants = load_fixture("mock_html", "variants.html")
        for episode in range(1, 13):
            site.static(
                f"/series/example/episodes/{episode}",
                body=variants,
                headers={"Content-Type": "text/html; charset=utf-8"},
            )
        yield site


def build_client(
    base_url: str,
    *,
    clock: FakeClock | None = None,
    max_retries: int = 2,
    delay: float = 0.0,
    max_concurrency: int = 2,
    retry_after_cap: float = 30.0,
) -> CompliantClient:
    settings = ClientSettings(
        user_agent=TEST_USER_AGENT,
        timeout_seconds=5.0,
        max_retries=max_retries,
        retry_backoff_seconds=0.1,
        retry_after_cap_seconds=retry_after_cap,
        max_concurrency_per_domain=max_concurrency,
        default_request_delay_seconds=delay,
    )
    transport = HostRewriteTransport(base_url)
    return CompliantClient(settings, transport=transport, clock=clock or FakeClock())


def build_raw_client(base_url: str, *, clock: FakeClock | None = None) -> httpx.Client:
    return httpx.Client(
        transport=HostRewriteTransport(base_url),
        headers={"User-Agent": TEST_USER_AGENT},
        follow_redirects=False,
    )
