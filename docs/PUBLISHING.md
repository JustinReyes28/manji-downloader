# Publishing to npm

This document records the state of npm publishing for Manji Downloader: what is
already in place, what is verified, what is blocked, and the exact steps to
publish. It exists because `npx manji-downloader` and
`npm install -g manji-downloader` are documented in the README but cannot work
until the packages are on the public registry.

**Current status: PUBLISHED. `v0.1.0` was released on 2026-11-09 and all six
packages are live on npm.**

```bash
npx manji-downloader@0.1.0 version     # -> manji 0.1.0
npm install -g manji-downloader        # -> manji version -> manji 0.1.0
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
- **Migrate to trusted publishing** before January 2027 (see §4.2).
- **PyPI is still not published** — the `publish-python` job was skipped because
  `PYPI_ENABLED` is unset. Follow §4.3, then set the variable and re-tag a new
  version (npm already holds `0.1.0`).

---

## 1. Answer: can we publish?

**Technically yes — the project is ready. It is blocked only on credentials that
the maintainer must supply.**

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

## 4. Steps for the maintainer

### 4.1 Re-authenticate npm locally

```bash
npm login
npm whoami          # must print your npm username
```

If the old token in `~/.npmrc` is stale, `npm login` replaces it. Verify it has
publish rights to the unscoped names listed above.

### 4.2 Create a granular token with 2FA bypass, then set the repository secret

This is the one step that cannot be automated. Verified on 2026-11-09: the
account has 2FA set to `auth-and-writes`, and the session token written by
`npm login` **cannot publish unattended** — a probe publish failed with
`EOTP` (one-time password required). A tag-triggered CI release using that token
would fail at the first platform package.

npm only offers **granular** access tokens in the web UI now; there is no
classic "Automation" type. Use these exact settings:

1. Open <https://www.npmjs.com/settings/justinreyes28/tokens> →
   **Generate New Token** → **Granular Access Token**.
2. Fill in:

   | Field | Value |
   | --- | --- |
   | Token name | `manji-downloader-ci` |
   | Bypass two-factor authentication (2FA) | **Checked** — required for unattended CI |
   | Allowed IP ranges | blank (GitHub-hosted runner IPs are dynamic) |
   | Packages and scopes → Permissions | **Read and write (publish and stage)** |
   | Select Packages | **All Packages** |
   | Organizations | No access |
   | Expiration | 30 days |

   **All Packages is mandatory.** The six `manji-downloader*` packages do not
   exist yet, so "Only select packages and scopes" cannot list them and the
   first publish would be rejected.

3. Generate, copy the token once, then:

   ```bash
   gh secret set NPM_TOKEN
   ```

   Paste at the prompt. Never commit it and never put it in a `.npmrc` inside
   the repository.

4. Confirm the flow works before tagging. A publish that needs an OTP fails with
   `EOTP`; the workflow will show that error on the first platform package.

`npm token create` is not a workaround: it prompts for a password and an OTP
interactively and cannot mint granular tokens at all.

#### This token is temporary

npm is retiring 2FA-bypass publishing around **January 2027**; such tokens will
only be able to read private packages and stage a publish for human approval.
Plan to migrate to trusted publishing:

1. After the first successful release, open each of the six packages on
   npmjs.com → **Settings → Trusted Publisher → GitHub Actions**.
2. Set owner `JustinReyes28`, repository `manji-downloader`, workflow
   filename `release.yml`, and allow direct publishing with `npm publish`.
3. Remove `NODE_AUTH_TOKEN` from `.github/workflows/release.yml`. The workflow
   already declares `id-token: write`, which is all OIDC needs.
4. Revoke the granular token and delete the `NPM_TOKEN` secret.

A 2FA-bypass token cannot configure trusted publishers itself — that needs an
interactive 2FA challenge in the browser.

### 4.3 Configure PyPI trusted publishing

1. Create a `pypi` environment in the repository (Settings → Environments).
2. On PyPI, add a trusted publisher for the project with:
   - Owner: `JustinReyes28`
   - Repository: `manji-downloader`
   - Workflow: `release.yml`
   - Environment: `pypi`

No long-lived PyPI token is needed with trusted publishing.

### 4.4 Tag and push

```bash
git tag v0.1.0
git push origin v0.1.0
```

This triggers the release workflow. Watch it:

```bash
gh run watch
```

### 4.5 Verify the published packages

```bash
npm view manji-downloader version
npx -y manji-downloader@0.1.0 --version
npm install -g manji-downloader && manji version
```

Smoke-test on at least one machine per OS family, as required by
`PACKAGING.md`.

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

## 7. After publishing

Update these so the documentation matches reality:

- `README.md` — remove any "not published yet" wording once the release exists.
- `ROADMAP.md` — mark distribution as live under the MVP milestone.
- `docs/phases/README.md` — close the publishing blocker.
- `AGENTS.md` — note that releases happen via tag, not manually.

## 8. Things to keep in mind

- **Version sync is enforced.** `scripts/check_versions.py` fails if
  `pyproject.toml`, `package.json`, and every platform package disagree. Bump all
  of them together.
- **Never add a `postinstall` script.** It would break the no-install-time-network
  guarantee behind `npx` and behind proxies.
- **Unpublishing is limited.** npm allows unpublishing within 72 hours; after
  that a version is effectively permanent. Verify with a dry run and the
  container harness before tagging.
- **`npm manji-downloader` alone is not a command.** Use `npx manji-downloader`
  or install globally.
- **Binaries are not committed.** `npm/platforms/*/` is gitignored; they are
  build artifacts produced by the workflow.
