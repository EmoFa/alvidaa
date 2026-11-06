'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require.resolve('./native-platform.js'), 'utf8');
const APP_CHANGE = 'o2n://app-service/all-apps-changed';
const INPUT_CHANGE = 'o2n://all-inputs/inputs-data-changed';

function fixture() {
  const listeners = new Map(), timers = new Map(), updates = [], calls = [];
  let serial = 0;
  const state = {
    apps: [{ appId: '12', appName: 'Example', url: 'app://example', storeType: 2 }],
    sources: [{ sourceId: 0, name: 'TV' }, { sourceId: 'HDMI1', name: 'HDMI 1' }]
  };
  function emit(name) { for (const fn of listeners.get(name) || []) fn(); }
  const sdk = {
    apc: { CMDMETHOD: { REMOTECONTROL: 'remote' }, start(arg) { calls.push(['apc', 'start', arg]); return 'started'; } },
    message: {
      on(name, fn) {
        if (!listeners.has(name)) listeners.set(name, new Set());
        listeners.get(name).add(fn);
      },
      off(name, fn) { listeners.get(name)?.delete(fn); }
    },
    me: { req(module) {
      return {
        getData(key, arg) {
          calls.push([module, 'getData', key, arg]);
          if (state.notifyDuringRead) emit(APP_CHANGE);
          if (module === 'app-service') {
            if (key === 'getAppInfoByAppId') return { result: state.restricted ? null : state.apps.find(a => String(a.appId) === arg.appId) };
            if (state.failApps) throw new Error('not initialized');
            return { result: state.apps };
          }
          if (module === 'all-inputs') return { result: state.sources };
          throw new Error('Unexpected module: ' + module);
        },
        open(...args) { calls.push([module, 'open', ...args]); return 'opened'; },
        invoke(...args) { calls.push([module, 'invoke', ...args]); return 'invoked'; }
      };
    } }
  };
  const context = { self: {},
    setTimeout(fn, delay) { const id = ++serial; timers.set(id, { fn, delay }); return id; },
    clearTimeout(id) { timers.delete(id); }
  };
  // No browser transports exist in this sandbox.
  vm.runInNewContext(source, context, { filename: 'native-platform.js' });
  const adapter = context.self.AlvidaaNativePlatform(sdk, x => updates.push(x));
  function next() {
    const item = timers.entries().next().value;
    assert.ok(item, 'expected a pending timer');
    timers.delete(item[0]); item[1].fn();
  }
  return { adapter, state, listeners, timers, updates, calls, emit, next,
    latest: () => updates.at(-1) };
}

test('reads native lists immediately and retains app metadata without transport', () => {
  const f = fixture(); f.adapter.start();
  assert.equal(f.latest().apps[0].storeType, 2);
  assert.equal(f.latest().apps[0].url, 'app://example');
  assert.equal(f.latest().sources[0].sourceId, 0);
  assert.equal(f.latest().waiting, false);
  assert.equal(f.timers.size, 0);
  assert.deepEqual(f.calls[0], ['app-service', 'getData', 'getCurrentShowApps', 'Launcher']);
  assert.deepEqual(f.calls[1], ['all-inputs', 'getData', 'getAllInputsData', undefined]);
  f.latest().apps.pop();
  assert.equal(f.state.apps.length, 1, 'array mutation must not change vendor data');
  f.adapter.stop();
});

test('empty boot data becomes ready through bounded retry', () => {
  const f = fixture(); const apps = f.state.apps; f.state.apps = [];
  f.adapter.start();
  assert.equal(f.latest().waiting, true);
  assert.equal(f.latest().retrying, true);
  assert.equal(f.timers.values().next().value.delay, 250);
  f.state.apps = apps; f.next();
  assert.equal(f.latest().apps.length, 1);
  assert.equal(f.latest().waiting, false);
  assert.equal(f.timers.size, 0);
});

test('retries stop, but a late init notification still recovers', () => {
  const f = fixture(); const apps = f.state.apps; f.state.apps = [];
  f.adapter.start();
  for (let i = 0; i < 6; i++) f.next();
  assert.equal(f.updates.length, 7);
  assert.equal(f.timers.size, 0);
  assert.equal(f.latest().retrying, false);
  assert.equal(f.latest().waiting, true);
  f.state.apps = apps; f.emit('o2n://sdk/init-finished'); f.next();
  assert.equal(f.latest().waiting, false);
});

test('partial failure preserves last good apps while refreshing inputs', () => {
  const f = fixture(); f.adapter.start();
  f.state.failApps = true;
  f.state.sources = [{ sourceId: 'HDMI2', name: 'Console' }];
  f.emit(INPUT_CHANGE); f.next();
  assert.equal(f.latest().apps[0].appName, 'Example');
  assert.equal(f.latest().sources[0].sourceId, 'HDMI2');
  assert.match(f.latest().errors[0], /not initialized/);
  f.state.failApps = false; f.next();
  assert.equal(f.latest().errors.length, 0);
});

test('malformed results are errors; successful empty lists replace old data', () => {
  const f = fixture(); f.adapter.start();
  f.state.sources = 'bad response'; f.adapter.refresh(); f.next();
  assert.equal(f.latest().sources.length, 2);
  assert.match(f.latest().errors[0], /did not return a list/);
  f.state.sources = []; f.emit(INPUT_CHANGE); f.next();
  assert.equal(f.latest().sources.length, 0);
  assert.equal(f.latest().errors.length, 0);
});

test('stop cleans listeners/timers; reactivation reads again without duplicates', () => {
  const f = fixture(); f.state.apps = []; f.adapter.start(); f.adapter.start();
  assert.equal(f.updates.length, 1);
  assert.equal([...f.listeners.values()].reduce((n, s) => n + s.size, 0), 4);
  const queued = f.timers.values().next().value.fn;
  f.adapter.stop(); f.adapter.stop(); queued(); f.emit(APP_CHANGE);
  assert.equal(f.timers.size, 0);
  assert.equal(f.updates.length, 1);
  assert.equal([...f.listeners.values()].reduce((n, s) => n + s.size, 0), 0);
  f.state.apps = [{ appId: '2', appName: 'New app' }]; f.adapter.start();
  assert.equal(f.latest().apps[0].appName, 'New app');
  assert.equal([...f.listeners.values()].reduce((n, s) => n + s.size, 0), 4);
});

test('change and resume notifications coalesce', () => {
  const f = fixture(); f.adapter.start();
  f.emit(APP_CHANGE); f.emit(INPUT_CHANGE); f.emit('o2n://sdk/str-resuming');
  assert.equal(f.timers.size, 1); f.next();
  assert.equal(f.updates.length, 2);
  assert.equal(f.timers.size, 0);
});

test('lazy-service notifications during reads cannot create an infinite retry loop', () => {
  const f = fixture(); f.state.notifyDuringRead = true; f.state.apps = [];
  f.adapter.start();
  for (let i = 0; i < 6; i++) f.next();
  assert.equal(f.timers.size, 0);
  assert.equal(f.updates.length, 7);
});

test('uses vendor input IDs unchanged and opens complete native Settings', () => {
  const f = fixture(); f.adapter.start();
  assert.equal(f.adapter.changeSource(0), 'invoked');
  assert.deepEqual(f.calls.at(-1), ['all-inputs', 'invoke', 'changeSourceTo', 0, 'launcher']);
  f.adapter.changeSource('HDMI1');
  assert.deepEqual(f.calls.at(-1), ['all-inputs', 'invoke', 'changeSourceTo', 'HDMI1', 'launcher']);
  assert.throws(() => f.adapter.changeSource('0'), /current native source list/);
  assert.throws(() => f.adapter.changeSource(undefined), /current native source list/);
  f.state.sources = [{ name: 'Missing ID' }, { sourceId: NaN }, { sourceId: '' }];
  f.adapter.refresh(); f.next();
  for (const id of [undefined, NaN, '']) {
    assert.throws(() => f.adapter.changeSource(id), /current native source list/);
  }
  assert.equal(f.adapter.openSettings(), 'opened');
  assert.equal(f.calls.at(-1)[0], 'setting');
  assert.equal(f.calls.at(-1)[2], 'settings');
  assert.equal(f.calls.at(-1)[3].vk, 'T');
});

test('app launches re-resolve metadata and use APC without lock bypass flags', () => {
  const f = fixture(); f.state.apps[0].isNotNeedLock = true; f.adapter.start();
  assert.equal(f.adapter.launchApp('12'), 'started');
  const call = f.calls.at(-1);
  assert.equal(call[0], 'apc'); assert.equal(call[2].appId, '12');
  assert.equal(call[2].storeType, 2); assert.equal(call[2].startMethod, 'remote');
  assert.equal(call[2].isNotNeedLock, undefined);
  assert.throws(() => f.adapter.launchApp('missing'), /current native app list/);
  f.state.restricted = true;
  assert.throws(() => f.adapter.launchApp('12'), /unavailable or restricted/);
});
