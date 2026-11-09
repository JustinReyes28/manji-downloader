"""Synthetic HTML catalog adapter used only by tests."""

from __future__ import annotations

import re
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit

from manji.adapters.base import AuthMode, SiteMetadata, Target
from manji.domain import MediaItem, MediaVariant, SeriesCatalog
from manji.errors import HTTPError
from manji.net.client import CompliantClient

SITE_ID = "mock_html"
HOST = "mock-html.test"

_CATEGORY_BY_SECTION = {
    "episodes": "episodes",
    "ovas": "ovas",
    "movies": "movies",
    "specials": "specials",
}
_NUMBER = re.compile(r"(\d+)")


class _CatalogParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.sections: dict[str, list[MediaItem]] = {
            "episodes": [],
            "ovas": [],
            "movies": [],
            "specials": [],
        }
        self._section: str | None = None
        self._in_title = False
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "h1" and "series-title" in (attributes.get("class") or ""):
            self._in_title = True
        elif tag == "section":
            self._section = attributes.get("id")
        elif tag == "a" and self._section in _CATEGORY_BY_SECTION:
            self._current_href = attributes.get("href")
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self._in_title = False
        elif tag == "section":
            self._section = None
        elif tag == "a" and self._current_href is not None and self._section is not None:
            text = "".join(self._current_text).strip()
            match = _NUMBER.search(text)
            if match:
                number = int(match.group(1))
                category = _CATEGORY_BY_SECTION[self._section]
                self.sections[category].append(
                    MediaItem(
                        id=f"{category}-{number:02d}",
                        number=number,
                        title=text,
                        url=self._current_href,
                    )
                )
            self._current_href = None
            self._current_text = []


class _VariantParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, str]] = []
        self._row: dict[str, str] | None = None
        self._field: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "tr" and attributes.get("data-variant-id"):
            self._row = {"id": attributes["data-variant-id"] or ""}
        elif self._row is not None and tag == "td":
            self._field = attributes.get("class")
            self._buffer = []
            if self._field == "size" and attributes.get("data-bytes"):
                self._row["size_bytes"] = attributes["data-bytes"] or ""
        elif self._row is not None and tag == "a":
            href = attributes.get("href")
            if href:
                self._row["url"] = href

    def handle_data(self, data: str) -> None:
        if self._row is not None and self._field is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._row is not None and self._field is not None:
            if self._field in {"quality", "container", "uploaded", "downloads", "size"}:
                self._row[self._field] = "".join(self._buffer).strip()
            self._field = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


class MockHtmlAdapter:
    def __init__(self, client: CompliantClient) -> None:
        self.client = client

    def get_site_metadata(self) -> SiteMetadata:
        return SiteMetadata(
            id=SITE_ID,
            display_name="Mock HTML Site",
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
        parser = _CatalogParser()
        parser.feed(self.client.get_text(series_url))
        if not parser.title:
            raise HTTPError("Mock HTML catalog has no series title.")
        return SeriesCatalog(
            title=parser.title.strip(),
            site_id=SITE_ID,
            source_url=series_url,
            episodes=tuple(parser.sections["episodes"]),
            ovas=tuple(parser.sections["ovas"]),
            movies=tuple(parser.sections["movies"]),
            specials=tuple(parser.sections["specials"]),
        )

    def resolve_episode_variants(self, item: MediaItem) -> tuple[MediaVariant, ...]:
        parser = _VariantParser()
        parser.feed(self.client.get_text(item.url))
        variants: list[MediaVariant] = []
        for row in parser.rows:
            uploaded = row.get("uploaded")
            variants.append(
                MediaVariant(
                    id=row.get("id", ""),
                    quality=row.get("quality", "unknown"),
                    container=row.get("container", ""),
                    size_bytes=int(row.get("size_bytes") or row.get("size") or 0),
                    uploaded_at=datetime.fromisoformat(uploaded.replace("Z", "+00:00"))
                    if uploaded
                    else None,
                    download_count=int(row.get("downloads") or 0),
                    url=row.get("url", ""),
                )
            )
        return tuple(variants)
