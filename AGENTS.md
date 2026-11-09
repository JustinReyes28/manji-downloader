# AGENTS.md — Manji Downloader

Guidance for AI coding agents. Read this file first, then the relevant spec doc.

## What this project is

`manji` is a compliance-first, universal CLI for retrieving anime series and episodic media from **authorized** sources. Pluggable site adapters normalize every site into one catalog model, so the CLI, filtering, and download layers never change when a site is added.

Pipeline: pasted URL → Adapter Registry → site adapter → `SeriesCatalog` → interactive/flag selection → variant resolution → filter/sort → direct download or `links.txt` export.

## Current state

- Repo contains specification documents and repository scaffolding only. No implementation or build tooling yet.
- Runtime, language, and package manager are **not chosen**. Do not assume one; when decided, record the toolchain and exact commands in this file and the README.
- Specs are Markdown files at the repo root (`README.md`, `ARCHITECTURE.md`, `CONFIGURATION.md`, `COMPLIANCE.md`, `TESTING.md`, `CONTRIBUTING.md`, `ROADMAP.md`). They are the source of truth; do not contradict them, and update them when behavior changes.
- Repository paperwork: `LICENSE` (MIT), `CODE_OF_CONDUCT.md`, `SECURITY.md`, and templates under `.github/`.

## Repository layout

- `README.md` — project overview, feature summary, and documentation index
- `ARCHITECTURE.md` — modules, adapter registry, and the `SourceAdapter` contract
- `CONFIGURATION.md` — YAML/TOML schema, defaults, and filename templates
- `COMPLIANCE.md` — acceptable use, `robots.txt`, rate limits, and credential hygiene
- `TESTING.md` — offline fixtures and mock-server test requirements
- `CONTRIBUTING.md` — adapter onboarding, PR checklist, and DCO sign-off
- `ROADMAP.md` — MVP, v0.2, and v1.0 milestones
- `AGENTS.md` — agent instructions (this file)

## Non-negotiable compliance rules

These are product requirements, not suggestions.

Never implement:

- Anti-bot or Cloudflare bypasses, CAPTCHA solving, challenge evasion, or headless stealth plugins
- TLS/JA3, canvas, WebGL, or client-header fingerprint spoofing
- DRM/EME/Widevine/HLS-AES decryption, paywall bypass, or access-control circumvention
- Proxy rotation to dodge limits, or unthrottled scraping
- Automated browser login, credential capture, or credential storage on the user's behalf

Required behavior:

- Check `robots.txt` per domain before catalog/episode requests; abort on disallowed paths and enforce `Crawl-delay`.
- Default caps: max 2 concurrent requests per domain; at least 1.0–1.5 s between episode lookups.
- 429/503: stop that domain's traffic, honor `Retry-After`, then exponential backoff.
- 403 or a challenge page: halt immediately with a manual browser-handoff message. Never retry around it.
- Credentials are user-supplied only (API key env vars or user-exported cookie files, `chmod 600`). Never commit secrets, cookies, or signed URLs.
- Redact `Authorization`/`Cookie` headers and signed query params (`token`, `sig`, `auth`, `key`) from all logs and exports.
- Fixtures, docs, and help text use synthetic placeholder sites/titles only — never live links to copyrighted content.

## Architecture contract

Keep these universal models and names stable:

- `SeriesCatalog` — series title plus categorized items: Episodes, OVAs, Movies, Specials
- `MediaVariant` — quality/resolution, container format, byte size, upload timestamp, download count, direct URL

Every `SourceAdapter` implements:

- `GetSiteMetadata()` — slug, display name, domains, default rate-limit profile
- `CanHandle(url)`
- `ValidateAccess(target)`
- `ResolveSeriesCatalog(seriesUrl) -> SeriesCatalog`
- `ResolveEpisodeVariants(episodeItem) -> MediaVariant[]`

Rules:

- Adapters return normalized models only. Site-specific types must not leak into the CLI, filter engine, or downloader.
- Adding a site = new adapter + registry entry + config slot + offline fixtures. No changes to core modules.
- All network I/O goes through the shared HTTP client, per-domain rate limiter, and `robots.txt` cache.
- Sort criteria: `biggest_size` | `latest` | `most_downloaded`. Quality fallback follows `preferred_qualities` order (1080p → 720p → 480p).
- Downloads: stream in chunks, write to `.tmp`, verify, then atomically rename. Support HTTP Range resume.
- `links.txt`: one resolved URL per line in episode order; optional `links-manifest.json` mapping URL → output filename.
- Filename template variables: `{series_title}`, `{site_id}`, `{category}`, `{episode_number}`, `{quality}`, `{id}`, `{date}`, `{ext}`. Sanitize illegal characters for Windows, macOS, and Linux.
- Write sidecar metadata (`series.json` / `episode.yaml`) with adapter ID, source URL, variant metrics, and timestamp.
- Range syntax: `1-12`, `5-5`, `5`, comma lists, and `0` meaning none. Reject inverted, negative, or out-of-bounds ranges with clear errors.
- Config: versioned YAML/TOML. Search order: `--config` path → `./manji-config.{yaml,toml}` → per-OS user config dir. Support `${ENV_NAME}` interpolation. New sites must be addable without code edits to core.
- CLI surface: interactive `manji`; subcommands `adapters list`, `info`, `retrieve`, `export-links`; global `--config`.

## Testing rules

- **Zero live network calls in tests.** Use synthetic fixtures under `tests/fixtures/adapters/<site_id>/` and localhost mock servers on an ephemeral port.
- Cover: URL routing and unsupported sites, range parser edge cases, quality fallback, deterministic selection for each sort criterion, rate limiter/`Retry-After`, `links.txt` ordering and manifest, atomic writes, and challenge/403 halting.
- Integration tests must simulate multiple site shapes (JSON API and HTML catalog), plus 429 and challenge responses.
- Run typecheck, lint, and tests before finishing; fix failures rather than suppressing them.

## Working conventions

- Keep adapters isolated; don't add site-specific branches to core modules.
- Never add evasion behavior, even behind a flag, "for testing".
- Update the relevant spec doc when adding CLI flags, config keys, or adapters.
- Document each adapter's approved access method before implementation. The specs contain TODOs for this; do not invent access methods.
- When the toolchain is chosen, replace placeholders here with real install/build/test/lint commands so this file stays actionable.
