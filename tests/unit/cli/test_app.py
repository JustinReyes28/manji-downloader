from __future__ import annotations

import pytest
from typer.testing import CliRunner

from manji.adapters.registry import get_registry
from manji.cli.app import app
from manji.errors import UnsupportedSiteError
from tests.helpers import StubAdapter, make_metadata

pytestmark = pytest.mark.unit

runner = CliRunner()


def test_version_output() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.output.startswith("manji ")


def test_adapters_list_empty() -> None:
    result = runner.invoke(app, ["adapters", "list"])
    assert result.exit_code == 0
    assert "No adapters registered." in result.output


def test_adapters_list_with_adapter() -> None:
    get_registry().register(StubAdapter(make_metadata()))
    result = runner.invoke(app, ["adapters", "list"])
    assert result.exit_code == 0
    assert "mock-json" in result.output


def test_no_arguments_without_tty_is_a_usage_error() -> None:
    """Phase 5: bare ``manji`` launches the wizard, so non-TTY input is a usage error."""

    result = runner.invoke(app, [])
    assert result.exit_code == 2
    assert "not a terminal" in result.output


def test_help_flag_shows_usage() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.output


def test_supported_commands_are_listed() -> None:
    result = runner.invoke(app, ["--help"])
    for command in ("adapters", "info", "retrieve", "export-links", "version"):
        assert command in result.output


def test_error_rendering() -> None:
    from manji.cli.app import _exit_with_error

    with pytest.raises(SystemExit) as excinfo:
        _exit_with_error(UnsupportedSiteError("no adapter"))
    assert excinfo.value.code == 3
