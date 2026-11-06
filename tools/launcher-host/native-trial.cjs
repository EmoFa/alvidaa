#!/usr/bin/env node
/* Trial execution DISABLED after the first hardware test: APM did not restart
 * the killed UI engine. Retained for read-only inspection, recovery when the
 * engine is absent, and local fault tests. See findings/08-native-live-trial.md.
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const vm = require('node:vm');
const cp = require('node:child_process');
const http = require('node:http');
const assert = require('node:assert/strict');
const HASHES = {
  '/APPS/channelA/hisenseUI/index.html': '2adbd1b1a6818eea861ca40f6cf7656024b1eb9fd42407aef0407aab8bcc92c4',
  '/APPS/channelA/hisenseUI/static/js/537.js': 'a32da977444d521a7b4c81ea1fac0a5c859468d6db059d26f755d4c5549e1e48',
  '/APPS/channelA/operation-ui/apps/launcher/js/app.js': '046b41aee0242ced3d3fcd9d5e0c0adb68e17ea3bfe14efa13d6225b6050bfad'
};
const APP = '/APPS/channelA/operation-ui/apps/launcher/js/app.js';
const CONFIG = '/var/local/alvidaa/config.json';
const STATE = '/var/local/alvidaa/native-trial';
const CACHE = '/var/local/hisenseUI/cobalt_home/.cache/cobalt';
const ENGINE = '/opt/hisenseUI/bin/hisenseUI';
const CACHE_NAMES = ['compiled_js', 'uncompiled_js'];
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const DISABLED = 'Trial disabled: UI restart strategy failed on hardware; validate stock-only restart first';
function assertCommandEnabled(command) {
  assert.ok(command !== 'start' && command !== 'worker', DISABLED);
}

function engines() {
  return fs.readdirSync('/proc').filter(id => /^\d+$/.test(id)).flatMap(id => {
    try { return fs.readlinkSync('/proc/' + id + '/exe') === ENGINE ? [Number(id)] : []; }
    catch { return []; }
  });
}
function signalEngine(pid, signal) {
  try {
    assert.equal(fs.readlinkSync('/proc/' + pid + '/exe'), ENGINE, 'engine PID changed');
    process.kill(pid, signal);
  } catch (error) { if (error.code !== 'ENOENT' && error.code !== 'ESRCH') throw error; }
}
function atomicWrite(file, data, metadata) {
  const tmp = file + '.native-tmp-' + process.pid;
  const fd = fs.openSync(tmp, 'wx', 0o600);
  try {
    try {
      fs.writeFileSync(fd, data);
      fs.fchownSync(fd, metadata.uid, metadata.gid);
      fs.fchmodSync(fd, metadata.mode & 0o7777);
      fs.fsyncSync(fd);
    } finally { fs.closeSync(fd); }
    fs.renameSync(tmp, file);
  } finally { if (fs.existsSync(tmp)) fs.unlinkSync(tmp); }
}
function readJSON(file) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); }
  catch (error) { throw new Error('Cannot read valid JSON from ' + file + ': ' + error.message); }
}
function regular(file) {
  const st = fs.lstatSync(file);
  assert.ok(st.isFile() && !st.isSymbolicLink(), 'not a regular file: ' + file);
  return st;
}

class Trial {
  constructor(options = {}) {
    // Root redirection and engine callbacks exist solely for local fault tests.
    this.root = options.root || '';
    this.hashes = options.hashes || HASHES;
    this.engines = options.engines || engines;
    this.signal = options.signal || signalEngine;
    this.state = this.p(STATE);
  }
  p(file) { return this.root + file; }
  preflight(candidate) {
    for (const [file, expected] of Object.entries(this.hashes)) {
      regular(this.p(file));
      assert.equal(hash(fs.readFileSync(this.p(file))), expected, 'baseline changed: ' + file);
    }
    assert.ok(!fs.existsSync(this.state), 'existing trial/backup: inspect or recover it; never overwrite');
    const config = readJSON(this.p(CONFIG));
    assert.ok(config && typeof config === 'object' && !Array.isArray(config));
    regular(this.p(CONFIG));
    for (const name of CACHE_NAMES) {
      const st = fs.lstatSync(this.p(CACHE + '/' + name));
      assert.ok(st.isDirectory() && !st.isSymbolicLink(), 'unexpected cache path');
      assert.ok(!fs.existsSync(this.p(CACHE + '/' + name + '.native-original')), 'cache backup collision');
    }
    const ids = this.engines();
    assert.ok(ids.length, 'no known Cobalt engine process');
    if (candidate) {
      regular(candidate);
      const source = fs.readFileSync(candidate, 'utf8');
      assert.ok(source.includes('root._V_M_.launcher = function'), 'not a native launcher candidate');
      new vm.Script(source, { filename: candidate }); // Parse only; do not run UI code.
    }
    return { enginePids: ids, watcherEnabled: !!config.watcher?.enabled, baseline: 'matched' };
  }
  prepare(candidate) {
    this.preflight(candidate);
    fs.mkdirSync(this.state, { mode: 0o700 }); // Atomic exclusion, no recursive overwrite.
    const manifest = { phase: 'prepared', files: [], caches: [] };
    for (const file of [APP, CONFIG]) {
      const st = regular(this.p(file));
      const data = fs.readFileSync(this.p(file));
      const backup = path.join(this.state, String(manifest.files.length) + '.orig');
      fs.writeFileSync(backup, data, { flag: 'wx', mode: 0o600 });
      manifest.files.push({ file, backup, uid: st.uid, gid: st.gid, mode: st.mode, original: hash(data) });
    }
    fs.copyFileSync(candidate, path.join(this.state, 'candidate.js'), fs.constants.COPYFILE_EXCL);
    fs.chmodSync(path.join(this.state, 'candidate.js'), 0o600);
    this.save(manifest);
    return manifest;
  }
  save(manifest) {
    atomicWrite(path.join(this.state, 'state.json'), JSON.stringify(manifest, null, 2),
      { uid: process.getuid(), gid: process.getgid(), mode: 0o600 });
  }
  load() { return readJSON(path.join(this.state, 'state.json')); }
  paused(operation) {
    const ids = this.engines();
    assert.ok(this.root || ids.length === 0, DISABLED);
    const stopped = [];
    try {
      for (const id of ids) { this.signal(id, 'SIGSTOP'); stopped.push(id); }
      operation();
    } finally {
      // APM owns restart. Never run the engine as root or source /etc/profile.
      const failures = [];
      for (const id of stopped) {
        try { this.signal(id, 'SIGKILL'); }
        catch (error) {
          failures.push(error.message);
          try { this.signal(id, 'SIGCONT'); } catch (resumeError) { failures.push(resumeError.message); }
        }
      }
      if (failures.length) throw new Error('Engine restart failed: ' + failures.join('; '));
    }
  }
  apply() {
    assert.ok(this.root, DISABLED);
    return this.applyFiles();
  }
  applyFiles() {
    const m = this.load();
    assert.equal(m.phase, 'prepared');
    for (const entry of m.files) {
      assert.equal(hash(fs.readFileSync(this.p(entry.file))), entry.original, 'file changed since preflight');
    }
    const config = readJSON(m.files[1].backup);
    config.watcher = Object.assign({}, config.watcher, { enabled: false });
    const writes = [fs.readFileSync(path.join(this.state, 'candidate.js')), Buffer.from(JSON.stringify(config, null, 2))];
    m.files.forEach((entry, i) => { entry.trial = hash(writes[i]); });
    m.phase = 'applying';
    this.save(m); // Record recovery data BEFORE modifying either file.
    this.paused(() => {
      m.files.forEach((entry, i) => atomicWrite(this.p(entry.file), writes[i], entry));
      for (const name of CACHE_NAMES) {
        const file = this.p(CACHE + '/' + name);
        const backup = file + '.native-original';
        assert.ok(!fs.existsSync(backup), 'cache backup collision');
        const st = fs.lstatSync(file);
        m.caches.push({ file, backup, uid: st.uid, gid: st.gid, mode: st.mode });
        this.save(m);
        fs.renameSync(file, backup);
        fs.mkdirSync(file, { mode: st.mode & 0o7777 });
        fs.chownSync(file, st.uid, st.gid);
        fs.chmodSync(file, st.mode & 0o7777);
      }
    });
    m.phase = 'active';
    this.save(m);
  }
  restore() {
    const m = this.load();
    if (m.phase === 'restored') return;
    // Do not overwrite work from another session, or restore corrupt backups.
    for (const entry of m.files) {
      assert.equal(hash(fs.readFileSync(entry.backup)), entry.original, 'backup corrupt');
      const current = hash(fs.readFileSync(this.p(entry.file)));
      assert.ok(current === entry.original || current === entry.trial, 'concurrent edit: ' + entry.file);
    }
    this.paused(() => {
      for (const entry of m.files) atomicWrite(this.p(entry.file), fs.readFileSync(entry.backup), entry);
      for (const entry of m.caches) {
        if (!fs.existsSync(entry.backup)) continue;
        if (fs.existsSync(entry.file)) {
          // Preserve trial caches for diagnosis; never touch origin storage.
          fs.renameSync(entry.file, entry.file + '.native-trial-' + Date.now());
        }
        fs.renameSync(entry.backup, entry.file);
      }
    });
    m.phase = 'restored';
    this.save(m);
  }
}

function bridgeHealth(port = 8770) {
  return new Promise((resolve, reject) => {
    const request = http.get({ host: '127.0.0.1', port, path: '/api/debug' }, response => {
      let body = '';
      response.on('data', chunk => {
        body += chunk;
        if (body.length > 65536) request.destroy(new Error('oversized bridge response'));
      });
      response.on('error', reject);
      response.on('end', () => {
        try {
          assert.equal(response.statusCode, 200, 'bridge debug endpoint unavailable');
          assert.equal(JSON.parse(body).mqtt?.connected, true, 'bridge MQTT disconnected');
          resolve(true);
        } catch (error) { reject(error); }
      });
    });
    request.setTimeout(3000, () => request.destroy(new Error('bridge health timeout')));
    request.on('error', reject);
  });
}

async function main() {
  assert.equal(process.getuid(), 0, 'run through the root SSH lane');
  const [command, candidate, ...flags] = process.argv.slice(2);
  assertCommandEnabled(command);
  const trial = new Trial();
  if (command === 'preflight') {
    const result = trial.preflight(candidate);
    await bridgeHealth();
    console.log(JSON.stringify({ ...result, bridgeMQTT: 'connected' }, null, 2));
    return;
  }
  if (command === 'status') { console.log(JSON.stringify(trial.load(), null, 2)); return; }
  if (command === 'recover') {
    const m = trial.load();
    if (m.workerPid) {
      let cmd = '';
      try { cmd = fs.readFileSync('/proc/' + m.workerPid + '/cmdline', 'utf8'); } catch { /* exited */ }
      assert.ok(!cmd.includes(__filename), 'worker still active; wait for automatic rollback');
    }
    trial.restore();
    console.log('Original launcher, watcher config and JS caches restored.');
    return;
  }
  if (command === 'start') {
    assert.ok(flags.includes('--ota-frozen') && flags.includes('--adult-mode'),
      'confirm OTA is frozen and TV is not in kids mode');
    await bridgeHealth();
    trial.prepare(candidate);
    const log = fs.openSync(path.join(trial.state, 'worker.log'), 'a', 0o600);
    const child = cp.spawn(process.execPath, [__filename, 'worker'], {
      detached: true, stdio: ['ignore', log, log], env: process.env
    });
    child.on('error', error => console.error('Watchdog failed to launch; no UI writes made:', error.message));
    child.unref();
    fs.closeSync(log);
    console.log('Trial requested. Check status for active. Automatic rollback after 180s; DO NOT REBOOT.');
    return;
  }
  if (command === 'worker') {
    const m = trial.load();
    assert.equal(m.phase, 'prepared');
    fs.writeFileSync(path.join(trial.state, 'worker.lock'), String(process.pid), { flag: 'wx', mode: 0o600 });
    m.workerPid = process.pid;
    trial.save(m);
    let stop = false;
    process.on('SIGTERM', () => { stop = true; });
    process.on('SIGINT', () => { stop = true; });
    try {
      trial.apply();
      console.log('ACTIVE', new Date().toISOString());
      const start = process.hrtime.bigint();
      while (!stop && process.hrtime.bigint() - start < 180000000000n) {
        await new Promise(resolve => setTimeout(resolve, 500));
      }
    } finally {
      trial.restore();
      console.log('RESTORED', new Date().toISOString());
    }
    return;
  }
  throw new Error('Use preflight [candidate], start candidate --ota-frozen --adult-mode, status, or recover');
}
// Phoenix ignores process.exitCode on normal shutdown; explicit exit is required.
if (require.main === module) main().catch(error => { console.error(error.stack); process.exit(1); });
module.exports = { Trial, hash, atomicWrite, bridgeHealth, assertCommandEnabled, APP, CONFIG, STATE, CACHE, HASHES };
