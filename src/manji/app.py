"""Dependency wiring: construct services from validated configuration."""

from __future__ import annotations

import threading
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from manji.adapters import AdapterRegistry, SourceAdapter
from manji.config import AppConfig, LoadedConfig, load_config
from manji.domain import Category, MediaItem, MediaVariant, SeriesCatalog
from manji.download.downloader import Downloader, DownloadResult
from manji.errors import ManjiError, SelectionError
from manji.export.links import SelectedVariant, export_links
from manji.log import configure_logging
from manji.net.client import CompliantClient, settings_from_config
from manji.organize.filenames import FilenameContext, build_destination
from manji.organize.sidecars import write_episode_sidecar, write_series_sidecar
from manji.selection.ranges import parse_range
from manji.selection.selector import SortCriterion, VariantSelector

DEFAULT_TEMPLATE = (
    "{series_title}/{category}/{series_title} - Episode {episode_number} [{quality}].{ext}"
)


@dataclass(frozen=True, slots=True)
class RangeSelection:
    """Raw range expressions per category, before validation against a catalog."""

    episodes: str = "1-12"
    ovas: str = "0"
    movies: str = "0"
    specials: str = "0"

    def as_dict(self) -> dict[Category, str]:
        return {
            Category.EPISODES: self.episodes,
            Category.OVAS: self.ovas,
            Category.MOVIES: self.movies,
            Category.SPECIALS: self.specials,
        }

    @classmethod
    def from_config(cls, config: AppConfig) -> RangeSelection:
        defaults = config.media_selection.default_ranges
        return cls(
            episodes=defaults.episodes,
            ovas=defaults.ovas,
            movies=defaults.movies,
            specials=defaults.specials,
        )


@dataclass(frozen=True, slots=True)
class ResolvedPlan:
    """A catalog plus the concrete items and variants selected for this run."""

    catalog: SeriesCatalog
    selection: tuple[SelectedVariant, ...]
    quality: str | None
    sort: SortCriterion

    def counts(self) -> dict[Category, int]:
        counts = dict.fromkeys(Category, 0)
        for entry in self.selection:
            counts[entry.category] += 1
        return counts

    @property
    def total(self) -> int:
        return len(self.selection)


@dataclass(slots=True)
class RetrievalReport:
    """Summary of a retrieval run."""

    results: list[DownloadResult] = field(default_factory=list)
    failures: list[tuple[SelectedVariant, str]] = field(default_factory=list)

    @property
    def downloaded(self) -> int:
        return sum(1 for result in self.results if not result.skipped)

    @property
    def skipped(self) -> int:
        return sum(1 for result in self.results if result.skipped)

    @property
    def ok(self) -> bool:
        return not self.failures


class Services:
    """Construct and own the runtime services for one CLI invocation."""

    def __init__(
        self,
        loaded: LoadedConfig,
        registry: AdapterRegistry,
        client: CompliantClient,
        *,
        owns_client: bool = True,
    ) -> None:
        self.loaded = loaded
        self.config = loaded.config
        self.registry = registry
        self.client = client
        self.owns_client = owns_client

    @classmethod
    def build(
        cls,
        loaded: LoadedConfig,
        *,
        registry: AdapterRegistry | None = None,
        client: CompliantClient | None = None,
        configure: bool = True,
    ) -> Services:
        if configure:
            configure_logging(loaded.config.logging)
        settings = settings_from_config(loaded.config)
        active_registry = registry or AdapterRegistry()
        active_client = client or CompliantClient(settings)
        return cls(
            loaded,
            active_registry,
            active_client,
            owns_client=client is None,
        )

    @classmethod
    def from_config_path(
        cls,
        explicit: str | Path | None = None,
        *,
        registry: AdapterRegistry | None = None,
        client: CompliantClient | None = None,
        configure: bool = True,
    ) -> Services:
        return cls.build(
            load_config(explicit=explicit),
            registry=registry,
            client=client,
            configure=configure,
        )

    def close(self) -> None:
        if self.owns_client:
            self.client.close()

    def resolve_catalog(self, series_url: str) -> tuple[SourceAdapter, SeriesCatalog]:
        adapter = self.registry.resolve_for_url(series_url)
        from manji.adapters import Target

        adapter.validate_access(Target.for_url(series_url, adapter.get_site_metadata()))
        return adapter, adapter.resolve_series_catalog(series_url)

    def resolve_plan(
        self,
        series_url: str,
        *,
        ranges: RangeSelection | None = None,
        quality: str | None = None,
        sort: SortCriterion | None = None,
    ) -> ResolvedPlan:
        adapter, catalog = self.resolve_catalog(series_url)
        active_ranges = ranges or RangeSelection.from_config(self.config)
        criterion = sort or self.config.media_selection.sort_criterion
        selector = VariantSelector(
            preferred_qualities=tuple(self.config.media_selection.preferred_qualities),
            preferred_formats=tuple(self.config.media_selection.preferred_formats),
            sort_criterion=criterion,
        )

        selection: list[SelectedVariant] = []
        for category, spec in active_ranges.as_dict().items():
            items = catalog.items(category)
            indexes = parse_range(spec, len(items), label=category.display_name)
            for index in indexes:
                item = items[index - 1]
                variant = selector.select(
                    adapter.resolve_episode_variants(item), requested_quality=quality
                )
                selection.append(SelectedVariant(category, item, variant))

        if not selection:
            raise SelectionError("No items were selected. Provide at least one non-zero range.")

        return ResolvedPlan(
            catalog=catalog, selection=tuple(selection), quality=quality, sort=criterion
        )

    def template(self) -> str:
        return self.config.storage.filename_template or DEFAULT_TEMPLATE

    def destination_for(self, plan: ResolvedPlan, entry: SelectedVariant) -> Path:
        context = FilenameContext.build(plan.catalog, entry.category, entry.item, entry.variant)
        return build_destination(
            self.config.storage.base_output_directory, self.template(), context
        )

    def write_series_sidecar(self, plan: ResolvedPlan) -> Path:
        return write_series_sidecar(self.config.storage.base_output_directory, plan.catalog)

    def retrieve(
        self,
        plan: ResolvedPlan,
        *,
        stop_event: threading.Event | None = None,
    ) -> RetrievalReport:
        downloader = Downloader(
            self.client, conflict_resolution=self.config.storage.conflict_resolution
        )
        report = RetrievalReport()
        written_series: set[Path] = set()

        for entry in plan.selection:
            destination = self.destination_for(plan, entry)
            try:
                result = downloader.download(
                    entry.variant.url,
                    destination,
                    stop_event=stop_event,
                    expected_size=entry.variant.size_bytes or None,
                )
            except ManjiError as error:
                report.failures.append((entry, str(error)))
                continue

            report.results.append(result)
            if self.config.storage.save_metadata_sidecar and not result.skipped:
                write_episode_sidecar(
                    result.destination.parent,
                    entry.category,
                    entry.item,
                    entry.variant,
                    site_id=plan.catalog.site_id,
                    source_url=plan.catalog.source_url,
                )
                if result.destination.parent not in written_series:
                    write_series_sidecar(result.destination.parent, plan.catalog)
                    written_series.add(result.destination.parent)

        return report

    def export(
        self,
        plan: ResolvedPlan,
        *,
        links_path: str | Path | None = None,
        manifest_path: str | Path | None = None,
    ) -> tuple[Path, Path | None, tuple[str, ...]]:
        batch = self.config.storage.batch_export
        resolved_links = Path(links_path or batch.links_file_path)
        if manifest_path is not None:
            resolved_manifest: Path | None = Path(manifest_path)
        elif batch.generate_rename_manifest:
            resolved_manifest = Path(batch.manifest_file_path)
        else:
            resolved_manifest = None

        return export_links(
            plan.catalog,
            plan.selection,
            links_path=resolved_links,
            template=self.template(),
            manifest_path=resolved_manifest,
        )


def summarize_catalog(catalog: SeriesCatalog) -> Iterable[tuple[Category, int]]:
    for category in Category:
        yield category, catalog.count(category)


def describe_variants(variants: Sequence[MediaVariant]) -> str:
    return ", ".join(sorted({variant.quality for variant in variants}))


def first_item(catalog: SeriesCatalog, category: Category) -> MediaItem | None:
    items = catalog.items(category)
    return items[0] if items else None
