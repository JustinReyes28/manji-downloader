# Development Phases

This directory replaces the single implementation plan with five incremental phases. Work through them in order; do not start the next phase until the current phase's acceptance criteria pass.

## Rules

- One phase at a time. Keep the diff reviewable.
- Run the phase's verification commands before moving on.
- Commit at the end of each phase with a `phase N:` prefix.
- Update the status in this file when a phase is complete.
- If a phase reveals a needed design change, update the relevant spec in the repository root before changing code.

## Toolchain

- Python 3.12+ (3.14 is installed locally).
- `uv` for environments, dependencies, locking, and command execution.
- `hatchling` for packaging, `ruff` for lint/format, `mypy` for type checking, `pytest` for tests.
- Runtime libraries: `httpx`, `pydantic`, `PyYAML`, `protego`, `typer`, `rich`, `questionary`.
- Test libraries: `pytest`, `pytest-cov`, `pytest-httpserver`, `respx`.
- Node.js 20+ and npm for the npm launcher and packaging tests (Node 25 / npm 11 are installed locally).
- PyInstaller for standalone binaries in Phase 5.

## Phase map

| Phase | Focus | Depends on | Status |
| --- | --- | --- | --- |
| [1. Foundation & Contracts](phase-1-foundation.md) | Python package, domain models, adapter protocol, CLI skeleton, CI | — | Complete |
| [2. Configuration & Selection](phase-2-config-and-selection.md) | YAML/TOML config, validation, ranges, quality and sorting | Phase 1 | Complete |
| [3. Compliance HTTP & Mock Adapters](phase-3-compliance-http.md) | Rate limiter, robots.txt, Retry-After, challenge halting, redaction, fixtures | Phase 2 | Complete |
| [4. Retrieval Pipeline](phase-4-retrieval-pipeline.md) | Downloader, resume, `links.txt`, manifests, filename templates, sidecars | Phase 3 | Complete |
| [5. CLI Integration & Release](phase-5-integration-and-release.md) | Full commands, wizard, end-to-end tests, npm/PyPI packaging, docs, PR | Phase 4 | Complete |

## Post-Phase 5 status

- **npm is published.** `0.1.0` shipped on 2026-11-09 and is installable with `npx manji-downloader`. Releases are tag-driven through `.github/workflows/release.yml`; see [docs/PUBLISHING.md](../PUBLISHING.md).
- **`0.1.1` is prepared but not released.** It moves npm publishing to trusted publishing (OIDC) and enables the PyPI job. It needs two browser-only, 2FA-gated setup steps (npm trusted publishers, PyPI publisher) before tagging.

## Remaining blocker

- **No real site adapter can be implemented yet.** A site must be designated and its approved access method documented (API/ToS, auth mode, robots/rate-limit notes). Until then, only synthetic test adapters are in scope, and `manji adapters list` reports no adapters.
