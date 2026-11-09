from __future__ import annotations

import pytest

from manji.errors import RateLimitedError, RobotsDisallowedError, RobotsUnavailableError
from manji.net.limiter import FakeClock
from manji.net.robots import RobotsCache, parse_retry_after
from tests.conftest import TEST_USER_AGENT, build_raw_client
from tests.helpers import MockSite

pytestmark = [pytest.mark.unit, pytest.mark.compliance]

ROBOTS = """
User-agent: *
Disallow: /private/
Crawl-delay: 2
"""


def _cache(clock: FakeClock, client) -> RobotsCache:
    cache = RobotsCache(user_agent=TEST_USER_AGENT, clock=clock)
    return cache


def test_allows_public_path(mock_json_site: MockSite, clock: FakeClock) -> None:
    with build_raw_client(mock_json_site.base_url) as client:
        cache = _cache(clock, client)
        delay = cache.check("https://mock-json.test/series/example", client)
    assert delay == 1.0


def test_disallowed_path_raises(mock_json_site: MockSite, clock: FakeClock) -> None:
    with build_raw_client(mock_json_site.base_url) as client:
        cache = _cache(clock, client)
        with pytest.raises(RobotsDisallowedError, match="disallows"):
            cache.check("https://mock-json.test/private/secret", client)


def test_missing_robots_allows_all(clock: FakeClock) -> None:
    from tests.helpers.mock_site import running_site

    with running_site() as site:
        site.static("/public/page", body="ok")
        with build_raw_client(site.base_url) as client:
            cache = _cache(clock, client)
            assert cache.check("https://mock-json.test/public/page", client) is None


def test_robots_403_fails_closed(clock: FakeClock) -> None:
    from tests.helpers.mock_site import running_site

    with running_site() as site:
        site.static("/robots.txt", status=403, body="denied")
        with build_raw_client(site.base_url) as client:
            cache = _cache(clock, client)
            with pytest.raises(RobotsUnavailableError, match="403"):
                cache.check("https://mock-json.test/series/example", client)


def test_robots_500_fails_closed(clock: FakeClock) -> None:
    from tests.helpers.mock_site import running_site

    with running_site() as site:
        site.static("/robots.txt", status=500, body="boom")
        with build_raw_client(site.base_url) as client:
            cache = _cache(clock, client)
            with pytest.raises(RobotsUnavailableError, match="failing closed"):
                cache.check("https://mock-json.test/series/example", client)


def test_robots_429_raises_rate_limit(clock: FakeClock) -> None:
    from tests.helpers.mock_site import running_site

    with running_site() as site:
        site.static("/robots.txt", status=429, body="slow down", headers={"Retry-After": "7"})
        with build_raw_client(site.base_url) as client:
            cache = _cache(clock, client)
            with pytest.raises(RateLimitedError) as excinfo:
                cache.check("https://mock-json.test/series/example", client)
    assert excinfo.value.retry_after == 7.0


def test_cache_reuses_robots_within_max_age(clock: FakeClock) -> None:
    from tests.helpers.mock_site import running_site

    with running_site() as site:
        site.static("/robots.txt", body=ROBOTS, headers={"Cache-Control": "max-age=600"})
        site.static("/series/example", body="ok")
        with build_raw_client(site.base_url) as client:
            cache = _cache(clock, client)
            cache.check("https://mock-json.test/series/example", client)
            cache.check("https://mock-json.test/series/example", client)
        assert site.hits("/robots.txt") == 1


def test_cache_refreshes_after_expiry(clock: FakeClock) -> None:
    from tests.helpers.mock_site import running_site

    with running_site() as site:
        site.static("/robots.txt", body=ROBOTS, headers={"Cache-Control": "max-age=60"})
        site.static("/series/example", body="ok")
        with build_raw_client(site.base_url) as client:
            cache = _cache(clock, client)
            cache.check("https://mock-json.test/series/example", client)
            clock.advance(61)
            cache.check("https://mock-json.test/series/example", client)
        assert site.hits("/robots.txt") == 2


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("7", 7.0),
        ("0", 0.0),
        (" 12 ", 12.0),
        ("-3", 0.0),
        ("", None),
        (None, None),
        ("not-a-date", None),
    ],
)
def test_retry_after_parsing(value: str | None, expected: float | None) -> None:
    assert parse_retry_after(value) == expected


def test_retry_after_http_date() -> None:
    from datetime import UTC, datetime, timedelta
    from email.utils import format_datetime

    future = datetime.now(UTC) + timedelta(seconds=30)
    parsed = parse_retry_after(format_datetime(future, usegmt=True))
    assert parsed is not None
    assert 25 <= parsed <= 35
