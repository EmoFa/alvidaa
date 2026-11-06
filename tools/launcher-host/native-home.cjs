#!/usr/bin/env node
'use strict';
// Persistent custom Home install/restore using the verified vendor restart path.
const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const assert = require('node:assert/strict');
const { Trial, bridgeHealth, hash, atomicWrite, CONFIG } = require('./native-trial.cjs');
const { restartEngine, captureContext, vendorOps } = require('./stock-ui-restart.cjs');
const { stageUpdate, applyUpdate, rollbackUpdate, finishUpdate } = require('./native-update.cjs');
const HOME = '/var/local/alvidaa/native-home';
const bridgeRequired = candidate => !fs.readFileSync(candidate, 'utf8').includes('ALVIDAA_FREE_MY_TV_NATIVE_V1');

class NativeHome extends Trial {
  constructor(options = {}) { super(options); this.state = this.p(HOME); }
  paused(operation) {
    assert.equal(this.engines().length, 0, 'refusing file/cache changes while UI is alive');
    operation();
  }
  restore() {
    if (this.load().update) rollbackUpdate(this);
    const prior = this.load();
    if (prior.phase === 'restored' && prior.stockConfigHash) {
      for (const entry of prior.files) {
        const expected = entry.file === CONFIG ? prior.stockConfigHash : entry.original;
        assert.equal(hash(fs.readFileSync(this.p(entry.file))), expected, 'concurrent edit: ' + entry.file);
      }
      return;
    }
    super.restore();
    assert.equal(this.engines().length, 0, 'refusing config changes while UI is alive');
    const m = this.load();
    const entry = m.files.find(file => file.file === CONFIG);
    const config = json(entry.backup);
    // Stock means stock Home, not the earlier watcher-to-browser workaround.
    config.watcher = Object.assign({}, config.watcher, { enabled: false });
    const data = Buffer.from(JSON.stringify(config, null, 2));
    atomicWrite(this.p(CONFIG), data, entry);
    m.stockConfigHash = hash(data);
    this.save(m);
  }
}
function json(file) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); }
  catch (error) { throw new Error('Cannot read ' + file + ': ' + error.message); }
}
function identity(pid) {
  try {
    const stat = fs.readFileSync('/proc/' + pid + '/stat', 'utf8');
    return stat.slice(stat.lastIndexOf(')') + 2).split(' ')[19];
  } catch (error) { if (error.code === 'ENOENT' || error.code === 'ESRCH') return null; throw error; }
}
function acquire(directory) {
  const lock = path.join(directory, 'operation.lock');
  const boot = fs.readFileSync('/proc/sys/kernel/random/boot_id', 'utf8').trim();
  if (fs.existsSync(lock)) {
    const old = json(lock);
    assert.ok(old.boot !== boot || identity(old.pid) !== old.born, 'another install/restore is running');
    fs.renameSync(lock, lock + '.stale-' + Date.now());
  }
  const fd = fs.openSync(lock, 'wx', 0o600);
  try {
    fs.writeFileSync(fd, JSON.stringify({ pid: process.pid, born: identity(process.pid), boot }));
    fs.fsyncSync(fd);
  } finally { fs.closeSync(fd); }
  return () => fs.unlinkSync(lock);
}
async function perform(home, context, action, restart = restartEngine, ops = vendorOps) {
  assert.ok(['install', 'update', 'restore'].includes(action), 'unknown operation');
  // Core shell must still be stock, including when restoring after a reboot.
  for (const [file, expected] of Object.entries(home.hashes)) {
    if (file.endsWith('/apps/launcher/js/app.js')) continue;
    assert.equal(hash(fs.readFileSync(home.p(file))), expected, 'shared shell changed: ' + file);
  }
  const change = action === 'install' ? () => home.applyFiles() :
    action === 'update' ? () => applyUpdate(home) : () => home.restore();
  try {
    const engine = await restart(ops(context, change));
    if (action === 'update') {
      finishUpdate(home, engine);
      return { phase: 'installed', enginePid: engine.pid };
    }
    const m = home.load();
    m.phase = action === 'restore' ? 'restored' : 'installed';
    m.enginePid = engine.pid;
    delete m.error;
    home.save(m);
    return { phase: m.phase, enginePid: engine.pid };
  } catch (error) {
    if (action === 'install' || action === 'update') {
      try {
        // Saved context also works if the custom engine already exited.
        const engine = await restart(ops(context, () => action === 'update' ? rollbackUpdate(home) : home.restore()));
        const m = home.load();
        m.phase = action === 'update' ? m.phase : 'restored'; m.enginePid = engine.pid; m.error = error.message;
        home.save(m);
      } catch (recoveryError) {
        const m = home.load();
        m.error = error.message; m.recoveryError = recoveryError.message;
        home.save(m);
        throw new Error(action + ' failed: ' + error.message + '; recovery failed: ' + recoveryError.message);
      }
    }
    throw error;
  }
}
function launchWorker(home, action) {
  const log = fs.openSync(path.join(home.state, 'worker.log'), 'a', 0o600);
  const child = cp.spawn(process.execPath, [__filename, 'worker', action], {
    detached: true, stdio: ['ignore', log, log], env: process.env
  });
  child.on('error', error => { console.error(error.message); process.exit(1); });
  child.unref(); fs.closeSync(log);
  console.log('Requested ' + action + '; check status. This is not confirmation of rendering.');
}
async function main() {
  assert.equal(process.getuid(), 0, 'root SSH required');
  const [command, arg] = process.argv.slice(2);
  const home = new NativeHome();
  if (command === 'status') {
    const m = home.load();
    console.log(JSON.stringify({ phase: m.phase, enginePid: m.enginePid, error: m.error, recoveryError: m.recoveryError }, null, 2));
    return;
  }
  if (command === 'preflight') {
    const result = home.preflight(arg);
    if (arg && bridgeRequired(arg)) await bridgeHealth();
    console.log(JSON.stringify(result, null, 2)); return;
  }
  if (command === 'install') {
    home.preflight(arg);
    if (bridgeRequired(arg)) await bridgeHealth();
    const context = captureContext();
    home.prepare(arg);
    // Private on-TV snapshot, never logged or uploaded; needed if UI is absent on recovery.
    fs.writeFileSync(path.join(home.state, 'context.json'), JSON.stringify(context), { flag: 'wx', mode: 0o600 });
    launchWorker(home, 'install'); return;
  }
  if (command === 'update') {
    const release = acquire(home.state);
    try { stageUpdate(home, arg); } finally { release(); }
    launchWorker(home, 'update'); return;
  }
  if (command === 'restore') {
    home.load(); // Require an existing backup before launching anything.
    launchWorker(home, 'restore'); return;
  }
  if (command === 'worker') {
    assert.ok(['install', 'update', 'restore'].includes(arg));
    const release = acquire(home.state);
    try {
      const contextFile = path.join(home.state, 'context.json');
      const context = home.engines().length ? captureContext() : json(contextFile);
      atomicWrite(contextFile, JSON.stringify(context), { uid: 0, gid: 0, mode: 0o600 });
      const result = await perform(home, context, arg);
      console.log(new Date().toISOString(), JSON.stringify(result));
    } finally { release(); }
    return;
  }
  throw new Error('Use preflight candidate, install candidate, update candidate, status, or restore');
}
if (require.main === module) main().catch(error => { console.error(error.stack); process.exit(1); });
module.exports = { NativeHome, perform, acquire };
