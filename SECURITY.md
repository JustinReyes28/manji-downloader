# Security Policy

## Supported Versions

Manji Downloader is currently pre-release and has no published versions. Security fixes are applied to the `main` branch only.

## Reporting a Vulnerability

Do not open a public issue for a security or compliance problem.

Preferred: use GitHub's private vulnerability reporting from the repository's **Security** tab.

Fallback: email `security@example.com` (replace this placeholder with a monitored address before public launch). Include:

- A description of the issue and its impact
- Steps to reproduce, or a minimal proof of concept
- Affected files, commands, or adapter
- Any suggested remediation

Maintainers will acknowledge reports within 48 hours and coordinate a fix and disclosure timeline.

## Scope

Security reports are especially relevant for:

- Credential handling, logging, and redaction of tokens, cookies, or signed URLs
- `robots.txt`, rate-limit, and `Retry-After` enforcement failures
- Path traversal, unsafe filename handling, or atomic-write/resume flaws
- Adapter isolation failures that leak site-specific data into core modules
- Any behavior that could enable access-control, DRM, paywall, or anti-bot circumvention

## Out of Scope

- Vulnerabilities in third-party sites or services
- Issues caused solely by user-supplied credentials or local configuration
- Requests for features that bypass access controls (see [COMPLIANCE.md](COMPLIANCE.md))
