"""Range expression parsing for episode, OVA, movie, and special selections."""

from __future__ import annotations

import re

from manji.errors import RangeParseError

_SINGLE = re.compile(r"(\d+)")
_RANGE = re.compile(r"(\d+)-(\d+)")
_NEGATIVE = re.compile(r"-(\d+)")


def parse_range(spec: str, total: int, *, label: str = "range") -> tuple[int, ...]:
    """Parse a selection expression into ordered, de-duplicated indexes.

    Accepts ``1-12``, ``5-5``, ``5``, comma lists, and ``0`` for none.
    Indexes are 1-based. ``total`` is the number of available items.
    """

    if total < 0:
        raise ValueError("total must not be negative")

    raw = spec.strip()
    if not raw:
        raise RangeParseError(
            f"{label}: empty selection. Use a number, a range like 1-12, or 0 for none."
        )

    segments = [segment.strip() for segment in raw.split(",")]
    if any(not segment for segment in segments):
        raise RangeParseError(f"{label}: empty segment in {spec!r}.")

    if "0" in segments and len(segments) > 1:
        raise RangeParseError(
            f"{label}: 0 means none and cannot be combined with other selections in {spec!r}."
        )

    if segments == ["0"]:
        return ()

    if total == 0:
        raise RangeParseError(f"{label}: no items are available, so the only valid value is 0.")

    selected: list[int] = []
    seen: set[int] = set()
    for segment in segments:
        normalized = segment.replace(" ", "")
        if _NEGATIVE.fullmatch(normalized):
            raise RangeParseError(f"{label}: negative index {normalized!r} is not allowed.")

        match = _RANGE.fullmatch(normalized)
        if match:
            start, end = int(match.group(1)), int(match.group(2))
        else:
            match = _SINGLE.fullmatch(normalized)
            if not match:
                raise RangeParseError(f"{label}: invalid segment {segment!r}.")
            start = end = int(match.group(1))

        if start > end:
            raise RangeParseError(f"{label}: inverted range {segment!r} is not allowed.")
        if start < 1 or end > total:
            raise RangeParseError(f"{label}: {segment!r} is outside the available range 1-{total}.")

        for index in range(start, end + 1):
            if index not in seen:
                seen.add(index)
                selected.append(index)

    return tuple(selected)
