# Manji Downloader — Configuration Specification

**Manji Downloader** is configured via structured configuration files (YAML or TOML), interactive `manji` CLI prompts, or command-line options. This document defines the schema, default values, multi-site adapter registry settings, and operational constraints for anime series selection, quality filtering, and batch link export.

## 1. Configuration File Locations

Manji Downloader searches for configuration files in the following hierarchical order:

1. File explicitly passed via `manji --config <path>`
2. Local working directory: `./manji-config.yaml` or `./manji-config.toml`
3. User configuration directory:
    - Linux/macOS: `~/.config/manji/config.yaml`
    - Windows: `%APPDATA%\ManjiDownloader\config.yaml`

## 2. YAML / TOML Schema Overview

Below is the complete configuration structure for Manji Downloader, including extensible site adapter slots for onboarding new anime sites over time.

Configuration is validated strictly: unknown keys, invalid enum values, and unsafe rate-limit settings are rejected with a clear error.

### YAML Schema Structure

```yaml
# ==============================================================================
# Manji Downloader - Universal Anime Downloader Configuration Schema
# ==============================================================================

version: "1.0"

# Global network and behavior settings
network:
  # Identifying user-agent string including project contact information
  user_agent: "ManjiDownloader/1.0 (+https://example.com/manji-downloader; contact@example.com)"

  # Network timeout values in seconds
  timeout_seconds: 30

  # Maximum connection retries on transient network failures
  max_retries: 3

  # Honor robots.txt directives across all supported anime sites (must be true; disabling is rejected)
  respect_robots_txt: true

# Multi-Site Adapter Registry (add new supported anime sites here as adapters are created)
site_adapters:
  # Adapter Slot 01 Placeholder
  site_adapter_01:
    enabled: true
    base_domain: "site01.example.org"
    auth_mode: "api_key" # Options: none | api_key | bearer_token | cookie_session
    api_key_env: "${ENV_SITE01_API_KEY}"
    min_request_delay_seconds: 1.5  # Minimum 1.0
    # TODO: document approved access method for this source.

  # Adapter Slot 02 Placeholder
  site_adapter_02:
    enabled: true
    base_domain: "site02.example.org"
    auth_mode: "cookie_session"
    cookie_file: "~/.config/manji/cookies/site02_cookies.txt"
    min_request_delay_seconds: 2.0  # Minimum 1.0
    # TODO: document approved access method for this source.

  # TODO: Add additional anime site adapter definitions as new sites are provided

# Interactive anime series, episode category, quality, and sorting preferences
media_selection:
  # Prompt interactively for episode ranges and quality when not passed via CLI flags
  interactive_prompts: true

  # Default category range filters ("all", "0" for none, or range like "1-12")
  default_ranges:
    episodes: "1-12"
    ovas: "0"
    movies: "0"
    specials: "0"

  # Ordered list of preferred video resolutions/qualities (falls back if primary is unavailable)
  preferred_qualities:
    - "1080p"
    - "720p"
    - "480p"

  # Preferred container/file extensions in order of priority
  preferred_formats:
    - "mkv"
    - "mp4"

  # Default variant sorting / tie-breaker criterion when multiple files exist for an episode:
  # Options: biggest_size | latest | most_downloaded
  sort_criterion: "biggest_size"

# Global concurrency and rate limiting controls
rate_limits:
  # Maximum concurrent requests per site domain (1-2; compliance cap)
  max_concurrent_requests_per_site: 2

  # Default inter-request delay in seconds between episode metadata/link lookups (minimum 1.0)
  default_request_delay_seconds: 1.5

# Local cache settings
cache:
  # Directory for storing cached series catalogs and episode variant lists
  directory: "~/.cache/manji"

  # Maximum cache size in megabytes
  max_size_mb: 500

  # Cache retention period in hours
  retention_hours: 72

  # Enable metadata caching
  enabled: true

# Storage, file naming, and batch link export (links.txt) conventions
storage:
  # Output mode: "direct_download" | "export_links" | "both"
  output_mode: "direct_download"

  # Root directory for downloaded anime files
  base_output_directory: "./Anime_Downloads"

  # Output filename formatting template for episodic anime series
  # Available variables: {series_title}, {site_id}, {category}, {episode_number}, {quality}, {id}, {date}, {ext}
  filename_template: "{series_title}/{category}/{series_title} - Episode {episode_number} [{quality}].{ext}"

  # Batch link export configuration (for IDM, aria2, wget, yt-dlp)
  batch_export:
    # File path for newline-separated download URLs
    links_file_path: "./links.txt"

    # Generate a companion manifest mapping each URL to its custom output filename
    generate_rename_manifest: true
    manifest_file_path: "./links-manifest.json"

  # File conflict resolution policy: overwrite | skip | rename
  conflict_resolution: "rename"

  # Save structured metadata sidecar file alongside downloaded asset
  save_metadata_sidecar: true

# Logging and diagnostics
logging:
  # Log level: DEBUG | INFO | WARN | ERROR
  level: "INFO"

  # Path to write diagnostic logs (leave empty for stdout/stderr only)
  file_path: "~/.local/state/manji/manji.log"

  # Enforce sanitization of tokens and cookies in logs
  sanitize_secrets: true
```

## 3. Configuration Properties Detail

### 3.1 Multi-Site Adapter Registry (`site_adapters`)

Each entry under `site_adapters` configures a supported anime platform:

- `enabled`: Toggles whether Manji Downloader will match URLs for this site adapter.
- `base_domain`: Primary domain matched by the URL router when a user pastes an anime series link.
- `auth_mode`: Authentication mechanism (`none`, `api_key`, `bearer_token`, `cookie_session`).
- `min_request_delay_seconds`: Site-specific pause between episode link lookups to ensure polite server etiquette.

### 3.2 Media Selection, Ranges & Variant Sorting (`media_selection`)

Controls how Manji Downloader filters anime episodes and selects among multiple candidate files per episode across all sites:

- `default_ranges`: Pre-fills default ranges for `episodes`, `ovas`, `movies`, and `specials` (e.g., `1-12` or `0` to skip). In interactive mode, the user can accept or override these values.
- `preferred_qualities`: Prioritized list of resolution tags (`1080p`, `720p`, `480p`).
- `sort_criterion`: Determines which file variant is chosen when multiple files exist for an episode:
    - `biggest_size`: Picks the largest file size (often corresponding to highest bitrate/quality).
    - `latest`: Picks the most recently uploaded release.
    - `most_downloaded`: Picks the file with the highest download count.

### 3.3 Batch Link Export (`storage.batch_export`)

- `output_mode`: Set to `export_links` to quickly resolve selected episode URLs into a text file without downloading media directly in the CLI, or `direct_download` to download via the built-in compliant engine.
- `links_file_path`: Path to the generated `links.txt` file (one URL per line, ready for import into IDM, `wget -i links.txt`, `aria2c -i links.txt`, or `yt-dlp -a links.txt`).
- `generate_rename_manifest`: Outputs a structured mapping of URLs to clean target filenames (`{series_title} - Episode {episode_number} [{quality}].{ext}`) so batch-downloaded files retain organized names.

### 3.4 Concurrency, Rate Limits & Cache

- `max_concurrent_requests_per_site`: Hard cap on parallel HTTP sockets per site during both episode link extraction and file downloads.
- `cache.directory`: Local directory (`~/.cache/manji`) caching series episode lists so repeated runs or range adjustments do not re-query unchanged catalog pages.

### 3.5 Per-Site Cookie Files (User-Supplied Only)

- Accepts paths to plain-text Netscape HTTP Cookie Files or structured session JSON exported manually by the user from their browser for a specific site.
- **Strict Constraint:** Manji Downloader will never automate browser login sequences, bypass anti-bot protections, or capture credentials; cookies must be provided directly by the authorized user and secured with `chmod 600`.

### 3.6 Output Filename Template

Available universal template variables for `filename_template`:

- `{series_title}`: Sanitized title of the anime series.
- `{site_id}`: Short identifier of the source site adapter.
- `{category}`: Content category (`Episodes`, `OVAs`, `Movies`, `Specials`).
- `{episode_number}`: Zero-padded episode or item number (e.g., `01`, `12`).
- `{quality}`: Detected resolution or quality tag (e.g., `1080p`, `720p`).
- `{id}`: Unique identifier of the item on the remote site.
- `{date}`: Publication or retrieval date in `YYYY-MM-DD` format.
- `{ext}`: File extension (`mkv`, `mp4`, etc.).
