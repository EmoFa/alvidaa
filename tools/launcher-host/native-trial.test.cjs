const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const assert = require('node:assert/strict');
const { Trial, hash, bridgeHealth, assertCommandEnabled, APP, CONFIG, STATE, CACHE } = require('./native-trial.cjs');
const http = require('node:http');

test('failed hardware restart strategy cannot be invoked on a real TV', () => {
  for (const cmd of ['start', 'worker']) assert.throws(() => assertCommandEnabled(cmd), /Trial disabled/);
  for (const cmd of ['preflight', 'status', 'recover']) assert.doesNotThrow(() => assertCommandEnabled(cmd));
  let signalled = false, operated = false;
  const trial = new Trial({ engines: () => [123], signal: () => { signalled = true; } });
  assert.throws(() => trial.apply(), /Trial disabled/);
  assert.throws(() => trial.paused(() => { operated = true; }), /Trial disabled/);
  assert.equal(signalled, false);
  assert.equal(operated, false);
});

test('bridge readiness rejects disconnected MQTT and malformed responses', async t => {
  let body = JSON.stringify({ mqtt: { connected: true } });
  const server = http.createServer((_req, res) => res.end(body));
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const port = server.address().port;
  assert.equal(await bridgeHealth(port), true);
  body = JSON.stringify({ mqtt: { connected: false } });
  await assert.rejects(bridgeHealth(port), /MQTT disconnected/);
  body = '{';
  await assert.rejects(bridgeHealth(port), SyntaxError);
});

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'native-trial-test-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const write = (file, data) => {
    fs.mkdirSync(path.dirname(root + file), { recursive: true });
    fs.writeFileSync(root + file, data, { mode: 0o640 });
  };
  write(APP, 'original launcher');
  write(CONFIG, JSON.stringify({ watcher: { enabled: true, app: 'Home' }, untouched: 123 }));
  for (const name of ['compiled_js', 'uncompiled_js']) write(CACHE + '/' + name + '/old', 'original cache');
  write('/var/local/hisenseUI/cobalt_home/.starboard.storage', 'precious user data');
  write('/candidate.js', fs.readFileSync(__dirname + '/native-launcher.js'));
  const signals = [];
  const trial = new Trial({ root, hashes: { [APP]: hash('original launcher') }, engines: () => [123],
    signal: (pid, signal) => signals.push([pid, signal]) });
  return { root, trial, candidate: root + '/candidate.js', signals, write };
}

test('preflight makes no writes and rejects drift, malformed JSON and candidate syntax', t => {
  const f = fixture(t);
  assert.equal(f.trial.preflight(f.candidate).watcherEnabled, true);
  assert.equal(fs.existsSync(f.root + STATE), false);
  f.write(APP, 'changed');
  assert.throws(() => f.trial.preflight(f.candidate), /baseline changed/);
  f.write(APP, 'original launcher');
  f.write(CONFIG, '{');
  assert.throws(() => f.trial.preflight(f.candidate), /valid JSON/);
  f.write(CONFIG, '{}');
  f.write('/candidate.js', 'root._V_M_.launcher = function (');
  assert.throws(() => f.trial.preflight(f.candidate), SyntaxError);
});

test('trial applies and automatically-restorable state preserves originals, metadata, storage', t => {
  const f = fixture(t);
  const originalConfig = fs.readFileSync(f.root + CONFIG);
  f.trial.prepare(f.candidate);
  assert.throws(() => f.trial.prepare(f.candidate), /existing trial/);
  f.trial.apply();
  assert.equal(f.trial.load().phase, 'active');
  assert.equal(JSON.parse(fs.readFileSync(f.root + CONFIG)).watcher.enabled, false);
  assert.equal(JSON.parse(fs.readFileSync(f.root + CONFIG)).untouched, 123);
  assert.equal(fs.statSync(f.root + APP).mode & 0o777, 0o640);
  assert.deepEqual(f.signals, [[123, 'SIGSTOP'], [123, 'SIGKILL']]);
  f.write(CACHE + '/compiled_js/new', 'trial cache');
  f.trial.restore();
  assert.equal(f.trial.load().phase, 'restored');
  assert.equal(fs.readFileSync(f.root + APP, 'utf8'), 'original launcher');
  assert.deepEqual(fs.readFileSync(f.root + CONFIG), originalConfig);
  assert.equal(fs.readFileSync(f.root + CACHE + '/compiled_js/old', 'utf8'), 'original cache');
  assert.equal(fs.readFileSync(f.root + '/var/local/hisenseUI/cobalt_home/.starboard.storage', 'utf8'), 'precious user data');
  f.trial.restore(); // Idempotent, backups are retained.
  assert.equal(f.signals.length, 4);
});

test('rollback refuses concurrent edits or corrupted backup rather than overwriting them', t => {
  const f = fixture(t);
  f.trial.prepare(f.candidate); f.trial.apply();
  f.write(APP, 'another operator changed this');
  assert.throws(() => f.trial.restore(), /concurrent edit/);
  fs.copyFileSync(f.candidate, f.root + APP);
  fs.writeFileSync(f.trial.load().files[0].backup, 'corrupt');
  assert.throws(() => f.trial.restore(), /backup corrupt/);
});

test('cache path collisions and symlinks fail preflight', t => {
  const f = fixture(t);
  fs.mkdirSync(f.root + CACHE + '/compiled_js.native-original');
  assert.throws(() => f.trial.preflight(f.candidate), /collision/);
  fs.rmdirSync(f.root + CACHE + '/compiled_js.native-original');
  fs.renameSync(f.root + APP, f.root + APP + '.real');
  fs.symlinkSync(f.root + APP + '.real', f.root + APP);
  assert.throws(() => f.trial.preflight(f.candidate), /regular file/);
});

test('partial apply is recoverable from saved manifest; paused engine is always released', t => {
  const f = fixture(t);
  f.trial.prepare(f.candidate);
  const save = f.trial.save.bind(f.trial);
  let once = true;
  f.trial.save = manifest => {
    save(manifest);
    if (manifest.caches.length === 1 && once) { once = false; throw new Error('simulated failure'); }
  };
  assert.throws(() => f.trial.apply(), /simulated failure/);
  assert.deepEqual(f.signals.slice(-1), [[123, 'SIGKILL']]);
  f.trial.restore();
  assert.equal(fs.readFileSync(f.root + APP, 'utf8'), 'original launcher');
  assert.equal(f.trial.load().phase, 'restored');
});

test('restart failure still releases every paused process', t => {
  const f = fixture(t);
  f.trial.engines = () => [123, 456];
  f.trial.signal = (pid, signal) => {
    f.signals.push([pid, signal]);
    if (pid === 123 && signal === 'SIGKILL') throw new Error('simulated signal error');
  };
  assert.throws(() => f.trial.paused(() => {}), /restart failed/);
  assert.deepEqual(f.signals, [
    [123, 'SIGSTOP'], [456, 'SIGSTOP'], [123, 'SIGKILL'], [123, 'SIGCONT'], [456, 'SIGKILL']
  ]);
});

test('prepared but never launched trial can be recovered without cache mutations', t => {
  const f = fixture(t);
  f.trial.prepare(f.candidate);
  f.trial.restore();
  assert.equal(f.trial.load().phase, 'restored');
  assert.equal(fs.readFileSync(f.root + CACHE + '/compiled_js/old', 'utf8'), 'original cache');
});
