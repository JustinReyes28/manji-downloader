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


def test_help_without_arguments() -> None:
    result = runner.invoke(app, [])
    assert "Usage" in result.output


def test_error_rendering() -> None:
    from manji.cli.app import _exit_with_error

    with pytest.raises(SystemExit) as excinfo:
        _exit_with_error(UnsupportedSiteError("no adapter"))
    assert excinfo.value.code == 3
