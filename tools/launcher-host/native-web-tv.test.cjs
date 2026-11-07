'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const create = require('./native-web-tv.js');
function setup() {
  const calls = []; let publish, changes = 0;
  const sdk = { key: { KEYMAP: { LEFT:37, UP:38, RIGHT:39, DOWN:40, ENTER:13, BACK:8 } },
    i18n: { t:key=>key==='SE0001'?'Television':key } };
  const data = {apps:[{appId:1,appName:'Netflix',img:'var/local/storeAppIcon/netflix.png'},
    {appId:2,appName:'Plex',img:'https://external.invalid/logo.png',presetImg:'file:///apps/launcher/plex.png'}],
    sources:[{sourceId:'TV',rename:'SE0001',name:'TV',hasSignal:true},
      {sourceId:'HDMI1',rename:'Console',hasSignal:false},{sourceId:0,name:'Aux',hasSignal:true}]};
  const platform = {start(){calls.push(['start']);publish(data);},stop(){calls.push(['stop']);},
    launchApp(id){calls.push(['app',id]);},changeSource(id){calls.push(['source',id]);},
    openSettings(){calls.push(['settings']);}};
  const options = {createPlatform(_sdk,fn){publish=fn;return platform;},onChange(){changes++;},
    back(){calls.push(['back']);},holdScreenSaver(hold){calls.push(['hold',hold]);return ()=>calls.push(['release']);},timeZone:'Australia/Brisbane'};
  const tv=create(sdk,options);
  return {tv,sdk,options,platform,calls,data,publish:value=>publish(value),changes:()=>changes};
}
function list(tv, method) { let value;tv[method](items=>{value=items;});return value; }
function launch(tv, id, params) { return new Promise(resolve=>tv.launch(id,params,resolve)); }

test('web adapter exposes native IDs, local-only icons and real input state',()=>{
  const f=setup();f.tv.start();
  const apps=list(f.tv,'apps'),inputs=list(f.tv,'inputs');
  assert.equal(apps[0].id,'app:1');assert.equal(apps[0].icon,'file:///hisenseUI/var/local/storeAppIcon/netflix.png');
  assert.equal(apps[1].icon,'file:///apps/launcher/plex.png');
  assert.equal(inputs[0].key,'live');assert.equal(inputs[0].label,'Television');assert.equal(inputs[0].symbol,'live_tv');
  assert.equal(inputs[1].symbol,'hdmi');
  assert.equal(inputs[1].connected,false);assert.equal(inputs[1].label,'Console');
  assert.equal(f.tv.keys.back,8);assert.equal(f.tv.zone(),'Australia/Brisbane');
  apps[0].title='changed';assert.equal(list(f.tv,'apps')[0].title,'Netflix');
});
test('invalid/self/duplicate entries are excluded, native app/input IDs cannot collide',()=>{
  const f=setup();f.data.apps.push({appId:206,appName:'Home'},{appId:'vidaa-home',appName:'Old home'},
    {appId:1,appName:'Duplicate'},{appId:{},appName:'Invalid'},{appId:NaN,appName:'Invalid'},
    {appId:'source:TV',appName:'Valid distinct app'});
  f.data.sources.push({sourceId:'vidaahome'},{sourceId:NaN},{sourceId:false},{sourceId:'TV'});
  f.tv.start();assert.equal(list(f.tv,'apps').length,3);assert.equal(list(f.tv,'inputs').length,3);
  assert.equal(list(f.tv,'apps')[2].id,'app:source:TV');
});
test('unsafe icon URLs and traversal do not reach the privileged renderer',()=>{
  const f=setup();f.data.apps=['https://x/icon.png','//x/icon.png','javascript:alert(1)',
    'data:image/svg+xml;base64,YQ==','var/local/storeAppIcon/../../secret',
    'file:///icons/%2e%2e/secret','file:///icons/back\\slash.png'].map((img,i)=>({appId:i,appName:'App',img}));
  f.tv.start();assert.ok(list(f.tv,'apps').every(app=>app.icon===''));
});
test('launches resolve through SDK platform; params cannot override APC checks',async()=>{
  const f=setup();f.tv.start();assert.equal(await launch(f.tv,'app:1',{isNotNeedLock:true,url:'https://bad.invalid'}),true);
  assert.deepEqual(f.calls.at(-1),['app','1']);
  assert.equal(await launch(f.tv,'source:0'),true);assert.deepEqual(f.calls.at(-1),['source',0]);
  assert.equal(await launch(f.tv,'source:TV'),true);assert.deepEqual(f.calls.at(-1),['source','TV']);
  assert.equal(await launch(f.tv,'unknown'),false);
});
test('removed apps and failed native requests report failure without bypass fallback',async()=>{
  const f=setup();f.tv.start();f.publish({apps:[],sources:[]});
  assert.equal(await launch(f.tv,'app:1'),false);assert.equal(await launch(f.tv,'source:TV'),false);
  f.publish(f.data);f.platform.launchApp=()=>{throw Error('restricted');};assert.equal(await launch(f.tv,'app:1'),false);
  f.platform.launchApp=()=>Promise.reject(Error('denied'));assert.equal(await launch(f.tv,'app:1'),false);
  f.platform.launchApp=()=>false;assert.equal(await launch(f.tv,'app:1'),false);
});
test('changes are deduplicated and callbacks stop after deactivation',()=>{
  const f=setup();f.tv.start();f.tv.start();assert.equal(f.changes(),1);
  f.publish(f.data);assert.equal(f.changes(),1);
  f.data.sources[1].hasSignal=true;f.publish(f.data);assert.equal(f.changes(),2);
  f.tv.stop();f.publish({apps:[],sources:[]});assert.equal(f.changes(),2);
  assert.equal(f.calls.filter(c=>c[0]==='start').length,1);
});
test('back and owned screensaver hold use explicit lifecycle adapters',()=>{
  const f=setup();let showingPhotos=false;
  f.tv.back();f.tv.holdScreenSaver(()=>true);assert.equal(f.calls.length,0);
  f.tv.start();f.tv.back();f.tv.holdScreenSaver(()=>showingPhotos);
  const predicate=f.calls.at(-1)[1];assert.equal(predicate(),false);
  showingPhotos=true;assert.equal(predicate(),true);
  f.tv.holdScreenSaver(()=>{throw Error('failed');});
  assert.equal(f.calls.at(-1)[1](),false);assert.equal(f.calls.at(-2)[0],'release');
  f.tv.stop();f.tv.stop();assert.equal(predicate(),false);
  assert.deepEqual(f.calls.slice(-2),[['release'],['stop']]);
  assert.throws(()=>f.tv.holdScreenSaver(true),/predicate/);
});
test('settings use the preserved vendor entry; inactive runtime cannot start actions',async()=>{
  const f=setup();f.tv.start();assert.equal(await new Promise(resolve=>f.tv.settings(resolve)),true);
  assert.deepEqual(f.calls.at(-1),['settings']);f.tv.stop();
  assert.equal(await new Promise(resolve=>f.tv.settings(resolve)),false);
  assert.equal(await launch(f.tv,'app:1'),false);
});
test('missing lifecycle contracts fail explicitly instead of silently faking support',()=>{
  const f=setup();assert.throws(()=>create(f.sdk,{createPlatform:f.options.createPlatform}),/lifecycle adapters/);
  f.platform.start=()=>{throw Error('not ready');};assert.throws(()=>f.tv.start(),/not ready/);
  assert.deepEqual(f.calls,[['stop']]);
});
