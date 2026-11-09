# Phase 2 — Configuration & Selection

**Status:** Not started
**Depends on:** Phase 1
**Unlocks:** Phase 3
**Commit checkpoint:** `phase 2: configuration and selection`

## Goal

Load and validate the documented YAML/TOML configuration with Pydantic, then implement the deterministic range, quality, container, and sorting logic that drives every retrieval.

## Deliverables

- [ ] `src/manji/config/` models, loader, path helpers, and env expansion.
- [ ] `manji-config.example.yaml` and `manji-config.example.toml`.
- [ ] `src/manji/selection/ranges.py`.
- [ ] `src/manji/selection/quality.py` and `selector.py`.
- [ ] Unit tests for both feature areas.
- [ ] README/CONFIGURATION updated if any behavior is clarified.

## Configuration

Mirror `CONFIGURATION.md` exactly: `version`, `network`, `site_adapters`, `media_selection`, `rate_limits`, `cache`, `storage`, `logging`.

Use Pydantic v2 models:

- `model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)`.
- `Literal["1.0"]` for the version.
- `StrEnum` models for auth mode, output mode, conflict resolution, sort criterion, and log level.
- `Field(ge=1.0)` for delays, `Field(ge=1, le=2)` for per-domain concurrency.
- `respect_robots_txt: Literal[True] = True`, so disabling it fails validation.
- Defaults exactly as documented.

Search order:

1. `--config <path>`
2. `./manji-config.yaml`
3. `./manji-config.toml`
4. per-OS user config directory (`~/.config/manji/config.yaml` or `%APPDATA%\ManjiDownloader\config.yaml`)

Rules:

- If both local YAML and TOML exist, return a clear error asking for `--config`.
- Parse YAML with `yaml.safe_load` and TOML with `tomllib`.
- Expand only `${ENV_NAME}` in string values; a missing variable is an error. Never include resolved values in errors or logs.
- Allow tests to inject the working directory, user config directory, and environment lookup.
- Validate cookie files exist and are `0600` on POSIX; return a warning on Windows.
- Expand `~` for validation and runtime paths.
- Return loaded path and warnings alongside the config.

Example configs must be loadable in tests with the API-key environment variables set. They are documentation, not a live-site configuration.

## Range parser

`parse_range(spec: str, total: int) -> tuple[int, ...]`:

- Accept `1-12`, `5-5`, `5`, comma lists, whitespace around segments, and `0` meaning none.
- Preserve input order and deduplicate.
- Reject empty segments, non-numeric values, negatives, inverted ranges, out-of-bounds indexes, and `0` mixed with other segments.
- `total == 0` allows only `0`.
- Raise `RangeParseError` with the failing segment.

## Quality, container, and sort engine

- Parse `1080p`, `720p`, `480p`, `2160p`, `4k`, and numeric heights; unknown labels rank below known ones.
- Select by `preferred_qualities` order. If none match, `best` chooses the highest height; otherwise raise `NoQualityMatchError` listing available qualities.
- Apply `preferred_formats` as a tie-breaker, not a hard filter.
- Sort by `biggest_size`, `latest`, or `most_downloaded`.
- Deterministic tie-breakers: preferred container, newest upload, largest size, highest download count, variant ID.
- `--quality` moves the chosen value to the front of the configured list; `best` selects the highest available.

## Tests

- Config: defaults, YAML/TOML parity, precedence, both-local-files error, env expansion, missing env, invalid values, `~` expansion, cookie permission check (skip on Windows), and unknown-key rejection.
- Range: every accepted and rejected case, deduplication, bounds, and `0`.
- Selection: each quality fallback path, `best`, unknown labels, each sort criterion, and every tie-breaker.
- Example configs load successfully in both formats.

## Acceptance

```bash
uv run pytest tests/unit/config tests/unit/selection
uv run pytest
uv run mypy src
uv run ruff check .
uv run manji version
```

Expected: all tests pass and both example configs validate.

## Out of scope

- Network requests.
- Adapters, downloads, and CLI retrieval commands.

## Handoff

Phase 3 consumes the validated config to configure timeouts, retries, rate limits, user agent, and site-specific delays. Do not duplicate config parsing in adapters.
