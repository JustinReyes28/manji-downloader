# Manji Downloader — Project Roadmap

This document outlines the planned progression of **Manji Downloader** from its initial universal adapter foundation to a multi-site, compliance-first anime series downloader and link extractor.

## 1. Milestone 1: Minimum Viable Product (MVP)

The objective of the MVP is to establish the universal **Source Adapter Registry**, the interactive `manji` CLI wizard, and the core downloading/link-export pipeline.

**Status:** Phases 1–5 of the implementation plan are complete. The package, contracts, configuration, selection engine, compliance HTTP layer, downloader, link exporter, organizer, CLI commands, wizard, and packaging scaffolding all exist and are covered by tests against synthetic mock adapters. Distribution is live: `0.1.0` shipped to npm and `0.1.1` adds PyPI. The MVP is still **not** useful to end users, because no production site adapter exists — that is the remaining blocker below.

### Completed

- Universal Adapter Registry & URL Router with normalized `SeriesCatalog` output.
- Interactive CLI wizard plus `info`, `retrieve`, and `export-links` commands.
- Variant filtering by quality/container and `biggest_size` / `latest` / `most_downloaded` sorting.
- `links.txt` export plus `links-manifest.json`, filename templates, and metadata sidecars.
- Compliant HTTP engine: per-domain `robots.txt`, rate limiting, `Retry-After` backoff, and challenge halting.
- Streaming downloader with atomic writes, Range resume, and conflict policies.
- Unit, integration, and CLI end-to-end tests using only loopback mock servers.
- PyPI/npm packaging, version-sync checks, and a tag-driven release workflow.
- **Distribution go-live:** `manji-downloader` and its five platform packages are published on npm, installable with `npx manji-downloader` and `npm install -g manji-downloader`. Releases use npm trusted publishing (OIDC), so no long-lived npm token is stored.

### Remaining

- **Initial Reference Site Adapter:** the first real adapter is blocked until an authorized source and its approved access method are documented. Until then only synthetic test adapters exist, so `manji adapters list` reports no adapters.

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
