"""Interactive wizard used by ``manji`` with no arguments."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import StrEnum

import questionary
from rich.console import Console
from rich.table import Table

from manji.app import RangeSelection, ResolvedPlan, Services
from manji.domain import CATEGORY_ORDER
from manji.errors import ManjiError
from manji.selection.selector import SortCriterion

console = Console()

BEST = "best"


class Action(StrEnum):
    """What the wizard should do after building a plan."""

    DOWNLOAD = "Direct local download"
    EXPORT = "Export URLs to links.txt"


@dataclass(frozen=True, slots=True)
class WizardResult:
    """Everything the wizard collected."""

    plan: ResolvedPlan
    action: Action


def _ask(prompt: object) -> object:
    """Ask a questionary prompt and abort cleanly on Ctrl+C."""

    try:
        answer = prompt.ask()  # type: ignore[attr-defined]
    except KeyboardInterrupt as error:
        raise SystemExit(130) from error
    if answer is None:
        raise SystemExit(130)
    return answer


def _sort_choices() -> list[questionary.Choice]:
    return [
        questionary.Choice("Biggest size", value=SortCriterion.BIGGEST_SIZE),
        questionary.Choice("Latest", value=SortCriterion.LATEST),
        questionary.Choice("Most downloaded", value=SortCriterion.MOST_DOWNLOADED),
    ]


def _quality_choices(configured: list[str]) -> list[str]:
    choices = [BEST]
    for label in configured:
        if label not in choices:
            choices.append(label)
    return choices


def _category_summary(plan: ResolvedPlan) -> None:
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
    console.print(
        f"Source: [bold]{plan.catalog.site_id}[/bold] | "
        f"Quality: [bold]{plan.quality or BEST}[/bold] | "
        f"Sort: [bold]{plan.sort.value}[/bold] | "
        f"Items: [bold]{plan.total}[/bold]"
    )


def _ask_ranges(services: Services) -> RangeSelection:
    defaults = RangeSelection.from_config(services.config)
    values = {}
    for key, label, default in (
        ("episodes", "Episode range", defaults.episodes),
        ("ovas", "OVA range", defaults.ovas),
        ("movies", "Movie range", defaults.movies),
        ("specials", "Special range", defaults.specials),
    ):
        answer = _ask(questionary.text(f"{label} (e.g. 1-12, or 0 for none):", default=default))
        values[key] = str(answer).strip()
    return RangeSelection(**values)


def _validate_url(value: str) -> bool | str:
    text = value.strip()
    if not text:
        return "Enter a series URL."
    if not text.startswith(("http://", "https://")):
        return "The URL must start with http:// or https://."
    return True


def run_wizard(services: Services) -> WizardResult:
    """Prompt the user for a full retrieval plan."""

    series_url = str(_ask(questionary.text("Anime series URL:", validate=_validate_url))).strip()

    adapter = services.registry.resolve_for_url(series_url)
    metadata = adapter.get_site_metadata()
    console.print(f"Detected adapter: [bold]{metadata.display_name}[/bold] ({metadata.id})")

    catalog = adapter.resolve_series_catalog(series_url)
    console.print(
        "Found: "
        + " | ".join(
            f"{catalog.count(category)} {category.display_name}" for category in CATEGORY_ORDER
        )
    )

    ranges = _ask_ranges(services)
    quality_choice = str(
        _ask(
            questionary.select(
                "Preferred quality:",
                choices=_quality_choices(list(services.config.media_selection.preferred_qualities)),
            )
        )
    )
    sort_choice = _ask(
        questionary.select(
            "Sort criterion:",
            choices=_sort_choices(),
            default=services.config.media_selection.sort_criterion,
        )
    )

    plan = services.resolve_plan(
        series_url,
        ranges=ranges,
        quality=None if quality_choice == BEST else quality_choice,
        sort=sort_choice,  # type: ignore[arg-type]
    )
    _category_summary(plan)

    action = Action(
        str(
            _ask(
                questionary.select(
                    "Action:",
                    choices=[questionary.Choice(item.value, value=item.value) for item in Action],
                )
            )
        )
    )

    if not bool(_ask(questionary.confirm("Proceed with this plan?", default=True))):
        raise SystemExit(1)
    return WizardResult(plan=plan, action=action)


def run_interactive(services: Services) -> int:
    """Run the wizard, then perform the chosen action. Returns an exit code."""

    try:
        result = run_wizard(services)
    except ManjiError as error:
        console.print(f"[red]error:[/red] {error}")
        return error.exit_code

    if result.action is Action.EXPORT:
        links, manifest, warnings = services.export(result.plan)
        console.print(f"Wrote {links}")
        if manifest is not None:
            console.print(f"Wrote {manifest}")
        for warning in warnings:
            console.print(f"[yellow]warning:[/yellow] {warning}")
        return 0

    stop_event = threading.Event()
    report = services.retrieve(result.plan, stop_event=stop_event)
    for entry, message in report.failures:
        console.print(f"[red]failed[/red] {entry.item.title}: {message}")
    console.print(f"Downloaded {report.downloaded} item(s); skipped {report.skipped}.")
    return 0 if report.ok else 6
