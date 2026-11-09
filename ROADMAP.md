# Manji Downloader — Project Roadmap

This document outlines the planned progression of **Manji Downloader** from its initial universal adapter foundation to a multi-site, compliance-first anime series downloader and link extractor.

## 1. Milestone 1: Minimum Viable Product (MVP)

The objective of the MVP is to establish the universal **Source Adapter Registry**, the interactive `manji` CLI wizard, and the core downloading/link-export pipeline.

### Deliverables & Goals

- **Universal Adapter Registry & URL Router:** Automatically detect which site adapter matches a pasted anime series URL and normalize catalog responses into a unified `SeriesCatalog` format.
- **Interactive CLI Wizard (**`manji`) & Flags: Prompt the user to paste an anime series URL and select ranges for Main Episodes, OVAs, Movies, and Specials (e.g., `1-12` or `0` for none).
- **Variant Sorting & Quality Selection:** Support filtering episode variants by resolution (`1080p`, `720p`, `480p`) and sorting by `Biggest Size`, `Latest`, or `Most Downloaded`.
    - Export resolved URLs to a newline-separated `links.txt` file for bulk download managers (IDM, `wget`, `aria2`, `yt-dlp`).
    - Provide built-in chunked streaming download with atomic file writes (`.tmp` to destination).
- **Compliant HTTP Engine & Rate Limiter:** Implement per-domain `robots.txt` enforcement, inter-episode lookup delays, and `Retry-After` backoff.
- **Initial Reference Site Adapter:** Implement the first source adapter for an authorized API/site to validate the end-to-end universal pipeline.
- **Core Test Suite:** Unit tests for URL routing, episode range parsing, variant sorting, and mock server integration tests.
- **Distribution Channels:** Publish the Python package to PyPI and the npm launcher (`npx manji-downloader`) backed by prebuilt Windows, macOS, and Linux binaries.

<!-- TODO: document approved access method for this source. -->

## 2. Milestone 2: Version 0.2 (Multi-Site Expansion & Interactive TUI)

The focus of v0.2 is onboarding additional anime site adapters, enriching the terminal UI, and supporting user-authenticated sessions safely.

### Deliverables & Goals

- **Multi-Site Adapter Expansion Pack (Batch 1):** Onboard additional source adapters for user-specified authorized anime catalogs and platforms using the universal `SourceAdapter` interface.
- **Interactive Terminal UI (TUI) Selector:** Rich terminal table displaying the detected site adapter, available categories, resolutions, file sizes, and upload dates before confirming download or export.
- **Custom Filename Manifests for External Downloaders:** Generate companion rename manifests (`links-manifest.json`) alongside `links.txt` so files downloaded via external tools are automatically named using `{series_title} - Episode {episode_number} [{quality}].{ext}`.
- **Per-Site User Session Cookie Support:** Ingest user-exported session cookies per domain with strict POSIX file permission checks (`chmod 600`).
    - Detect authentication challenges, Cloudflare interstitials, or verification prompts on any supported site.
    - Gracefully pause CLI execution and prompt the user with the URL for manual resolution in a standard web browser.
    - Resume operation once the user confirms completion and updates session data.
- **Local Catalog Caching:** Cache resolved series catalogs and episode variant lists via `ETag` / `If-Modified-Since` headers so re-running with a different episode range does not re-query the site.
- **Signed Release Artifacts:** Code-sign Windows binaries, notarize macOS binaries, and publish npm packages with provenance.

<!-- TODO: List specific Batch 1 anime site adapters as target URLs/sites are provided -->

<!-- TODO: document approved access method for this source. -->

## 3. Milestone 3: Version 1.0 (Plugin Ecosystem, Series Sync & Production Readiness)

Version 1.0 represents the stable, production-ready release of Manji Downloader with a drop-in adapter plugin system, incremental series tracking across sites, and compliance audit tools.

### Deliverables & Goals

- **Pluggable Site Adapter Architecture:** Allow users and contributors to install adapter packages that register through the `manji.adapters` entry-point group without changing the core package.
- **Cross-Site Series Sync ("Watchlist" Mode):** Track previously downloaded anime episodes locally and fetch or export only newly released episodes across supported sites.
- **Quality & Site Fallback Profiles:** Automatically fall back to a secondary resolution (`720p` if `1080p` is missing) or an alternative configured authorized mirror when requested by the user.
- **Media Server Metadata Sidecars:** Support exporting series and episode metadata in standardized media center formats (Jellyfin / Plex / Kodi NFO, JSON-LD, YAML).
- **Compliance Audit Tooling (**`manji audit`): Dedicated sub-command to inspect active site adapters, verify `robots.txt` compliance, and validate per-site rate-limit safety before launching batch jobs.
- **Resumable Transfers & Exclusion Registry:** Full byte-range resume on interrupted direct downloads and automated synchronization with the maintainer-managed domain opt-out list.
- **Broader Distribution:** Homebrew, Scoop, and winget manifests alongside npm and PyPI.

<!-- TODO: Identify candidate authorized anime platforms for official v1.0 adapter certification -->
