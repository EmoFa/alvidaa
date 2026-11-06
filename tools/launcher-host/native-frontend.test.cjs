'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function setup(prefs) {
  const calls = [], timers = new Map(); let next = 0;
  const bodyListeners = new Set();
  const root = { innerWidth: 1280, addEventListener() {}, removeEventListener() {},
    document: { body: { addEventListener(_name,fn){bodyListeners.add(fn);}, removeEventListener(_name,fn){bodyListeners.delete(fn);} } }, bodyListeners };
  const sdk = { key: { KEYMAP: { HOME:36, LAUNCHER:547, SOURCE:515, KEYPAD_INPUT:516, UP:38, DOWN:40, LEFT:37, RIGHT:39, ENTER:13, BACK:8 } },
    storage: { get:()=>prefs, set:(_key,value)=>calls.push(['save',value]) },
    apc: { CMDMETHOD: { KEY_INPUT_START:'input' } }, router: { isCurrentPathEqualTo:()=>true } };
  root._V_SDK_ = { vre: { SDK: function () { return sdk; } } };
  let notify;
  root.AlvidaaNativePlatform = () => ({ start(){calls.push(['start']);notify({apps:[
    {appId:'1',appName:'Netflix',img:'https://must-not-fetch/icon.png'},
    {appId:'2',appName:'Plex',img:'file:///local/icon.png'},
    {appId:'vidaa-home',appName:'Old browser home'}],sources:[{sourceId:0,name:'TV'},{sourceId:'HDMI1',name:'HDMI1'}],errors:[],waiting:false});},
    stop(){calls.push(['stop']);},refresh(){calls.push(['refresh']);},
    launchApp(id){calls.push(['launch',id]);}, changeSource(id){calls.push(['source',id]);},openSettings(){calls.push(['settings']);} });
  const create = root.AlvidaaNativePlatform;
  root.AlvidaaNativePlatform = (_sdk, callback) => { notify=callback; return create(); };
  const context = {self:root, setInterval(fn){let id=++next;timers.set(id,fn);return id;},clearInterval(id){timers.delete(id);} };
  vm.runInNewContext(fs.readFileSync(__dirname+'/free-my-tv-native.js','utf8'),context);
  const component = root.AlvidaaFreeMyTV(sdk), instance = component.data();
  instance.$route={query:{}};
  for(const [key,fn] of Object.entries(component.methods)) instance[key]=fn.bind(instance);
  return {root,sdk,context,component,instance,calls,timers};
}
test('offline frontend starts once, excludes browser Home and cleans up',()=>{
  const f=setup(); f.component.mounted.call(f.instance); f.component.activated.call(f.instance);
  assert.equal(f.calls.filter(c=>c[0]==='start').length,1);
  assert.equal(f.instance.apps.length,2); assert.equal(f.root.AlvidaaNativeActive,f.instance);
  f.component.deactivated.call(f.instance); assert.equal(f.timers.size,0); assert.equal(f.root.AlvidaaNativeActive,null);
  f.component.activated.call(f.instance); assert.equal(f.calls.filter(c=>c[0]==='start').length,2);
});
test('remote navigates apps, native settings and inputs; Back remains vendor-owned at Home',()=>{
  const f=setup(),v=f.instance,k=f.sdk.key.KEYMAP; v.start();
  assert.equal(v.handleKey(k.BACK),false); assert.equal(v.handleKey(999),false);
  v.handleKey(k.ENTER); assert.deepEqual(f.calls.at(-1),['launch','1']);
  v.handleKey(k.DOWN); assert.equal(v.view,'inputs'); v.handleKey(k.ENTER);
  assert.deepEqual(f.calls.at(-1),['source',0]);
  v.handleKey(k.BACK); v.handleKey(k.UP);
  v.index=3; v.handleKey(k.ENTER); assert.deepEqual(f.calls.at(-1),['settings']);
  v.$route.query={value:k.SOURCE}; v.routeFocus(); assert.equal(v.view,'inputs');
});
test('preferences persist theme, empty favorites and shelf reordering',()=>{
  const f=setup(),v=f.instance; v.start(); v.show('edit'); v.select();
  assert.equal(v.shelf()[0].appId,'2'); v.index=1; v.select(); assert.equal(v.shelf().length,0);
  v.index=0; v.select(); v.index=1; v.select();
  v.show('reorder'); v.select(); v.handleKey(f.sdk.key.KEYMAP.RIGHT);
  assert.equal(v.shelf()[0].appId,'2'); assert.equal(v.index,1);
  v.show('prefs'); v.index=1; v.select(); assert.equal(v.theme,'dark');
  assert.ok(f.calls.some(c=>c[0]==='save'));
  const empty=setup({favorites:[],theme:'light'}); empty.instance.start();
  assert.equal(empty.instance.shelf().length,0); assert.equal(empty.instance.theme,'light');
});
test('renderer scales design and never loads remote icons/canvas/iframe',()=>{
  const f=setup(); f.instance.start();
  const tree=f.component.render.call(f.instance,(tag,data,children)=>({tag,data,children}));
  const flat=[]; function walk(n){if(!n||typeof n!=='object')return;flat.push(n);for(const c of n.children||[])walk(c);} walk(tree);
  assert.ok(flat.some(n=>n.children?.includes('For You')));
  assert.equal(flat.filter(n=>n.tag==='img').length,0);
  assert.equal(flat.filter(n=>n.data?.style?.backgroundImage).length,1);
  assert.equal(flat.find(n=>n.data?.style?.backgroundImage).data.style.backgroundImage,'url("file:///local/icon.png")');
  assert.ok(!flat.some(n=>['canvas','iframe','script'].includes(n.tag)));
  assert.equal(flat.find(n=>n.children?.includes('For You')).data.style.fontSize,76*1280/1920+'px');
  assert.equal(f.instance.localIcon({img:'var/local/storeAppIcon/logo.png'}),'file:///hisenseUI/var/local/storeAppIcon/logo.png');
  assert.equal(f.instance.localIcon({img:'https://cdn.example/logo',presetImg:'file:///builtin.png'}),'file:///builtin.png');
  assert.equal(f.instance.localIcon({img:'http://127.0.0.1:8770/api/icon/1'}),'');
  f.sdk.i18n={t:key=>key==='LA0159'?'Media':key};
  assert.equal(f.instance.sourceName({rename:'LA0159',name:'Media'}),'Media');
  assert.equal(f.instance.sourceName({rename:'PlayStation',name:'HDMI3'}),'PlayStation');
});
test('entry replaces only main component, retains guards/pages/init/key groups and is idempotent',()=>{
  const f=setup();
  const guard=()=>{},init=()=>{},kids=()=>{},game=()=>{},originalKey=()=>{};
  const stock={route:[{path:'/Launcher',component:{old:true},beforeEnter:guard},{path:'/KidsLauncher',component:kids},{path:'/GameLauncher',component:game}],
    page:{kidsLauncherHome:kids,gameLauncherHome:game},init,key:{keydown:{groups:[{keys:[36,515],handler:originalKey}]}}};
  f.root._V_M_={launcher:()=>stock};
  vm.runInNewContext(fs.readFileSync(__dirname+'/native-entry.js','utf8'),f.context);
  const result=f.root._V_M_.launcher();
  assert.equal(result.route[0].component.name,'Launcher'); assert.equal(result.route[0].beforeEnter,guard);
  assert.equal(result.route[1].component,kids); assert.equal(result.page.gameLauncherHome,game); assert.equal(result.init,init);
  assert.equal(result.key.keydown.groups[0].handler,originalKey);
  assert.equal(f.root._V_M_.launcher(),result); assert.equal(result.key.keydown.groups.length,1);
});
test('bubbling Home keys precede defaults, pass unrelated keys and detach cleanly',()=>{
  const f=setup();f.instance.start();f.instance.start();assert.equal(f.root.bodyListeners.size,1);
  const handler=[...f.root.bodyListeners][0];let stopped=0;
  const send=keyCode=>handler({keyCode,stopPropagation(){stopped++;}});
  send(999);send(f.sdk.key.KEYMAP.SOURCE);send(f.sdk.key.KEYMAP.BACK);assert.equal(stopped,0);
  f.instance.show('prefs');send(f.sdk.key.KEYMAP.BACK);assert.equal(stopped,1);assert.equal(f.instance.view,'home');
  f.sdk.router.isCurrentPathEqualTo=()=>false;send(f.sdk.key.KEYMAP.DOWN);assert.equal(stopped,1);
  f.instance.stop();assert.equal(f.root.bodyListeners.size,0);
});
test('native focus announcements respect the vendor screen-reader setting and route',()=>{
  const f=setup(),spoken=[]; let enabled=false;
  f.sdk.tts={isEnable:()=>enabled,speak:text=>spoken.push(text)};f.instance.start();
  f.instance.announce();assert.equal(spoken.length,0);
  enabled=true;f.instance.announce();assert.equal(spoken.at(-1),'Netflix');
  f.instance.show('inputs');f.instance.announce();assert.equal(spoken.at(-1),'TV');
  f.sdk.router.isCurrentPathEqualTo=()=>false;f.instance.announce();assert.equal(spoken.length,2);
});
