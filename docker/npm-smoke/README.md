# npm installation smoke test

This directory proves that the two documented npm entry points work end to end,
inside a disposable container, without installing anything on the host:

```bash
npx manji-downloader --help
npm install -g manji-downloader && manji --help
```

## Why a local registry?

Nothing is published to npmjs.org yet. `npm view manji-downloader` returns 404
until the release workflow in `.github/workflows/release.yml` runs against a
`v*` tag. To test the real install path anyway, this harness:

1. Builds a Linux `manji` binary with PyInstaller inside the container.
2. Generates the matching `manji-downloader-linux-x64` platform package.
3. Publishes both packages to a throwaway [Verdaccio](https://verdaccio.org/)
   registry on the internal compose network.
4. Installs from that registry using the exact commands a user would run.

No host files, npm caches, or global installs are touched, and the registry is
not exposed to the host.

## Run it

```bash
docker compose -f docker/npm-smoke/compose.yaml build lab
docker compose -f docker/npm-smoke/compose.yaml up \
  --abort-on-container-exit --exit-code-from lab
```

A successful run ends with `ALL NPM SMOKE CHECKS PASSED` and exits 0.

## Clean up

```bash
docker compose -f docker/npm-smoke/compose.yaml down -v
docker rmi npm-smoke-lab:latest
```

The `-v` flag also removes the registry storage volume.

## Notes

- The architecture is detected from `uname -m`, so the harness works on both
  x64 and arm64 hosts; the platform package name follows automatically.
- `verdaccio.yaml` sets `max_body_size: 200mb` because the PyInstaller binary is
  roughly 22 MB, above Verdaccio's 10 MB default publish limit.
- Publishing uses a throwaway account created through Verdaccio's adduser
  endpoint. npm refuses to publish with no credentials even when the registry
  allows anonymous access.
- This is a distribution test only. Once the packages are published, the same
  commands work against the public registry with no local registry involved.
