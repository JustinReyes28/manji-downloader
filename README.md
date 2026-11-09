# Manji Downloader

**Manji Downloader** is a compliance-first, universal command-line (CLI) anime series and episodic media retrieval assistant. Built around a pluggable multi-site adapter architecture, it allows you to paste an anime series URL from any supported authorized source, interactively select episodes, OVAs, movies, or specials, filter by video quality and sorting criteria, and either download files locally or export batch links.

> **Project status:** specification phase. The repository currently contains the architecture, configuration, compliance, testing, and roadmap documents. No implementation or toolchain has been chosen yet.

## 1. Overview

Manji Downloader provides a unified, interactive CLI experience across multiple anime catalogs and media repositories. Rather than relying on single-site scripts, Manji Downloader uses an extensible **Source Adapter Registry** that automatically detects the target site from the pasted URL and presents a consistent selection menu.

- **Primary Goal:** Provide a single, universal CLI interface (`manji`) to discover, filter, and organize anime series and episodic media across a growing list of compatible, authorized sites.
- **Interactive Experience:** Inspired by streamlined batch-link workflows (such as [Tokyo-Downloader](https://github.com/MaJoRX0/Tokyo-Downloader)), allowing users to paste a series link and interactively choose episode ranges, media categories, video resolutions, and sorting preferences.
- **Philosophy:** Compliance-first architecture with strict adherence to access controls, `robots.txt`, terms of service, and polite rate limits across every configured site adapter.
- **Current Status:** Scaffolding and multi-site adapter specification phase.

## 2. Authorized-Use and Legal Notice

**IMPORTANT LEGAL NOTICE**

**Manji Downloader** is strictly intended for retrieving anime and media content that you own, have explicit authorization or licensing to download, or is published under open-access terms permitting automated retrieval.

- **No Circumvention:** This tool does NOT contain features or mechanisms to bypass access controls, Digital Rights Management (DRM), subscription paywalls, or anti-bot safeguards (such as Cloudflare interstitial challenges).
- **Terms of Service:** Users are solely responsible for ensuring that their configured site adapters, retrieval workflows, and downstream batch downloads comply with all applicable third-party Terms of Service, Acceptable Use Policies, and `robots.txt` specifications.
- **Compliance Obligation:** Use of this software constitutes an agreement to adhere to all relevant local and international copyright, intellectual property, and computer misuse laws.

## 3. Features

- **Universal Multi-Site Adapter System:** Paste a series URL from any configured source; Manji Downloader automatically routes the URL to the matching site adapter while keeping the interactive prompts identical.
- **Interactive Series & Category Selection:** Inspect and select across all available anime content categories—including Main Episodes, OVAs, Movies, and Specials/Extras.
- **Flexible Range Filtering:** Specify exact episode or item ranges (e.g., `1-12`, single items like `5-5`, comma-separated selections, or `0` to skip a category).
- **Quality, Format & Sorting Controls:** Choose preferred file variants per episode using configurable selection criteria:
    - **Resolution / Quality:** Select preferred video resolutions (e.g., `1080p`, `720p`, `480p`) and container formats (`MKV`, `MP4`), with automatic fallback if a preferred tier is unavailable.
    - **Biggest Size:** Automatically pick the largest file size / highest bitrate encode available for each episode.
    - **Latest:** Select the most recently uploaded or updated release.
    - **Most Downloaded:** Select the most popular verified file variant.
- **Dual Output Modes (Direct Download or Batch Link Export):**
    - **Direct Compliant Download:** Stream and organize anime episodes locally into structured series/season folders using the built-in rate-limited downloader.
    - **Batch Link Export (`links.txt`):** Save resolved direct download URLs as a newline-separated list in `links.txt` (alongside optional filename mapping manifests) for bulk import into external download managers (such as IDM, `aria2`, `wget`, or `yt-dlp`).
- **Compliance Engine:** Per-domain `robots.txt` verification, polite inter-episode lookup delays, and automatic `Retry-After` backoff.
- **Challenge-Aware Layer:** Safe handling of authentication or verification challenges via official APIs, user-provided session cookies, or manual browser handoff without automated evasion.

## 4. Supported Sites & Adapter Placeholders

Manji Downloader is designed to expand compatibility across multiple anime platforms via modular source adapters:

| Site / Source Identifier | URL Pattern Placeholder | Access Method | Status |
| --- | --- | --- | --- |
| `adapter_template_01` | `https://[site-01-placeholder]/anime/*` | Official API / User Session | Planned (v0.1) |
| `adapter_template_02` | `https://[site-02-placeholder]/series/*` | Official API / Open Catalog | Planned (v0.2) |
| `adapter_template_03` | `https://[site-03-placeholder]/watch/*` | User-Provided Session | Planned (v0.2) |

## 5. Quickstart Placeholders

### Prerequisites

- Target runtime environment (e.g., Python 3.10+ / Go 1.21+ / Node.js 18+)
- Valid credentials, API keys, or user-supplied session cookies for authorized sources requiring login
- Configured local destination directory or external download manager

### Installation Placeholder

```bash
# Placeholder: Package installation command

[package-manager] install manji-downloader
```

### Interactive Workflow Placeholder

```bash
# Launch Manji Downloader interactive mode
manji

# Step-by-step interactive prompts displayed to the user:
# 1. Enter Anime Series URL: [paste series URL from any supported site]
#    -> Detected Source Adapter: [site-adapter-name]
#    -> Found: 24 Episodes | 2 OVAs | 1 Movie | 3 Specials
# 2. Select Episode Range (e.g., 1-24, or 0 for none): [user input]
# 3. Select OVA Range (e.g., 1-2, or 0 for none): [user input]
# 4. Select Movie / Special Ranges (e.g., 1-1, or 0 for none): [user input]
# 5. Select Preferred Quality / Resolution (1080p / 720p / 480p / Best Available): [user input]
# 6. Select Sorting Criteria (Biggest Size / Latest / Most Downloaded): [user input]
# 7. Select Action (1: Direct Local Download | 2: Export URLs to links.txt): [user input]
```

### Non-Interactive CLI Usage Placeholders

```bash
# General syntax placeholder
manji [global-options] <command> [command-options] [arguments]

# List all registered site adapters and their status
manji adapters list

# Retrieve a specific anime episode range and quality directly to local storage
manji retrieve [series-url] --episodes 1-12 --ovas 0 --specials 1-2 --quality 1080p --sort biggest-size --output-dir ./Anime

# Export resolved episode links to links.txt for an external download manager (IDM / aria2 / wget)
manji export-links [series-url] --episodes 1-24 --quality 1080p --sort latest --export-file links.txt

# Inspect available episodes, qualities, and file sizes for a series URL without downloading
manji info [series-url]
```

## 6. Configuration Overview

Manji Downloader reads operational parameters from a structured configuration file (`manji-config.yaml` or `manji-config.toml`) located in standard system configuration directories or passed explicitly via `--config`.

Key configuration elements include:

- **Multi-Site Adapter Profiles:** Per-site base URLs, rate limits, and authentication settings.
- **Default Media Preferences:** Preferred resolution hierarchy (`1080p`, `720p`), container formats (`mkv`, `mp4`), and default variant sorting rule (`biggest_size`, `latest`, `most_downloaded`).
- **Batch Export Settings:** Default export file path (`links.txt`) and custom filename mapping options.
- **Rate Limiting Policies:** Inter-request delays when resolving multi-episode metadata, burst limits, and concurrency caps.

For complete schema details and configuration examples, refer to [CONFIGURATION.md](CONFIGURATION.md).

## 7. Frequently Asked Questions (FAQ)

### How does Manji Downloader support multiple anime sites?

Manji Downloader uses a modular **Source Adapter Interface**. Each supported site has a dedicated adapter module that translates that site's catalog structure into Manji Downloader's universal `SeriesCatalog` and `EpisodeVariant` format. When you paste a link, the adapter registry automatically matches the domain and handles the rest seamlessly.

### How do I choose specific episodes, OVAs, or quality tiers?

When you paste a series URL in interactive mode (or pass CLI flags), Manji Downloader queries the matched site adapter and displays the available counts of Main Episodes, OVAs, Movies, and Specials. You can enter a range (such as `1-12`) or `0` to skip a category, then pick your preferred quality (`1080p`, `720p`, `480p`) and sorting rule (**Biggest Size**, **Latest**, or **Most Downloaded**).

### Can I export links to use with Internet Download Manager (IDM), aria2, or wget?

Yes. Selecting the batch export option saves all resolved episode download URLs into `links.txt` (one URL per line), along with an optional rename manifest so your downloaded episodes retain clean, standardized filenames.

### What happens if a supported site enables Cloudflare or bot challenges?

Manji Downloader never attempts to bypass anti-bot protections or DRM. If a site presents an interactive challenge, the tool safely pauses and guides you through a manual browser handoff or official API authentication.

## Documentation

| Document | Contents |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, module decomposition, and the source adapter contract |
| [CONFIGURATION.md](CONFIGURATION.md) | YAML/TOML schema, defaults, file locations, and filename templates |
| [COMPLIANCE.md](COMPLIANCE.md) | Acceptable use, robots.txt policy, rate limits, and credential hygiene |
| [TESTING.md](TESTING.md) | Offline fixture strategy, unit and mock-server integration tests |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Adapter onboarding, pull request checklist, and DCO sign-off |
| [ROADMAP.md](ROADMAP.md) | MVP, v0.2, and v1.0 deliverables |

## Contributing

Contributions are welcome, especially compliant site adapters and selection/filtering improvements. Read [CONTRIBUTING.md](CONTRIBUTING.md) first. Commits must be signed off under the Developer Certificate of Origin (`git commit -s`).

## Security

Report vulnerabilities and compliance loopholes privately as described in [SECURITY.md](SECURITY.md). Do not open a public issue for security reports.

## License

Released under the [MIT License](LICENSE).
