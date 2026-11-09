"""Test transports that keep every request on loopback."""

from __future__ import annotations

import ipaddress
from collections.abc import Callable
from urllib.parse import urlsplit

import httpx

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

_SHARED_TRANSPORT: httpx.BaseTransport | None = None


def shared_transport() -> httpx.BaseTransport:
    """Reuse one pooled transport so tests do not rebuild TLS state repeatedly."""

    global _SHARED_TRANSPORT
    if _SHARED_TRANSPORT is None:
        _SHARED_TRANSPORT = LoopbackOnlyTransport(httpx.HTTPTransport())
    return _SHARED_TRANSPORT


def is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    if host.lower() in LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class LoopbackOnlyTransport(httpx.BaseTransport):
    """Reject any request whose connection target is not loopback."""

    def __init__(self, inner: httpx.BaseTransport) -> None:
        self._inner = inner
        self.blocked: list[str] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if not is_loopback_host(host):
            self.blocked.append(str(request.url))
            raise httpx.ConnectError(
                f"Blocked non-loopback request to {host!r}; tests must stay offline.",
                request=request,
            )
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()


class HostRewriteTransport(httpx.BaseTransport):
    """Map known synthetic ``*.test`` hosts onto a local mock server."""

    def __init__(
        self,
        base_url: str,
        inner: httpx.BaseTransport | None = None,
        *,
        hosts: frozenset[str] | set[str] | None = None,
    ) -> None:
        self._base_url = httpx.URL(base_url)
        self._inner = inner or shared_transport()
        self._hosts = frozenset(
            host.lower() for host in (hosts or {"mock-json.test", "mock-html.test"})
        )

    def rewrite(self, url: httpx.URL) -> httpx.URL:
        host = (url.host or "").lower()
        if host not in self._hosts:
            return url
        return url.copy_with(
            scheme=self._base_url.scheme,
            host=self._base_url.host,
            port=self._base_url.port,
            raw_path=url.raw_path,
        )

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        original = request.url
        rewritten = self.rewrite(original)
        request.url = rewritten
        if rewritten.host is not None and rewritten.host != original.host:
            request.headers["host"] = self._base_url.netloc.decode("ascii")
        response = self._inner.handle_request(request)
        response.request = request
        return response

    def close(self) -> None:
        # The shared transport outlives individual test clients.
        return None


def synthetic_host(site: str) -> str:
    """Return the canonical synthetic host for a mock site identifier."""

    return f"{site}.test"


def url_host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


Resolver = Callable[[str], str]
