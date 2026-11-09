"""Typer application and command wiring."""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, NoReturn

import typer
from rich.console import Console
from rich.table import Table

from manji.adapters import get_registry
from manji.config import AppConfig, LoadedConfig, load_config
from manji.errors import ManjiError
from manji.version import BUILD_DATE, COMMIT, __version__

console = Console()
error_console = Console(stderr=True)


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


app = ManjiApp(
    name="manji",
    help="Compliance-first retrieval for authorized anime series.",
    no_args_is_help=True,
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


@app.callback()
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


def _exit_with_error(error: ManjiError) -> NoReturn:
    error_console.print(f"[red]error:[/red] {error}")
    raise SystemExit(error.exit_code)


def main() -> None:
    """Console-script entry point."""

    app()
