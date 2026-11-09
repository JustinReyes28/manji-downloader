"""Generate platform npm packages from PyInstaller build artifacts."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tomllib
from pathlib import Path

PLATFORMS: dict[str, dict[str, object]] = {
    "win32-x64": {"os": "win32", "cpu": "x64", "binary": "manji.exe"},
    "darwin-x64": {"os": "darwin", "cpu": "x64", "binary": "manji"},
    "darwin-arm64": {"os": "darwin", "cpu": "arm64", "binary": "manji"},
    "linux-x64": {"os": "linux", "cpu": "x64", "binary": "manji"},
    "linux-arm64": {"os": "linux", "cpu": "arm64", "binary": "manji"},
}


def project_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def build_platform(
    name: str, binary: Path, output_root: Path, version: str, *, dry_run: bool = False
) -> Path:
    spec = PLATFORMS[name]
    package_dir = output_root / name
    manifest = {
        "name": f"manji-downloader-{name}",
        "version": version,
        "description": f"Prebuilt manji binary for {name}.",
        "license": "MIT",
        "repository": {
            "type": "git",
            "url": "git+https://github.com/JustinReyes28/manji-downloader.git",
        },
        "homepage": "https://github.com/JustinReyes28/manji-downloader#readme",
        "os": [spec["os"]],
        "cpu": [spec["cpu"]],
        "files": [str(spec["binary"])],
        "publishConfig": {"access": "public"},
    }
    if dry_run:
        print(json.dumps(manifest, indent=2))
        return package_dir / "package.json"
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "package.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    destination = package_dir / str(spec["binary"])
    shutil.copy2(binary, destination)
    return package_dir / "package.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True, choices=sorted(PLATFORMS))
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("npm/platforms"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.dry_run and not args.binary.is_file():
        print(f"binary not found: {args.binary}", file=sys.stderr)
        return 1
    manifest = build_platform(
        args.platform,
        args.binary,
        args.output,
        project_version(args.root),
        dry_run=args.dry_run,
    )
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
