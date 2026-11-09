'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { test } = require('node:test');

const wrapper = path.join(__dirname, '..', '..', 'bin', 'manji.js');

function run(args, env = {}) {
  return spawnSync(process.execPath, [wrapper, ...args], {
    encoding: 'utf8',
    env: { ...process.env, ...env },
  });
}

test('delegates to MANJI_BINARY and forwards arguments', () => {
  const result = run(['-e', "process.stdout.write('ok')"], {
    MANJI_BINARY: process.execPath,
  });
  assert.equal(result.status, 0);
  assert.equal(result.stdout, 'ok');
});

test('propagates the child exit code', () => {
  const result = run(['-e', 'process.exit(7)'], {
    MANJI_BINARY: process.execPath,
  });
  assert.equal(result.status, 7);
});

test('reports an unsupported platform', () => {
  const result = run([], {
    MANJI_BINARY: '',
    MANJI_PLATFORM: 'plan9-x64',
  });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /no prebuilt binary/);
});

test('reports a missing MANJI_BINARY', () => {
  const result = run([], {
    MANJI_BINARY: path.join(__dirname, 'does-not-exist'),
  });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /MANJI_BINARY does not exist/);
});
