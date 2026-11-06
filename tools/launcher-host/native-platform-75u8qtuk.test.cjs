#!/usr/bin/env node
/* Offline contract test for the 75U8QTUK native adapter. No TV access.
 * Run: node tools/launcher-host/native-platform-75u8qtuk.test.cjs
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const source = fs.readFileSync(path.join(__dirname, 'native-platform-75u8qtuk.js'), 'utf8');
const sandbox = { setTimeout, clearTimeout, module: { exports: {} } };
sandbox.self = sandbox;
vm.runInNewContext(source, sandbox, { filename: 'native-platform-75u8qtuk.js' });
const create = sandbox.module.exports;

function mockSdk(overrides) {
  const calls = { getData: [], invoke: [], open: [], start: [], on: [], off: [] };
  const listeners = {};
  const apps = (overrides && overrides.apps) || [
    { appId: 1, appName: 'Netflix', url: 'netflix://', storeType: 95, img: '', typeCode: '600002' },
    { appId: 206, appName: 'Home', url: '', storeType: 0, img: '' }
  ];
  const sources = (overrides && overrides.sources) || [
    { sourceId: 'HDMI1', name: 'HDMI 1', rename: '', deviceName: '', icon: '', hasSignal: true }
  ];
  const modules = {
    'app-service': {
      getData(key, arg) {
        calls.getData.push(['app-service', key, arg]);
        if (key === 'getAppList') {
          // The argument is created inside the VM realm; compare fields, not
          // prototypes (deepStrictEqual rejects cross-realm objects).
          assert.ok(arg && arg.sceneCode === 'launcher');
          return { result: apps };
        }
        if (key === 'getAppInfo') {
          assert.equal(arg.checkRange, 1);
          assert.equal(arg.url, '');
          return { result: apps.find(a => String(a.appId) === String(arg.appId)) || null };
        }
        throw new Error('unexpected app-service getData: ' + key);
      },
      invoke(...args) { calls.invoke.push(['app-service', ...args]); }
    },
    'all-inputs': {
      getData(key, arg) {
        calls.getData.push(['all-inputs', key, arg]);
        if (key === 'getAllInputsData') return { result: sources };
        throw new Error('unexpected all-inputs getData: ' + key);
      },
      invoke(...args) { calls.invoke.push(['all-inputs', ...args]); }
    },
    setting: {
      open(...args) { calls.open.push(['setting', ...args]); return 'settings-opened'; }
    }
  };
  const sdk = {
    me: { req(name) {
      assert.ok(modules[name], 'unknown module ' + name);
      return modules[name];
    } },
    message: {
      on(event, fn) { calls.on.push(event); listeners[event] = fn; },
      off(event, fn) { calls.off.push(event); assert.equal(listeners[event], fn); }
    },
    apc: {
      CMDMETHOD: { LAUNCHER_RECOMMEND: '52', KEY_INPUT_START: '207' },
      start(params) { calls.start.push(Object.assign({}, params)); return 'started'; }
    }
  };
  return { sdk, calls, listeners, apps, sources };
}

// 1. start() reads both lists with the model-correct keys and reports them.
{
  const m = mockSdk();
  const updates = [];
  const p = create(m.sdk, data => updates.push(data));
  p.start();
  assert.deepEqual(m.calls.getData.map(c => [c[0], c[1]]), [
    ['app-service', 'getAppList'], ['all-inputs', 'getAllInputsData']
  ]);
  assert.equal(updates.length, 1);
  assert.equal(updates[0].apps.length, 2);
  assert.equal(updates[0].sources.length, 1);
  assert.equal(updates[0].waiting, false);
  assert.deepEqual(m.calls.on, [
    'o2n://sdk/init-finished',
    'o2n://app-service/all-apps-changed',
    'o2n://all-inputs/inputs-data-changed',
    'o2n://sdk/str-resuming'
  ]);
  p.stop();
  assert.equal(m.calls.off.length, 4);
}

// 2. launchApp uses getAppInfo(checkRange:1) then apc.start with stock shape.
{
  const m = mockSdk();
  const p = create(m.sdk, () => {});
  p.start();
  assert.equal(p.launchApp(1), 'started');
  assert.deepEqual(m.calls.start[0], {
    name: 'Netflix', appId: 1, url: 'netflix://', storeType: 95,
    startMethod: '52', typeCode: '600002', rateInfo: ''
  });
  assert.throws(() => p.launchApp(999), /not in the current native app list/);
  p.stop();
}

// 3. openSettings uses open("settings") with no vk; changeSource validates.
{
  const m = mockSdk();
  const p = create(m.sdk, () => {});
  p.start();
  assert.equal(p.openSettings(), 'settings-opened');
  assert.deepEqual(m.calls.open[0], ['setting', 'settings']);
  p.changeSource('HDMI1');
  assert.deepEqual(m.calls.invoke[0], ['all-inputs', 'changeSourceTo', 'HDMI1', 'launcher']);
  assert.throws(() => p.changeSource('HDMI9'), /not in the current native source list/);
  p.stop();
}

// 4. A missing CMDMETHOD falls back to the source-verified constant "52".
{
  const m = mockSdk();
  m.sdk.apc.CMDMETHOD = undefined;
  const p = create(m.sdk, () => {});
  p.start();
  p.launchApp(1);
  assert.equal(m.calls.start[0].startMethod, '52');
  p.stop();
}

// 5. One broken service does not hide the other; errors are surfaced.
{
  const m = mockSdk();
  m.sdk.me.req = name => {
    if (name === 'app-service') return { getData() { throw new Error('service down'); } };
    return {
      getData() { return { result: m.sources }; },
      invoke() {}
    };
  };
  const updates = [];
  const p = create(m.sdk, data => updates.push(data));
  p.start();
  assert.equal(updates[0].errors.length, 1);
  assert.match(updates[0].errors[0], /Apps: service down/);
  assert.equal(updates[0].sources.length, 1);
  assert.equal(updates[0].waiting, true);
  p.stop();
}

console.log('native-platform-75u8qtuk.test.cjs: 5 groups OK');
