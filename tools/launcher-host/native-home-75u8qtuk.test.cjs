#!/usr/bin/env node
/* Load-time smoke test for the 75U8QTUK appended bundle (no vendor code).
 * Verifies the four appended parts execute in order, the /Launcher route is
 * replaced by our component, and the model icon override accepts vendor URLs.
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

class SDK {
  constructor() {
    this.key = { KEYMAP };
    this.storage = { get: () => null, set: () => {} };
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

const icon = component.methods.localIcon.call({}, {
  appId: 1, appName: 'Netflix', img: 'https://img.vidaahub.com/epgdata/mamPic/600/114/icon.png'
});
assert.equal(icon, 'https://img.vidaahub.com/epgdata/mamPic/600/114/icon.png');
assert.equal(component.methods.localIcon.call({}, {
  appId: 2, appName: 'Local', img: 'var/local/storeAppIcon/2.png'
}), 'file:///hisenseUI/var/local/storeAppIcon/2.png');
assert.equal(component.methods.localIcon.call({}, { appId: 3, appName: 'None', img: 'v-ic-airplay' }), '');

// The wrapper is idempotent: repeated factory calls return the same object.
assert.equal(sandbox._V_M_.launcher(), stock);

console.log('native-home-75u8qtuk.test.cjs: load-time smoke OK');
