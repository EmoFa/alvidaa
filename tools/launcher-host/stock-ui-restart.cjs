#!/usr/bin/env node
'use strict';
// Stock-only lifecycle test. Never installs a launcher or changes caches.
const fs = require('node:fs');
const cp = require('node:child_process');
const assert = require('node:assert/strict');
const { HASHES, hash, atomicWrite } = require('./native-trial.cjs');
const ENGINE = '/opt/hisenseUI/bin/hisenseUI';
const CONFIG = '/var/local/alvidaa/config.json';
const DIR = '/var/local/alvidaa/stock-restart-check';
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

function processes() {
  const found = [];
  for (const id of fs.readdirSync('/proc').filter(id => /^\d+$/.test(id))) {
    try {
      const base = '/proc/' + id;
      if (fs.readlinkSync(base + '/exe') !== ENGINE) continue;
      const stat = fs.readFileSync(base + '/stat', 'utf8');
      const born = stat.slice(stat.lastIndexOf(')') + 2).split(' ')[19];
      const status = fs.readFileSync(base + '/status', 'utf8');
      const credentials = status.split('\n').filter(line => /^(Uid|Gid|Groups|CapEff):/.test(line))
        .map(line => line.trim().replace(/\s+/g, ' ')).join('\n');
      found.push({ pid: Number(id), identity: id + ':' + born, credentials });
    } catch (error) { if (error.code !== 'ENOENT' && error.code !== 'ESRCH') throw error; }
  }
  return found;
}
async function restartEngine(ops) {
  const initial = ops.list();
  assert.ok(initial.length <= 1, 'expected at most one UI engine');
  const original = initial[0] || ops.original;
  assert.ok(original, 'expected exactly one stock UI engine or saved recovery context');
  if (initial.length) ops.stop(original);
  let current;
  for (let i = 0; i < 30; i++) {
    await ops.wait(200);
    current = ops.list();
    if (!current.some(p => p.identity === original.identity)) break;
  }
  assert.ok(!current.some(p => p.identity === original.identity), 'SIGTERM did not stop engine; no forced kill or duplicate launch');
  await ops.wait(2000);
  current = ops.list();
  assert.ok(current.length <= 1, 'multiple UI engines; refusing to launch another');
  if (ops.change) {
    assert.equal(current.length, 0, 'engine restarted before file change; refusing live mutation');
    await ops.change();
  }
  if (current.length === 0) await ops.launch();
  for (let i = 0; i < 60; i++) {
    current = ops.list();
    assert.ok(current.length <= 1, 'multiple UI engines after restart');
    if (current.length === 1) break;
    await ops.wait(500);
  }
  assert.equal(current.length, 1, 'UI did not start; stock files are unchanged, cold power cycle may be needed');
  assert.notEqual(current[0].identity, original.identity, 'old engine still present');
  assert.equal(current[0].credentials, original.credentials, 'restarted engine credentials mismatch');
  const replacement = current[0];
  await ops.wait(3000);
  const stable = ops.list();
  assert.equal(stable.length, 1, 'engine did not remain alive');
  assert.equal(stable[0].identity, replacement.identity, 'engine restarted/crashed during stability window');
  return replacement;
}
function captureContext() {
  const current = processes();
  assert.equal(current.length, 1, 'expected one live engine to capture');
  const original = current[0];
  const env = {};
  for (const item of fs.readFileSync('/proc/' + original.pid + '/environ', 'utf8').split('\0')) {
    const split = item.indexOf('=');
    if (split > 0) env[item.slice(0, split)] = item.slice(split + 1);
  }
  assert.equal(processes()[0]?.identity, original.identity, 'engine changed during context capture');
  return { original, env };
}
function vendorOps(context, change) {
  return {
    list: processes, wait, original: context.original, change,
    stop(info) {
      assert.equal(info.credentials, context.original.credentials, 'unexpected engine credentials');
      assert.ok(processes().some(p => p.identity === info.identity), 'engine PID changed');
      process.kill(info.pid, 'SIGTERM');
    },
    launch() {
      assert.equal(processes().length, 0, 'another engine appeared');
      return new Promise((resolve, reject) => {
        const child = cp.spawn('/usr/local/bin/secure_exec', ['hisenseUI', '/opt/hisenseUI/startgui.sh'],
          { env: context.env, cwd: '/opt/hisenseUI', detached: true, stdio: 'ignore' });
        child.once('error', reject);
        child.once('spawn', () => { child.unref(); resolve(); });
      });
    }
  };
}
async function main() {
  assert.equal(process.getuid(), 0, 'root SSH required');
  assert.equal(process.argv[2], '--watching', 'operator must be watching the TV');
  for (const [file, expected] of Object.entries(HASHES)) {
    assert.equal(hash(fs.readFileSync(file)), expected, 'not stock: ' + file);
  }
  const initial = processes();
  assert.equal(initial.length, 1);
  const original = initial[0];
  // Keep platform environment private/in-memory; do not print device identifiers.
  const env = {};
  for (const item of fs.readFileSync('/proc/' + original.pid + '/environ', 'utf8').split('\0')) {
    const split = item.indexOf('=');
    if (split > 0) env[item.slice(0, split)] = item.slice(split + 1);
  }
  assert.equal(processes()[0]?.identity, original.identity, 'engine changed while capturing context');
  const metadata = fs.lstatSync(CONFIG);
  assert.ok(metadata.isFile() && !metadata.isSymbolicLink());
  const raw = fs.readFileSync(CONFIG);
  let config;
  try { config = JSON.parse(raw); } catch { throw new Error('invalid bridge configuration'); }
  config.watcher = Object.assign({}, config.watcher, { enabled: false });
  const disabled = Buffer.from(JSON.stringify(config, null, 2));
  fs.mkdirSync(DIR, { mode: 0o700 }); // Existing test evidence is never overwritten.
  fs.writeFileSync(DIR + '/config.original', raw, { flag: 'wx', mode: 0o600 });
  const state = { phase: 'prepared', originalPid: original.pid };
  function record() { fs.writeFileSync(DIR + '/state.json', JSON.stringify(state, null, 2), { mode: 0o600 }); }
  record();
  try {
    atomicWrite(CONFIG, disabled, metadata);
    // Allow an already-scheduled watcher action to finish before the restart.
    await wait(7000);
    assert.equal(processes()[0]?.identity, original.identity, 'engine changed before test');
    state.phase = 'restarting'; record();
    const replacement = await restartEngine({
      list: processes, wait,
      stop(processInfo) {
        assert.equal(processInfo.identity, original.identity, 'different engine');
        assert.ok(processes().some(p => p.identity === processInfo.identity), 'engine PID changed');
        process.kill(processInfo.pid, 'SIGTERM');
      },
      launch() {
        assert.equal(processes().length, 0, 'another engine appeared');
        return new Promise((resolve, reject) => {
          const child = cp.spawn('/usr/local/bin/secure_exec', ['hisenseUI', '/opt/hisenseUI/startgui.sh'],
            { env, cwd: '/opt/hisenseUI', detached: true, stdio: 'ignore' });
          child.once('error', reject);
          child.once('spawn', () => { child.unref(); resolve(); });
        });
      }
    });
    state.phase = 'engine-running'; state.pid = replacement.pid; record();
    console.log('ENGINE RUNNING WITH MATCHING CREDENTIALS. Press Home; confirm STOCK Home. Watcher off for 60 seconds.');
    await wait(60000);
  } catch (error) {
    state.error = error.message;
    throw error;
  } finally {
    // Do not overwrite another session's edits. No UI/cache files are touched.
    assert.equal(hash(fs.readFileSync(CONFIG)), hash(disabled), 'concurrent config change; original is in ' + DIR);
    atomicWrite(CONFIG, raw, metadata);
    state.phase = 'config-restored'; record();
    console.log('Original watcher config restored.');
  }
}
if (require.main === module) main().catch(error => { console.error(error.stack); process.exit(1); });
module.exports = { restartEngine, captureContext, vendorOps, processes };
