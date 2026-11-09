from __future__ import annotations

import pytest

from manji.domain import CATEGORY_ORDER, Category, MediaItem, SeriesCatalog

pytestmark = pytest.mark.unit


def _item(number: int) -> MediaItem:
    return MediaItem(
        id=f"i{number}", number=number, title=f"Item {number}", url=f"https://x/{number}"
    )


def _catalog() -> SeriesCatalog:
    return SeriesCatalog(
        title="Example",
        site_id="mock",
        source_url="https://x/series",
        episodes=tuple(_item(n) for n in range(1, 25)),
        ovas=(_item(1), _item(2)),
        movies=(_item(1),),
        specials=(_item(1), _item(2), _item(3)),
    )


def test_category_order() -> None:
    assert CATEGORY_ORDER == (
        Category.EPISODES,
        Category.OVAS,
        Category.MOVIES,
        Category.SPECIALS,
    )


def test_category_display_names() -> None:
    assert [c.display_name for c in CATEGORY_ORDER] == [
        "Episodes",
        "OVAs",
        "Movies",
        "Specials",
    ]


def test_items_per_category() -> None:
    catalog = _catalog()
    assert len(catalog.items(Category.EPISODES)) == 24
    assert len(catalog.items(Category.OVAS)) == 2
    assert len(catalog.items(Category.MOVIES)) == 1
    assert len(catalog.items(Category.SPECIALS)) == 3


def test_counts_and_total() -> None:
    catalog = _catalog()
    assert catalog.counts() == {
        Category.EPISODES: 24,
        Category.OVAS: 2,
        Category.MOVIES: 1,
        Category.SPECIALS: 3,
    }
    assert catalog.total_items() == 30


def test_empty_catalog() -> None:
    catalog = SeriesCatalog(title="Empty", site_id="mock", source_url="https://x")
    assert catalog.total_items() == 0
    assert catalog.items(Category.EPISODES) == ()
    assert list(catalog.iter_items()) == []


def test_iter_items_uses_category_order() -> None:
    catalog = _catalog()
    ordered = list(catalog.iter_items())
    assert ordered[0] == (Category.EPISODES, _item(1))
    assert ordered[24] == (Category.OVAS, _item(1))
    assert ordered[-1] == (Category.SPECIALS, _item(3))


def test_models_are_frozen() -> None:
    item = _item(1)
    with pytest.raises(AttributeError):
        item.title = "changed"  # type: ignore[misc]
