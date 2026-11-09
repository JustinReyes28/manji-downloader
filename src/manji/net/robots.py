"""robots.txt fetching, caching, and enforcement."""

from __future__ import annotations

import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
from protego import Protego

from manji.errors import RateLimitedError, RobotsDisallowedError, RobotsUnavailableError
from manji.net.limiter import Clock, SystemClock

DEFAULT_CACHE_SECONDS = 3600.0
_MAX_CACHE_SECONDS = 86400.0
_CACHE_CONTROL = re.compile(r"max-age\s*=\s*(\d+)", re.IGNORECASE)

RobotsFetcher = Callable[[str], httpx.Response]


@dataclass(slots=True)
class _CacheEntry:
    parser: Protego | None
    expires_at: float
    crawl_delay: float | None


class RobotsCache:
    """Per scheme+host robots.txt cache with fail-closed semantics."""

    def __init__(
        self,
        *,
        user_agent: str,
        clock: Clock | None = None,
        cache_seconds: float = DEFAULT_CACHE_SECONDS,
    ) -> None:
        self.user_agent = user_agent
        self._clock: Clock = clock or SystemClock()
        self._cache_seconds = cache_seconds
        self._entries: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()

    def _origin_key(self, url: str) -> tuple[str, str]:
        parts = urlsplit(url)
        scheme = parts.scheme.lower() or "https"
        host = parts.hostname or ""
        if not host:
            raise RobotsUnavailableError(f"Cannot determine a host for {url!r}.")
        return f"{scheme}://{host}", f"{scheme}://{host}/robots.txt"

    def _cache_ttl(self, response: httpx.Response) -> float:
        cache_control = response.headers.get("cache-control", "")
        match = _CACHE_CONTROL.search(cache_control)
        if match:
            return min(float(match.group(1)), _MAX_CACHE_SECONDS)
        return self._cache_seconds

    def load(self, url: str, client: httpx.Client | RobotsFetcher) -> _CacheEntry:
        """Return the cached parser for a URL, fetching robots.txt when needed."""

        origin, robots_url = self._origin_key(url)
        now = self._clock.monotonic()
        with self._lock:
            entry = self._entries.get(origin)
        if entry is not None and entry.expires_at > now:
            return entry

        try:
            if isinstance(client, httpx.Client):
                response = client.get(robots_url, headers={"User-Agent": self.user_agent})
            else:
                response = client(robots_url)
        except httpx.HTTPError as error:
            raise RobotsUnavailableError(
                f"Could not fetch robots.txt from {robots_url}: {error}. Failing closed."
            ) from error
        status = response.status_code

        if status == 200:
            parser = Protego.parse(response.text)
            crawl_delay = self._crawl_delay(parser)
            entry = _CacheEntry(parser, now + self._cache_ttl(response), crawl_delay)
        elif status in (404, 410):
            entry = _CacheEntry(None, now + self._cache_seconds, None)
        elif status in (401, 403):
            raise RobotsUnavailableError(
                f"robots.txt at {robots_url} returned {status}; access is denied."
            )
        elif status == 429:
            retry_after = parse_retry_after(response.headers.get("retry-after"))
            raise RateLimitedError(
                f"robots.txt at {robots_url} is rate limited.", retry_after=retry_after
            )
        else:
            raise RobotsUnavailableError(
                f"robots.txt at {robots_url} returned {status}; failing closed."
            )

        with self._lock:
            self._entries[origin] = entry
        return entry

    def _crawl_delay(self, parser: Protego) -> float | None:
        for agent in (self.user_agent, "*"):
            delay = parser.crawl_delay(agent)
            if delay is not None:
                return float(delay)
        return None

    def check(self, url: str, client: httpx.Client | RobotsFetcher) -> float | None:
        """Ensure the URL is allowed; return its Crawl-delay when published."""

        entry = self.load(url, client)
        if entry.parser is None:
            return entry.crawl_delay
        allowed = entry.parser.can_fetch(url, self.user_agent)
        if not allowed and self.user_agent != "*":
            allowed = entry.parser.can_fetch(url, "*")
        if not allowed:
            raise RobotsDisallowedError(
                f"robots.txt at {url} disallows this request for user agent "
                f"{self.user_agent!r}. The operation was aborted."
            )
        return entry.crawl_delay

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


def parse_retry_after(value: str | None) -> float | None:
    """Parse ``Retry-After`` as seconds or an HTTP date."""

    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        seconds = float(text)
    except ValueError:
        from email.utils import parsedate_to_datetime

        try:
            target = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
        if target is None:
            return None
        from datetime import UTC, datetime

        if target.tzinfo is None:
            target = target.replace(tzinfo=UTC)
        return max(0.0, (target - datetime.now(UTC)).total_seconds())
    return max(0.0, seconds)
