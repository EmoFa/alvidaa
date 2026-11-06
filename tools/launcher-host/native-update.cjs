'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { APP, CONFIG, hash, atomicWrite } = require('./native-trial.cjs');
const privateWrite = (file, data) => fs.writeFileSync(file, data, { flag: 'wx', mode: 0o600 });
function expectedHash(m, entry) {
  const phase = m.update ? m.update.baselinePhase : m.phase;
  return phase === 'restored' ? (entry.file === CONFIG ? m.stockConfigHash || entry.original : entry.original) : entry.trial;
}
function verify(home, m) {
  for (const entry of m.files) {
    assert.equal(hash(fs.readFileSync(entry.backup)), entry.original, 'stock backup corrupt');
    const st = fs.lstatSync(home.p(entry.file));
    assert.ok(st.isFile() && !st.isSymbolicLink(), 'unexpected target type');
    assert.equal(hash(fs.readFileSync(home.p(entry.file))), expectedHash(m, entry), 'concurrent edit: ' + entry.file);
  }
}
function stageUpdate(home, candidate) {
  const m = home.load();
  assert.ok(['installed', 'restored'].includes(m.phase), 'update requires a stable installed/restored Home');
  verify(home, m);
  const st = fs.lstatSync(candidate);
  assert.ok(st.isFile() && !st.isSymbolicLink(), 'candidate must be a regular file');
  const data = fs.readFileSync(candidate);
  assert.ok(data.includes('ALVIDAA_FREE_MY_TV_NATIVE_V1'), 'not a Free My TV native bundle');
  new vm.Script(data.toString(), { filename: candidate });
  const directory = fs.mkdtempSync(path.join(home.state, 'update-'));
  fs.chmodSync(directory, 0o700);
  const before = JSON.stringify(m);
  privateWrite(path.join(directory, 'state-before.json'), before);
  privateWrite(path.join(directory, 'previous.js'), fs.readFileSync(home.p(APP)));
  privateWrite(path.join(directory, 'candidate.js'), data);
  m.update = { directory, baselinePhase: m.phase, beforeHash: hash(before), previousHash: hash(fs.readFileSync(home.p(APP))),
    candidateHash: hash(data), caches: [] };
  m.phase = 'update-prepared';
  home.save(m);
  return m.update;
}
function applyUpdate(home) {
  const m = home.load();
  assert.equal(m.phase, 'update-prepared');
  verify(home, m);
  const u = m.update, entry = m.files.find(e => e.file === APP);
  const data = fs.readFileSync(path.join(u.directory, 'candidate.js'));
  assert.equal(hash(data), u.candidateHash, 'candidate changed after staging');
  home.paused(() => {
    entry.trial = u.candidateHash;
    m.phase = 'updating'; home.save(m); // journal before touching app/cache bytes
    atomicWrite(home.p(APP), data, entry);
    for (const old of m.caches) {
      if (!fs.existsSync(old.file)) continue;
      const st = fs.lstatSync(old.file);
      assert.ok(st.isDirectory() && !st.isSymbolicLink(), 'unexpected cache path');
      // After a stock restore, re-establish the original-cache backup rather
      // than leaving the next stock restore with only the new native caches.
      const backup = u.baselinePhase === 'restored' ? old.backup : path.join(u.directory, 'cache-' + u.caches.length);
      assert.ok(!fs.existsSync(backup), 'cache backup collision');
      u.caches.push({ file: old.file, backup, uid: st.uid, gid: st.gid, mode: st.mode });
      home.save(m);
      fs.renameSync(old.file, backup);
      fs.mkdirSync(old.file, { mode: st.mode & 0o7777 });
      fs.chownSync(old.file, st.uid, st.gid); fs.chmodSync(old.file, st.mode & 0o7777);
    }
  });
}
function rollbackUpdate(home) {
  const m = home.load(), u = m.update;
  assert.ok(u, 'no pending update to roll back');
  const before = fs.readFileSync(path.join(u.directory, 'state-before.json'));
  const data = fs.readFileSync(path.join(u.directory, 'previous.js'));
  assert.equal(hash(before), u.beforeHash, 'previous manifest corrupt');
  assert.equal(hash(data), u.previousHash, 'previous candidate corrupt');
  let previous;
  try { previous = JSON.parse(before); }
  catch (error) { throw new Error('Previous manifest is invalid: ' + error.message); }
  const current = hash(fs.readFileSync(home.p(APP)));
  assert.ok(current === u.previousHash || current === u.candidateHash, 'concurrent launcher edit');
  // Other files must still match; a rollback must not overwrite another agent.
  for (const e of previous.files.filter(e => e.file !== APP)) {
    assert.equal(hash(fs.readFileSync(home.p(e.file))), expectedHash(previous, e), 'concurrent edit: ' + e.file);
  }
  home.paused(() => {
    atomicWrite(home.p(APP), data, previous.files.find(e => e.file === APP));
    for (const cache of u.caches) {
      if (!fs.existsSync(cache.backup)) continue;
      if (fs.existsSync(cache.file)) fs.renameSync(cache.file, cache.backup + '.failed-' + Date.now());
      fs.renameSync(cache.backup, cache.file);
    }
    home.save(previous);
  });
}
function finishUpdate(home, engine) {
  const m = home.load();
  if (m.update) {
    privateWrite(path.join(m.update.directory, 'journal.json'), JSON.stringify(m.update));
    m.lastUpdate = m.update.directory;
    delete m.update;
    m.phase = 'installed'; m.enginePid = engine.pid;
    delete m.error;
    home.save(m);
  }
}
module.exports = { stageUpdate, applyUpdate, rollbackUpdate, finishUpdate };
