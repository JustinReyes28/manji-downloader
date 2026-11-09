"""Typer application and command wiring."""

from __future__ import annotations

import functools
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer
from rich.console import Console
from rich.table import Table

from manji.adapters import get_registry
from manji.app import RangeSelection, ResolvedPlan, Services
from manji.config import AppConfig, LoadedConfig, load_config
from manji.domain import CATEGORY_ORDER, Category
from manji.errors import ConfigError, ManjiError, SelectionError
from manji.selection.selector import SortCriterion
from manji.version import BUILD_DATE, COMMIT, __version__

console = Console()
error_console = Console(stderr=True)

SORT_ALIASES = {
    "biggest-size": SortCriterion.BIGGEST_SIZE,
    "biggest_size": SortCriterion.BIGGEST_SIZE,
    "latest": SortCriterion.LATEST,
    "most-downloaded": SortCriterion.MOST_DOWNLOADED,
    "most_downloaded": SortCriterion.MOST_DOWNLOADED,
}

ServicesFactory = Callable[[LoadedConfig], Services]
_services_factory: ServicesFactory | None = None


def set_services_factory(factory: ServicesFactory | None) -> None:
    """Override service construction (used by tests to inject loopback clients)."""

    global _services_factory
    _services_factory = factory


def _build_services(loaded: LoadedConfig) -> Services:
    if _services_factory is not None:
        return _services_factory(loaded)
    return Services.build(loaded, registry=get_registry())


class ManjiApp(typer.Typer):
    """Typer app that maps ``ManjiError`` to the documented exit codes."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return super().__call__(*args, **kwargs)
        except ManjiError as error:
            _exit_with_error(error)
        except KeyboardInterrupt:
            error_console.print("[yellow]interrupted[/yellow]")
            raise SystemExit(130) from None


def guarded[F: Callable[..., Any]](command: F) -> F:
    """Map domain errors raised by a command to its documented exit code."""

    @functools.wraps(command)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return command(*args, **kwargs)
        except ManjiError as error:
            _exit_with_error(error)

    return wrapper  # type: ignore[return-value]


@dataclass(slots=True)
class CliState:
    """Values resolved by the root callback and shared with subcommands."""

    config_path: str | None = None
    loaded: LoadedConfig | None = None

    @property
    def config(self) -> AppConfig:
        if self.loaded is None:
            return AppConfig()
        return self.loaded.config

    def services(self) -> Services:
        active = self.loaded or load_config(explicit=self.config_path)
        return _build_services(active)


app = ManjiApp(
    name="manji",
    help=(
        "Compliance-first retrieval for authorized anime series. "
        "Run without arguments for the interactive wizard."
    ),
    no_args_is_help=False,
    invoke_without_command=True,
    add_completion=False,
)

adapters_app = typer.Typer(
    name="adapters",
    help="Inspect registered site adapters.",
    no_args_is_help=True,
)
app.add_typer(adapters_app, name="adapters")


def _format_version() -> str:
    parts = [f"manji {__version__}"]
    if COMMIT:
        parts.append(f"commit {COMMIT}")
    if BUILD_DATE:
        parts.append(f"built {BUILD_DATE}")
    return " | ".join(parts)


def parse_sort(value: str | None) -> SortCriterion | None:
    """Map a CLI sort value (``biggest-size``) to the enum."""

    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in SORT_ALIASES:
        return SORT_ALIASES[normalized]
    allowed = ", ".join(sorted(SORT_ALIASES))
    raise ConfigError(f"Unknown sort criterion {value!r}. Choose one of: {allowed}.")


@app.callback(invoke_without_command=True)
@guarded
def _root(
    ctx: typer.Context,
    config: Annotated[
        str | None,
        typer.Option("--config", help="Path to a manji configuration file."),
    ] = None,
) -> None:
    """Run ``manji`` commands with an optional configuration file."""

    loaded = load_config(explicit=config)
    for warning in loaded.warnings:
        error_console.print(f"[yellow]warning:[/yellow] {warning}")
    ctx.obj = CliState(config_path=config, loaded=loaded)

    if ctx.invoked_subcommand is not None:
        return
    if not sys.stdin.isatty():
        raise ConfigError(
            "No command given and stdin is not a terminal. Use 'manji retrieve', "
            "'manji export-links', or 'manji info' with explicit flags."
        )

    from manji.cli.wizard import run_interactive

    services = ctx.obj.services()
    try:
        code = run_interactive(services)
    finally:
        services.close()
    raise typer.Exit(code=code)


@app.command("version")
@guarded
def version_command() -> None:
    """Print version and build metadata."""

    typer.echo(_format_version())


@adapters_app.command("list")
@guarded
def adapters_list() -> None:
    """List registered site adapters."""

    entries = get_registry().list_supported_sites()
    if not entries:
        typer.echo("No adapters registered.")
        return

    table = Table(title="Registered adapters")
    table.add_column("ID", style="bold")
    table.add_column("Name")
    table.add_column("Domains")
    table.add_column("Auth")
    table.add_column("Min delay (s)", justify="right")
    for metadata in entries:
        table.add_row(
            metadata.id,
            metadata.display_name,
            ", ".join(metadata.domains),
            metadata.auth_mode.value,
            f"{metadata.default_min_request_delay_seconds:g}",
        )
    console.print(table)


def _ranges_from_flags(
    config: AppConfig,
    episodes: str | None,
    ovas: str | None,
    movies: str | None,
    specials: str | None,
) -> RangeSelection:
    defaults = RangeSelection.from_config(config)
    return RangeSelection(
        episodes=episodes if episodes is not None else defaults.episodes,
        ovas=ovas if ovas is not None else defaults.ovas,
        movies=movies if movies is not None else defaults.movies,
        specials=specials if specials is not None else defaults.specials,
    )


def _print_plan(plan: ResolvedPlan, *, verbose: bool) -> None:
    table = Table(title=plan.catalog.title)
    table.add_column("Category")
    table.add_column("Selected", justify="right")
    table.add_column("Available", justify="right")
    selected = plan.counts()
    for category in CATEGORY_ORDER:
        table.add_row(
            category.display_name,
            str(selected[category]),
            str(plan.catalog.count(category)),
        )
    console.print(table)

    if verbose:
        detail = Table(title="Selected variants")
        detail.add_column("Category")
        detail.add_column("No.", justify="right")
        detail.add_column("Title")
        detail.add_column("Quality")
        detail.add_column("Container")
        detail.add_column("Size", justify="right")
        detail.add_column("Uploaded")
        detail.add_column("Downloads", justify="right")
        for entry in plan.selection:
            detail.add_row(
                entry.category.display_name,
                f"{entry.item.number:02d}",
                entry.item.title,
                entry.variant.quality,
                entry.variant.container,
                f"{entry.variant.size_bytes:,}",
                entry.variant.uploaded_at.isoformat() if entry.variant.uploaded_at else "-",
                str(entry.variant.download_count),
            )
        console.print(detail)

    console.print(
        f"Source: [bold]{plan.catalog.site_id}[/bold] | "
        f"Quality: [bold]{plan.quality or 'best'}[/bold] | "
        f"Sort: [bold]{plan.sort.value}[/bold] | Items: [bold]{plan.total}[/bold]"
    )


def _resolve_plan(
    services: Services,
    series_url: str,
    *,
    ranges: RangeSelection,
    quality: str | None,
    sort: SortCriterion | None,
) -> ResolvedPlan:
    return services.resolve_plan(series_url, ranges=ranges, quality=quality, sort=sort)


@app.command("info")
@guarded
def info_command(
    ctx: typer.Context,
    series_url: Annotated[str, typer.Argument(help="Series URL to inspect.")],
    episodes: Annotated[str | None, typer.Option(help="Episode range (e.g. 1-12).")] = None,
    ovas: Annotated[str | None, typer.Option(help="OVA range, or 0 for none.")] = None,
    movies: Annotated[str | None, typer.Option(help="Movie range, or 0 for none.")] = None,
    specials: Annotated[str | None, typer.Option(help="Special range, or 0 for none.")] = None,
    quality: Annotated[str | None, typer.Option(help="Quality label, or 'best'.")] = None,
    sort: Annotated[
        str | None, typer.Option(help="biggest-size | latest | most-downloaded.")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show every selected item.")
    ] = False,
) -> None:
    """Inspect a series catalog without downloading anything."""

    services: Services = ctx.obj.services()
    try:
        ranges = _ranges_from_flags(services.config, episodes, ovas, movies, specials)
        plan = _resolve_plan(
            services,
            series_url,
            ranges=ranges,
            quality=quality,
            sort=parse_sort(sort),
        )
        _print_plan(plan, verbose=verbose)
    finally:
        services.close()


@app.command("retrieve")
@guarded
def retrieve_command(
    ctx: typer.Context,
    series_url: Annotated[str, typer.Argument(help="Series URL to download.")],
    episodes: Annotated[str | None, typer.Option(help="Episode range (e.g. 1-12).")] = None,
    ovas: Annotated[str | None, typer.Option(help="OVA range, or 0 for none.")] = None,
    movies: Annotated[str | None, typer.Option(help="Movie range, or 0 for none.")] = None,
    specials: Annotated[str | None, typer.Option(help="Special range, or 0 for none.")] = None,
    quality: Annotated[str | None, typer.Option(help="Quality label, or 'best'.")] = None,
    sort: Annotated[
        str | None, typer.Option(help="biggest-size | latest | most-downloaded.")
    ] = None,
    output_dir: Annotated[
        Path | None, typer.Option("--output-dir", help="Override the configured output directory.")
    ] = None,
) -> None:
    """Download the selected items through the compliant client."""

    services: Services = ctx.obj.services()
    try:
        if output_dir is not None:
            services.config.storage.base_output_directory = str(output_dir)
        ranges = _ranges_from_flags(services.config, episodes, ovas, movies, specials)
        plan = _resolve_plan(
            services,
            series_url,
            ranges=ranges,
            quality=quality,
            sort=parse_sort(sort),
        )
        _print_plan(plan, verbose=False)
        report = services.retrieve(plan, stop_event=threading.Event())
        for entry, message in report.failures:
            error_console.print(f"[red]failed[/red] {entry.item.title}: {message}")
        console.print(
            f"Downloaded [bold]{report.downloaded}[/bold] item(s); "
            f"skipped {report.skipped}; failed {len(report.failures)}."
        )
        if report.failures:
            raise typer.Exit(code=6)
    finally:
        services.close()


@app.command("export-links")
@guarded
def export_links_command(
    ctx: typer.Context,
    series_url: Annotated[str, typer.Argument(help="Series URL to resolve.")],
    episodes: Annotated[str | None, typer.Option(help="Episode range (e.g. 1-24).")] = None,
    ovas: Annotated[str | None, typer.Option(help="OVA range, or 0 for none.")] = None,
    movies: Annotated[str | None, typer.Option(help="Movie range, or 0 for none.")] = None,
    specials: Annotated[str | None, typer.Option(help="Special range, or 0 for none.")] = None,
    quality: Annotated[str | None, typer.Option(help="Quality label, or 'best'.")] = None,
    sort: Annotated[
        str | None, typer.Option(help="biggest-size | latest | most-downloaded.")
    ] = None,
    export_file: Annotated[
        Path | None, typer.Option("--export-file", help="Path for the generated links.txt.")
    ] = None,
    manifest_file: Annotated[
        Path | None, typer.Option("--manifest-file", help="Path for links-manifest.json.")
    ] = None,
) -> None:
    """Resolve links and write links.txt plus the optional manifest."""

    services: Services = ctx.obj.services()
    try:
        ranges = _ranges_from_flags(services.config, episodes, ovas, movies, specials)
        plan = _resolve_plan(
            services,
            series_url,
            ranges=ranges,
            quality=quality,
            sort=parse_sort(sort),
        )
        _print_plan(plan, verbose=False)
        links, manifest, warnings = services.export(
            plan, links_path=export_file, manifest_path=manifest_file
        )
    finally:
        services.close()

    console.print(f"Wrote [bold]{links}[/bold] ({plan.total} URL(s))")
    if manifest is not None:
        console.print(f"Wrote [bold]{manifest}[/bold]")
    for warning in warnings:
        error_console.print(f"[yellow]warning:[/yellow] {warning}")


def _exit_with_error(error: ManjiError) -> NoReturn:
    error_console.print(f"[red]error:[/red] {error}")
    raise SystemExit(error.exit_code)


def main() -> None:
    """Console-script entry point."""

    app()


__all__ = [
    "Category",
    "ManjiApp",
    "SelectionError",
    "app",
    "guarded",
    "main",
    "parse_sort",
]
