# Manji Downloader — Contributing Guidelines

Thank you for your interest in contributing to **Manji Downloader**. Because Manji Downloader is built as a universal, multi-site anime series retrieval assistant, we especially welcome contributions that onboard new compliant site adapters, refine interactive episode/quality selection, or improve batch link export (`links.txt`).

## 1. Code of Conduct & Core Principles

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). All contributors are expected to uphold high ethical and engineering standards:

- **Compliance First:** We do not accept site adapters or patches designed to circumvent access controls, defeat bot protection systems (such as Cloudflare challenges), decrypt DRM streams, bypass paywalls, or violate website Terms of Service.
- **Polite Server Etiquette:** Multi-episode link extraction and downloading across every site adapter must respect `robots.txt` directives and enforce conservative per-domain rate limits rather than unthrottled multi-threading.
- **Constructive Collaboration:** Maintain a polite, welcoming, and professional environment for all community members.

## 2. How to Add a New Site Adapter

When adding support for a new anime platform or media catalog to Manji Downloader, follow this standardized onboarding checklist:

1. **Verify Compliance & Access Method:** Confirm that the target site permits programmatic catalog/download access via an official API, open-access terms, or user-authenticated sessions, and respected `robots.txt` rules.
2. **Implement the `SourceAdapter` protocol:**
    - Define `get_site_metadata()` with the site's unique slug, URL match patterns, and a conservative default `min_request_delay_seconds`.
    - Implement `can_handle(url)` and `validate_access(target)` for routing and credential checks.
    - Implement `resolve_series_catalog(series_url)` to normalize the site's series page into `Main Episodes`, `OVAs`, `Movies`, and `Specials`.
    - Implement `resolve_episode_variants(episode_item)` to normalize each episode's available quality tiers (`1080p`, `720p`, `480p`), container formats (`mkv`, `mp4`), file sizes, upload dates, and download counts.
3. **Register the Adapter:** Add the adapter to the central `AdapterRegistry` and add a corresponding configuration slot in `CONFIGURATION.md`.
4. **Create Offline Test Fixtures:** Place sanitized, synthetic response fixtures under `tests/fixtures/adapters/<site_id>/` and write unit tests verifying URL routing, category counts, and variant extraction without making live network calls.

## 3. Development Setup & Code Style

Manji Downloader targets Python 3.12+ and uses `uv` for environments and dependency locking.

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Contributors should adhere to modern coding practices:

- **Static Analysis & Type Checking:** Code must pass `ruff check` and `mypy` without warnings.
- **Formatting:** Code must be formatted with `ruff format`.
- **Typed Contracts:** Public functions and adapter methods must be fully typed.
- **Neutral Fixtures & Examples:** Documentation, CLI help text, and unit test fixtures must use generic placeholder URLs and synthetic series titles—never live links to copyrighted series or unauthorized portals.
- **No Embedded Credentials:** Never commit credentials, personal cookies, signed media URLs, or live API keys to the repository.

## 4. Pull Request (PR) Checklist

Before submitting a pull request to Manji Downloader, verify that your contribution satisfies the following requirements:

- **No Circumvention or Evasion:** PR contains zero Cloudflare/anti-bot bypass code, DRM decryption, or paywall circumvention logic.
- **Normalized Adapter Output:** If adding or updating a site adapter, it strictly returns standard `SeriesCatalog` and `MediaVariant` models without breaking interactive CLI prompts.
- **Typed Code:** `uv run mypy src` passes and public contracts have complete type hints.
- **Rate-Limit Compliance:** All series catalog and episode variant requests pass through Manji Downloader's central per-domain rate limiter and respect `robots.txt`.
- **Offline Tests Included:** Unit tests with local synthetic fixtures are provided for new site adapters, range parsing, quality filtering, or variant sorting logic.
- **No Live Network Calls in Tests:** All tests use local mock servers or offline fixtures; zero requests to live external websites.
- **Documentation Updated:** Relevant documentation files (`README.md`, `ARCHITECTURE.md`, `CONFIGURATION.md`, etc.) are updated to list new options or adapter slots.
- **Credential Redaction Verified:** Any logging or `links.txt` export additions safeguard against leaking sensitive session tokens.
- **Packaging Verified:** `npm test` passes, `npm pack --dry-run` contains only the launcher, README, and license, and Python/npm versions match.
- **DCO Sign-Off Included:** Commits are signed off in accordance with the Developer Certificate of Origin.

## 5. Developer Certificate of Origin (DCO) & Sign-Off

To ensure all contributions are legally unencumbered and open source, Manji Downloader requires the Developer Certificate of Origin (DCO).

### DCO Statement (Version 1.1)

By making a contribution to this project, I certify that:

1. The contribution was created in whole or in part by me and I have the right to submit it under the open source license indicated in the file; or
2. The contribution is based upon previous work that, to the best of my knowledge, is covered under an appropriate open source license and I have the right under that license to submit that work; or
3. The contribution was provided directly to me by some other person who certified (1) or (2) and I have not modified it.
4. I understand and agree that this project and the contribution are public and that a record of the contribution is maintained indefinitely.

### How to Sign Off

Add the following line to each commit message:

```text
Signed-off-by: Full Name <email@example.com>
```

(Using git: `git commit -s -m "Commit message"`)

## 6. Packaging & Release

Manji Downloader ships through PyPI and npm. The Python package is the source of truth; the npm package is a thin launcher for prebuilt binaries. See [PACKAGING.md](PACKAGING.md) for the full design.

- **Version Sync:** `pyproject.toml`, the root `package.json`, and every platform package must share one version.
- **Binary Builds:** Build with PyInstaller in CI for each supported platform. Never commit binaries.
- **npm Platform Packages:** Each package carries `os`/`cpu` metadata and the matching binary.
- **No Install-Time Downloads:** Do not add a `postinstall` script that fetches binaries.
- **Publishing:** Use PyPI trusted publishing and npm provenance. Release tags use `vX.Y.Z`.

Before a release:

```bash
uv build
npm test
npm pack --dry-run
```

Then smoke-test `npx -y manji-downloader@<version> --version` on each supported OS family.

## 7. Security & Abuse Reporting

If you discover a security vulnerability, an unintentional compliance loophole, or suspect tool misuse:

- **Do Not Open a Public Issue:** Please report security or compliance concerns privately.
- **Contact:** Send details to `security@example.com`.
- **Response Timeline:** Maintainers will acknowledge reports within 48 hours and coordinate remediation.
