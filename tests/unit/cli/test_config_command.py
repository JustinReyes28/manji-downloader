from __future__ import annotations

import pytest
from typer.testing import CliRunner

from manji.cli.app import app

pytestmark = pytest.mark.unit

runner = CliRunner()


def test_config_option_missing_file_exits_two(tmp_path) -> None:
    result = runner.invoke(app, ["--config", str(tmp_path / "absent.yaml"), "version"])
    assert result.exit_code == 2


def test_config_option_valid_file(tmp_path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("version: '1.0'\nnetwork:\n  timeout_seconds: 5\n", encoding="utf-8")
    result = runner.invoke(app, ["--config", str(path), "version"])
    assert result.exit_code == 0, result.output


def test_config_option_invalid_exits_two(tmp_path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("version: '1.0'\nnetwork:\n  respect_robots_txt: false\n", encoding="utf-8")
    result = runner.invoke(app, ["--config", str(path), "version"])
    assert result.exit_code == 2
