"""Shared compliance-aware HTTP client."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass

import httpx

from manji.config.models import AppConfig
from manji.errors import AccessDeniedError, HTTPError, NetworkError, RateLimitedError
from manji.log import get_logger
from manji.net.challenge import is_challenge, raise_for_challenge
from manji.net.limiter import Clock, DomainLimiter, SystemClock
from manji.net.redaction import Sanitizer
from manji.net.robots import RobotsCache, parse_retry_after

logger = get_logger("net.client")

REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
RETRYABLE_STATUSES = frozenset({500, 502, 504})
MAX_REDIRECTS = 10
DEFAULT_RETRY_AFTER_CAP = 60.0
CHUNK_SIZE = 64 * 1024


@dataclass(frozen=True, slots=True)
class ClientSettings:
    """Network settings sourced from the validated configuration."""

    user_agent: str
    timeout_seconds: float = 30.0
    max_retries: int = 3
    max_redirects: int = MAX_REDIRECTS
    retry_backoff_seconds: float = 0.5
    retry_after_cap_seconds: float = DEFAULT_RETRY_AFTER_CAP
    max_concurrency_per_domain: int = 2
    default_request_delay_seconds: float = 1.5


def domain_of(url: str) -> str:
    return (httpx.URL(url).host or "").lower()


class CompliantClient:
    """One gate for every request: robots.txt, per-domain limits, and halting."""

    def __init__(
        self,
        settings: ClientSettings,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Clock | None = None,
        sanitizer: Sanitizer | None = None,
        limiter: DomainLimiter | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self._clock: Clock = clock or SystemClock()
        self._sanitizer = sanitizer or Sanitizer()
        self._limiter = limiter or DomainLimiter(
            max_concurrency=settings.max_concurrency_per_domain,
            default_delay=settings.default_request_delay_seconds,
            clock=self._clock,
        )
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(settings.timeout_seconds),
            follow_redirects=False,
            headers={"User-Agent": settings.user_agent},
        )
        self._robots = RobotsCache(user_agent=settings.user_agent, clock=self._clock)

    @property
    def limiter(self) -> DomainLimiter:
        return self._limiter

    @property
    def robots(self) -> RobotsCache:
        return self._robots

    @property
    def http(self) -> httpx.Client:
        return self._http

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> CompliantClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
        json: object | None = None,
        content: bytes | None = None,
    ) -> httpx.Response:
        """Perform a compliance-checked request, following redirects manually."""

        current_url = url
        current_method = method
        redirects = 0
        first = True

        while True:
            response = self._request_once(
                current_method,
                current_url,
                headers=headers,
                params=params if first else None,
                data=data if first else None,
                json=json if first else None,
                content=content if first else None,
            )
            first = False

            if response.status_code not in REDIRECT_STATUSES:
                return response

            location = response.headers.get("location")
            if not location:
                response.close()
                raise HTTPError(
                    f"Redirect from {domain_of(current_url)} has no Location header.",
                    status_code=response.status_code,
                )
            redirects += 1
            if redirects > self.settings.max_redirects:
                response.close()
                raise HTTPError(
                    f"More than {self.settings.max_redirects} redirects starting at {url}.",
                    status_code=response.status_code,
                )
            if response.status_code == 303:
                current_method = "GET"
            next_url = str(httpx.URL(current_url).join(location))
            if domain_of(next_url) != domain_of(current_url):
                headers = _strip_cross_origin_credentials(headers)
            current_url = next_url
            response.close()

    def _request_once(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None,
        params: Mapping[str, str] | None,
        data: Mapping[str, str] | None,
        json: object | None,
        content: bytes | None,
    ) -> httpx.Response:
        domain = domain_of(url)
        attempt = 0

        while True:
            self._check_domain(domain, url)
            self._limiter.acquire(domain)
            started = self._clock.monotonic()
            try:
                response = self._http.request(
                    method,
                    url,
                    headers=dict(headers or {}),
                    params=params,
                    data=data,
                    json=json,
                    content=content,
                )
            except httpx.HTTPError as error:
                if attempt < self.settings.max_retries and _is_retryable_transport(error):
                    attempt += 1
                    self._sleep(self._backoff_seconds(attempt))
                    continue
                raise NetworkError(
                    f"Network failure requesting {self._sanitizer.redact_url(url)}: "
                    f"{self._sanitizer.redact_text(str(error))}"
                ) from error
            finally:
                self._limiter.release(domain)

            logger.debug(
                "%s %s -> %s in %.3fs",
                method,
                self._sanitizer.redact_url(url),
                response.status_code,
                self._clock.monotonic() - started,
            )

            status = response.status_code

            if status in (429, 503) and not is_challenge(status, response.headers, response.text):
                retry_after = parse_retry_after(response.headers.get("retry-after"))
                wait = (
                    retry_after if retry_after is not None else self._backoff_seconds(attempt + 1)
                )
                if wait > self.settings.retry_after_cap_seconds:
                    response.close()
                    self._limiter.block(domain, self.settings.retry_after_cap_seconds)
                    raise RateLimitedError(
                        f"{domain} asked to retry after {wait:.0f}s, above the "
                        f"{self.settings.retry_after_cap_seconds:.0f}s cap. Stopping this domain.",
                        retry_after=retry_after,
                    )
                self._limiter.block(domain, wait)
                if attempt < self.settings.max_retries:
                    attempt += 1
                    response.close()
                    self._sleep(wait)
                    continue
                response.close()
                raise RateLimitedError(
                    f"{domain} kept returning HTTP {status} after {attempt} retries.",
                    retry_after=retry_after,
                )

            if status in RETRYABLE_STATUSES and attempt < self.settings.max_retries:
                attempt += 1
                response.close()
                self._sleep(self._backoff_seconds(attempt))
                continue

            if status in (401, 403, 503):
                body = response.text
                headers_snapshot = dict(response.headers)
                response.close()
                if status == 401:
                    raise AccessDeniedError(
                        f"Access denied by {domain} with HTTP 401. "
                        "Verify your credentials; this request was not retried."
                    )
                raise_for_challenge(
                    status_code=status,
                    headers=headers_snapshot,
                    body=body,
                    url=self._sanitizer.redact_url(url),
                    domain=domain,
                )

            if status >= 400:
                detail = f"{domain} returned HTTP {status} for {self._sanitizer.redact_url(url)}."
                response.close()
                raise HTTPError(detail, status_code=status)

            return response

    def _check_domain(self, domain: str, url: str) -> None:
        remaining = self._limiter.blocked_for(domain)
        if remaining > 0:
            raise RateLimitedError(
                f"{domain} is blocked for another {remaining:.1f}s after rate limiting.",
                retry_after=remaining,
            )
        try:
            crawl_delay = self._robots.check(url, self._fetch_robots)
        except RateLimitedError as error:
            if error.retry_after:
                self._limiter.block(
                    domain, min(error.retry_after, self.settings.retry_after_cap_seconds)
                )
            raise
        if crawl_delay is not None:
            self._limiter.set_crawl_delay(domain, crawl_delay)

    def _fetch_robots(self, robots_url: str) -> httpx.Response:
        """Fetch robots.txt through the same per-domain limiter."""

        domain = domain_of(robots_url)
        self._limiter.acquire(domain)
        try:
            return self._http.get(robots_url)
        finally:
            self._limiter.release(domain)

    def _backoff_seconds(self, attempt: int) -> float:
        return float(self.settings.retry_backoff_seconds * (2 ** max(0, attempt - 1)))

    def _sleep(self, seconds: float) -> None:
        if seconds > 0:
            self._clock.sleep(seconds)

    def get(self, url: str, **kwargs: object) -> httpx.Response:
        return self.request("GET", url, **kwargs)  # type: ignore[arg-type]

    def get_text(self, url: str, **kwargs: object) -> str:
        response = self.get(url, **kwargs)
        try:
            return response.text
        finally:
            response.close()

    def get_json(self, url: str, **kwargs: object) -> object:
        response = self.get(url, **kwargs)
        try:
            return response.json()
        finally:
            response.close()

    @contextmanager
    def stream(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        method: str = "GET",
    ) -> Iterator[httpx.Response]:
        """Stream a response through the same limiter and robots checks."""

        domain = domain_of(url)
        self._check_domain(domain, url)
        self._limiter.acquire(domain)
        try:
            request = self._http.build_request(method, url, headers=dict(headers or {}))
            response = self._http.send(request, stream=True)
            try:
                yield response
            finally:
                response.close()
        finally:
            self._limiter.release(domain)


def _strip_cross_origin_credentials(
    headers: Mapping[str, str] | None,
) -> dict[str, str] | None:
    """Drop credentials before following a redirect to a different host."""

    if headers is None:
        return None
    sensitive = {"authorization", "proxy-authorization", "cookie"}
    return {key: value for key, value in headers.items() if key.lower() not in sensitive}


def _is_retryable_transport(error: httpx.HTTPError) -> bool:
    return isinstance(
        error,
        (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.RemoteProtocolError,
            httpx.WriteError,
            httpx.PoolTimeout,
        ),
    )


def settings_from_config(config: AppConfig) -> ClientSettings:
    """Build client settings from the validated application configuration."""

    network = config.network
    rate_limits = config.rate_limits
    return ClientSettings(
        user_agent=network.user_agent,
        timeout_seconds=network.timeout_seconds,
        max_retries=network.max_retries,
        max_concurrency_per_domain=rate_limits.max_concurrent_requests_per_site,
        default_request_delay_seconds=rate_limits.default_request_delay_seconds,
    )
