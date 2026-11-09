from __future__ import annotations

from datetime import UTC, datetime

from manji.adapters import AuthMode, SiteMetadata
from manji.domain import MediaItem, MediaVariant, SeriesCatalog


def make_metadata(
    site_id: str = "mock-json",
    domains: tuple[str, ...] = ("mock-json.test",),
) -> SiteMetadata:
    return SiteMetadata(
        id=site_id,
        display_name=f"Mock {site_id}",
        domains=domains,
        default_min_request_delay_seconds=1.5,
        auth_mode=AuthMode.NONE,
        url_patterns=(r"^https://mock-json\.test/series/",),
    )


class StubAdapter:
    def __init__(self, metadata: SiteMetadata, *, handles: str = "") -> None:
        self._metadata = metadata
        self._handles = handles or metadata.domains[0]

    def get_site_metadata(self) -> SiteMetadata:
        return self._metadata

    def can_handle(self, url: str) -> bool:
        return self._handles in url

    def validate_access(self, target: object) -> None:
        return None

    def resolve_series_catalog(self, series_url: str) -> SeriesCatalog:
        return SeriesCatalog(
            title="Example Series",
            site_id=self._metadata.id,
            source_url=series_url,
            episodes=(MediaItem(id="e1", number=1, title="Episode 1", url="https://x/1"),),
        )

    def resolve_episode_variants(self, item: MediaItem) -> tuple[MediaVariant, ...]:
        return (
            MediaVariant(
                id=f"{item.id}-1080",
                quality="1080p",
                container="mkv",
                size_bytes=100,
                uploaded_at=datetime(2024, 1, 1, tzinfo=UTC),
                download_count=1,
                url=f"{item.url}/1080",
            ),
        )
