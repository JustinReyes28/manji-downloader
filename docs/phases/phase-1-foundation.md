# Phase 1 — Foundation & Contracts

**Status:** Not started
**Depends on:** none
**Unlocks:** Phase 2
**Commit checkpoint:** `phase 1: foundation and contracts`

## Goal

Create an installable Python package with the public domain contracts, a working CLI skeleton, and CI, so every later phase has a stable base.

## Prerequisite: Python and uv

Python 3.14 and `uv` are installed locally. Verify:

```powershell
python --version
uv --version
```

No global packages need to be installed; `uv sync` creates the virtual environment and installs the dev tools.

## Deliverables

- [ ] `pyproject.toml` with a `hatchling` build backend and `manji` console script.
- [ ] `uv.lock` and `.python-version`.
- [ ] `src/manji/` package with `__init__.py`, `__main__.py`, and version metadata.
- [ ] `src/manji/domain/catalog.py` domain models.
- [ ] `src/manji/adapters/base.py` and `registry.py` adapter protocol and registry.
- [ ] `src/manji/errors.py` exception hierarchy.
- [ ] `src/manji/cli/` Typer app with `version` and `adapters list`.
- [ ] `tests/` skeleton with pytest configuration.
- [ ] `ruff`, `mypy`, `pytest`, and coverage configuration.
- [ ] `Makefile` targets for sync/test/lint/format/typecheck/build.
- [ ] `.github/workflows/ci.yml`.
- [ ] `AGENTS.md` and README updated with Python commands.

## Detailed scope

### Package and entry point

`pyproject.toml` must define:

```toml
[project]
name = "manji-downloader"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "httpx>=0.27",
  "pydantic>=2.8",
  "PyYAML>=6.0",
  "protego>=0.3",
  "typer>=0.12",
  "rich>=13.7",
  "questionary>=2.0",
]

[project.scripts]
manji = "manji.cli.app:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Use `src/` layout with package data `src/manji/py.typed`. Build with `uv build`.

Put development tools in a `dev` dependency group: `pytest`, `pytest-cov`, `pytest-httpserver`, `respx`, `ruff`, `mypy`, and `types-PyYAML`. `uv sync` installs this group by default.

`src/manji/version.py` exposes `__version__` from installed package metadata (fallback `0.0.0+dev`) and optional `COMMIT`/`BUILD_DATE` environment values.

`src/manji/__main__.py` calls `manji.cli.app:main` so `python -m manji` works.

Exit codes:

- 0 success
- 1 generic
- 2 usage/config
- 3 unsupported site
- 4 access/challenge
- 5 network/rate limit
- 6 partial failure

Typer/Click handles usage errors as exit code 2. Map custom exceptions in the CLI entry point.

### Domain contracts

`src/manji/domain/catalog.py`:

```python
class Category(StrEnum):
    EPISODES = "episodes"
    OVAS = "ovas"
    MOVIES = "movies"
    SPECIALS = "specials"

@dataclass(frozen=True, slots=True)
class MediaItem:
    id: str
    number: int
    title: str
    url: str

@dataclass(frozen=True, slots=True)
class MediaVariant:
    id: str
    quality: str
    container: str
    size_bytes: int
    uploaded_at: datetime | None
    download_count: int
    url: str

@dataclass(frozen=True, slots=True)
class SeriesCatalog:
    title: str
    site_id: str
    source_url: str
    episodes: tuple[MediaItem, ...] = ()
    ovas: tuple[MediaItem, ...] = ()
    movies: tuple[MediaItem, ...] = ()
    specials: tuple[MediaItem, ...] = ()
```

Add helpers for category order, display names, `items(category)`, and counts.

### Adapter protocol and registry

`src/manji/adapters/base.py`:

```python
class SourceAdapter(Protocol):
    def get_site_metadata(self) -> SiteMetadata: ...
    def can_handle(self, url: str) -> bool: ...
    def validate_access(self, target: Target) -> None: ...
    def resolve_series_catalog(self, series_url: str) -> SeriesCatalog: ...
    def resolve_episode_variants(self, item: MediaItem) -> tuple[MediaVariant, ...]: ...
```

Include `SiteMetadata` (ID, display name, domains, default minimum delay, auth mode, URL patterns), `Target`, and `AuthMode`.

`src/manji/adapters/registry.py`:

- `register(adapter)` rejects empty/duplicate IDs and invalid metadata.
- `resolve_for_url(url)` validates HTTP/HTTPS and returns the first matching adapter.
- `list_supported_sites()` returns a deterministic tuple.
- Unsupported URLs raise `UnsupportedSiteError` with a clear message.

`src/manji/errors.py` defines `ManjiError` and subclasses:
`UnsupportedSiteError`, `AccessNotConfiguredError`, `AccessDeniedError`, `ChallengeDetectedError`, `RateLimitedError`, `ConfigError`, `RangeParseError`, `SelectionError`, `NoVariantsError`, `NoQualityMatchError`, `DownloadError`, `RobotsDisallowedError`, `RobotsUnavailableError`, `NetworkError`, `HTTPError`.

### CLI skeleton

- Typer app with a global `--config` option (unused until Phase 2) and a version flag.
- `manji version` prints version, commit, and build date.
- `manji adapters list` prints a Rich table; with no adapters, print `No adapters registered.`
- No args prints help; the interactive wizard arrives in Phase 5.
- The CLI entry point catches `ManjiError` and maps it to the exit codes above.

### Tooling and CI

- `ruff` for lint and formatting, line length 100, target `py312`.
- `mypy` with strict settings for `src/manji`, `warn_unused_ignores`, and `disallow_untyped_defs`. Add per-module `ignore_missing_imports` overrides only if upstream stubs are unavailable (for example `protego` or `questionary`).
- `pytest` with markers `unit`, `integration`, `compliance`, and coverage reporting.
- `Makefile`: `sync`, `test`, `lint`, `format`, `typecheck`, `build`, `run`.
- `.github/workflows/ci.yml`:
  - checkout
  - `astral-sh/setup-uv`
  - `uv sync --frozen`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src`
  - `uv run pytest`
  - matrix: Python 3.12, 3.13, 3.14

Update README and `AGENTS.md` with:

```bash
uv sync
uv run manji version
uv run manji adapters list
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

## Tests

- `tests/unit/domain/`: category order, display names, `items()`, counts.
- `tests/unit/adapters/`: registration, duplicate rejection, URL routing, unsupported URL, deterministic listing.
- `tests/unit/cli/`: `version` output and empty `adapters list` using Typer's `CliRunner`.

## Acceptance

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv run manji version
uv run manji adapters list
uv build
```

Expected:

- Lint, format, type checking, and tests are clean.
- `version` prints build metadata.
- `adapters list` prints `No adapters registered.`
- A wheel and sdist are produced.
- No network code exists yet.

## Out of scope

- Configuration loading.
- HTTP client, rate limiting, or robots.txt.
- Real or mock adapters.
- Downloading or exporting.

## Handoff

Phase 2 adds the config loader and selection engine on top of these contracts. Do not change the public names in `manji.domain` or `manji.adapters` without updating the specs and later phase documents.
