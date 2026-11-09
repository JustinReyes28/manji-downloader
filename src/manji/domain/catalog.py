"""Universal catalog models shared by every site adapter."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final


class Category(StrEnum):
    """Media categories exposed by every adapter."""

    EPISODES = "episodes"
    OVAS = "ovas"
    MOVIES = "movies"
    SPECIALS = "specials"

    @property
    def display_name(self) -> str:
        return CATEGORY_DISPLAY_NAMES[self]


CATEGORY_ORDER: Final[tuple[Category, ...]] = (
    Category.EPISODES,
    Category.OVAS,
    Category.MOVIES,
    Category.SPECIALS,
)

CATEGORY_DISPLAY_NAMES: Final[dict[Category, str]] = {
    Category.EPISODES: "Episodes",
    Category.OVAS: "OVAs",
    Category.MOVIES: "Movies",
    Category.SPECIALS: "Specials",
}


@dataclass(frozen=True, slots=True)
class MediaItem:
    """A single episode, OVA, movie, or special in a series catalog."""

    id: str
    number: int
    title: str
    url: str


@dataclass(frozen=True, slots=True)
class MediaVariant:
    """A downloadable file variant for one media item."""

    id: str
    quality: str
    container: str
    size_bytes: int
    uploaded_at: datetime | None
    download_count: int
    url: str


@dataclass(frozen=True, slots=True)
class SeriesCatalog:
    """Normalized series catalog returned by every site adapter."""

    title: str
    site_id: str
    source_url: str
    episodes: tuple[MediaItem, ...] = ()
    ovas: tuple[MediaItem, ...] = ()
    movies: tuple[MediaItem, ...] = ()
    specials: tuple[MediaItem, ...] = ()

    def items(self, category: Category) -> tuple[MediaItem, ...]:
        match category:
            case Category.EPISODES:
                return self.episodes
            case Category.OVAS:
                return self.ovas
            case Category.MOVIES:
                return self.movies
            case Category.SPECIALS:
                return self.specials

    def count(self, category: Category) -> int:
        return len(self.items(category))

    def counts(self) -> dict[Category, int]:
        return {category: self.count(category) for category in CATEGORY_ORDER}

    def total_items(self) -> int:
        return sum(self.counts().values())

    def iter_items(self) -> Iterator[tuple[Category, MediaItem]]:
        for category in CATEGORY_ORDER:
            for item in self.items(category):
                yield category, item
