"""Quality label parsing and ranking."""

from __future__ import annotations

import re

_HEIGHT = re.compile(r"(\d{3,4})(?:p)?")
_ALIASES: dict[str, int] = {
    "4k": 2160,
    "uhd": 2160,
    "fhd": 1080,
    "hd": 720,
    "sd": 480,
}


def parse_quality_height(label: str) -> int | None:
    """Return the pixel height for a quality label, or ``None`` if unknown."""

    text = label.strip().lower()
    if not text:
        return None
    if text in _ALIASES:
        return _ALIASES[text]
    match = _HEIGHT.fullmatch(text)
    if match:
        return int(match.group(1))
    return None


def quality_rank(label: str) -> tuple[int, int]:
    """Rank a quality label; unknown labels sort below every known height."""

    height = parse_quality_height(label)
    if height is None:
        return (0, 0)
    return (1, height)


def quality_key(label: str) -> str:
    """Canonical comparison key so ``4k`` and ``2160p`` match."""

    height = parse_quality_height(label)
    if height is not None:
        return f"{height}p"
    return label.strip().lower()


def sort_qualities(labels: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Return the labels ordered from highest to lowest tier, unknown labels last."""

    return tuple(sorted(labels, key=quality_rank, reverse=True))
