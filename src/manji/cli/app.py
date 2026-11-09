"""Typer application and command wiring."""

from __future__ import annotations

import sys
from typing import Annotated, NoReturn

import typer
from rich.console import Console
from rich.table import Table

from manji.adapters import get_registry
from manji.errors import ManjiError
from manji.version import BUILD_DATE, COMMIT, __version__

console = Console()
error_console = Console(stderr=True)

app = typer.Typer(
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
def _root(
    config: Annotated[
        str | None,
        typer.Option("--config", help="Path to a manji configuration file."),
    ] = None,
) -> None:
    """Run ``manji`` commands. Configuration loading arrives in Phase 2."""


@app.command("version")
def version_command() -> None:
    """Print version and build metadata."""

    typer.echo(_format_version())


@adapters_app.command("list")
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
    raise typer.Exit(code=error.exit_code)


def main() -> None:
    """Console-script entry point mapping domain errors to exit codes."""

    try:
        app()
    except ManjiError as error:
        _exit_with_error(error)
    except typer.Exit:
        raise
    except KeyboardInterrupt:
        error_console.print("[yellow]interrupted[/yellow]")
        sys.exit(130)
