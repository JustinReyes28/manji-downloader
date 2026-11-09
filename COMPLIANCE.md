# Manji Downloader — Compliance & Acceptable Use Policy

This document defines the core principles, legal requirements, and operational boundaries governing the use and development of **Manji Downloader**, including the onboarding of new site adapters over time. Compliance is a first-class architectural requirement across every supported site adapter, interactive episode selector, and batch download workflow.

## 1. Authorized Use & Multi-Site Adapter Policy

Users and contributors of Manji Downloader must ensure they have legitimate authority to access, retrieve, and store anime series, episodic media, or digital files from any configured source before initiating a retrieval or link-extraction task.

### Permissible Use Cases & Site Adapters

- Retrieving episodic media, anime series archives, or digital collections explicitly owned or licensed for offline download by the user.
- Onboarding site adapters for platforms that provide official APIs, open-access catalogs, Creative Commons / public-domain media, or authorized personal-backup endpoints.
- Automated catalog queries and downloads via authorized developer credentials, registered API tokens, or active authenticated sessions belonging to the user.

### Prohibited Use Cases & Adapters

- Circumventing paywalls, Digital Rights Management (DRM), anti-bot interstitials (e.g., Cloudflare challenges), or access-control lists (ACLs) on any target site.
- Scraping or extracting bulk episode links in violation of a platform's binding Terms of Service.
- Using unthrottled multi-threading to harvest series links or overwhelming target media servers with high-concurrency download managers.
- Redistributing copyrighted anime series, episodes, OVAs, or movies without appropriate licenses or statutory exemptions.

## 2. Per-Site robots.txt and Terms of Service

Because Manji Downloader supports multiple target sites through its Adapter Registry, it enforces per-domain respect for server directives and governing contracts.

### Per-Domain robots.txt Adherence

- Before a site adapter issues series catalog or episode variant requests against its domain, Manji Downloader fetches and inspects that domain's `robots.txt`.
- If the series path, episode listing path, or media endpoint is marked `Disallow` for the active User-Agent or wildcard `*`, the retrieval process halts immediately for that site.
- `Crawl-delay` directives specified in each site's `robots.txt` are parsed and enforced as the minimum interval between consecutive episode lookups on that domain.

### Terms of Service Alignment

- Every site adapter added to Manji Downloader must align with the target platform's usage guidelines.
- Where a platform’s Terms of Service explicitly prohibit automated link extraction or external download accelerators, that domain must not be enabled.

## 3. Rate Limits, Multi-Episode Resolution & Server Etiquette

Resolving available qualities and file variants across an entire anime series (e.g., 12 to 24+ episodes plus OVAs, movies, and specials) across multiple sites can generate significant request volume if unthrottled. To protect remote infrastructure, Manji Downloader enforces conservative traffic policies per site:

- **Per-Site Rate Profiles:** Each site adapter defines conservative default concurrency and request delay settings tailored to avoid stressing that host.
- **Controlled Concurrency:** Operations default to serial or low-concurrency (maximum 2 workers per domain) execution rather than aggressive multi-threaded scraping.
- **Inter-Episode Request Delays:** A mandatory delay (minimum 1.0–1.5 seconds by default) is enforced between each episode metadata lookup unless an official API explicitly permits higher throughput.
- **HTTP 429, 403 & 503 Handling:**
    - Upon receiving HTTP 429 (Too Many Requests), Manji Downloader suspends all requests to that domain immediately and honors `Retry-After` headers or exponential backoff.
    - Upon receiving HTTP 403 or an anti-bot challenge page (such as a Cloudflare interstitial), the adapter halts immediately rather than retrying aggressively or attempting bypasses.
- **External Download Manager Etiquette (**`links.txt`**):**
    - When exporting batch URLs to `links.txt` for use with external tools (such as IDM, `aria2`, `wget`, or `yt-dlp`), users are responsible for configuring their external download manager with polite per-host connection limits so they do not trigger IP bans or degrade service for others.

## 4. Copyright and Privacy

Media and metadata retrieved using this tool may be subject to intellectual property laws and privacy regulations.

### Intellectual Property

- Manji Downloader is a retrieval and organization utility and confers no rights, licenses, or ownership over downloaded anime episodes or media files.
- Users are solely responsible for ensuring downstream storage and playback of downloaded materials conform to copyright, fair use, or personal-backup statutes in their jurisdiction.

### Personally Identifiable Information (PII) & Tokenized Links

- Users must ensure exported `links.txt` files do not inadvertently share private, user-specific signed URLs or session tokens from authenticated anime platforms with third parties.
- Exported link manifests that contain embedded account signatures are flagged with a warning in the `manji` CLI output.

## 5. Logging Redaction & Credential Hygiene

To safeguard user credentials across all configured anime site adapters:

- **Automated Masking:** Log formatters automatically scan and redact known credential patterns across all adapters, including:
    - `Authorization: Bearer <token>` and `Basic <token>` headers
    - Per-site `Cookie` and `Set-Cookie` headers
    - `Signed URL query parameters (?token=, ?sig=, ?auth=, ?key=)` in diagnostic logs
- **Local Storage Security:** Per-site cookie files and API tokens must be stored with restricted filesystem permissions (e.g., `chmod 600` on POSIX systems).
- **Diagnostics Isolation:** Detailed network trace logs must never be exported to public issue trackers without prior verification of redaction.

## 6. Abuse Reporting & Domain Opt-Out

We are committed to operating in harmony with infrastructure providers, anime distributors, and site operators.

### Webmaster & Site Operator Opt-Out

- If you are a site operator or content publisher and wish to prevent Manji Downloader from querying catalogs or retrieving files from your domain, you may:
    1. Add a `Disallow` rule in your `robots.txt` targeting the `ManjiDownloader` User-Agent identifier.
    2. Contact the maintainers to have your domain added to Manji Downloader's built-in domain exclusion list.

### Abuse Inquiries

- To report improper tool usage, unintended server impacts, or compliance issues, please contact the maintainers.
- Contact placeholder: `maintainers@example.com`
