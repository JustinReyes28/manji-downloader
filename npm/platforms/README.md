# Generated npm platform packages

This directory is populated by the release workflow. Each supported platform gets
a generated package containing a PyInstaller binary:

```text
npm/platforms/win32-x64/
  package.json
  manji.exe
npm/platforms/linux-x64/
  package.json
  manji
```

The generated package metadata includes the matching `os` and `cpu` fields so
npm installs only the current platform. Binaries are never committed to the
repository; they are release artifacts uploaded by CI.

The root `manji-downloader` package references these packages through
`optionalDependencies`. See [PACKAGING.md](../../PACKAGING.md) for the full
release process.
