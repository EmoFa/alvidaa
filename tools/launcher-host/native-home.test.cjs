const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const assert = require('node:assert/strict');
const { NativeHome, perform, acquire } = require('./native-home.cjs');
const { APP, CONFIG, CACHE, hash } = require('./native-trial.cjs');
function setup(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'native-home-test-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const write = (name, content) => {
    fs.mkdirSync(path.dirname(root + name), { recursive: true });
    fs.writeFileSync(root + name, content, { mode: 0o640 });
  };
  write(APP, 'stock launcher'); write(CONFIG, '{"watcher":{"enabled":true},"untouched":123}');
  const shell = '/APPS/channelA/hisenseUI/index.html'; write(shell, 'stock shell');
  for (const name of ['compiled_js', 'uncompiled_js']) write(CACHE + '/' + name + '/stock', 'cache');
  const candidate = root + '/candidate.js';
  fs.writeFileSync(candidate, fs.readFileSync(__dirname + '/native-launcher.js'));
  let running = true;
  const home = new NativeHome({ root, hashes: { [APP]: hash('stock launcher'), [shell]: hash('stock shell') },
    engines: () => running ? [123] : [] });
  home.prepare(candidate);
  return { root, home, write,
    ops: (_context, change) => ({ change }),
    restart: async op => { running = false; await op.change(); running = true; return { pid: 456 }; }
  };
}
test('persistent install and stock restore keep watcher off and retain original backup', async t => {
  const f = setup(t);
  const original = fs.readFileSync(f.root + CONFIG);
  const installed = await perform(f.home, {}, 'install', f.restart, f.ops);
  assert.equal(installed.phase, 'installed');
  assert.match(fs.readFileSync(f.root + APP, 'utf8'), /NATIVE TEST N02/);
  assert.equal(JSON.parse(fs.readFileSync(f.root + CONFIG)).watcher.enabled, false);
  const restored = await perform(f.home, {}, 'restore', f.restart, f.ops);
  assert.equal(restored.phase, 'restored');
  assert.equal(fs.readFileSync(f.root + APP, 'utf8'), 'stock launcher');
  const expected = JSON.parse(original); expected.watcher.enabled = false;
  assert.deepEqual(JSON.parse(fs.readFileSync(f.root + CONFIG)), expected);
  assert.deepEqual(fs.readFileSync(f.home.load().files[1].backup), original);
  assert.equal(fs.statSync(f.root + APP).mode & 0o777, 0o640);
  await perform(f.home, {}, 'restore', f.restart, f.ops);
  f.write(CONFIG, '{"another":"session"}');
  await assert.rejects(perform(f.home, {}, 'restore', f.restart, f.ops), /concurrent edit/);
});
test('failed custom startup automatically restores stock files and restarts', async t => {
  const f = setup(t);
  let calls = 0;
  const fail = async op => {
    const result = await f.restart(op);
    if (++calls === 1) throw new Error('custom engine exited');
    return result;
  };
  await assert.rejects(perform(f.home, {}, 'install', fail, f.ops), /custom engine exited/);
  assert.equal(calls, 2);
  assert.equal(f.home.load().phase, 'restored');
  assert.equal(fs.readFileSync(f.root + APP, 'utf8'), 'stock launcher');
});
test('file swaps reject a live engine and unknown shared-shell changes', async t => {
  const f = setup(t);
  assert.throws(() => f.home.applyFiles(), /UI is alive/);
  f.write('/APPS/channelA/hisenseUI/index.html', 'injected overlay');
  await assert.rejects(perform(f.home, {}, 'install', f.restart, f.ops), /shared shell changed/);
});
test('operation lock rejects a live owner and preserves stale-lock evidence', t => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'native-lock-test-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const release = acquire(dir);
  assert.throws(() => acquire(dir), /another install/);
  release();
  fs.writeFileSync(path.join(dir, 'operation.lock'), JSON.stringify({ boot: 'old-boot', pid: 1, born: '0' }));
  acquire(dir)();
  assert.ok(fs.readdirSync(dir).some(name => name.startsWith('operation.lock.stale-')));
});
