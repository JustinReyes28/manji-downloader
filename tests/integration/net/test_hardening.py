from __future__ import annotations

import httpx
import pytest

from manji.errors import NetworkError
from manji.net.client import ClientSettings, CompliantClient, _strip_cross_origin_credentials
from manji.net.limiter import FakeClock
from tests.conftest import TEST_USER_AGENT, build_client
from tests.helpers import HostRewriteTransport, MockSite

pytestmark = [pytest.mark.integration, pytest.mark.compliance]


class _FailPageOnceTransport(httpx.BaseTransport):
    """Fail the first non-robots request, then delegate to the loopback transport."""

    def __init__(self, inner: httpx.BaseTransport) -> None:
        self._inner = inner
        self.failed = False

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if not self.failed and request.url.path != "/robots.txt":
            self.failed = True
            raise httpx.ConnectError("simulated transport failure", request=request)
        return self._inner.handle_request(request)

    def close(self) -> None:
        return None


def test_transport_error_releases_the_domain_slot(mock_json_site: MockSite) -> None:
    """A failed request must not leak its concurrency slot."""

    inner = HostRewriteTransport(mock_json_site.base_url)
    failing = _FailPageOnceTransport(inner)
    settings = ClientSettings(
        user_agent=TEST_USER_AGENT,
        timeout_seconds=5.0,
        max_retries=0,
        retry_after_cap_seconds=30.0,
        max_concurrency_per_domain=1,
        default_request_delay_seconds=0.0,
    )
    client = CompliantClient(settings, transport=failing, clock=FakeClock())
    try:
        with pytest.raises(NetworkError):
            client.get("https://mock-json.test/series/example")
        payload = client.get_json("https://mock-json.test/series/example")
        assert isinstance(payload, dict)
    finally:
        client.close()


def test_robots_fetch_uses_the_per_domain_limiter(mock_json_site: MockSite) -> None:
    clock = FakeClock()
    client = build_client(mock_json_site.base_url, clock=clock, delay=2.0)
    try:
        client.get_json("https://mock-json.test/series/example")
    finally:
        client.close()
    assert 2.0 in clock.sleeps


def test_strip_cross_origin_credentials() -> None:
    headers = {
        "Authorization": "Bearer secret",
        "Cookie": "session=abc",
        "Proxy-Authorization": "Basic x",
        "X-Trace": "keep",
    }
    stripped = _strip_cross_origin_credentials(headers)
    assert stripped == {"X-Trace": "keep"}
    assert _strip_cross_origin_credentials(None) is None


def test_cross_origin_redirect_drops_credentials() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\n")
        if request.url.host == "mock-json.test":
            return httpx.Response(
                302, headers={"Location": "https://mock-html.test/series/example"}
            )
        return httpx.Response(200, json={"ok": True})

    client = CompliantClient(
        ClientSettings(user_agent=TEST_USER_AGENT, timeout_seconds=5.0),
        transport=httpx.MockTransport(handler),
        clock=FakeClock(),
    )
    try:
        response = client.get(
            "https://mock-json.test/series/start",
            headers={"Authorization": "Bearer secret-token", "X-Trace": "keep"},
        )
        response.close()
    finally:
        client.close()

    first_hop = [request for request in seen if request.url.host == "mock-json.test"]
    second_hop = [request for request in seen if request.url.host == "mock-html.test"]
    assert first_hop, "the original host should have been requested"
    assert second_hop, "the redirect target should have been requested"

    first_headers = {key.lower(): value for key, value in first_hop[-1].headers.items()}
    assert first_headers.get("authorization") == "Bearer secret-token"
    hop_headers = {key.lower(): value for key, value in second_hop[0].headers.items()}
    assert "authorization" not in hop_headers
