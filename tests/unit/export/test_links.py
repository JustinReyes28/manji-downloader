from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from manji.domain import CATEGORY_ORDER, Category, MediaItem, MediaVariant, SeriesCatalog
from manji.errors import SelectionError
from manji.export.links import (
    SelectedVariant,
    build_links_text,
    build_manifest,
    export_links,
    ordered_selection,
    sensitive_query_warnings,
)

pytestmark = pytest.mark.unit

TEMPLATE = "{series_title}/{category}/{series_title} - Episode {episode_number} [{quality}].{ext}"
MOMENT = datetime(2024, 5, 6, tzinfo=UTC)


def catalog() -> SeriesCatalog:
    return SeriesCatalog(
        title="Example Series",
        site_id="mock_json",
        source_url="https://mock.test/series/example",
    )


def selected(
    category: Category, number: int, *, quality: str = "1080p", url: str | None = None
) -> SelectedVariant:
    item = MediaItem(
        id=f"{category}-{number}", number=number, title=f"Item {number}", url=f"https://x/{number}"
    )
    variant = MediaVariant(
        id=f"{category}-{number}-{quality}",
        quality=quality,
        container="mkv",
        size_bytes=100,
        uploaded_at=MOMENT,
        download_count=1,
        url=url or f"https://mock.test/media/{category}/{number}.mkv",
    )
    return SelectedVariant(category=category, item=item, variant=variant)


def test_ordered_selection_uses_category_then_number() -> None:
    entries = [
        selected(Category.SPECIALS, 1),
        selected(Category.EPISODES, 2),
        selected(Category.OVAS, 1),
        selected(Category.EPISODES, 1),
        selected(Category.MOVIES, 1),
    ]
    ordered = ordered_selection(entries)
    assert [(entry.category, entry.item.number) for entry in ordered] == [
        (Category.EPISODES, 1),
        (Category.EPISODES, 2),
        (Category.OVAS, 1),
        (Category.MOVIES, 1),
        (Category.SPECIALS, 1),
    ]


def test_links_text_has_one_url_per_line_with_final_newline() -> None:
    text = build_links_text([selected(Category.EPISODES, 1), selected(Category.EPISODES, 2)])
    assert text == (
        "https://mock.test/media/episodes/1.mkv\nhttps://mock.test/media/episodes/2.mkv\n"
    )


def test_empty_selection_is_an_error() -> None:
    with pytest.raises(SelectionError, match="No items were selected"):
        build_links_text([])


def test_manifest_schema() -> None:
    manifest = build_manifest(
        catalog(),
        [selected(Category.EPISODES, 1)],
        TEMPLATE,
        generated_at=MOMENT,
    )
    assert manifest["version"] == "1.0"
    assert manifest["generated_at"] == "2024-05-06T00:00:00Z"
    series = manifest["series"]
    assert isinstance(series, dict)
    assert series["title"] == "Example Series"
    assert series["site_id"] == "mock_json"
    entries = manifest["entries"]
    assert isinstance(entries, list)
    assert entries[0] == {
        "url": "https://mock.test/media/episodes/1.mkv",
        "filename": "Example Series/Episodes/Example Series - Episode 01 [1080p].mkv",
    }


def test_manifest_entries_follow_selection_order() -> None:
    manifest = build_manifest(
        catalog(),
        [selected(Category.OVAS, 1), selected(Category.EPISODES, 1)],
        TEMPLATE,
    )
    entries = manifest["entries"]
    assert isinstance(entries, list)
    assert entries[0]["url"].endswith("/episodes/1.mkv")
    assert entries[1]["url"].endswith("/ovas/1.mkv")


def test_export_writes_both_files(tmp_path: Path) -> None:
    links, manifest_path, warnings = export_links(
        catalog(),
        [selected(Category.EPISODES, 1)],
        links_path=tmp_path / "links.txt",
        template=TEMPLATE,
        manifest_path=tmp_path / "links-manifest.json",
        generated_at=MOMENT,
    )
    assert links.read_text(encoding="utf-8").endswith(".mkv\n")
    assert manifest_path is not None
    assert manifest_path.is_file()
    assert warnings == ()


def test_export_without_manifest(tmp_path: Path) -> None:
    links, manifest_path, _ = export_links(
        catalog(),
        [selected(Category.EPISODES, 1)],
        links_path=tmp_path / "links.txt",
        template=TEMPLATE,
    )
    assert links.is_file()
    assert manifest_path is None


def test_export_empty_selection_writes_nothing(tmp_path: Path) -> None:
    with pytest.raises(SelectionError):
        export_links(catalog(), [], links_path=tmp_path / "links.txt", template=TEMPLATE)
    assert not (tmp_path / "links.txt").exists()


def test_sensitive_query_parameters_are_warned_not_stripped() -> None:
    url = "https://mock.test/media/1.mkv?token=abc&page=2"
    messages = sensitive_query_warnings([url])
    assert len(messages) == 1
    assert "token" in messages[0]
    # The URL itself is unchanged by warning.
    assert "token=abc" in url


@pytest.mark.parametrize("key", ["sig", "auth", "key", "password", "session"])
def test_each_sensitive_key_warns(key: str) -> None:
    messages = sensitive_query_warnings([f"https://mock.test/m?{key}=x"])
    assert messages and key in messages[0]


def test_clean_urls_produce_no_warnings() -> None:
    assert sensitive_query_warnings(["https://mock.test/media/1.mkv"]) == ()


def test_export_warns_for_sensitive_urls(tmp_path: Path) -> None:
    with pytest.warns(UserWarning, match="sensitive query"):
        _, _, messages = export_links(
            catalog(),
            [selected(Category.EPISODES, 1, url="https://mock.test/m.mkv?sig=abc")],
            links_path=tmp_path / "links.txt",
            template=TEMPLATE,
        )
    assert messages


def test_category_order_matches_domain_constant() -> None:
    assert list(CATEGORY_ORDER) == [
        Category.EPISODES,
        Category.OVAS,
        Category.MOVIES,
        Category.SPECIALS,
    ]
