"""Credential redaction for logs, errors, and exports."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, MutableMapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REDACTED = "REDACTED"

SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
    }
)

SENSITIVE_QUERY_KEYS = frozenset(
    {
        "token",
        "sig",
        "signature",
        "auth",
        "key",
        "api_key",
        "apikey",
        "password",
        "session",
    }
)

_BEARER_PATTERN = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+")


class Sanitizer:
    """Mask credentials in headers, URLs, and free text."""

    def __init__(
        self,
        *,
        headers: frozenset[str] = SENSITIVE_HEADERS,
        query_keys: frozenset[str] = SENSITIVE_QUERY_KEYS,
    ) -> None:
        self.headers = headers
        self.query_keys = query_keys

    def redact_headers(self, headers: Mapping[str, str]) -> dict[str, str]:
        return {
            name: REDACTED if name.lower() in self.headers else value
            for name, value in headers.items()
        }

    def redact_url(self, url: str) -> str:
        try:
            parts = urlsplit(url)
        except ValueError:
            return url

        query = urlencode(
            [
                (key, REDACTED if key.lower() in self.query_keys else value)
                for key, value in parse_qsl(parts.query, keep_blank_values=True)
            ]
        )

        netloc = parts.netloc
        if "@" in netloc:
            userinfo, host = netloc.rsplit("@", 1)
            if ":" in userinfo:
                user, _ = userinfo.split(":", 1)
                netloc = f"{user}:{REDACTED}@{host}"
            else:
                netloc = f"{REDACTED}@{host}"

        return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))

    def redact_text(self, text: str) -> str:
        redacted = _BEARER_PATTERN.sub(lambda match: f"{match.group(1)} {REDACTED}", text)

        def mask_url(match: re.Match[str]) -> str:
            return self.redact_url(match.group(0))

        redacted = re.sub(r"https?://[^\s'\"<>]+", mask_url, redacted)
        for key in sorted(self.query_keys):
            redacted = re.sub(
                rf"(?i)([?&]{re.escape(key)}=)[^&\s'\"]+",
                rf"\1{REDACTED}",
                redacted,
            )
        return redacted


DEFAULT_SANITIZER = Sanitizer()


class RedactionFilter(logging.Filter):
    """Logging filter that scrubs credentials from messages and arguments."""

    def __init__(self, sanitizer: Sanitizer | None = None, name: str = "") -> None:
        super().__init__(name)
        self.sanitizer = sanitizer or DEFAULT_SANITIZER

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.sanitizer.redact_text(record.msg)
        if record.args:
            record.args = _sanitize_args(record.args, self.sanitizer)  # type: ignore[assignment]
        if record.exc_text:
            record.exc_text = self.sanitizer.redact_text(record.exc_text)
        return True


def _sanitize_args(args: object, sanitizer: Sanitizer) -> object:
    if isinstance(args, Mapping):
        return {
            key: sanitizer.redact_text(value) if isinstance(value, str) else value
            for key, value in args.items()
        }
    if isinstance(args, tuple):
        return tuple(
            sanitizer.redact_text(item) if isinstance(item, str) else item for item in args
        )
    if isinstance(args, str):
        return sanitizer.redact_text(args)
    return args


def sanitize_mapping(
    mapping: MutableMapping[str, str], sanitizer: Sanitizer | None = None
) -> MutableMapping[str, str]:
    """Redact header-like mappings in place and return them."""

    active = sanitizer or DEFAULT_SANITIZER
    for key in list(mapping):
        if key.lower() in active.headers:
            mapping[key] = REDACTED
    return mapping
