'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {storage}=require('./native-web-runtime.js');
const PREFIX='alvidaa.freeMyTV.web.';
test('Settings scope uses SDK module identity rather than a guessed canonical path',()=>{
 const fs=require('node:fs'),vm=require('node:vm');let configuration;
 const root={AlvidaaNativeSettingsTheme:{configure:value=>{configuration=value;}}};
 vm.runInNewContext(fs.readFileSync(require.resolve('./native-web-runtime.js'),'utf8'),{self:root});
 let changing={},current={path:'/runtime-namespace/setting/settings'},owner='setting';
 root.AlvidaaFreeMyTV({storage:{get:()=>'{"theme":"light"}'},router:{
  getChangingPage:()=>changing,getCurrentPage:()=>current,parseRoute:page=>{assert.equal(page,current);return {moduleName:owner};}
 }});
 assert.equal(configuration.route(),'/setting');assert.equal(configuration.preferences(),'{"theme":"light"}');
 owner='launcher';assert.equal(configuration.route(),'');
});
test('native overlays suppress visibility and timezone changes remount once without changing preferences',()=>{
 const fs=require('node:fs'),vm=require('node:vm'),timers=new Map();let id=0,zone=1,foreground=true,runs=0,disposed=0;
 const events=[],values=new Map([[PREFIX+'fmtv.prefs','{"theme":"auto"}']]);
 const root={document:{hidden:false,getElementById:()=>({}),body:{addEventListener(){},removeEventListener(){}}},
  modeljs:{getIntValue:()=>zone},setTimeout:(fn,delay)=>{timers.set(++id,{fn,delay});return id;},clearTimeout:key=>timers.delete(key),
  AlvidaaNativeWebBundle:{tree:[],run:()=>{runs++;return {control:{}};}},
  AlvidaaNativeWebTV:()=>({keys:{},start(){},stop(){}}),AlvidaaNativeWebScreenSaver:()=>()=>{},
  AlvidaaNativeWebScope:()=>({window:{},emit:name=>events.push(name),dispose:()=>disposed++}),
  AlvidaaNativeWebCompat:()=>({invalidate(){},dispose(){},accept(){}})};
 root.XMLHttpRequest=function(){this.open=()=>{};this.setRequestHeader=()=>{};this.abort=()=>{};
  this.send=()=>{this.readyState=4;this.status=200;this.responseText='{"ret":false}';this.onreadystatechange();};};
 vm.runInNewContext(fs.readFileSync(require.resolve('./native-web-runtime.js'),'utf8'),{self:root});
 const sdk={storage:{get:key=>values.get(key),set:(key,value)=>values.set(key,value)},router:{isCurrentPathEqualTo:()=>foreground}};
 const component=root.AlvidaaFreeMyTV(sdk),instance={$el:{innerHTML:''}};Object.assign(instance,component.methods);
 function tick(){const [key,timer]=[...timers].sort((a,b)=>a[1].delay-b[1].delay)[0];timers.delete(key);timer.fn();}
 component.mounted.call(instance);assert.equal(runs,1);
 foreground=false;tick();assert.deepEqual(events,['visibilitychange']);
 zone=0;tick();assert.equal(runs,1,'do not remount under a native overlay');
 foreground=true;tick();assert.equal(runs,1,'defer remount outside the current mount/poll stack');
 tick();assert.equal(runs,2);assert.equal(disposed,1);assert.equal(values.get(PREFIX+'fmtv.prefs'),'{"theme":"auto"}');
 tick();assert.equal(runs,2);instance.stop();assert.equal(timers.size,0);
});
function fixture(initial={}){
 const data=new Map(Object.entries(initial)),writes=[];
 const sdk={storage:{get:key=>data.get(key),set:(key,value)=>{writes.push(key);data.set(key,value);}}};
 return {data,writes,sdk};
}
test('web preferences migrate theme and ordered favorites without modifying the legacy store',()=>{
 const legacy=JSON.stringify({theme:'light',favorites:['netflix','42','youtube']});
 const f=fixture({'alvidaa.freeMyTV':legacy,'vendor.preference':'keep'}),local=storage(f.sdk);
 assert.deepEqual(JSON.parse(local.getItem('fmtv.prefs')),{theme:'light',shelf:['app:netflix','app:42','app:youtube']});
 assert.equal(f.data.get('alvidaa.freeMyTV'),legacy);assert.equal(f.data.get('vendor.preference'),'keep');
 assert.deepEqual(f.writes,[PREFIX+'fmtv.prefs']);
});
test('saved upstream choices survive a new adapter instance and are not overwritten by legacy choices',()=>{
 const f=fixture({'alvidaa.freeMyTV':{theme:'light',favorites:['old']}}),first=storage(f.sdk);
 const prefs=JSON.stringify({theme:'dark',lang:'pt-BR',shelf:['app:new'],weather:false,quotes:false});
 first.setItem('fmtv.prefs',prefs);first.setItem('fmtv.cache.test','cached');
 const second=storage(f.sdk);assert.equal(second.getItem('fmtv.prefs'),prefs);assert.equal(second.getItem('fmtv.cache.test'),'cached');
 second.removeItem('fmtv.cache.test');assert.equal(storage(f.sdk).getItem('fmtv.cache.test'),null);
 assert.equal(f.data.get('alvidaa.freeMyTV').theme,'light');
});
test('empty favorites remain empty and malformed legacy data is not rewritten',()=>{
 const f=fixture({'alvidaa.freeMyTV':{theme:'auto',favorites:[]}});
 assert.deepEqual(JSON.parse(storage(f.sdk).getItem('fmtv.prefs')),{theme:'auto',shelf:[]});
 const bad=fixture({'alvidaa.freeMyTV':'broken legacy JSON'});assert.equal(storage(bad.sdk).getItem('fmtv.prefs'),null);assert.deepEqual(bad.writes,[]);
});
test('upstream storage cannot address unrelated vendor keys',()=>{
 const f=fixture(),local=storage(f.sdk);
 for(const name of ['vendor.preference','../fmtv.prefs','fmtv.X','fmtv.prefs\n']){
  assert.throws(()=>local.getItem(name),/Unexpected preference key/);
  assert.throws(()=>local.setItem(name,'x'),/Unexpected preference key/);
  assert.throws(()=>local.removeItem(name),/Unexpected preference key/);
 }
 assert.deepEqual(f.writes,[]);
});
