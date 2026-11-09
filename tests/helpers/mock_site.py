"""Local mock site harness backed by a stdlib ThreadingHTTPServer."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

ResponseSpec = tuple[int, dict[str, str], bytes]
Handler = Callable[[str, str], ResponseSpec]


def _apply_range(
    range_header: str, payload: bytes, headers: dict[str, str], *, honour: bool = True
) -> ResponseSpec:
    """Honour a simple ``bytes=start-`` Range request, mirroring real servers."""

    spec = range_header.removeprefix("bytes=").split(",", 1)[0].strip()
    if not honour:
        return 200, headers, payload
    start_text, _, end_text = spec.partition("-")
    try:
        start = int(start_text) if start_text else 0
        end = int(end_text) if end_text else len(payload) - 1
    except ValueError:
        return 200, headers, payload
    total = len(payload)
    if start >= total:
        headers = dict(headers)
        headers["Content-Range"] = f"bytes */{total}"
        return 416, headers, b""
    end = min(end, total - 1)
    body = payload[start : end + 1]
    headers = dict(headers)
    headers["Content-Range"] = f"bytes {start}-{end}/{total}"
    headers["Accept-Ranges"] = "bytes"
    return 206, headers, body


@dataclass
class Route:
    handler: Handler
    hits: int = 0


@dataclass
class MockSite:
    """A loopback HTTP server that serves synthetic routes for a mock site."""

    routes: dict[str, Route] = field(default_factory=dict)
    requests: list[tuple[str, str]] = field(default_factory=list)
    _server: ThreadingHTTPServer | None = None
    _thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError("MockSite.start() has not been called.")
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def route(self, path: str, handler: Handler) -> None:
        self.routes[path] = Route(handler)

    def static(
        self,
        path: str,
        *,
        status: int = 200,
        body: str | bytes = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        payload = body.encode("utf-8") if isinstance(body, str) else body
        response_headers = dict(headers or {})

        def handler(_method: str, _path: str) -> ResponseSpec:
            return status, response_headers, payload

        self.route(path, handler)

    def json(self, path: str, payload: object, *, status: int = 200) -> None:
        self.static(
            path,
            status=status,
            body=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def hits(self, path: str) -> int:
        route = self.routes.get(path)
        return 0 if route is None else route.hits

    def total_requests(self) -> int:
        return len(self.requests)

    def start(self) -> MockSite:
        outer = self

        class _Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args: Any) -> None:
                return

            def _serve(self, method: str) -> None:
                parsed = urlsplit(self.path)
                path = parsed.path
                outer.requests.append((method, self.path))
                route = outer.routes.get(path)
                if route is None:
                    body = b"not found"
                    self.send_response(404)
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                route.hits += 1
                status, headers, payload = route.handler(method, self.path)
                headers = {
                    key: value
                    for key, value in headers.items()
                    if key.lower() not in {"content-length", "content-range"}
                }
                range_header = self.headers.get("Range", "")
                if status == 200 and range_header.startswith("bytes=") and payload:
                    status, headers, payload = _apply_range(range_header, payload, headers)
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if method != "HEAD":
                    self.wfile.write(payload)

            def do_GET(self) -> None:
                self._serve("GET")

            def do_HEAD(self) -> None:
                self._serve("HEAD")

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(
            target=lambda: self._server.serve_forever(poll_interval=0.01), daemon=True
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None


@contextmanager
def running_site() -> Iterator[MockSite]:
    site = MockSite().start()
    try:
        yield site
    finally:
        site.stop()
