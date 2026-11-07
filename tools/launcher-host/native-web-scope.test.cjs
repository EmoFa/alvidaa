'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const create=require('./native-web-scope.js');
function setup(){
  const timers=new Map(),events=new Map(),queries=[];let serial=0,active=true;
  const element={addEventListener:(n,f)=>events.set('element:'+n,f),removeEventListener:n=>events.delete('element:'+n),
    querySelector:q=>{queries.push(q);return {selector:q};},querySelectorAll:q=>{queries.push(q);return [];}};
  const host={innerWidth:1920,innerHeight:1080,navigator:{language:'en-AU'},
    document:{body:{},documentElement:{},createElement:tag=>({tag}),createTextNode:text=>({text})},
    addEventListener:(n,f)=>events.set('host:'+n,f),removeEventListener:n=>events.delete('host:'+n),
    setTimeout:(fn,_delay)=>{timers.set(++serial,fn);return serial;},setInterval:(fn,_delay)=>{timers.set(++serial,fn);return serial;},
    clearTimeout:id=>timers.delete(id),clearInterval:id=>timers.delete(id)};
  const options={isActive:()=>active,keys:{left:37,up:38,right:39,down:40,ok:13,back:8},storage:{},
    XMLHttpRequest:function CacheOnly(){},Image:function LocalOnly(){},imageElement:()=>({nativeImage:true})};
  const scope=create(host,element,options);
  return {scope,host,element,options,events,timers,queries,active:value=>{active=value;}};
}
test('document, selectors and globals stay within the owned Home subtree',()=>{
  const f=setup(),d=f.scope.document,w=f.scope.window;
  assert.equal(d.body,f.element);assert.equal(d.documentElement,f.element);assert.notEqual(d.body,f.host.document.body);
  assert.equal(w.window,w);assert.equal(w.self,w);assert.equal(w.XMLHttpRequest,f.options.XMLHttpRequest);
  assert.equal(w.Image,f.options.Image);assert.equal(w.location,undefined);
  d.getElementById('clock');d.querySelector('#settings .row');d.querySelectorAll('.focus');
  assert.deepEqual(f.queries,['#fmtv-web-clock','#fmtv-web-settings .row','.focus']);
  assert.equal(d.getElementById('unsafe" selector'),null);
});
test('only handled navigation is consumed; system keys and explicit Back forwarding survive',()=>{
  const f=setup();let calls=0;
  f.scope.document.addEventListener('keydown',e=>{calls++;e.preventDefault();if(e.keyCode===8)f.scope.forwardKey();});
  assert.equal(f.scope.key({keyCode:38}),true);
  assert.equal(f.scope.key({keyCode:999}),false);
  assert.equal(f.scope.key({keyCode:8}),false);
  f.active(false);assert.equal(f.scope.key({keyCode:38}),false);assert.equal(calls,3);
  assert.equal(f.scope.document.hidden,true);
});
test('timers are owned, clear safely and cannot run after disposal',()=>{
  const f=setup();let ticks=0;
  const once=f.scope.window.setTimeout(value=>{ticks+=value;},5,2);
  f.timers.get(once)();assert.equal(ticks,2);
  const interval=f.scope.window.setInterval(()=>ticks++,5),late=f.timers.get(interval);
  f.scope.window.clearTimeout(12345);assert.ok(f.timers.has(interval));
  f.scope.dispose();assert.equal(f.timers.has(interval),false);late();assert.equal(ticks,2);
  assert.equal(f.scope.window.setTimeout(()=>ticks++,0),null);
  assert.throws(()=>{const other=setup();other.scope.window.setTimeout('unsafe()',0);},/String timers/);
});
test('native listeners are gated by route and detached idempotently',()=>{
  const f=setup();let resized=0;
  f.scope.window.addEventListener('resize',()=>resized++);
  f.events.get('host:resize')({});assert.equal(resized,1);
  f.active(false);f.events.get('host:resize')({});assert.equal(resized,1);
  f.scope.dispose();f.scope.dispose();assert.equal(f.events.size,0);
  f.scope.emit('resize');assert.equal(resized,1);
});
test('native rendering adapters are explicit; unsupported elements cannot silently degrade',()=>{
  const f=setup();assert.deepEqual(f.scope.document.createElement('img'),{nativeImage:true});
  for(const tag of ['script','iframe','canvas','style','link'])assert.throws(()=>f.scope.document.createElement(tag),/explicit native adapter/);
  assert.throws(()=>f.scope.document.createElementNS('svg','svg'),/prepared for Cobalt/);
  assert.throws(()=>create(f.host,f.element,{}),/adapters are required/);
});
