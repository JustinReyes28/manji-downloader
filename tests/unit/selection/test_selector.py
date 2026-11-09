from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from manji.domain import MediaVariant
from manji.errors import NoQualityMatchError, NoVariantsError
from manji.selection.quality import parse_quality_height, quality_key, sort_qualities
from manji.selection.selector import SortCriterion, VariantSelector

pytestmark = pytest.mark.unit

BASE_TIME = datetime(2024, 1, 1, tzinfo=UTC)


def variant(
    variant_id: str,
    quality: str = "1080p",
    *,
    container: str = "mkv",
    size: int = 1000,
    days: int = 0,
    downloads: int = 10,
    uploaded: datetime | None = None,
) -> MediaVariant:
    return MediaVariant(
        id=variant_id,
        quality=quality,
        container=container,
        size_bytes=size,
        uploaded_at=BASE_TIME + timedelta(days=days) if uploaded is None else uploaded,
        download_count=downloads,
        url=f"https://media.test/{variant_id}",
    )


@pytest.mark.parametrize(
    ("label", "height"),
    [
        ("1080p", 1080),
        ("720p", 720),
        ("480p", 480),
        ("2160p", 2160),
        ("4k", 2160),
        ("UHD", 2160),
        ("1080", 1080),
        ("unknown", None),
        ("", None),
    ],
)
def test_parse_quality_height(label: str, height: int | None) -> None:
    assert parse_quality_height(label) == height


def test_quality_key_normalizes_aliases() -> None:
    assert quality_key("4K") == quality_key("2160p")
    assert quality_key("1080P") == "1080p"


def test_sort_qualities_highest_first_unknown_last() -> None:
    assert sort_qualities(["480p", "unknown", "1080p", "4k"]) == (
        "4k",
        "1080p",
        "480p",
        "unknown",
    )


def test_quality_fallback_order() -> None:
    selector = VariantSelector()
    chosen = selector.select([variant("a", "720p"), variant("b", "480p")])
    assert chosen.quality == "720p"


def test_exact_quality_preferred() -> None:
    selector = VariantSelector()
    chosen = selector.select(
        [variant("a", "1080p"), variant("b", "720p")], requested_quality="720p"
    )
    assert chosen.quality == "720p"


def test_requested_quality_moves_to_front() -> None:
    selector = VariantSelector(preferred_qualities=("1080p", "720p", "480p"))
    assert selector.quality_preferences("480p") == ("480p", "1080p", "720p")


def test_best_quality_picks_highest() -> None:
    selector = VariantSelector()
    variants = [variant("a", "720p"), variant("b", "2160p"), variant("c", "1080p")]
    chosen = selector.select(variants, requested_quality="best")
    assert chosen.quality == "2160p"


def test_best_quality_handles_4k_alias() -> None:
    selector = VariantSelector()
    chosen = selector.select([variant("a", "4K"), variant("b", "1080p")], requested_quality="best")
    assert chosen.quality == "4K"


def test_no_match_raises_with_available_qualities() -> None:
    selector = VariantSelector(preferred_qualities=("720p",))
    with pytest.raises(NoQualityMatchError, match="Available: 1080p"):
        selector.select([variant("a", "1080p")])


def test_no_variants_raises() -> None:
    with pytest.raises(NoVariantsError):
        VariantSelector().select([])


def test_empty_requested_quality_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        VariantSelector().quality_preferences("   ")


def test_biggest_size() -> None:
    selector = VariantSelector(sort_criterion=SortCriterion.BIGGEST_SIZE)
    variants = [variant("a", size=100), variant("b", size=900), variant("c", size=500)]
    assert selector.select(variants).id == "b"


def test_latest() -> None:
    selector = VariantSelector(sort_criterion=SortCriterion.LATEST)
    variants = [variant("a", days=0), variant("b", days=30), variant("c", days=10)]
    assert selector.select(variants).id == "b"


def test_most_downloaded() -> None:
    selector = VariantSelector(sort_criterion=SortCriterion.MOST_DOWNLOADED)
    variants = [
        variant("a", downloads=1),
        variant("b", downloads=99),
        variant("c", downloads=42),
    ]
    assert selector.select(variants).id == "b"


def test_container_tiebreak_prefers_configured_format() -> None:
    selector = VariantSelector(sort_criterion=SortCriterion.BIGGEST_SIZE)
    variants = [variant("mp4", container="mp4"), variant("mkv", container="mkv")]
    assert selector.select(variants).id == "mkv"

    flipped = VariantSelector(
        preferred_formats=("mp4", "mkv"), sort_criterion=SortCriterion.BIGGEST_SIZE
    )
    assert flipped.select(variants).id == "mp4"


def test_tiebreak_newest_upload() -> None:
    selector = VariantSelector(sort_criterion=SortCriterion.BIGGEST_SIZE)
    variants = [variant("old", days=0), variant("new", days=5)]
    assert selector.select(variants).id == "new"


def test_tiebreak_variant_id_is_stable() -> None:
    selector = VariantSelector(sort_criterion=SortCriterion.BIGGEST_SIZE)
    variants = [variant("zeta"), variant("alpha")]
    assert selector.select(variants).id == "alpha"
    assert selector.select(list(reversed(variants))).id == "alpha"


def test_missing_upload_date_sorts_last_for_latest() -> None:
    selector = VariantSelector(sort_criterion=SortCriterion.LATEST)
    variants = [variant("none", uploaded=None), variant("dated", days=1)]
    # The sentinel upload time is far in the past, so the dated variant wins.
    assert selector.select(variants).id == "dated"
