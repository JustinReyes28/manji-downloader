from __future__ import annotations

import pytest

from manji.adapters import AuthMode, SiteMetadata
from manji.adapters.registry import AdapterRegistry
from manji.errors import UnsupportedSiteError
from tests.helpers import StubAdapter, make_metadata

pytestmark = pytest.mark.unit


def test_register_and_route() -> None:
    registry = AdapterRegistry()
    adapter = StubAdapter(make_metadata())
    registry.register(adapter)
    assert registry.resolve_for_url("https://mock-json.test/series/1") is adapter


def test_duplicate_registration_rejected() -> None:
    registry = AdapterRegistry()
    registry.register(StubAdapter(make_metadata()))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(StubAdapter(make_metadata()))


def test_empty_id_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        SiteMetadata(
            id="",
            display_name="Empty",
            domains=("example.test",),
            default_min_request_delay_seconds=1.0,
            auth_mode=AuthMode.NONE,
        )


def test_metadata_requires_domain() -> None:
    with pytest.raises(ValueError, match="at least one domain"):
        SiteMetadata(
            id="no-domain",
            display_name="No Domain",
            domains=(),
            default_min_request_delay_seconds=1.0,
            auth_mode=AuthMode.NONE,
        )


def test_negative_delay_rejected() -> None:
    with pytest.raises(ValueError, match="negative request delay"):
        SiteMetadata(
            id="neg",
            display_name="Negative",
            domains=("example.test",),
            default_min_request_delay_seconds=-1.0,
            auth_mode=AuthMode.NONE,
        )


def test_unsupported_url() -> None:
    registry = AdapterRegistry()
    registry.register(StubAdapter(make_metadata()))
    with pytest.raises(UnsupportedSiteError):
        registry.resolve_for_url("https://other.test/series/1")


@pytest.mark.parametrize("url", ["ftp://mock-json.test/x", "not-a-url", "https://"])
def test_invalid_urls_rejected(url: str) -> None:
    registry = AdapterRegistry()
    registry.register(StubAdapter(make_metadata()))
    with pytest.raises(UnsupportedSiteError):
        registry.resolve_for_url(url)


def test_listing_is_deterministic() -> None:
    registry = AdapterRegistry()
    registry.register(StubAdapter(make_metadata("zeta", ("zeta.test",))))
    registry.register(StubAdapter(make_metadata("alpha", ("alpha.test",))))
    ids = [meta.id for meta in registry.list_supported_sites()]
    assert ids == ["alpha", "zeta"]


def test_len_and_get() -> None:
    registry = AdapterRegistry()
    adapter = StubAdapter(make_metadata())
    assert len(registry) == 0
    registry.register(adapter)
    assert len(registry) == 1
    assert registry.get("mock-json") is adapter
    assert registry.get("missing") is None
    registry.clear()
    assert len(registry) == 0
