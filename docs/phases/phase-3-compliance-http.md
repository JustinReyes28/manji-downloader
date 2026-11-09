# Phase 3 — Compliance HTTP & Mock Adapters

**Status:** Complete (commit `fb0c926`)
**Depends on:** Phase 2
**Unlocks:** Phase 4
**Commit checkpoint:** `phase 3: compliance http and mock adapters`

## Goal

Build the shared network layer that enforces robots.txt, per-domain rate limits, Retry-After, and challenge halting. Add synthetic adapters and fixtures so the layer is tested end-to-end without live traffic.

## Deliverables

- [x] `src/manji/log.py` with logging setup and a redaction filter.
- [x] `src/manji/net/client.py` shared `httpx` client.
- [x] `src/manji/net/limiter.py` per-domain limiter with an injectable clock.
- [x] `src/manji/net/robots.py` using `protego`.
- [x] `src/manji/net/challenge.py` and `redaction.py`.
- [x] `tests/adapters/mock_json.py` and `mock_html.py`.
- [x] `tests/helpers/` loopback transport and mock-site harness.
- [x] Fixtures under `tests/fixtures/adapters/<site_id>/`.
- [x] Unit and integration tests for every compliance branch.

## HTTP client requirements

Use synchronous `httpx.Client`; async is unnecessary at the mandated concurrency. All requests go through one `CompliantClient`:

- Apply configured user agent, timeout, and maximum redirects.
- Acquire a per-domain concurrency slot (max 2) and wait for the domain delay.
- Check `robots.txt` before catalog, episode, media, and redirect targets.
- Handle redirects manually so every hop passes through robots and the limiter.
- Never retry a 403 or challenge page.
- Honor `Retry-After` on 429/503; cap the wait and raise `RateLimitedError` instead of blocking forever.
- Retry transient 5xx and network errors up to `max_retries` with exponential backoff.
- Log method, redacted URL, status, and duration only.
- Expose a `stream()` context manager for Phase 4 downloads.

## Per-domain limiter

- One state per host: `threading.BoundedSemaphore(max_concurrency)`, next-allowed timestamp, blocked-until timestamp, minimum delay, and crawl delay.
- Inject a clock with `monotonic()` and `sleep()` for deterministic tests.
- A blocked domain applies to all concurrent requests for that host.
- Enforce the larger of the configured delay and `Crawl-delay`.

## robots.txt behavior

- Fetch per scheme+host; cache with `Cache-Control` max-age (default 1 hour).
- 200 → parse with `protego` and enforce `Disallow`/`Allow`.
- 404/410 → allow.
- 401/403 → deny.
- 429 → honor `Retry-After` or raise `RateLimitedError`.
- 5xx or network failure → fail closed with `RobotsUnavailableError`.
- `respect_robots_txt: False` is rejected at config validation.

## Challenge and rate-limit behavior

- Detect Cloudflare/CAPTCHA markers only on 403/503 or when `cf-mitigated` is present.
- Raise `ChallengeDetectedError` with a manual browser-handoff message and the domain.
- Raise `AccessDeniedError` for a plain 401/403 without retrying.
- Parse `Retry-After` as seconds or an HTTP date.

## Redaction

Mask before logging or returning errors:

- `Authorization`, `Proxy-Authorization`, `Cookie`, `Set-Cookie` header values.
- Query keys: `token`, `sig`, `signature`, `auth`, `key`, `api_key`, `apikey`, `password`, `session`.
- URL userinfo passwords.

Provide a `Sanitizer` class and a `logging.Filter` that redacts records and args. Test the sanitizer directly and through a captured log handler.

## Mock adapters and fixtures

- `mock_json`: synthetic host `mock-json.test`, catalog JSON, per-item variant JSON.
- `mock_html`: synthetic host `mock-html.test`, HTML catalog and variant tables.
- Fixtures: 24 episodes, 2 OVAs, 1 movie, 3 specials, multiple quality tiers, `robots.txt`, a 429 response, and a 403 challenge page.
- `MockSite` helper starts a local `pytest-httpserver` or `ThreadingHTTPServer`.
- A `HostRewriteTransport` maps `mock-*.test` to the local server; a `LoopbackOnlyTransport` rejects any non-loopback host.
- Adapters never call a live site.

## Tests

- Registry routing for both mock adapters.
- robots allow, disallow, 404, 401/403, 5xx fail-closed, and cache reuse.
- Crawl-delay parsing and delay enforcement with a fake clock.
- 429 with `Retry-After`, then success; blocked-domain behavior.
- Plain 403 → `AccessDeniedError`, exactly one request.
- Challenge 403 → `ChallengeDetectedError`, exactly one request, no retry.
- Redirect handling re-checks robots on each hop.
- Redaction of headers, URLs, and log output.
- Catalog normalization counts: 24/2/1/3.

## Acceptance

```bash
uv run pytest tests/unit/net tests/unit/logging tests/integration/net
uv run pytest
uv run mypy src
uv run ruff check .
```

Expected: all compliance tests pass; no test contacts a non-loopback host.

## Out of scope

- Downloading media files.
- `links.txt` export.
- CLI retrieval commands.

## Handoff

Phase 4 uses this client for media downloads and export resolution. All downloads must reuse the same limiter and robots checks; do not create a second HTTP client.
