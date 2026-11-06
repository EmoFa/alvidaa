const test = require('node:test');
const assert = require('node:assert/strict');
const { restartEngine } = require('./stock-ui-restart.cjs');
function harness(options = {}) {
  const old = { pid: 1, identity: '1:100', credentials: 'uid311 groups caps' };
  const next = { pid: 2, identity: '2:200', credentials: options.credentials || old.credentials };
  let current = options.empty ? [] : [old], launches = 0;
  return {
    ops: {
      list: () => current,
      stop: () => { if (!options.ignoreStop) current = options.auto ? [next] : []; },
      wait: async ms => { if (options.crash && ms === 3000) current = []; },
      launch: async () => { launches++; if (!options.failLaunch) current = options.duplicate ? [next, { ...next, pid: 3 }] : [next]; }
    },
    launches: () => launches
  };
}
test('explicit relaunch checks credentials and stability', async () => {
  const h = harness();
  assert.equal((await restartEngine(h.ops)).pid, 2);
  assert.equal(h.launches(), 1);
});
test('does not duplicate an engine restarted by the platform', async () => {
  const h = harness({ auto: true });
  await restartEngine(h.ops);
  assert.equal(h.launches(), 0);
});
test('does not force-kill or duplicate a process ignoring SIGTERM', async () => {
  const h = harness({ ignoreStop: true });
  await assert.rejects(restartEngine(h.ops), /no forced kill/);
  assert.equal(h.launches(), 0);
});
test('file changes require an absent engine and run before launch', async () => {
  const h = harness();
  let changed = false;
  h.ops.change = () => { assert.equal(h.ops.list().length, 0); assert.equal(h.launches(), 0); changed = true; };
  await restartEngine(h.ops);
  assert.equal(changed, true);
  const auto = harness({ auto: true });
  auto.ops.change = () => assert.fail('must not mutate a running UI');
  await assert.rejects(restartEngine(auto.ops), /refusing live mutation/);
});
test('saved context can recover when the UI is already gone', async () => {
  const h = harness({ empty: true });
  h.ops.original = { pid: 1, identity: '1:100', credentials: 'uid311 groups caps' };
  h.ops.change = () => assert.equal(h.ops.list().length, 0);
  assert.equal((await restartEngine(h.ops)).pid, 2);
});
test('rejects missing initial engine, failed launch, wrong identity and crash', async () => {
  for (const [options, message] of [
    [{ empty: true }, /exactly one/], [{ failLaunch: true }, /did not start/],
    [{ credentials: 'root' }, /credentials mismatch/], [{ duplicate: true }, /multiple UI engines/],
    [{ crash: true }, /remain alive/]
  ]) await assert.rejects(restartEngine(harness(options).ops), message);
});
