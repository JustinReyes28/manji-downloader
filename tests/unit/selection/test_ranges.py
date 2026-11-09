from __future__ import annotations

import pytest

from manji.errors import RangeParseError
from manji.selection import parse_range

pytestmark = pytest.mark.unit


def test_simple_range() -> None:
    assert parse_range("1-12", 24) == tuple(range(1, 13))


def test_single_value() -> None:
    assert parse_range("5", 24) == (5,)


def test_single_range_same_bounds() -> None:
    assert parse_range("5-5", 24) == (5,)


def test_zero_means_none() -> None:
    assert parse_range("0", 24) == ()
    assert parse_range("0", 0) == ()


def test_comma_list_preserves_order() -> None:
    assert parse_range("3, 1-2", 24) == (3, 1, 2)


def test_deduplicates_while_preserving_first_seen_order() -> None:
    assert parse_range("1-3,2-4", 24) == (1, 2, 3, 4)


def test_whitespace_around_segments() -> None:
    assert parse_range("  1 - 2 , 4 ", 10) == (1, 2, 4)


def test_full_bounds() -> None:
    assert parse_range(f"1-{24}", 24) == tuple(range(1, 25))


def test_total_zero_only_allows_zero() -> None:
    with pytest.raises(RangeParseError, match="only valid value is 0"):
        parse_range("1", 0)


@pytest.mark.parametrize(
    ("spec", "total", "message"),
    [
        ("", 24, "empty selection"),
        ("1,,2", 24, "empty segment"),
        ("1-", 24, "invalid segment"),
        ("-1", 24, "negative index"),
        ("abc", 24, "invalid segment"),
        ("1.5", 24, "invalid segment"),
        ("12-1", 24, "inverted range"),
        ("0,1", 24, "cannot be combined"),
        ("25", 24, "outside the available range"),
        ("1-30", 24, "outside the available range"),
    ],
)
def test_rejections(spec: str, total: int, message: str) -> None:
    with pytest.raises(RangeParseError, match=message):
        parse_range(spec, total)


def test_label_appears_in_error() -> None:
    with pytest.raises(RangeParseError, match="OVAs"):
        parse_range("99", 2, label="OVAs")


def test_negative_total_rejected() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        parse_range("1", -1)
