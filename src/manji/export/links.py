"""`links.txt` and `links-manifest.json` export."""

from __future__ import annotations

import json
import warnings
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from manji.domain import Category, MediaItem, MediaVariant, SeriesCatalog
from manji.errors import SelectionError
from manji.fs import atomic_write_text
from manji.net.redaction import SENSITIVE_QUERY_KEYS
from manji.organize.filenames import FilenameContext, render_relative_path

MANIFEST_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class SelectedVariant:
    """One resolved download target in episode order."""

    category: Category
    item: MediaItem
    variant: MediaVariant


def ordered_selection(selection: Iterable[SelectedVariant]) -> tuple[SelectedVariant, ...]:
    """Sort by category order, then item number, then variant ID for determinism."""

    return tuple(
        sorted(
            selection,
            key=lambda entry: (
                _category_index(entry.category),
                entry.item.number,
                entry.variant.id,
            ),
        )
    )


def _category_index(category: Category) -> int:
    from manji.domain import CATEGORY_ORDER

    return CATEGORY_ORDER.index(category)


def sensitive_query_warnings(urls: Iterable[str]) -> tuple[str, ...]:
    """Return warnings for URLs that carry token-like query parameters."""

    from urllib.parse import parse_qsl, urlsplit

    messages: list[str] = []
    for url in urls:
        try:
            query = urlsplit(url).query
        except ValueError:
            continue
        risky = sorted(
            {
                key
                for key, _ in parse_qsl(query, keep_blank_values=True)
                if key.lower() in SENSITIVE_QUERY_KEYS
            }
        )
        if risky:
            messages.append(
                f"URL contains sensitive query parameter(s) ({', '.join(risky)}). "
                "The link was kept exactly as resolved so it continues to work; "
                "do not share this file with anyone."
            )
    return tuple(dict.fromkeys(messages))


def build_manifest(
    catalog: SeriesCatalog,
    selection: Sequence[SelectedVariant],
    template: str,
    *,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    moment = (generated_at or datetime.now(UTC)).astimezone(UTC)
    entries = []
    for entry in ordered_selection(selection):
        context = FilenameContext.build(catalog, entry.category, entry.item, entry.variant)
        entries.append(
            {
                "url": entry.variant.url,
                "filename": render_relative_path(template, context),
            }
        )
    return {
        "version": MANIFEST_VERSION,
        "generated_at": moment.isoformat().replace("+00:00", "Z"),
        "series": {
            "title": catalog.title,
            "site_id": catalog.site_id,
            "source_url": catalog.source_url,
        },
        "entries": entries,
    }


def build_links_text(selection: Sequence[SelectedVariant]) -> str:
    if not selection:
        raise SelectionError("No items were selected, so no links were exported.")
    return "".join(f"{entry.variant.url}\n" for entry in ordered_selection(selection))


def write_links_file(path: Path | str, selection: Sequence[SelectedVariant]) -> Path:
    return atomic_write_text(path, build_links_text(selection))


def write_manifest(
    path: Path | str,
    catalog: SeriesCatalog,
    selection: Sequence[SelectedVariant],
    template: str,
    *,
    generated_at: datetime | None = None,
) -> Path:
    payload = build_manifest(catalog, selection, template, generated_at=generated_at)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    return atomic_write_text(path, text)


def export_links(
    catalog: SeriesCatalog,
    selection: Iterable[SelectedVariant],
    *,
    links_path: Path | str,
    template: str,
    manifest_path: Path | str | None = None,
    generated_at: datetime | None = None,
) -> tuple[Path, Path | None, tuple[str, ...]]:
    """Write ``links.txt`` and optionally the manifest; return paths and warnings."""

    ordered = ordered_selection(selection)
    if not ordered:
        raise SelectionError("No items were selected, so no links were exported.")

    links_target = write_links_file(links_path, ordered)
    manifest_target = None
    if manifest_path is not None:
        manifest_target = write_manifest(
            manifest_path, catalog, ordered, template, generated_at=generated_at
        )

    messages = sensitive_query_warnings(entry.variant.url for entry in ordered)
    for message in messages:
        warnings.warn(message, stacklevel=2)
    return links_target, manifest_target, messages
