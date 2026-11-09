"""Packaging tests: npm manifest shape, platform matrix, and version sync."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.build_platform_package import PLATFORMS, build_platform
from scripts.check_versions import check, check_optional_dependencies, python_version

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[3]


def root_package() -> dict[str, object]:
    return json.loads((ROOT / "package.json").read_text(encoding="utf-8"))


def test_root_package_ships_only_launcher_files() -> None:
    payload = root_package()
    assert payload["files"] == ["bin/manji.js", "README.md", "LICENSE"]
    assert "postinstall" not in payload.get("scripts", {})
    assert payload["bin"]["manji"] == "bin/manji.js"


def test_optional_dependencies_cover_every_platform() -> None:
    optional = root_package()["optionalDependencies"]
    assert isinstance(optional, dict)
    assert set(optional) == {f"manji-downloader-{name}" for name in PLATFORMS}


def test_versions_are_in_sync() -> None:
    assert check() == []


def _write_package(path: Path, optional: object, version: str = "0.1.1") -> Path:
    target = path / "package.json"
    target.write_text(
        json.dumps(
            {"name": "manji-downloader", "version": version, "optionalDependencies": optional}
        ),
        encoding="utf-8",
    )
    return target


def test_optional_dependencies_pins_are_checked(tmp_path: Path) -> None:
    pinned = {f"manji-downloader-{name}": "0.1.1" for name in PLATFORMS}
    manifest = _write_package(tmp_path, pinned)
    assert check_optional_dependencies(manifest, "0.1.1") == []


def test_stale_optional_dependency_pin_is_reported(tmp_path: Path) -> None:
    pinned = {f"manji-downloader-{name}": "0.1.1" for name in PLATFORMS}
    pinned["manji-downloader-linux-x64"] = "0.1.0"
    manifest = _write_package(tmp_path, pinned)
    problems = check_optional_dependencies(manifest, "0.1.1")
    assert len(problems) == 1
    assert "manji-downloader-linux-x64" in problems[0]
    assert "0.1.0" in problems[0]


def test_missing_platform_in_optional_dependencies_is_reported(tmp_path: Path) -> None:
    pinned = {f"manji-downloader-{name}": "0.1.1" for name in PLATFORMS}
    del pinned["manji-downloader-darwin-arm64"]
    manifest = _write_package(tmp_path, pinned)
    problems = check_optional_dependencies(manifest, "0.1.1")
    assert any("missing" in problem and "darwin-arm64" in problem for problem in problems)


def test_unknown_platform_in_optional_dependencies_is_reported(tmp_path: Path) -> None:
    pinned = {f"manji-downloader-{name}": "0.1.1" for name in PLATFORMS}
    pinned["manji-downloader-plan9-x64"] = "0.1.1"
    manifest = _write_package(tmp_path, pinned)
    problems = check_optional_dependencies(manifest, "0.1.1")
    assert any("unknown" in problem and "plan9" in problem for problem in problems)


def test_missing_optional_dependencies_mapping_is_reported(tmp_path: Path) -> None:
    target = tmp_path / "package.json"
    target.write_text(
        json.dumps({"name": "manji-downloader", "version": "0.1.1"}), encoding="utf-8"
    )
    problems = check_optional_dependencies(target, "0.1.1")
    assert problems and "no optionalDependencies" in problems[0]


def test_platform_matrix_matches_documented_targets() -> None:
    assert set(PLATFORMS) == {
        "win32-x64",
        "darwin-x64",
        "darwin-arm64",
        "linux-x64",
        "linux-arm64",
    }
    assert PLATFORMS["win32-x64"]["binary"] == "manji.exe"
    for name, spec in PLATFORMS.items():
        if name != "win32-x64":
            assert spec["binary"] == "manji"


def test_generated_platform_package_metadata(tmp_path: Path) -> None:
    binary = tmp_path / "manji.exe"
    binary.write_bytes(b"fake-binary")
    manifest_path = build_platform("win32-x64", binary, tmp_path / "npm", python_version())
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["name"] == "manji-downloader-win32-x64"
    assert payload["os"] == ["win32"]
    assert payload["cpu"] == ["x64"]
    assert payload["version"] == python_version()
    assert (manifest_path.parent / "manji.exe").read_bytes() == b"fake-binary"


def test_platform_package_rejects_unknown_name(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        build_platform("plan9-x64", tmp_path / "x", tmp_path, "0.1.0")
