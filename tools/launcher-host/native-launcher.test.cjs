const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const source = fs.readFileSync(__dirname + '/native-launcher.js', 'utf8');

function harness() {
  let kids = false, path = '/Launcher', nextTimer = 0;
  const timers = new Map(), sockets = [], pushes = [];
  const keys = { HOME: 10, LAUNCHER: 11, UP: 12, DOWN: 13, LEFT: 14, RIGHT: 15, ENTER: 16 };
  class Socket {
    constructor(url) { this.url = url; this.readyState = 1; this.sent = []; sockets.push(this); }
    send(value) { this.sent.push(JSON.parse(value)); }
    close() { this.readyState = 3; if (this.onclose) this.onclose(); }
    message(value) { this.onmessage({ data: JSON.stringify(value) }); }
  }
  const root = {
    WebSocket: Socket,
    _V_M_: { setting: 'untouched' },
    _V_SDK_: {
      biz: { Logger: function () { this.always = () => {}; }, kidsMode: { getKidsMode: () => kids } },
      vre: { SDK: function (name, options) {
        assert.equal(name, 'launcher');
        assert.equal(options.storagePrefix, 'Alvidaa');
        this.key = { KEYMAP: keys };
        this.router = {
          push: value => { pushes.push(value); path = value.path; return Promise.resolve(); },
          isCurrentPathEqualTo: value => path === value
        };
      } }
    }
  };
  const schedule = callback => { timers.set(++nextTimer, callback); return nextTimer; };
  vm.runInNewContext(source, { self: root, setInterval: schedule, setTimeout: schedule,
    clearInterval: id => timers.delete(id), clearTimeout: id => timers.delete(id) });
  const module = root._V_M_.launcher();
  const component = module.route[0].component;
  const instance = Object.assign(component.data(), component.methods);
  return { root, module, component, instance, sockets, timers, pushes, keys,
    setKids: value => { kids = value; }, setPath: value => { path = value; } };
}

test('actual saved vendor module loader accepts the candidate', {
  skip: !process.env.NATIVE_VENDOR_537
}, async () => {
  const h = harness(), routes = [], handlers = [];
  const log = { always() {}, warn() {}, info() {}, error() {} };
  const dependencies = {
    '9e3e': { log, region: { getCurrnetRegion: () => 'EM_C' },
      hisfactory: { getFacCountry: () => ({ code: 'AUS' }) },
      system: { getCurBrand: () => 'HIS', getOemBoard: () => 0,
        getCurDTVStandardState: () => ({ value: 0 }), getFteshow: () => false },
      country: { getCurrentCountryInfoState: () => ({ value: { code: 'AUS' } }) } },
    cTCn: { addDefaultHandler: (...args) => handlers.push(args) },
    VyUK: { addRoutes: (...args) => routes.push(args) },
    nNfm: { Z: log }
  };
  function requireModule(id) {
    assert.ok(id in dependencies, 'unmocked dependency: ' + id);
    return dependencies[id];
  }
  requireModule.d = (target, getters) => Object.entries(getters).forEach(([key, get]) => {
    Object.defineProperty(target, key, { get });
  });
  // Register chunk factories without executing the vendor boot entry.
  const context = { self: { webpackChunksystem_ui: [], _V_IPK_: {},
    _V_IPK_UPGRADE_: { fail() { assert.fail('vendor loader rejected module'); } } } };
  vm.runInNewContext(fs.readFileSync(process.env.NATIVE_VENDOR_537, 'utf8'), context, { timeout: 1000 });
  const loader = Object.assign({}, ...context.self.webpackChunksystem_ui.map(c => c[1])).gNlz;
  assert.equal(typeof loader, 'function');
  const exported = {};
  loader({}, exported, requireModule);
  exported.Z$({ launcher: { canInit: true, entry: () => h.module } });
  const client = new exported.Yl('launcher');
  client._super.loadModule();
  assert.equal(routes.length, 1);
  assert.equal(routes[0][0], 'launcher');
  assert.equal(handlers.length, 1);
  await client.open('launcherHome', { source: 'power' });
  assert.equal(h.pushes[0].query.source, 'power');
  assert.equal(client.getData('launcherAppVersion').result, 'alvidaa-local-prototype');
});

test('registers only launcher, preserves route metadata and Home contract', async () => {
  const h = harness();
  assert.equal(h.root._V_M_.setting, 'untouched');
  assert.equal(h.module.route[0].meta.sourceInfo.appId, '206');
  await h.module.page.launcherHome({ source: 'home' });
  assert.equal(h.pushes[0].path, '/Launcher');
  assert.equal(h.pushes[0].query.source, 'home');
  assert.equal(h.module.data.launcherDisableCecChange, true);
  h.setPath('/setting');
  assert.equal(h.module.data.launcherDisableCecChange, false);
  h.setKids(true);
  await assert.rejects(h.module.page.launcherHome(), /Kids mode/);
  h.module.route[0].beforeEnter({}, {}, result => assert.equal(result, false));
  await assert.rejects(h.module.page.kidsLauncherHome(), /unsupported/);
  await assert.rejects(h.module.page.gameLauncherHome(), /unsupported/);
});

test('mount/activate is idempotent; deactivation removes sockets and timers', () => {
  const h = harness(), c = h.component, v = h.instance;
  c.mounted.call(v); c.activated.call(v);
  assert.equal(h.sockets.length, 1);
  assert.equal(h.timers.size, 2);
  h.sockets[0].onopen();
  assert.equal(h.timers.size, 1);
  assert.equal(h.sockets[0].url, 'ws://127.0.0.1:8770/ws');
  c.deactivated.call(v);
  assert.equal(h.sockets[0].readyState, 3);
  assert.equal(h.timers.size, 0);
  c.activated.call(v);
  assert.equal(h.sockets.length, 2);
  c.beforeDestroy.call(v);
  assert.equal(h.timers.size, 0);
});

test('bridge snapshots, SDK keys, and action messages work without DOM listeners', () => {
  const h = harness(), v = h.instance;
  v.start();
  const socket = h.sockets[0];
  socket.message({ t: 'hello', sources: [{ id: 1, name: 'HDMI 1' }],
    apps: [{ name: 'YouTube' }, { name: 'Home', appId: 'vidaa-home' }, { name: ' ' }] });
  assert.equal(v.apps.length, 1);
  const key = h.module.key.keydown.groups[1].handler;
  key({ keyCode: h.keys.ENTER });
  assert.deepEqual(socket.sent[0], { t: 'source', id: '1' });
  key({ keyCode: h.keys.DOWN }); key({ keyCode: h.keys.ENTER });
  assert.deepEqual(socket.sent[1], { t: 'launch', name: 'YouTube' });
  h.setPath('/setting'); key({ keyCode: h.keys.ENTER });
  assert.equal(socket.sent.length, 2);
  socket.onmessage({ data: '{bad json' }); socket.message(null);
  socket.message({ t: 'hello', sources: [null], apps: [null, {}] });
  assert.equal(v.apps.length, 0);
  assert.equal(v.sources.length, 0);
  v.activate();
  assert.equal(socket.sent.length, 2);
  v.stop();
});

test('retries a disconnected bridge, but cancels retry when hidden', () => {
  const h = harness(), v = h.instance;
  v.start(); h.sockets[0].close();
  assert.equal(h.timers.size, 2);
  assert.match(v.status, /retrying/);
  h.timers.get(v._retry)();
  assert.equal(h.sockets.length, 2);
  v.stop();
  assert.equal(h.timers.size, 0);
});

test('a stalled connection times out and schedules a retry', () => {
  const h = harness(), v = h.instance;
  v.start();
  h.timers.get(v._connectTimeout)();
  assert.equal(h.sockets[0].readyState, 3);
  assert.match(v.status, /retrying/);
  assert.ok(h.timers.has(v._retry));
  v.stop();
  assert.equal(h.timers.size, 0);
});

test('renders clock and paged text tiles without canvas, iframe, or HTML injection', () => {
  const h = harness(), v = h.instance;
  v.sources = Array.from({ length: 8 }, (_, i) => ({ id: String(i), name: '<input ' + i + '>' }));
  v.col = 7;
  const tree = h.component.render.call(v, (tag, data, children) => ({ tag, data, children }));
  const text = JSON.stringify(tree);
  assert.match(text, /ALVIDAA — NATIVE TEST N02/);
  assert.match(text, /<input 7>/);
  assert.doesNotMatch(text, /<input 0>/);
  assert.doesNotMatch(text, /canvas|iframe|innerHTML/);
  assert.match(v.time, /^\d\d:\d\d$/);
});
