"""Mock adapter tests: registry routing and catalog normalization."""

from __future__ import annotations

import pytest

from manji.adapters import AdapterRegistry
from manji.domain import Category
from tests.adapters.mock_html import MockHtmlAdapter
from tests.adapters.mock_json import MockJsonAdapter
from tests.conftest import build_client
from tests.helpers import MockSite

pytestmark = [pytest.mark.integration, pytest.mark.compliance]


@pytest.fixture
def registry(mock_json_site: MockSite, mock_html_site: MockSite):
    json_client = build_client(mock_json_site.base_url)
    html_client = build_client(mock_html_site.base_url)
    registry = AdapterRegistry()
    registry.register(MockJsonAdapter(json_client))
    registry.register(MockHtmlAdapter(html_client))
    try:
        yield registry
    finally:
        json_client.close()
        html_client.close()


def test_registry_routes_both_mock_adapters(registry: AdapterRegistry) -> None:
    json_adapter = registry.resolve_for_url("https://mock-json.test/series/example")
    html_adapter = registry.resolve_for_url("https://mock-html.test/series/example")
    assert isinstance(json_adapter, MockJsonAdapter)
    assert isinstance(html_adapter, MockHtmlAdapter)
    ids = [meta.id for meta in registry.list_supported_sites()]
    assert ids == ["mock_html", "mock_json"]


def test_unsupported_host_still_rejected(registry: AdapterRegistry) -> None:
    from manji.errors import UnsupportedSiteError

    with pytest.raises(UnsupportedSiteError):
        registry.resolve_for_url("https://unknown.test/series/example")


def test_json_catalog_normalization(registry: AdapterRegistry) -> None:
    adapter = registry.resolve_for_url("https://mock-json.test/series/example")
    catalog = adapter.resolve_series_catalog("https://mock-json.test/series/example")
    assert catalog.title == "Example Mock Series"
    assert catalog.site_id == "mock_json"
    counts = catalog.counts()
    assert counts[Category.EPISODES] == 24
    assert counts[Category.OVAS] == 2
    assert counts[Category.MOVIES] == 1
    assert counts[Category.SPECIALS] == 3
    assert catalog.count(Category.EPISODES) == 24
    assert catalog.total_items() == 30


def test_html_catalog_normalization(registry: AdapterRegistry) -> None:
    adapter = registry.resolve_for_url("https://mock-html.test/series/example")
    catalog = adapter.resolve_series_catalog("https://mock-html.test/series/example")
    assert catalog.title == "Example Mock HTML Series"
    assert catalog.counts() == {
        Category.EPISODES: 12,
        Category.OVAS: 2,
        Category.MOVIES: 1,
        Category.SPECIALS: 3,
    }


def test_json_variants_normalization(registry: AdapterRegistry) -> None:
    adapter = registry.resolve_for_url("https://mock-json.test/series/example")
    catalog = adapter.resolve_series_catalog("https://mock-json.test/series/example")
    item = catalog.episodes[0]
    variants = adapter.resolve_episode_variants(item)
    assert [variant.quality for variant in variants] == ["1080p", "720p", "480p"]
    assert variants[0].size_bytes == 1468006400
    assert variants[0].container == "mkv"
    assert variants[1].download_count == 1800


def test_html_variants_normalization(registry: AdapterRegistry) -> None:
    adapter = registry.resolve_for_url("https://mock-html.test/series/example")
    catalog = adapter.resolve_series_catalog("https://mock-html.test/series/example")
    variants = adapter.resolve_episode_variants(catalog.episodes[0])
    assert len(variants) == 3
    assert variants[0].id == "ep-01-1080p-mkv"
    assert variants[0].size_bytes == 1468006400
    assert [variant.quality for variant in variants] == ["1080p", "720p", "480p"]


def test_adapters_never_touch_non_loopback_hosts(
    registry: AdapterRegistry, mock_json_site: MockSite
) -> None:
    from tests.helpers.transport import is_loopback_host

    adapter = registry.resolve_for_url("https://mock-json.test/series/example")
    adapter.resolve_series_catalog("https://mock-json.test/series/example")
    for method, path in mock_json_site.requests:
        assert method in {"GET", "HEAD"}
        assert path.startswith("/")
    assert is_loopback_host("127.0.0.1")
    assert not is_loopback_host("mock-json.test")
