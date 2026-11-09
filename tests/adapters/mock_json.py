"""Synthetic JSON catalog adapter used only by tests."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from manji.adapters.base import AuthMode, SiteMetadata, Target
from manji.domain import MediaItem, MediaVariant, SeriesCatalog
from manji.errors import HTTPError
from manji.net.client import CompliantClient

SITE_ID = "mock_json"
HOST = "mock-json.test"


class MockJsonAdapter:
    def __init__(self, client: CompliantClient) -> None:
        self.client = client

    def get_site_metadata(self) -> SiteMetadata:
        return SiteMetadata(
            id=SITE_ID,
            display_name="Mock JSON Site",
            domains=(HOST,),
            default_min_request_delay_seconds=1.0,
            auth_mode=AuthMode.NONE,
            url_patterns=(rf"^https://{HOST}/series/",),
        )

    def can_handle(self, url: str) -> bool:
        parts = urlsplit(url)
        return (parts.hostname or "").lower() == HOST and parts.path.startswith("/series/")

    def validate_access(self, target: Target) -> None:
        return None

    def resolve_series_catalog(self, series_url: str) -> SeriesCatalog:
        payload = self.client.get_json(series_url)
        data = _as_mapping(payload, "catalog")
        series = _as_mapping(data.get("series"), "series")
        return SeriesCatalog(
            title=_as_text(series.get("title"), "title"),
            site_id=SITE_ID,
            source_url=series_url,
            episodes=_items(data.get("episodes"), "episodes"),
            ovas=_items(data.get("ovas"), "ovas"),
            movies=_items(data.get("movies"), "movies"),
            specials=_items(data.get("specials"), "specials"),
        )

    def resolve_episode_variants(self, item: MediaItem) -> tuple[MediaVariant, ...]:
        payload = self.client.get_json(item.url)
        data = _as_mapping(payload, "variant payload")
        raw_variants = data.get("variants")
        if not isinstance(raw_variants, list):
            raise HTTPError(f"Variant payload for {item.id} has no variants list.")
        variants: list[MediaVariant] = []
        for raw in raw_variants:
            variant = _as_mapping(raw, "variant")
            uploaded = variant.get("uploaded_at")
            variants.append(
                MediaVariant(
                    id=_as_text(variant.get("id"), "id"),
                    quality=_as_text(variant.get("quality"), "quality"),
                    container=_as_text(variant.get("container"), "container"),
                    size_bytes=int(_as_text(variant.get("size_bytes"), "size_bytes")),
                    uploaded_at=_parse_datetime(uploaded),
                    download_count=int(_as_text(variant.get("download_count"), "download_count")),
                    url=_as_text(variant.get("url"), "url"),
                )
            )
        return tuple(variants)


def _as_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HTTPError(f"Malformed mock JSON {label}.")
    return value


def _as_text(value: object, label: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    raise HTTPError(f"Malformed mock JSON field {label}.")


def _items(value: object, label: str) -> tuple[MediaItem, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise HTTPError(f"Malformed mock JSON category {label}.")
    items = []
    for raw in value:
        entry = _as_mapping(raw, label)
        items.append(
            MediaItem(
                id=_as_text(entry.get("id"), "id"),
                number=int(_as_text(entry.get("number"), "number")),
                title=_as_text(entry.get("title"), "title"),
                url=_as_text(entry.get("url"), "url"),
            )
        )
    return tuple(items)


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
