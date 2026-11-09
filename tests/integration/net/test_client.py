from __future__ import annotations

import pytest

from manji.errors import (
    AccessDeniedError,
    ChallengeDetectedError,
    HTTPError,
    RateLimitedError,
)
from manji.net.limiter import FakeClock
from tests.conftest import build_client, load_fixture
from tests.helpers import MockSite
from tests.helpers.mock_site import running_site

pytestmark = [pytest.mark.integration, pytest.mark.compliance]


def test_get_json_round_trip(mock_json_site: MockSite) -> None:
    client = build_client(mock_json_site.base_url)
    try:
        payload = client.get_json("https://mock-json.test/series/example")
        assert isinstance(payload, dict)
        assert payload["series"]["title"] == "Example Mock Series"
    finally:
        client.close()


def test_every_request_checks_robots_first(mock_json_site: MockSite) -> None:
    client = build_client(mock_json_site.base_url)
    try:
        client.get_json("https://mock-json.test/series/example")
        client.get_json("https://mock-json.test/series/example/episodes/1")
    finally:
        client.close()
    robots_hits = mock_json_site.hits("/robots.txt")
    assert robots_hits == 1, "robots.txt should be cached across requests"


def test_robots_disallowed_aborts_without_request(mock_json_site: MockSite) -> None:
    client = build_client(mock_json_site.base_url)
    try:
        with pytest.raises(Exception, match="disallows"):
            client.get("https://mock-json.test/private/secret")
    finally:
        client.close()
    assert mock_json_site.hits("/private/secret") == 0


def test_plain_403_raises_denial_and_is_not_retried(mock_json_site: MockSite) -> None:
    mock_json_site.static("/series/example", status=403, body="<html>Forbidden</html>")
    client = build_client(mock_json_site.base_url)
    try:
        with pytest.raises(AccessDeniedError):
            client.get("https://mock-json.test/series/example")
    finally:
        client.close()
    assert mock_json_site.hits("/series/example") == 1


def test_challenge_403_halts_after_one_request(mock_json_site: MockSite) -> None:
    mock_json_site.static(
        "/series/example",
        status=403,
        body=load_fixture("mock_json", "challenge.html"),
        headers={"Content-Type": "text/html"},
    )
    client = build_client(mock_json_site.base_url)
    try:
        with pytest.raises(ChallengeDetectedError, match="browser"):
            client.get("https://mock-json.test/series/example")
    finally:
        client.close()
    assert mock_json_site.hits("/series/example") == 1


def test_429_with_retry_after_then_success(mock_json_site: MockSite) -> None:
    attempts = {"count": 0}
    payload = load_fixture("mock_json", "variants.json")

    def handler(_method: str, _path: str):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return 429, {"Retry-After": "3"}, b"slow down"
        return 200, {"Content-Type": "application/json"}, payload.encode()

    mock_json_site.route("/series/example", handler)
    clock = FakeClock()
    client = build_client(mock_json_site.base_url, clock=clock)
    try:
        response = client.get("https://mock-json.test/series/example")
        assert response.status_code == 200
        response.close()
    finally:
        client.close()

    assert attempts["count"] == 2
    assert 3.0 in clock.sleeps


def test_retry_after_above_cap_stops_domain(mock_json_site: MockSite) -> None:
    mock_json_site.static(
        "/series/example",
        status=429,
        body="slow down",
        headers={"Retry-After": "600"},
    )
    client = build_client(mock_json_site.base_url, retry_after_cap=15.0)
    try:
        with pytest.raises(RateLimitedError, match="above the"):
            client.get("https://mock-json.test/series/example")
        with pytest.raises(RateLimitedError, match="blocked"):
            client.get("https://mock-json.test/series/example")
    finally:
        client.close()


def test_repeated_429_exhausts_retries(mock_json_site: MockSite) -> None:
    mock_json_site.static("/series/example", status=429, body="nope", headers={"Retry-After": "0"})
    clock = FakeClock()
    client = build_client(mock_json_site.base_url, clock=clock, max_retries=2)
    try:
        with pytest.raises(RateLimitedError, match="kept returning"):
            client.get("https://mock-json.test/series/example")
    finally:
        client.close()
    assert mock_json_site.hits("/series/example") == 3


def test_redirect_rechecks_robots_on_each_hop(mock_json_site: MockSite) -> None:
    mock_json_site.static(
        "/series/example",
        status=302,
        body="",
        headers={"Location": "/private/secret"},
    )
    client = build_client(mock_json_site.base_url)
    try:
        with pytest.raises(Exception, match="disallows"):
            client.get("https://mock-json.test/series/example")
    finally:
        client.close()
    assert mock_json_site.hits("/private/secret") == 0


def test_redirect_followed_when_allowed(mock_json_site: MockSite) -> None:
    mock_json_site.static(
        "/series/redirect", status=301, body="", headers={"Location": "/series/example"}
    )
    client = build_client(mock_json_site.base_url)
    try:
        payload = client.get_json("https://mock-json.test/series/redirect")
        assert isinstance(payload, dict)
    finally:
        client.close()


def test_missing_location_header_errors(mock_json_site: MockSite) -> None:
    mock_json_site.static("/series/redirect", status=302, body="")
    client = build_client(mock_json_site.base_url)
    try:
        with pytest.raises(HTTPError, match="Location"):
            client.get("https://mock-json.test/series/redirect")
    finally:
        client.close()


def test_server_error_retried_then_raised(mock_json_site: MockSite) -> None:
    mock_json_site.static("/series/example", status=500, body="boom")
    clock = FakeClock()
    client = build_client(mock_json_site.base_url, clock=clock, max_retries=2)
    try:
        with pytest.raises(HTTPError, match="500"):
            client.get("https://mock-json.test/series/example")
    finally:
        client.close()
    assert mock_json_site.hits("/series/example") == 3


def test_server_error_then_success(mock_json_site: MockSite) -> None:
    attempts = {"count": 0}

    def handler(_method: str, _path: str):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return 502, {}, b"bad gateway"
        return 200, {"Content-Type": "application/json"}, b"{}"

    mock_json_site.route("/series/example", handler)
    client = build_client(mock_json_site.base_url, max_retries=2)
    try:
        response = client.get("https://mock-json.test/series/example")
        assert response.status_code == 200
        response.close()
    finally:
        client.close()


def test_unexpected_4xx_raises_http_error(mock_json_site: MockSite) -> None:
    client = build_client(mock_json_site.base_url)
    try:
        with pytest.raises(HTTPError) as excinfo:
            client.get("https://mock-json.test/series/example/missing")
    finally:
        client.close()
    assert excinfo.value.status_code == 404


def test_no_redirects_are_followed_beyond_limit(mock_json_site: MockSite) -> None:
    def handler(_method: str, _path: str):
        return 302, {"Location": "/series/example"}, b""

    mock_json_site.route("/series/example", handler)
    client = build_client(mock_json_site.base_url)
    try:
        with pytest.raises(HTTPError, match="redirects"):
            client.get("https://mock-json.test/series/example")
    finally:
        client.close()


def test_domain_delay_applied_between_requests(mock_json_site: MockSite) -> None:
    clock = FakeClock()
    client = build_client(mock_json_site.base_url, clock=clock, delay=1.5)
    try:
        client.get_json("https://mock-json.test/series/example")
        client.get_json("https://mock-json.test/series/example/episodes/1")
    finally:
        client.close()
    assert 1.5 in clock.sleeps


def test_stream_context_manager(mock_json_site: MockSite) -> None:
    client = build_client(mock_json_site.base_url)
    try:
        with client.stream("https://mock-json.test/series/example") as response:
            body = b"".join(response.iter_bytes())
        assert b"Example Mock Series" in body
    finally:
        client.close()


def test_loopback_transport_blocks_external_hosts() -> None:
    """Any non-loopback host is refused before a socket is opened."""

    from manji.errors import RobotsUnavailableError
    from tests.helpers.transport import is_loopback_host

    client = build_client("http://127.0.0.1:1")
    try:
        with pytest.raises(RobotsUnavailableError, match="Failing closed"):
            client.get("https://not-loopback.example.test/series/example")
    finally:
        client.close()

    assert not is_loopback_host("not-loopback.example.test")


def test_robots_unavailable_fails_closed() -> None:
    from manji.errors import RobotsUnavailableError

    with running_site() as site:
        site.static("/robots.txt", status=503, body="unavailable")
        client = build_client(site.base_url)
        try:
            with pytest.raises((RobotsUnavailableError, RateLimitedError)):
                client.get("https://mock-json.test/series/example")
        finally:
            client.close()
