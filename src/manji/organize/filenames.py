"""Filename templates, cross-platform sanitization, and safe paths."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from manji.domain import Category, MediaItem, MediaVariant, SeriesCatalog
from manji.errors import ConfigError, DownloadError
from manji.fs import safe_join

ALLOWED_VARIABLES = frozenset(
    {
        "series_title",
        "site_id",
        "category",
        "episode_number",
        "quality",
        "id",
        "date",
        "ext",
    }
)

MAX_SEGMENT_LENGTH = 120

_VARIABLE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_ILLEGAL_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_TRAILING_DOTS_AND_SPACES = re.compile(r"[. ]+$")

_RESERVED_WINDOWS_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
)


@dataclass(frozen=True, slots=True)
class FilenameContext:
    """Values available to a filename template."""

    series_title: str
    site_id: str
    category: Category
    episode_number: int
    quality: str
    id: str
    date: date
    ext: str

    @classmethod
    def build(
        cls,
        catalog: SeriesCatalog,
        category: Category,
        item: MediaItem,
        variant: MediaVariant,
        *,
        retrieved_at: datetime | None = None,
    ) -> FilenameContext:
        moment = variant.uploaded_at or retrieved_at or datetime.now(UTC)
        return cls(
            series_title=catalog.title,
            site_id=catalog.site_id,
            category=category,
            episode_number=item.number,
            quality=variant.quality,
            id=variant.id,
            date=moment.date(),
            ext=variant.container.strip().lower().lstrip("."),
        )


def validate_template(template: str) -> tuple[str, ...]:
    """Validate a template and return the variable names it references."""

    if not template.strip():
        raise ConfigError("Filename template must not be empty.")
    if template.lstrip().startswith(("/", "\\")):
        raise ConfigError(f"Filename template must be relative, got {template!r}.")

    names = tuple(_VARIABLE.findall(template))
    unknown = sorted(set(names) - ALLOWED_VARIABLES)
    if unknown:
        allowed = ", ".join(sorted(ALLOWED_VARIABLES))
        raise ConfigError(
            f"Unknown filename template variable(s): {', '.join(unknown)}. Allowed: {allowed}."
        )

    remainder = _VARIABLE.sub("", template)
    if "{" in remainder or "}" in remainder:
        raise ConfigError(f"Malformed filename template braces in {template!r}.")
    return names


def _clean_characters(value: str) -> str:
    replaced = _ILLEGAL_CHARACTERS.sub("_", value)
    return _TRAILING_DOTS_AND_SPACES.sub("", replaced.strip())


def _validate_segment(segment: str) -> str:
    if not segment:
        raise DownloadError("Filename template produced an empty path segment.")
    if segment in {".", ".."}:
        raise DownloadError(f"Filename template produced a traversal segment {segment!r}.")
    if segment.split(".")[0].strip().upper() in _RESERVED_WINDOWS_NAMES:
        raise DownloadError(f"Filename segment {segment!r} is a reserved Windows device name.")
    if len(segment) > MAX_SEGMENT_LENGTH:
        raise DownloadError(
            f"Filename segment {segment!r} exceeds {MAX_SEGMENT_LENGTH} characters."
        )
    return segment


def render_relative_path(template: str, context: FilenameContext) -> str:
    """Render a template into a sanitized relative path using ``/`` separators."""

    validate_template(template)
    for segment in template.split("/"):
        if segment.strip() in {"", ".", ".."}:
            kind = "empty path segment" if not segment.strip() else "traversal segment"
            raise DownloadError(f"Filename template produced an {kind}.")
    values = {
        "series_title": _clean_characters(context.series_title),
        "site_id": _clean_characters(context.site_id),
        "category": _clean_characters(context.category.display_name),
        "episode_number": f"{context.episode_number:02d}",
        "quality": _clean_characters(context.quality),
        "id": _clean_characters(context.id),
        "date": context.date.strftime("%Y-%m-%d"),
        "ext": _clean_characters(context.ext),
    }
    for name in ("series_title", "site_id", "category", "id", "ext"):
        if not values[name]:
            values[name] = "_"

    rendered = template.format(**values)
    segments = [_validate_segment(_clean_characters(part)) for part in rendered.split("/")]
    return "/".join(segments)


def build_destination(base_directory: Path | str, template: str, context: FilenameContext) -> Path:
    """Render the template and join it safely under ``base_directory``."""

    return safe_join(base_directory, render_relative_path(template, context))
