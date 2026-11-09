"""Unit tests for the interactive wizard flow using stubbed prompts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from manji.app import RangeSelection, ResolvedPlan, Services
from manji.cli import wizard
from manji.domain import Category, MediaItem, MediaVariant, SeriesCatalog
from manji.export.links import SelectedVariant
from manji.selection.selector import SortCriterion

pytestmark = pytest.mark.unit


def plan() -> ResolvedPlan:
    item = MediaItem(id="e1", number=1, title="Episode 1", url="https://x/1")
    variant = MediaVariant(
        id="v1",
        quality="1080p",
        container="mkv",
        size_bytes=10,
        uploaded_at=datetime(2024, 1, 1, tzinfo=UTC),
        download_count=1,
        url="https://x/m.mkv",
    )
    catalog = SeriesCatalog(
        title="Example",
        site_id="mock_json",
        source_url="https://x/series",
        episodes=(item,),
    )
    return ResolvedPlan(
        catalog=catalog,
        selection=(SelectedVariant(Category.EPISODES, item, variant),),
        quality="1080p",
        sort=SortCriterion.BIGGEST_SIZE,
    )


class FakeAdapter:
    def get_site_metadata(self) -> Any:
        from manji.adapters import AuthMode, SiteMetadata

        return SiteMetadata(
            id="mock_json",
            display_name="Mock JSON",
            domains=("mock.test",),
            default_min_request_delay_seconds=1.0,
            auth_mode=AuthMode.NONE,
        )

    def resolve_series_catalog(self, series_url: str) -> SeriesCatalog:
        return plan().catalog


class FakeServices:
    def __init__(self) -> None:
        from manji.config.models import AppConfig

        self.config = AppConfig()
        self.registry = type("Reg", (), {"resolve_for_url": lambda self, url: FakeAdapter()})()
        self.resolved: dict[str, Any] = {}
        self.exported = False

    def resolve_plan(self, series_url: str, **kwargs: Any) -> ResolvedPlan:
        self.resolved = kwargs
        return plan()

    def export(self, resolved: ResolvedPlan, **kwargs: Any):
        self.exported = True
        from pathlib import Path

        return Path("links.txt"), None, ()


def _scripted(monkeypatch: pytest.MonkeyPatch, answers: list[Any]) -> None:
    queue = list(answers)

    class Prompt:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args

        def ask(self) -> Any:
            return queue.pop(0)

    monkeypatch.setattr(wizard.questionary, "text", lambda *a, **k: Prompt())
    monkeypatch.setattr(wizard.questionary, "select", lambda *a, **k: Prompt())
    monkeypatch.setattr(wizard.questionary, "confirm", lambda *a, **k: Prompt())


def test_wizard_collects_plan_and_action(monkeypatch: pytest.MonkeyPatch) -> None:
    services = FakeServices()
    _scripted(
        monkeypatch,
        [
            "https://mock.test/series/x",  # URL
            "1-1",  # episodes
            "0",  # ovas
            "0",  # movies
            "0",  # specials
            "1080p",  # quality
            SortCriterion.LATEST,  # sort
            wizard.Action.EXPORT.value,  # action
            True,  # confirm
        ],
    )
    result = wizard.run_wizard(services)  # type: ignore[arg-type]
    assert result.plan.total == 1
    assert result.action is wizard.Action.EXPORT
    assert services.resolved["quality"] == "1080p"
    assert services.resolved["sort"] is SortCriterion.LATEST


def test_best_quality_maps_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    services = FakeServices()
    _scripted(
        monkeypatch,
        [
            "https://mock.test/series/x",
            "1-1",
            "0",
            "0",
            "0",
            wizard.BEST,
            SortCriterion.BIGGEST_SIZE,
            wizard.Action.EXPORT.value,
            True,
        ],
    )
    wizard.run_wizard(services)  # type: ignore[arg-type]
    assert services.resolved["quality"] is None


def test_declining_confirmation_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    services = FakeServices()
    _scripted(
        monkeypatch,
        [
            "https://mock.test/series/x",
            "1-1",
            "0",
            "0",
            "0",
            "1080p",
            SortCriterion.LATEST,
            wizard.Action.DOWNLOAD.value,
            False,
        ],
    )
    with pytest.raises(SystemExit) as excinfo:
        wizard.run_wizard(services)  # type: ignore[arg-type]
    assert excinfo.value.code == 1


def test_run_interactive_export_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        wizard, "run_wizard", lambda services: wizard.WizardResult(plan(), wizard.Action.EXPORT)
    )
    services = FakeServices()
    assert wizard.run_interactive(services) == 0  # type: ignore[arg-type]
    assert services.exported


def test_run_interactive_reports_manji_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from manji.errors import ConfigError

    def boom(_services: object) -> wizard.WizardResult:
        raise ConfigError("bad config")

    monkeypatch.setattr(wizard, "run_wizard", boom)
    assert wizard.run_interactive(FakeServices()) == 2  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://ok.test/x", True),
        ("http://ok.test/x", True),
        ("", "Enter a series URL."),
        ("ftp://nope", "The URL must start with http:// or https://."),
    ],
)
def test_url_validation(value: str, expected: bool | str) -> None:
    assert wizard._validate_url(value) == expected


def test_range_selection_maps_categories() -> None:
    selection = RangeSelection("1-2", "3", "4", "5")
    assert selection.as_dict() == {
        Category.EPISODES: "1-2",
        Category.OVAS: "3",
        Category.MOVIES: "4",
        Category.SPECIALS: "5",
    }


def test_range_selection_from_config() -> None:
    from manji.config.models import AppConfig

    config = AppConfig()
    selection = RangeSelection.from_config(config)
    assert selection.episodes == "1-12"
    assert selection.ovas == "0"


def test_services_close_only_closes_owned_clients() -> None:
    from manji.config import load_config

    class StubClient:
        closed = False

        def close(self) -> None:
            self.closed = True

    client = StubClient()
    services = Services.build(
        load_config(cwd=None, env={}),
        client=client,
        configure=False,  # type: ignore[arg-type]
    )
    services.close()
    assert client.closed is False
