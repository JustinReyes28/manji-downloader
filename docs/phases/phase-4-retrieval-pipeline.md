# Phase 4 — Retrieval Pipeline

**Status:** Complete (commit `4675c08`)
**Depends on:** Phase 3
**Unlocks:** Phase 5
**Commit checkpoint:** `phase 4: retrieval pipeline`

## Goal

Implement the final output paths: compliant streaming downloads, `links.txt` export, and organized filenames with metadata sidecars.

## Deliverables

- [x] `src/manji/download/downloader.py` streaming downloader with atomic writes and Range resume.
- [x] Conflict policies: `overwrite`, `skip`, `rename`.
- [x] `src/manji/export/links.py` for `links.txt` and `links-manifest.json`.
- [x] `src/manji/organize/filenames.py` templates, sanitization, and safe path joins.
- [x] `src/manji/organize/sidecars.py` metadata writers.
- [x] `src/manji/fs.py` atomic text/binary write helpers.
- [x] Unit and integration tests using the Phase 3 mock servers.

## Downloader

- Stream in 64 KB chunks to `<destination>.tmp` in the destination directory.
- Check a stop event between chunks and stop promptly.
- Verify content length when the server provides it.
- Flush and `os.fsync`, close, then `os.replace` into place.
- Resume:
  - Reuse an existing `.tmp` and send `Range` plus `If-Range` with stored ETag/Last-Modified.
  - A 206 response appends; a 200 response restarts from zero.
  - A 416 response either finalizes an already complete file or raises a clear error.
- Write resume metadata next to the temp file and remove it on success.
- On cancellation or interruption, keep `.tmp` and metadata so the download can resume.
- All requests go through the shared Phase 3 client, including robots checks and rate limits.

## Exporter

- `links.txt`: one resolved URL per line, final newline, category order Episodes → OVAs → Movies → Specials, then item order.
- `links-manifest.json`:
  - `version`, `generated_at`, `series`, and an ordered `entries` array of `{url, filename}`.
  - Written atomically.
- Warn when a URL contains sensitive query parameters; do not silently strip them.
- Empty selection is an error.

## Organizer

- Template variables: `{series_title}`, `{site_id}`, `{category}`, `{episode_number}`, `{quality}`, `{id}`, `{date}`, `{ext}`.
- Unknown variables are errors.
- `{episode_number}` is zero-padded to two digits.
- Sanitize illegal characters for Windows, macOS, and Linux.
- Reject path traversal, absolute paths, and reserved Windows names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`).
- Trim trailing dots and spaces; enforce a safe segment length.
- Provide `safe_join(base, relative)` and verify the result stays under the base directory.
- Write `series.json` and `episode.yaml` with adapter ID, source URL, variant metrics, and timestamp. Omit credentials and signed media URLs or store them redacted.

## Tests

- Download success, content-length mismatch, cancellation, and atomic replace.
- Resume from a partial file, server ignores Range, and 416 handling.
- Skip, overwrite, and rename conflict policies.
- `links.txt` ordering and exact contents.
- Manifest schema and ordering.
- Filename sanitization on all platforms, reserved names, traversal attempts, and unknown variables.
- Sidecar contents exclude secrets and signed URLs.

## Acceptance

```bash
uv run pytest tests/unit/download tests/unit/export tests/unit/organize tests/integration/download
uv run pytest
uv run mypy src
uv run ruff check .
```

Expected: all tests pass and no `.tmp` file is left behind after a successful download.

## Out of scope

- CLI command wiring.
- Interactive prompts.
- Real site adapters.

## Handoff

Phase 5 wires these services into the CLI and the mock end-to-end scenario. Keep the service APIs independent of Typer.
