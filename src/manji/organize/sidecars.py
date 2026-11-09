"""Metadata sidecar writers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from manji.domain import Category, MediaItem, MediaVariant, SeriesCatalog
from manji.fs import atomic_write_json, atomic_write_text
from manji.net.redaction import Sanitizer

SIDECAR_VERSION = "1.0"


def _timestamp(moment: datetime | None) -> str:
    value = moment or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def series_payload(
    catalog: SeriesCatalog,
    *,
    sanitizer: Sanitizer | None = None,
    retrieved_at: datetime | None = None,
) -> dict[str, object]:
    active = sanitizer or Sanitizer()
    return {
        "version": SIDECAR_VERSION,
        "generated_at": _timestamp(retrieved_at),
        "adapter": catalog.site_id,
        "title": catalog.title,
        "source_url": active.redact_url(catalog.source_url),
        "counts": {category.value: catalog.count(category) for category in Category},
    }


def episode_payload(
    category: Category,
    item: MediaItem,
    variant: MediaVariant,
    *,
    site_id: str,
    source_url: str,
    sanitizer: Sanitizer | None = None,
    retrieved_at: datetime | None = None,
) -> dict[str, object]:
    active = sanitizer or Sanitizer()
    return {
        "version": SIDECAR_VERSION,
        "generated_at": _timestamp(retrieved_at),
        "adapter": site_id,
        "category": category.value,
        "episode_number": item.number,
        "title": item.title,
        "source_url": active.redact_url(source_url),
        "variant": {
            "id": variant.id,
            "quality": variant.quality,
            "container": variant.container,
            "size_bytes": variant.size_bytes,
            "uploaded_at": variant.uploaded_at.isoformat() if variant.uploaded_at else None,
            "download_count": variant.download_count,
            "url": active.redact_url(variant.url),
        },
    }


def write_series_sidecar(
    directory: Path | str,
    catalog: SeriesCatalog,
    *,
    filename: str = "series.json",
    sanitizer: Sanitizer | None = None,
    retrieved_at: datetime | None = None,
) -> Path:
    target = Path(directory) / filename
    payload = series_payload(catalog, sanitizer=sanitizer, retrieved_at=retrieved_at)
    return atomic_write_json(target, payload)


def write_episode_sidecar(
    destination: Path | str,
    category: Category,
    item: MediaItem,
    variant: MediaVariant,
    *,
    site_id: str,
    source_url: str,
    filename: str = "episode.yaml",
    sanitizer: Sanitizer | None = None,
    retrieved_at: datetime | None = None,
) -> Path:
    target = Path(destination) / filename
    payload = episode_payload(
        category,
        item,
        variant,
        site_id=site_id,
        source_url=source_url,
        sanitizer=sanitizer,
        retrieved_at=retrieved_at,
    )
    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    return atomic_write_text(target, text)
