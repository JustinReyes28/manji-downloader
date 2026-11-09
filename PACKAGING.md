# Manji Downloader — Packaging & Distribution

## Channels

| Channel | Command | Runtime |
| --- | --- | --- |
| PyPI | `uv tool install manji-downloader` or `pipx install manji-downloader` | Python 3.12+ |
| npm | `npx manji-downloader` or `npm install -g manji-downloader` | Node.js 20+ |
| GitHub Releases | Download a standalone archive | None |

`npm manji-downloader` on its own is not a command. Use `npx manji-downloader` for a one-off run, or `npm install -g manji-downloader` and then call `manji`.

## Design

- The Python package is the source of truth. The site adapters, filtering, HTTP compliance, and downloader live only in Python.
- The npm package is a thin launcher. It never contains site logic.
- Standalone binaries are built with PyInstaller (`--onefile`) in CI for each supported platform.
- Platform binaries ship as separate npm packages referenced through `optionalDependencies`. npm installs only the package matching the current `os` and `cpu`.
- There is no `postinstall` download step. This keeps `npx` working behind proxies and avoids executing arbitrary install-time network code.
- The root npm package contains only `bin/manji.js`, the README, the license, and package metadata.

## Platform matrix

| npm package | `os` | `cpu` | Binary |
| --- | --- | --- | --- |
| `manji-downloader-win32-x64` | `win32` | `x64` | `manji.exe` |
| `manji-downloader-darwin-x64` | `darwin` | `x64` | `manji` |
| `manji-downloader-darwin-arm64` | `darwin` | `arm64` | `manji` |
| `manji-downloader-linux-x64` | `linux` | `x64` | `manji` |
| `manji-downloader-linux-arm64` | `linux` | `arm64` | `manji` |

Windows arm64, 32-bit platforms, and FreeBSD are not supported initially.

Approximate sizes:

- Root npm package: under 50 KB.
- Each platform package: 25–50 MB, driven by the bundled Python runtime and dependencies.
- `npx manji-downloader` therefore downloads roughly 30–50 MB on first use.

## How `npx` works

1. npm downloads the root `manji-downloader` package.
2. npm installs the matching optional platform package.
3. `bin/manji.js` resolves `<platform-package>/package.json`, locates the bundled binary, and spawns it with the user's arguments and inherited stdio.
4. The launcher exits with the child's exit code. On POSIX it sets the executable bit before spawning.

If no platform package exists, the launcher prints a clear message and suggests `uv tool install manji-downloader`.

## Versioning

- `pyproject.toml` holds the single source-of-truth version.
- The Python package, root npm package, and every platform npm package must share the same version.
- Release tags use `vX.Y.Z`.
- CI fails if the versions differ:

  ```bash
  uv run python scripts/check_versions.py
  ```

## Building binaries

```bash
uv sync --group build
uv run pyinstaller manji.spec --distpath dist --workpath build/pyinstaller
```

The spec file (`manji.spec`) builds a one-file console binary named `manji`
(`manji.exe` on Windows). It bundles `manji` submodules plus the runtime
dependencies (`yaml`, `protego`, `questionary`, `typer`, `rich`).

Generate a platform npm package from a built binary:

```bash
uv run python scripts/build_platform_package.py \
  --platform win32-x64 \
  --binary dist/manji.exe \
  --output npm/platforms
```

The script copies the binary and writes a `package.json` with the matching
`os`/`cpu` metadata and the version from `pyproject.toml`.

- Build on each target OS/architecture; do not cross-compile.
- Build binaries with the newest Python version supported by PyInstaller and pin it in the release workflow. The Python package itself still supports 3.12+.
- Build Linux binaries in a manylinux-compatible container or the oldest supported distribution to avoid glibc mismatches.
- Set `MACOSX_DEPLOYMENT_TARGET` and build on the oldest supported macOS runner for broad compatibility.
- The release workflow uploads `dist/manji` or `dist/manji.exe` as artifacts.
- Binaries and generated platform packages are never committed.
- Do not publish the root npm package until every platform package exists; the release workflow enforces that order.
- PyInstaller one-file builds extract to a temporary directory at startup. Code signing and notarization are follow-up hardening items.

## Release workflow

`.github/workflows/release.yml` is triggered by a `v*` tag:

1. Run the Python test, lint, type-check, and version-sync checks.
2. Build PyInstaller binaries for the platform matrix.
3. Build the Python wheel and sdist; publish to PyPI using trusted publishing.
4. Generate `npm/platforms/<platform>/package.json` for each artifact and copy the binary next to it.
5. Publish each platform package with `npm publish --access public --provenance`.
6. Publish the root `manji-downloader` package.
7. Smoke-test `npx -y manji-downloader@<version> --version` on at least one runner per OS family.

## Security

- No install-time binary downloads.
- Publish npm packages with provenance from GitHub Actions.
- Publish Python artifacts with PyPI trusted publishing.
- Publish SHA-256 checksums for GitHub Release archives.
- Code signing (Windows Authenticode) and macOS notarization are planned before v1.0.
- Users should only install the unscoped `manji-downloader` package and verify the repository link.

## Tests

- `npm test` runs `node --test test/npm/wrapper.test.js` and covers launcher resolution, argument forwarding, exit codes, and missing-platform messages.
- `npm pack --dry-run` verifies the root package contains only intended files.
- Install the packed tarball in a temporary directory and run `npx --yes ./manji-downloader-<version>.tgz --version`.
- Run the built binary with `manji version` on every supported OS.
- Verify version sync between `pyproject.toml` and all npm packages.
