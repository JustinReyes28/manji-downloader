# Phase 5 — CLI Integration, Packaging & Release

**Status:** Not started
**Depends on:** Phase 4
**Unlocks:** first real adapter work (separate milestone)
**Commit checkpoint:** `phase 5: cli integration, packaging, and end-to-end tests`

## Goal

Wire the core packages into the documented CLI, prove the full flow against mock adapters, package the Python and npm distributions, update documentation, and publish the branch for review.

## Deliverables

- [ ] `src/manji/app.py` dependency wiring and service construction.
- [ ] CLI commands: `info`, `retrieve`, `export-links`.
- [ ] Interactive wizard for `manji` with no arguments.
- [ ] Non-interactive flags and clear non-TTY behavior.
- [ ] End-to-end integration tests.
- [ ] Root `package.json` and `bin/manji.js` npm launcher.
- [ ] npm launcher tests.
- [ ] PyInstaller spec and platform build script.
- [ ] Generated platform npm packages with `os`/`cpu` metadata.
- [ ] Release workflow for PyPI and npm.
- [ ] Version-sync check across Python and npm packages.
- [ ] `PACKAGING.md` documentation.
- [ ] README, AGENTS.md, and ROADMAP status updates.
- [ ] Green CI and a pull request.

## CLI commands

```text
manji [--config path]
manji adapters list
manji info <series-url>
manji retrieve <series-url> --episodes 1-12 --ovas 0 --movies 0 --specials 0 \
  --quality 1080p --sort biggest-size --output-dir ./Anime
manji export-links <series-url> --episodes 1-24 --quality 1080p --sort latest \
  --export-file links.txt
manji version
```

Behavior:

- `info` resolves the catalog and prints category counts, selected items, available qualities, sizes, dates, and counts without downloading.
- `retrieve` resolves variants, selects deterministically, downloads, and writes sidecars.
- `export-links` resolves variants and writes `links.txt` plus the manifest.
- Flags override config; missing values fall back to `media_selection` defaults.
- If stdin is not a TTY and required flags are missing, exit with a clear usage error instead of prompting.
- Exit codes follow Phase 1.

## Interactive wizard

Use `questionary` with Rich output. Prompt for:

1. Series URL.
2. Detected adapter and category counts.
3. Episode, OVA, movie, and special ranges.
4. Quality (or best available).
5. Sort criterion.
6. Action: direct download or export links.

Show the resolved plan before starting. On Ctrl+C, exit cleanly and keep any partial download plus resume metadata so a later run can continue.

## End-to-end tests

- Full mock JSON flow: catalog → select Episodes 1–5 and OVAs 1–1 → 1080p → biggest size → export exactly 6 URLs in order.
- Direct download flow: one episode → atomic file and sidecar.
- HTML mock adapter flow to prove the registry is site-agnostic.
- 429 then success; 403 challenge halts with a handoff message and no retry.
- Redaction checks on CLI output.
- No non-loopback network access.

## Packaging & distribution

- Keep the Python package as the source of truth; the npm launcher contains no site logic.
- Build PyInstaller one-file binaries for `win32-x64`, `darwin-x64`, `darwin-arm64`, `linux-x64`, and `linux-arm64`.
- The root npm package `manji-downloader` ships only `bin/manji.js`, the README, and the license.
- Platform packages `manji-downloader-{platform}-{arch}` contain the binary and declare matching `os`/`cpu` metadata.
- Use `optionalDependencies`, not a `postinstall` download.
- `npx manji-downloader` and `npm install -g manji-downloader` must work. `npm manji-downloader` alone is not a command.
- Publish the Python package with trusted publishing and npm packages with provenance.
- Use `pyproject.toml` as the version source; sync the root and platform npm packages.
- See `PACKAGING.md` for the full release design.

## Documentation

- Replace README quickstart placeholders with Python and npm install commands.
- Update the project status to reflect a working mock-mode core.
- Update AGENTS.md with final commands and the phase workflow.
- Mark MVP progress in ROADMAP.md without claiming a real adapter exists.
- Note that the first real adapter remains blocked on an authorized site and documented access method.
- Publish `PACKAGING.md` and verify the `npx manji-downloader` and `uv tool install manji-downloader` paths.

## Acceptance

```bash
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv run manji version
uv run manji adapters list
uv build
npm test
npm pack --dry-run
```

Manual checks:

- `manji` with no args shows the wizard.
- `manji adapters list` reports no production adapters until a real one is registered.
- The mock end-to-end tests produce the documented six URLs.
- `node bin/manji.js --version` works with a locally built binary or `MANJI_BINARY` override.
- After publishing, `npx -y manji-downloader@<version> --version` works on each supported OS family.

## Out of scope

- Real site adapters.
- Catalog caching (v0.2).
- Cookie-session loading (schedule before the first authenticated adapter).
- Third-party plugin loading (v1.0; use the `manji.adapters` entry-point group later).
- Windows arm64, 32-bit platforms, and FreeBSD binaries.
- Code signing and macOS notarization (v0.2).

## Release step

1. Ensure CI is green.
2. Push `feat/python-mvp-foundation`.
3. Open a pull request using the repository template.
4. Link the relevant phase checklists and note the real-adapter blocker.
5. After merge and tagging, publish PyPI and npm, then smoke-test `npx -y manji-downloader@<version> --version`.
