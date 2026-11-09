#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');

const PLATFORMS = {
  'win32-x64': { package: 'manji-downloader-win32-x64', binary: 'manji.exe' },
  'darwin-x64': { package: 'manji-downloader-darwin-x64', binary: 'manji' },
  'darwin-arm64': { package: 'manji-downloader-darwin-arm64', binary: 'manji' },
  'linux-x64': { package: 'manji-downloader-linux-x64', binary: 'manji' },
  'linux-arm64': { package: 'manji-downloader-linux-arm64', binary: 'manji' },
};

function fail(message) {
  process.stderr.write(`manji-downloader: ${message}\n`);
  process.exit(1);
}

function resolveBinary() {
  if (process.env.MANJI_BINARY) {
    if (!fs.existsSync(process.env.MANJI_BINARY)) {
      fail(`MANJI_BINARY does not exist: ${process.env.MANJI_BINARY}`);
    }
    return process.env.MANJI_BINARY;
  }

  const platformKey = process.env.MANJI_PLATFORM || `${process.platform}-${process.arch}`;
  const target = PLATFORMS[platformKey];
  if (!target) {
    fail(
      `no prebuilt binary for ${platformKey}.\n` +
        'Install the Python package instead: uv tool install manji-downloader',
    );
  }

  let packageJson;
  try {
    packageJson = require.resolve(`${target.package}/package.json`);
  } catch {
    fail(
      `missing platform package ${target.package}.\n` +
        'Reinstall with npm, or install the Python package: uv tool install manji-downloader',
    );
  }

  const binaryPath = path.join(path.dirname(packageJson), target.binary);
  if (!fs.existsSync(binaryPath)) {
    fail(`platform package ${target.package} does not contain ${target.binary}`);
  }
  return binaryPath;
}

function main() {
  const binaryPath = resolveBinary();

  if (process.platform !== 'win32') {
    try {
      fs.chmodSync(binaryPath, 0o755);
    } catch {
      // The spawn below reports a useful error if the file is still not executable.
    }
  }

  const child = spawn(binaryPath, process.argv.slice(2), {
    stdio: 'inherit',
    windowsHide: true,
  });

  child.on('error', (error) => {
    fail(`failed to start ${binaryPath}: ${error.message}`);
  });

  child.on('exit', (code, signal) => {
    if (signal) {
      try {
        process.kill(process.pid, signal);
      } catch {
        process.exit(1);
      }
      return;
    }
    process.exit(code ?? 1);
  });
}

main();
