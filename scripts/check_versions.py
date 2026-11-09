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
