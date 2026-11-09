"""Deterministic variant selection by quality, container, and sort criterion."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from manji.domain.catalog import MediaVariant
from manji.errors import NoQualityMatchError, NoVariantsError
from manji.selection.quality import quality_key, quality_rank

BEST_QUALITY = "best"


class SortCriterion(StrEnum):
    """How to choose between variants of the same quality."""

    BIGGEST_SIZE = "biggest_size"
    LATEST = "latest"
    MOST_DOWNLOADED = "most_downloaded"


def _timestamp(value: datetime | None) -> float:
    if value is None:
        return float("-inf")
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.timestamp()


@dataclass(frozen=True, slots=True)
class VariantSelector:
    """Pick one variant per item using quality preferences and a sort criterion."""

    preferred_qualities: tuple[str, ...] = ("1080p", "720p", "480p")
    preferred_formats: tuple[str, ...] = ("mkv", "mp4")
    sort_criterion: SortCriterion = SortCriterion.BIGGEST_SIZE

    def quality_preferences(self, requested_quality: str | None = None) -> tuple[str, ...]:
        """Build the ordered quality preference list for a run."""

        if requested_quality is None:
            return self.preferred_qualities
        requested = requested_quality.strip()
        if not requested:
            raise ValueError("Requested quality must not be empty.")
        if requested.lower() == BEST_QUALITY:
            return (BEST_QUALITY,)
        key = quality_key(requested)
        remaining = tuple(
            quality for quality in self.preferred_qualities if quality_key(quality) != key
        )
        return (requested, *remaining)

    def available_qualities(self, variants: Sequence[MediaVariant]) -> tuple[str, ...]:
        labels = sorted({variant.quality for variant in variants}, key=quality_rank, reverse=True)
        return tuple(labels)

    def select(
        self,
        variants: Sequence[MediaVariant],
        *,
        requested_quality: str | None = None,
    ) -> MediaVariant:
        """Return the winning variant, raising when nothing can satisfy the request."""

        if not variants:
            raise NoVariantsError("No variants are available to select from.")

        preferences = self.quality_preferences(requested_quality)
        for preference in preferences:
            if preference.lower() == BEST_QUALITY:
                best = max(variants, key=lambda variant: quality_rank(variant.quality))
                top_key = quality_key(best.quality)
                candidates = [
                    variant for variant in variants if quality_key(variant.quality) == top_key
                ]
                return min(candidates, key=self.sort_key)

            key = quality_key(preference)
            candidates = [variant for variant in variants if quality_key(variant.quality) == key]
            if candidates:
                return min(candidates, key=self.sort_key)

        available = ", ".join(self.available_qualities(variants)) or "none"
        requested = ", ".join(preferences)
        raise NoQualityMatchError(
            f"No variant matches the requested qualities ({requested}). Available: {available}."
        )

    def sort_key(self, variant: MediaVariant) -> tuple[float, float, float, float, float, str]:
        """Deterministic ordering key: criterion, container, date, size, count, ID."""

        uploaded = _timestamp(variant.uploaded_at)
        match self.sort_criterion:
            case SortCriterion.BIGGEST_SIZE:
                primary = -float(variant.size_bytes)
            case SortCriterion.LATEST:
                primary = -uploaded
            case SortCriterion.MOST_DOWNLOADED:
                primary = -float(variant.download_count)
        return (
            primary,
            float(self._container_rank(variant.container)),
            -uploaded,
            -float(variant.size_bytes),
            -float(variant.download_count),
            variant.id,
        )

    def _container_rank(self, container: str) -> int:
        normalized = container.strip().lower().lstrip(".")
        for index, preferred in enumerate(self.preferred_formats):
            if preferred.strip().lower().lstrip(".") == normalized:
                return index
        return len(self.preferred_formats)
