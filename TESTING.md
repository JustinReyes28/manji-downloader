# Manji Downloader — Testing Strategy & Quality Assurance

This document defines testing standards, test harnesses, and quality assurance principles for **Manji Downloader**, covering universal multi-site URL routing, interactive episode range parsing, quality/variant sorting, batch link export, and rate-limited catalog resolution.

# 1. Testing Philosophy & Strict Policy

## Strict Constraint: No Live Protected-Site Tests

- **Zero External Network Calls During Testing:** Automated tests for Manji Downloader and its site adapters must never make network requests to live third-party anime sites, streaming platforms, or protected endpoints.
- **Rationale:**
    - Prevents accidental denial-of-service or unwanted load on external servers when testing multi-episode series extraction across multiple site adapters.
    - Eliminates test flakiness caused by external network latency, layout changes, Cloudflare challenges, or transient server issues.
    - Ensures test suites remain completely compliant with third-party Terms of Service.
- **Enforcement:** The test runner executes in an isolated environment where all external network traffic is stubbed or redirected to local mock servers serving synthetic anime series catalogs.

# 2. Unit Testing Scope

Unit tests verify discrete modules in isolation using unit test frameworks and local fixture files for each registered site adapter.

## 2.1 Multi-Site Adapter Registry & URL Router Tests

- Verification that pasted URLs from different supported domains route to the exact corresponding `SourceAdapter` implementation.
- Verification that unrecognized or disabled domains return a clear, actionable `UnsupportedSiteError` without issuing network calls.
- Contract testing ensuring every registered site adapter normalizes its output into the standard `SeriesCatalog` and `MediaVariant` structures.

## 2.2 CLI & Interactive Range Parser Tests

- Validation of episode/OVA/movie/special range expressions:
    - Standard inclusive ranges (e.g., `1-12` resolves to episodes 1 through 12).
    - Single-episode selections (e.g., `1-1` or `5`).
    - Category skip indicator (`0` returns an empty selection list for that category).
    - Rejection of inverted ranges (`12-1`), negative numbers, or out-of-bounds episode indices.
- Validation of `manji` CLI flag overrides vs. interactive prompt inputs.

## 2.3 Variant Filtering & Sorting Engine Tests

- **Quality & Resolution Matching:** Verification that variants across different site adapters are accurately filtered by `1080p`, `720p`, or `480p` tags and fallback order when a target resolution is missing for a specific episode.
- **Sorting Criteria Verification:**
    - `Biggest Size`: Confirms deterministic selection of the largest byte-size variant among candidates.
    - `Latest`: Confirms selection of the variant with the most recent upload timestamp.
    - `Most Downloaded`: Confirms selection of the variant with the highest download count.

## 2.4 Per-Site Fixture Parsing Tests

- Each site adapter added to Manji Downloader must include offline static fixtures (synthetic JSON/HTML/XML responses) representing:
    - A series overview page containing Main Episodes, OVAs, Movies, and Specials.
    - An episode variant page listing multiple qualities (`1080p`, `720p`, `480p`) and file sizes.
- Unit tests verify that the adapter extracts exact episode counts and metadata from these offline fixtures.

## 2.5 Per-Domain Rate Limiter Tests

- Verification of independent limiter state per target site domain during multi-episode link extraction.
- Precise enforcement of minimum delay intervals between consecutive episode lookups.
- Correct calculation of backoff durations upon receiving simulated `Retry-After` headers.

## 2.6 Batch Link Exporter (`links.txt`) & Organizer Tests

- Verification that `links.txt` outputs clean, newline-separated URLs in exact episode order with no trailing corruption.
- Verification of companion rename manifest (`links-manifest.json`) mapping URLs to `{series_title}/{category}/{series_title} - Episode {episode_number} [{quality}].{ext}`.
- Sanitization of illegal filesystem characters in anime series and episode titles across Windows, macOS, and Linux.

## 2.7 npm Launcher & Packaging Tests

- Launcher resolves `MANJI_BINARY`, forwards arguments, and propagates the child exit code.
- Unsupported platforms and missing platform packages produce a clear error with a PyPI fallback suggestion.
- `npm pack --dry-run` includes only `bin/manji.js`, `README.md`, `LICENSE`, and `package.json`.
- Platform package metadata contains the correct `os`, `cpu`, `files`, and version.
- Version sync check: `pyproject.toml`, root `package.json`, and all platform packages match.
- Tarball smoke test: install the packed package in a temporary directory and run `npx --yes ./manji-downloader-<version>.tgz --version`.
- Built PyInstaller binaries report the same version as the Python package.

# 3. Integration Testing with Mock Servers

Integration tests evaluate end-to-end component interaction against locally hosted mock HTTP servers simulating multiple supported anime catalog architectures.

The Python implementation uses `pytest-httpserver` (or a stdlib `ThreadingHTTPServer`) for local servers and `httpx` as the shared client. A loopback-only transport rejects any non-local host.

## Mock Server Requirements

- The mock server runs on `localhost` (ephemeral port) during test execution.
- Simulates multiple distinct site structures (`MockSiteA` using a REST JSON catalog, `MockSiteB` using structured HTML listings):
    - Series index endpoint listing 24 mock episodes, 2 OVAs, 1 movie, and 3 specials.
    - Per-episode variant endpoints returning multiple quality tiers (`1080p`, `720p`, `480p`) with distinct sizes, dates, and download counts.
    - `429 Too Many Requests` responses with `Retry-After` headers during rapid episode lookups.
    - Simulated anti-bot / Cloudflare challenge interstitial (`403 Forbidden` challenge fixture) to verify immediate safe halting.
    - `robots.txt` endpoints with varied `User-agent`, `Disallow`, and `Crawl-delay` directives.

## Test Scenarios

1. **Multi-Site Interactive Selection &** `links.txt` **Export Flow:** Paste mock series URL for `MockSiteA` -> verify Adapter Registry selects `MockSiteA` adapter -> check mock `robots.txt` -> select Episodes `1-5` and OVAs `1-1` -> filter for `1080p` sorted by `Biggest Size` -> enforce rate delay -> verify generated `links.txt` contains the exact 6 expected URLs.
2. **Direct Download Flow (**`MockSiteB`**):** Select Episode `1-1` from `MockSiteB` -> stream mock binary payload -> verify atomic file write and sidecar metadata creation.
3. **Challenge & Halting Flow:** Mock server returns simulated Cloudflare/challenge page -> client immediately halts episode link extraction without retrying -> verifies manual browser handoff message is displayed.

# 4. Test Execution

```bash
# Run the complete test suite (unit and integration)
uv run pytest

# Run unit tests only (URL router, range parser, variant sorter, link exporter)
uv run pytest -m unit

# Run tests for a specific adapter's offline fixtures
uv run pytest tests/adapters -k mock_json

# Run mock multi-site server integration tests
uv run pytest -m integration

# Run linting and type checks
uv run ruff check .
uv run mypy src

# Run npm launcher tests and inspect the published file set
npm test
npm pack --dry-run
```
