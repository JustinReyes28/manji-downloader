# Publishing to npm and PyPI

This document records the publishing setup for Manji Downloader: what is live,
how a release is cut, and what still needs manual cleanup. It exists because
release mistakes here are expensive — npm versions are effectively permanent, and
a half-published release breaks `npx` for some platforms.

**Current status: PUBLISHED. `0.1.0` is live on npm; `0.1.1` adds PyPI.**

```bash
npx manji-downloader@0.1.1 version     # -> manji 0.1.1
npm install -g manji-downloader        # -> manji version -> manji 0.1.1
uv tool install manji-downloader==0.1.1
```

Release run: <https://github.com/JustinReyes28/manji-downloader/actions/runs/42598433091>

| Package | Version |
| --- | --- |
| `manji-downloader` | 0.1.0 |
| `manji-downloader-win32-x64` | 0.1.0 |
| `manji-downloader-darwin-x64` | 0.1.0 |
| `manji-downloader-darwin-arm64` | 0.1.0 |
| `manji-downloader-linux-x64` | 0.1.0 |
| `manji-downloader-linux-arm64` | 0.1.0 |

### Follow-ups from the first release

- **Staged placeholders remain.** npm creates a `0.0.0-stage` placeholder version
  on each package during first publish. It is harmless (it is not the `latest`
  dist-tag) but cannot be removed by an unattended token — unpublish requires an
  interactive OTP. Remove it in a browser session if you want a clean version
  list.
- **`manji-downloader-probe-zz` exists.** A throwaway package was published while
  verifying that the token could publish unattended. It is unrelated to the
  project and should be deleted from npmjs.com (Packages → delete), which needs
  an interactive 2FA confirmation.
- **The bootstrap token must be revoked.** It was pasted into a chat transcript in
  plaintext and is therefore public. Revoke `manji-downloader-ci` at
  <https://www.npmjs.com/settings/justinreyes28/tokens> and delete the
  `NPM_TOKEN` secret once the first OIDC release is green. See §4.4 for the
  fallback if OIDC has trouble.

---

## 1. Answer: can we publish?

**Yes — and we have. All six packages are public.** This section is kept as the
record of what was verified before the first release.

Verified on 2026-11-09:

| Check | Result |
| --- | --- |
| All six npm package names | Available (404 from the registry) |
| Root package `npm publish --dry-run` | Succeeds, 4 files, 7.4 kB tarball |
| Root package contents | `bin/manji.js`, `README.md`, `LICENSE`, `package.json` only |
| `postinstall` scripts | None (by design; binaries ship as optional dependencies) |
| Platform package generation | Verified end to end in a container |
| `npx` + global install from a registry | Verified end to end in a container |
| PyPI name `manji-downloader` | Available |
| `pyproject.toml` version | `0.1.0`, matches all npm packages |
| Repository visibility | Public |

What is **missing**:

| Blocker | Detail |
| --- | --- |
| npm publish token | **The one real blocker.** 2FA is `auth-and-writes`, and the `npm login` session token cannot publish unattended (`EOTP`, verified with a probe publish). CI needs a **granular token with 2FA bypass** (see §4.2). |
| PyPI trusted publisher | No `pypi` GitHub environment exists (0 environments). The release workflow now skips that job until `PYPI_ENABLED=true` is set, so it does not block npm. |
| Release binaries | None exist yet. They are built by the workflow on a tag. |
| Version tag | No `v*` tag exists locally or on the remote. |

Already done:

| Item | Status |
| --- | --- |
| npm account login | Verified: `npm whoami` returns `justinreyes28` |
| `NPM_TOKEN` secret | Set — but currently holds the session token, which cannot publish. Replace with an Automation token. |
| Release workflow auth | Fixed: `NODE_AUTH_TOKEN` is now job-level so every platform publish authenticates |
| macOS runners | Fixed: `macos-13`/`macos-14` are retired; now `macos-15-intel` / `macos-15` |
| PyPI job isolation | Gated behind `vars.PYPI_ENABLED` so it cannot fail an npm-only release |

Nothing here is a code problem. Each item is a one-time setup action by the
repository owner.

---

## 2. What publishing involves

Two packages must exist and the order matters:

1. **Five platform packages** — `manji-downloader-{os}-{arch}`. Each carries a
   ~22 MB PyInstaller binary and declares `os`/`cpu` so npm installs only the
   matching one.
2. **The root launcher** — `manji-downloader`. It ships only `bin/manji.js` and
   resolves the platform package at runtime.

The root package must be published **last**. If it went first, every `npx` run
would fail with "missing platform package" until the platform packages appeared.

| npm package | `os` | `cpu` | Binary |
| --- | --- | --- | --- |
| `manji-downloader-win32-x64` | `win32` | `x64` | `manji.exe` |
| `manji-downloader-darwin-x64` | `darwin` | `x64` | `manji` |
| `manji-downloader-darwin-arm64` | `darwin` | `arm64` | `manji` |
| `manji-downloader-linux-x64` | `linux` | `x64` | `manji` |
| `manji-downloader-linux-arm64` | `linux` | `arm64` | `manji` |

---

## 3. How the release workflow does it

`.github/workflows/release.yml` runs on a `v*` tag:

1. `verify` — lint, format, mypy, pytest, version-sync check.
2. `binaries` — five runners build PyInstaller binaries and generate platform
   packages as artifacts.
3. `publish-python` — builds the wheel/sdist and publishes to PyPI via trusted
   publishing.
4. `publish-npm` — downloads all five platform artifacts, publishes each
   platform package, then publishes the root launcher.

### Fix applied

`NODE_AUTH_TOKEN` was previously set only on the final publish step, so the five
platform publishes would have failed with `E401`. It is now set at the job level
so every publish step authenticates, and the workflow fails loudly if a platform
artifact is missing instead of publishing a partial release.

---

## 4. How releases are made

Publishing is **tag-driven** and uses **trusted publishing (OIDC)** for npm and
PyPI. No long-lived registry token is stored.

### 4.1 Prerequisites (one-time)

**npm — a trusted publisher on each of the six packages.** Open each package on
npmjs.com → **Settings → Trusted Publisher → GitHub Actions**:

| Field | Value |
| --- | --- |
| Organization or user | `JustinReyes28` |
| Repository | `manji-downloader` |
| Workflow filename | `release.yml` |
| Environment name | blank |
| Allowed actions | allow **`npm publish`** |

Notes that have bitten before:

- Connections **cannot be edited** — delete and recreate on any typo.
- A new connection must complete its first successful publish **within 2 days**
  or it expires. Configure immediately before tagging.
- OIDC needs **npm ≥ 11.5.1 / Node ≥ 22.14**. The workflow uses Node 24 and
  asserts the npm version.

**PyPI — a trusted publisher.** PyPI → Publishing → add a pending publisher with
owner `JustinReyes28`, repository `manji-downloader`, workflow `release.yml`,
environment `pypi`. The matching GitHub environment exists, and the workflow's
`publish-python` job is enabled by the repository variable `PYPI_ENABLED=true`.

### 4.2 Cut the release

```bash
git tag v0.1.1
git push origin v0.1.1
gh run watch
```

Bump the version in `pyproject.toml` **and** in `package.json` (both `version`
and every `optionalDependencies` pin) before tagging.
`scripts/check_versions.py` fails the release on drift, and the workflow also
verifies the launcher pins match the build version.

### 4.3 Verify

```bash
npm view manji-downloader version
npx -y manji-downloader@0.1.1 version
npm install -g manji-downloader@0.1.1 && manji version
uv tool install manji-downloader==0.1.1 && manji version
```

### 4.4 Fallback: token-based publishing

Only if OIDC is unavailable. A granular token with 2FA bypass can still publish,
but npm is retiring that capability around **January 2027**, and such tokens
cannot unpublish or manage trusted publishers. If you must use one:

1. Generate a granular token: **Bypass two-factor authentication** checked,
   **Read and write (publish and stage)**, **All Packages**, 30-day expiry.
2. `gh secret set NPM_TOKEN`.
3. Re-add to `.github/workflows/release.yml` under `publish-npm`:

   ```yaml
   env:
     NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
   ```

   and restore `registry-url: "https://registry.npmjs.org"` on `setup-node`.
4. Remove both again once OIDC works.

`npm token create` is not a workaround: it prompts for a password and an OTP
interactively and cannot mint granular tokens at all.

---

## 5. If you want a manual publish first

The workflow is the supported path, but a one-off manual publish is possible for
a single platform. Every binary must be built on its native OS; PyInstaller does
not cross-compile.

```bash
# On a Linux x64 host, from the repository root:
uv sync --group build
uv run pyinstaller manji.spec --distpath dist --workpath build/pyinstaller

uv run python scripts/build_platform_package.py \
  --platform linux-x64 --binary dist/manji --output npm/platforms

npm publish npm/platforms/linux-x64 --access public
npm publish --access public
```

Repeat per platform, then publish the root package. A partial publish leaves
`npx` broken for the missing platforms, so prefer the workflow.

---

## 6. Verified container evidence

The `docker/npm-smoke/` harness proves the whole install path works today
against a local registry, without touching the host:

```bash
docker compose -f docker/npm-smoke/compose.yaml build lab
docker compose -f docker/npm-smoke/compose.yaml up \
  --abort-on-container-exit --exit-code-from lab
```

It builds the Linux binary, generates the platform package, publishes both
packages, then runs:

```text
npx manji-downloader --help              -> help output
npx manji-downloader version             -> manji 0.1.0
npx manji-downloader adapters list       -> No adapters registered.
npm install -g manji-downloader          -> added 2 packages
manji version                            -> manji 0.1.0
manji --help                             -> help output
ALL NPM SMOKE CHECKS PASSED
```

The only untested-by-release difference is the registry itself: the harness uses
Verdaccio instead of `registry.npmjs.org`. Publishing to npmjs.org exercises the
same package contents and the same launcher logic.

---

## 7. Documentation checklist (done)

These are complete; keep them true when releasing again:

- `README.md` — install commands show the published versions.
- `ROADMAP.md` — distribution is marked live under the MVP milestone.
- `docs/phases/README.md` — the publishing blocker is closed.
- `AGENTS.md` — records that releases are tag-driven, never manual.

## 8. Things to keep in mind

- **Version sync is enforced.** `scripts/check_versions.py` fails if
  `pyproject.toml`, `package.json`, the `optionalDependencies` pins, or any
  platform package disagree. Bump all of them together; the release workflow
  re-checks the pins before publishing.
- **Never add a `postinstall` script.** It would break the no-install-time-network
  guarantee behind `npx` and behind proxies.
- **Unpublishing is limited.** npm allows unpublishing within 72 hours; after
  that a version is effectively permanent. Verify with a dry run and the
  container harness before tagging.
- **`npm manji-downloader` alone is not a command.** Use `npx manji-downloader`
  or install globally.
- **Binaries are not committed.** `npm/platforms/*/` is gitignored; they are
  build artifacts produced by the workflow.
- **No npm secret should exist.** If `gh secret list` shows `NPM_TOKEN`, OIDC is
  not fully in use yet — finish the migration in §4.4.
