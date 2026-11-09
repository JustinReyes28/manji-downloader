from __future__ import annotations

import logging

import pytest

from manji.net.redaction import REDACTED, RedactionFilter, Sanitizer, sanitize_mapping

pytestmark = pytest.mark.unit


def test_header_redaction() -> None:
    sanitizer = Sanitizer()
    headers = {
        "Authorization": "Bearer abc123",
        "Cookie": "session=abc",
        "Set-Cookie": "session=abc",
        "Proxy-Authorization": "Basic xyz",
        "Accept": "application/json",
    }
    assert sanitizer.redact_headers(headers) == {
        "Authorization": REDACTED,
        "Cookie": REDACTED,
        "Set-Cookie": REDACTED,
        "Proxy-Authorization": REDACTED,
        "Accept": "application/json",
    }


@pytest.mark.parametrize(
    "key",
    ["token", "sig", "signature", "auth", "key", "api_key", "apikey", "password", "session"],
)
def test_query_key_redaction(key: str) -> None:
    sanitizer = Sanitizer()
    redacted = sanitizer.redact_url(f"https://example.test/media?{key}=super-secret&page=2")
    assert f"{key}={REDACTED}" in redacted
    assert "super-secret" not in redacted
    assert "page=2" in redacted


def test_url_userinfo_password_redacted() -> None:
    sanitizer = Sanitizer()
    redacted = sanitizer.redact_url("https://user:hunter2@example.test/path")
    assert "hunter2" not in redacted
    assert f"user:{REDACTED}@" in redacted


def test_text_redaction_of_bearer_tokens() -> None:
    sanitizer = Sanitizer()
    text = "request failed with Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig"
    redacted = sanitizer.redact_text(text)
    assert "eyJhbGciOiJIUzI1NiJ9" not in redacted
    assert REDACTED in redacted


def test_text_redaction_of_embedded_urls() -> None:
    sanitizer = Sanitizer()
    text = "GET https://example.test/file?token=abc123&x=1 failed"
    redacted = sanitizer.redact_text(text)
    assert "abc123" not in redacted
    assert "x=1" in redacted


def test_text_redaction_of_bare_query_pairs() -> None:
    sanitizer = Sanitizer()
    redacted = sanitizer.redact_text("redirecting to /media?token=abc123")
    assert "abc123" not in redacted


def test_logging_filter_redacts_message_and_args(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("manji.test.redaction")
    logger.setLevel(logging.DEBUG)
    logger.addFilter(RedactionFilter())
    logger.propagate = True

    with caplog.at_level(logging.DEBUG, logger="manji.test.redaction"):
        logger.info("fetching %s", "https://example.test/a?token=abcdef")
        logger.info("Authorization: Bearer supersecrettoken")

    combined = "\n".join(record.getMessage() for record in caplog.records)
    assert "abcdef" not in combined
    assert "supersecrettoken" not in combined
    assert REDACTED in combined


def test_sanitize_mapping_masks_in_place() -> None:
    headers = {"cookie": "a=b", "accept": "text/html"}
    result = sanitize_mapping(headers)
    assert result["cookie"] == REDACTED
    assert result["accept"] == "text/html"


def test_case_insensitive_header_matching() -> None:
    sanitizer = Sanitizer()
    assert sanitizer.redact_headers({"AUTHORIZATION": "x"}) == {"AUTHORIZATION": REDACTED}


def test_invalid_url_is_returned_unchanged() -> None:
    sanitizer = Sanitizer()
    assert sanitizer.redact_url("not a url") == "not a url"
