#!/usr/bin/env node
/* Load-time + behaviour smoke test for the 75U8QTUK appended bundle (no vendor
 * code). Verifies the four appended parts execute in order, the /Launcher
 * route is replaced, the vendor icon override, the merged apps+inputs list,
 * the input dispatch, and the CSS wallpaper picker.
 * Run: node tools/launcher-host/native-home-75u8qtuk.test.cjs
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { PARTS } = require('./build-native-75u8qtuk.cjs');

const KEYMAP = { BACK: 8, BACKSPACE: 8, ENTER: 13, LEFT: 37, RIGHT: 39, UP: 38,
  DOWN: 40, HOME: 36, EXIT: 27, LAUNCHER: 547, SOURCE: 505, KEYPAD_INPUT: 610 };

const storageWrites = [];
class SDK {
  constructor() {
    this.key = { KEYMAP };
    this.storage = {
      get: () => null,
      set: (key, value) => storageWrites.push({ key, value })
    };
    this.apc = { CMDMETHOD: { LAUNCHER_RECOMMEND: '52', KEY_INPUT_START: '207' }, start: () => {} };
    this.router = { isCurrentPathEqualTo: () => true };
    this.tts = { isEnable: () => false, speak: () => {} };
    this.i18n = { t: key => key };
    this.message = { on: () => {}, off: () => {} };
    this.me = { req: () => ({ getData: () => ({ result: [] }), invoke: () => {}, open: () => {} }) };
  }
}

const sandbox = {
  console,
  setTimeout,
  clearTimeout,
  setInterval: () => 1,
  clearInterval: () => {},
  innerWidth: 1920,
  addEventListener: () => {},
  removeEventListener: () => {},
  document: { body: { addEventListener: () => {}, removeEventListener: () => {} } },
  _V_M_: { launcher: () => ({
    name: 'Launcher', version: '1', meta: {}, page: {}, data: {}, key: {},
    init: () => {}, reset: () => {},
    route: [{ path: '/Launcher', component: () => null }, { path: '/Launcher/myApps', component: () => null }]
  }) },
  _V_SDK_: { vre: { SDK } }
};
sandbox.self = sandbox;
sandbox.window = sandbox;
vm.createContext(sandbox);

PARTS.forEach(file => {
  const source = fs.readFileSync(path.join(__dirname, file), 'utf8');
  vm.runInContext(source, sandbox, { filename: file });
});

assert.equal(typeof sandbox.AlvidaaNativePlatform, 'function', 'adapter did not attach');
assert.equal(typeof sandbox.AlvidaaFreeMyTV, 'function', 'frontend did not attach');

const stock = sandbox._V_M_.launcher();
assert.equal(stock.route.length, 2, 'other vendor routes must survive');
const component = stock.route[0].component;
assert.ok(component && typeof component === 'object', 'route component must be a component object');
assert.equal(typeof component.render, 'function', 'component needs a Vue render function');
assert.equal(component.name, 'Launcher');
assert.equal(sandbox._V_M_.launcher(), stock, 'wrapper must be idempotent');

// Minimal Vue-2-like createElement: keeps plain string children.
function h(tag, data, children) {
  return { tag, data: data || {}, children: children || [] };
}

function makeVm() {
  const calls = { changeSource: [], launchApp: [], refresh: 0, settings: 0 };
  const state = Object.assign({}, component.data.call({}), component.methods);
  state.apps = [
    { appId: 1, appName: 'YouTube', img: '', typeCode: '600002' },
    { appId: 2, appName: 'TV Browser', img: '', typeCode: '600002' }
  ];
  state.sources = [
    { sourceId: 'HDMI1', name: 'HDMI 1', rename: '', icon: 'v-ic-hdmi' },
    { sourceId: 'HDMI2', name: 'HDMI 2', rename: '', icon: 'v-ic-hdmi' }
  ];
  state.status = 'Native · 2 apps · 2 inputs';
  state._platform = {
    changeSource: id => { calls.changeSource.push(id); return 'switched'; },
    launchApp: id => { calls.launchApp.push(id); return 'started'; },
    refresh: () => { calls.refresh++; },
    openSettings: () => { calls.settings++; }
  };
  return { state, calls };
}

// 1. Vendor icon override.
{
  const { state } = makeVm();
  assert.equal(state.localIcon({ img: 'https://img.vidaahub.com/a/b.png' }),
    'https://img.vidaahub.com/a/b.png');
  assert.equal(state.localIcon({ img: 'var/local/storeAppIcon/2.png' }),
    'file:///hisenseUI/var/local/storeAppIcon/2.png');
  assert.equal(state.localIcon({ img: 'v-ic-airplay' }), '');
}

// 2. Merged list on the "All" tab and on the Home shelf.
{
  const { state } = makeVm();
  state.view = 'apps'; state.zone = 'shelf'; state.index = 0;
  const all = state.list();
  assert.equal(all.length, 4, 'apps + inputs must be one list');
  assert.ok(all[2].__alvidaaSource, 'third item must be a wrapped input');
  assert.equal(all[2].appName, 'HDMI 1');
  assert.equal(all[2].__alvidaaSource.sourceId, 'HDMI1');
  state.view = 'home';
  assert.equal(state.list().length, 4, 'Home shelf must also include inputs');
  state.view = 'inputs';
  assert.equal(state.list().length, 2, 'Inputs tab stays an input-only shortcut');
}

// 3. OK dispatches inputs to changeSource and apps to launchApp.
{
  const { state, calls } = makeVm();
  state.view = 'apps'; state.zone = 'shelf'; state.index = 2;
  state.select();
  assert.deepEqual(calls.changeSource, ['HDMI1']);
  assert.equal(calls.launchApp.length, 0);
  state.index = 0;
  state.select();
  assert.deepEqual(calls.launchApp, [1]);
}

// 4. Down from Home lands on the merged list, not the inputs-only view.
{
  const { state } = makeVm();
  state.view = 'home'; state.zone = 'shelf'; state.moving = false;
  assert.equal(state.handleKey(KEYMAP.DOWN), true);
  assert.equal(state.view, 'apps');
}

// 5. Wallpaper preference: default, pref row, cycle, persistence, refresh.
{
  const { state, calls } = makeVm();
  assert.equal(state.wallpaper, 'none');
  state.view = 'prefs'; state.zone = 'shelf'; state.index = 4;
  assert.equal(state.list()[4], 'Wallpaper: None');
  const before = storageWrites.length;
  state.select();
  assert.equal(state.wallpaper, 'dusk');
  assert.equal(state.list()[4], 'Wallpaper: Dusk');
  assert.ok(storageWrites.length > before, 'wallpaper must be persisted');
  assert.equal(storageWrites[storageWrites.length - 1].value.wallpaper, 'dusk');
  assert.equal(calls.refresh, 1, 'OK still refreshes apps and inputs');
  // Theme cycling still works and still saves the wallpaper.
  state.index = 1;
  state.select();
  assert.equal(state.theme, 'dark');
  assert.equal(storageWrites[storageWrites.length - 1].value.wallpaper, 'dusk');
}

// 6. Render: the merged tab is relabelled and a gradient is prepended.
{
  const { state } = makeVm();
  state.view = 'home'; state.zone = 'shelf'; state.index = 0;
  let vnode = component.render.call(state, h);
  const labels = vnode.children
    .filter(node => node.data && node.data.attrs && node.data.attrs['aria-label'])
    .map(node => node.data.attrs['aria-label']);
  assert.ok(labels.includes('All'), 'All apps tab must be relabelled "All"');
  assert.ok(!labels.includes('All apps'));
  assert.ok(!vnode.children[0].data.style.backgroundImage, 'no overlay for "none"');

  state.wallpaper = 'dusk';
  vnode = component.render.call(state, h);
  assert.match(vnode.children[0].data.style.backgroundImage, /linear-gradient/);
  assert.equal(vnode.children[0].data.style.pointerEvents, 'none');
  // The overlay is first, so every existing tile still paints on top.
  assert.ok(vnode.children.length > 1);
}

console.log('native-home-75u8qtuk.test.cjs: load-time + customization smoke OK');
