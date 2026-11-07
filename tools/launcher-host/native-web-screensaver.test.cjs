'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const create=require('./native-web-screensaver.js');
function setup(){
  const listeners=new Map(),calls=[];let isHome=true;
  const sdk={router:{isCurrentPathEqualTo:()=>isHome},message:{
    on:(name,fn)=>listeners.set(name,fn),off:(name,fn)=>{if(listeners.get(name)===fn)listeners.delete(name);},
    emit:(name,data)=>calls.push({name,data})}};
  return {sdk,listeners,calls,register:create(sdk),route:value=>{isHome=value;}};
}
test('native arbitration preserves system timeout and respects dynamic photo availability',()=>{
  const f=setup();let photos=false;const release=f.register(()=>photos);
  assert.equal(f.calls[0].name,'n2o://screen-saver/art-start-screensaver');
  assert.deepEqual(Object.keys(f.calls[0].data),['beforeStart']);
  const allowed=f.calls[0].data.beforeStart;
  assert.equal(allowed(),true);photos=true;assert.equal(allowed(),false);
  photos=false;f.route(false);assert.equal(allowed(),false);
  release();assert.equal(f.listeners.size,0);f.route(true);assert.equal(allowed(),false);
  assert.equal(f.calls.length,1,'release must not overwrite another page\'s native timer');
});
test('arbitration re-arms after original SDK initialization, never from another route',()=>{
  const f=setup();f.register(()=>false);
  const initialized=f.listeners.get('o2n://sdk/init-finished');initialized();assert.equal(f.calls.length,2);
  f.route(false);initialized();assert.equal(f.calls.length,2);
});
test('predicate failures allow native protection rather than disabling it',()=>{
  const f=setup();f.register(()=>{throw Error('photo cache unavailable');});
  assert.equal(f.calls[0].data.beforeStart(),true);
});
test('failed registration removes listeners and release is idempotent',()=>{
  const f=setup();f.sdk.message.emit=()=>{throw Error('unavailable');};
  assert.throws(()=>f.register(()=>true),/unavailable/);assert.equal(f.listeners.size,0);
  const other=setup();const release=other.register(()=>false);release();release();assert.equal(other.listeners.size,0);
});
