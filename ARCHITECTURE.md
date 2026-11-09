# Manji Downloader — Architecture & System Design

This document details the high-level architecture, module decomposition, and multi-site extension patterns of **Manji Downloader**. The system is designed as a compliance-first, universal anime series retrieval assistant where new site adapters can be plugged in seamlessly over time without modifying the core CLI, filtering engine, or downloader.

## 1. System Overview

Manji Downloader follows a pipelined, layered architecture. When a user pastes an anime series URL from any supported site, the URL flows through the **Multi-Site Adapter Registry**, policy validation, catalog normalization, interactive user selection (category, episode range, quality, sorting), rate-limited variant resolution, and final execution (direct local download or `links.txt` batch export).

### Core Architectural Principles

- **Universal Multi-Site Extensibility:** Site-specific catalog structures are isolated inside modular Source Adapters that normalize data into a single universal `SeriesCatalog` and `EpisodeVariant` model.
- **Interactive & Batch Dual-Mode:** Supports both guided interactive terminal menus (`manji`) and non-interactive CLI flag execution.
- **Compliance by Design:** Per-domain policy checks (`robots.txt`, rate limits) sit directly in the request execution path across all registered site adapters.
- **Fail-Safe Operation:** Non-bypassable guardrails ensure requests halt immediately upon permission denial, Cloudflare/anti-bot interstitials, or unrecognized challenges.
- **Zero Evasion:** Strict absence of fingerprint spoofing, headless browser evasion, DRM decryption, or automated CAPTCHA-solving hooks.

<!-- TODO: Insert architecture diagram: [Pasted URL] -> [Adapter Registry] -> [Site Adapter (1..N)] -> [Normalized SeriesCatalog] -> [Interactive Range/Quality Selector] -> [Downloader / links.txt Exporter] -->

## 2. Module Decomposition

### 2.1 CLI Parser & Interactive Prompt Engine

- **Responsibility:** Ingest command-line arguments, manage the `manji` interactive terminal wizard, validate episode range syntax, and dispatch commands to core controllers.
- **Key Functions:**
    - **Interactive Wizard:** Prompts the user to paste an anime series URL, displays the automatically detected site adapter and discovered item counts (Main Episodes, OVAs, Movies, Specials), accepts range inputs (e.g., `1-12` or `0` for none), and presents quality/sorting choices.
    - **Range Expression Parser:** Parses and validates range strings (`1-24`, `1-1`, comma-separated lists, or `0`) against the total available items in each category.
    - **Configuration Merging:** Merges CLI flags, interactive choices, per-site adapter settings, and global configuration defaults.

<!-- TODO: Define CLI argument schema and interactive state machine interfaces -->

### 2.2 Multi-Site Adapter Registry & Source Adapter Interface

- **Responsibility:** Enable universal compatibility across multiple anime platforms by dynamically routing incoming URLs to the appropriate site module and normalizing the results.
- **Adapter Registry Functions:**
    - `RegisterAdapter(adapter)`: Registers a site adapter into the active runtime catalog.
    - `ResolveAdapterForUrl(url)`: Matches the pasted URL's domain and path pattern against registered adapters and returns the matching handler (or a clear unsupported-site message).
    - `ListSupportedSites()`: Returns metadata on all registered site adapters, their supported URL patterns, and authentication requirements.
- **Source Adapter Interface Contract (Implemented per Site):**
    - `GetSiteMetadata()`: Returns the adapter's unique slug, display name, supported domains, and default rate-limit profile.
    - `CanHandle(url)`: Inspects an incoming anime series or episode URL to confirm compatibility.
    - `ValidateAccess(target)`: Verifies whether required API tokens or user session credentials are present for that site.
    - `ResolveSeriesCatalog(seriesUrl)`: Queries the site's authorized endpoints to return a normalized `SeriesCatalog` containing the series title and categorized lists of `Episodes`, `OVAs`, `Movies`, and `Specials`.
    - `ResolveEpisodeVariants(episodeItem)`: Queries the site's authorized endpoints for a specific episode to return normalized `MediaVariant` objects (resolution/quality tag, container format, byte size, upload timestamp, download count, and direct URL).
- **Onboarding New Sites Later Down the Road:**
    - Adding support for a new anime site requires only creating a new adapter module implementing the interface above and registering its domain pattern—no changes are required in the CLI prompt engine, quality sorter, or downloader.

<!-- TODO: document approved access method for this source. -->

<!-- TODO: Add per-site adapter specification stubs as target anime sites are provided -->

### 2.3 Variant Filtering & Sorting Engine

- **Responsibility:** Filter and rank normalized candidate files for each selected episode across any supported site according to user criteria.
- **Key Functions:**
    - **Category & Range Filtering:** Restricts processing to the exact subset of Episodes, OVAs, Movies, and Specials selected by the user.
    - **Quality / Format Matching:** Filters available variants by target resolution (`1080p`, `720p`, `480p`), codec, or container (`MKV`, `MP4`), with configurable fallback rules if a preferred resolution is unavailable on that site.
    - **Deterministic Sorting Criteria:** Selects the winning file variant per episode using the user's chosen sorting rule:
        - `Biggest Size`: Selects the variant with the largest byte size.
        - `Latest`: Selects the variant with the newest upload/publication timestamp.
        - `Most Downloaded`: Selects the variant with the highest verified download count.

<!-- TODO: Define tie-breaker precedence rules when multiple variants match quality criteria -->

### 2.4 HTTP Client Abstraction

- **Responsibility:** Provide a centralized network layer shared by all site adapters, encapsulating session handling, headers, timeouts, and transport security.
- **Capabilities:**
    - Configurable connection pooling and per-domain persistent sessions.
    - Standardized TLS configuration adhering to secure system defaults.
    - Interceptor chain for telemetry, per-domain rate limiting, and response validation.

### 2.5 Per-Domain Rate Limiter

- **Responsibility:** Regulate request frequency independently for each supported anime site—especially when resolving download links across dozens of episodes—to protect remote infrastructure from overloading.
- **Mechanisms:**
    - Independent token bucket / leaky bucket state per target host.
    - Immediate compliance with `Retry-After` headers on HTTP 429 / 503 responses.
    - Configurable per-site minimum delays between consecutive episode metadata lookups.
    - Strict concurrency caps (replacing unthrottled multi-threading with bounded, polite worker pools).

### 2.6 Cache Layer

- **Responsibility:** Minimize redundant network roundtrips across supported sites by caching normalized series catalogs, episode variant lists, and `robots.txt` records.
- **Key Functions:**
    - Cache validation using `ETag` and `Last-Modified` HTTP headers.
    - robots.txt policy caching respecting `Cache-Control` max-age per domain.
    - Local cache eviction policies based on TTL and disk usage quotas.

### 2.7 Downloader & Batch Link Exporter (links.txt)

- **Responsibility:** Execute the final retrieval plan either by streaming files locally or exporting structured link lists for external download managers.
- **Direct Downloader Functions:**
    - Chunked streaming to prevent high memory consumption on large anime video files.
    - Atomic writes via temporary files (write to `.tmp`, verify integrity, rename).
    - Resumable transfers using standard HTTP `Range` headers where supported.
- **Batch Link Exporter Functions (**`links.txt`**):**
    - Generates a clean, newline-separated `links.txt` file containing resolved URLs for bulk import into external tools (e.g., IDM, `aria2`, `wget`, `yt-dlp`).
    - Outputs an optional companion rename/manifest file (`links-manifest.json`) mapping each raw URL to its standardized anime series and episode filename.

### 2.8 Metadata Organizer

- **Responsibility:** Structure downloaded anime assets into clean series/category folders regardless of which site adapter they originated from.
- **Key Functions:**
    - Templated directory tree creation based on universal variables (`{series_title}`, `{site_id}`, `{category}`, `{episode_number}`, `{quality}`).
    - Sidecar file generation (`series.json` or `episode.yaml`) detailing provenance, source adapter ID, source URL, selected variant metrics, and retrieval timestamp.

### 2.9 Logging and Telemetry

- **Responsibility:** Provide comprehensive operational insight while protecting user privacy across all configured site adapters.
- **Key Functions:**
    - Configurable log levels (DEBUG, INFO, WARN, ERROR).
    - Automatic redaction of sensitive data (passwords, API keys, session cookies, signed URL tokens).

## 3. Challenge-Aware HTTP Layer

Because Manji Downloader is designed to interact with diverse external hosts over time, its HTTP layer operates under an explicit "challenge-aware" philosophy. Unlike single-site scrapers (such as [Tokyo-Downloader](https://github.com/MaJoRX0/Tokyo-Downloader)) that break when a site enables Cloudflare protection or attempt brittle bypasses, Manji Downloader addresses challenges strictly through safe, authorized mechanisms:

### Permitted Authentication & Ingestion Paths

1. **Official Site APIs:** Preferred channel whenever a supported anime platform provides a documented developer or catalog API.
2. **User-Provided Session Cookies:** Where personal account access is authorized, users may supply their own exported browser session cookies per site in a protected local configuration file.
3. **Manual Browser Handoff:**
    - If a supported site presents an interactive verification prompt, Cloudflare interstitial, CAPTCHA, or re-authentication challenge, Manji Downloader immediately halts automated requests for that domain.
    - The system displays a clear message directing the user to open the URL in their standard desktop web browser to satisfy the challenge or authenticate manually.
    - Once completed, the user updates their local session tokens or cookies, allowing `manji` to resume normally.
4. **Respect for Robots.txt and Terms of Service:**
    - Every domain interaction checks for `robots.txt` directives prior to querying series catalogs or episode links.
    - If an endpoint or user-agent is disallowed by `robots.txt`, the operation aborts with a descriptive status code.

### Architectural Prohibitions (No Evasion)

- **No Fingerprint Manipulation:** No spoofing of TLS/JA3 fingerprints, canvas, WebGL, or browser client headers.
- **No Anti-Bot Circumvention:** No integration with Cloudflare bypass libraries, automated CAPTCHA solvers, proxy rotators, or headless browser stealth plugins.
- **No Paywall or DRM Bypass:** No decryption of encrypted media streams (EME/Widevine/HLS-AES) and no header spoofing to bypass subscription paywalls.

<!-- TODO: document approved access method for this source. -->
