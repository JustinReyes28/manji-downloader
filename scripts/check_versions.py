"""Verify the Python and npm package versions stay in sync."""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = {
    "win32-x64": ("win32", "x64", "manji.exe"),
    "darwin-x64": ("darwin", "x64", "manji"),
    "darwin-arm64": ("darwin", "arm64", "manji"),
    "linux-x64": ("linux", "x64", "manji"),
    "linux-arm64": ("linux", "arm64", "manji"),
}


def python_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        document = tomllib.load(handle)
    return str(document["project"]["version"])


def package_version(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload["version"])


def check() -> list[str]:
    expected = python_version()
    problems: list[str] = []

    root_package = ROOT / "package.json"
    if root_package.is_file():
        actual = package_version(root_package)
        if actual != expected:
            problems.append(f"package.json is {actual}, expected {expected}")
        problems.extend(check_optional_dependencies(root_package, expected))

    platforms_root = ROOT / "npm" / "platforms"
    if platforms_root.is_dir():
        for directory in sorted(platforms_root.iterdir()):
            manifest = directory / "package.json"
            if not manifest.is_file():
                continue
            actual = package_version(manifest)
            if actual != expected:
                problems.append(f"{manifest.relative_to(ROOT)} is {actual}, expected {expected}")
    return problems


def check_optional_dependencies(path: Path, expected: str) -> list[str]:
    """Verify every platform package is pinned to the release version.

    Without this, a version bump can publish a launcher that still installs the
    previous release's binaries.
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    optional = payload.get("optionalDependencies")
    if not isinstance(optional, dict):
        return [f"{path.name} has no optionalDependencies mapping"]

    problems: list[str] = []
    expected_keys = {f"manji-downloader-{name}" for name in PLATFORMS}
    actual_keys = set(optional)
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        if missing:
            problems.append(f"{path.name} optionalDependencies is missing: {', '.join(missing)}")
        if extra:
            problems.append(f"{path.name} optionalDependencies has unknown: {', '.join(extra)}")

    for name, pinned in sorted(optional.items()):
        if pinned != expected:
            problems.append(f"{path.name} pins {name} at {pinned}, expected {expected}")
    return problems


def main() -> int:
    problems = check()
    if problems:
        for problem in problems:
            print(f"version drift: {problem}", file=sys.stderr)
        return 1
    print(f"versions in sync: {python_version()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
