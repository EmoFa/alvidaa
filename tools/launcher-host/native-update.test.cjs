'use strict';
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const test=require('node:test'),assert=require('node:assert/strict');
const {NativeHome,perform}=require('./native-home.cjs');
const {APP,CONFIG,CACHE,hash}=require('./native-trial.cjs');
const {stageUpdate,applyUpdate}=require('./native-update.cjs');
async function setup(t){
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'native-update-test-'));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  function write(file,data){fs.mkdirSync(path.dirname(root+file),{recursive:true});fs.writeFileSync(root+file,data,{mode:0o640});}
  write(APP,'stock');write(CONFIG,'{"watcher":{"enabled":true}}');
  for(const name of ['compiled_js','uncompiled_js'])write(CACHE+'/'+name+'/original','stock-cache');
  write('/candidate.js',fs.readFileSync(__dirname+'/native-launcher.js'));
  let running=true;
  const home=new NativeHome({root,hashes:{[APP]:hash('stock')},engines:()=>running?[123]:[]});
  home.prepare(root+'/candidate.js');
  const ops=(_context,change)=>({change});
  const restart=async op=>{running=false;await op.change();running=true;return {pid:456};};
  await perform(home,{},'install',restart,ops);
  const previous=fs.readFileSync(root+APP);
  write('/update.js','/* ALVIDAA_FREE_MY_TV_NATIVE_V1 */ self.test = true;');
  return {root,home,write,restart,ops,previous,candidate:root+'/update.js'};
}
test('update preserves stock backups, metadata and storage; stock restore still works',async t=>{
  const f=await setup(t); f.write(CACHE+'/compiled_js/current','native-cache'); f.write(CACHE+'/origin.storage','keep');
  const originalHash=f.home.load().files[0].original;
  stageUpdate(f.home,f.candidate);
  assert.throws(()=>applyUpdate(f.home),/UI is alive/);
  await perform(f.home,{},'update',f.restart,f.ops);
  assert.equal(f.home.load().phase,'installed');assert.equal(f.home.load().files[0].original,originalHash);
  assert.match(fs.readFileSync(f.root+APP,'utf8'),/self.test/);
  assert.equal(fs.statSync(f.root+APP).mode&0o777,0o640);
  assert.equal(fs.readFileSync(f.root+CACHE+'/origin.storage','utf8'),'keep');
  assert.ok(fs.existsSync(f.home.load().lastUpdate+'/previous.js'));
  await perform(f.home,{},'restore',f.restart,f.ops);
  assert.equal(fs.readFileSync(f.root+APP,'utf8'),'stock');
  assert.equal(JSON.parse(fs.readFileSync(f.root+CONFIG)).watcher.enabled,false);
  assert.equal(fs.readFileSync(f.root+CACHE+'/compiled_js/original','utf8'),'stock-cache');
});
test('failed update startup rolls back prior native bytes and caches, not stock',async t=>{
  const f=await setup(t);f.write(CACHE+'/compiled_js/current','prior-cache');stageUpdate(f.home,f.candidate);
  let calls=0;
  const fail=async op=>{const engine=await f.restart(op);if(++calls===1)throw new Error('candidate crashed');return engine;};
  await assert.rejects(perform(f.home,{},'update',fail,f.ops),/candidate crashed/);
  assert.deepEqual(fs.readFileSync(f.root+APP),f.previous);
  assert.equal(f.home.load().phase,'installed');
  assert.equal(fs.readFileSync(f.root+CACHE+'/compiled_js/current','utf8'),'prior-cache');
});
test('staging rejects concurrent edits, bad syntax and duplicate pending update',async t=>{
  const f=await setup(t);
  f.write('/bad.js','/* ALVIDAA_FREE_MY_TV_NATIVE_V1 */ function {');
  assert.throws(()=>stageUpdate(f.home,f.root+'/bad.js'),SyntaxError);
  f.write(CONFIG,'{"another":"agent"}');assert.throws(()=>stageUpdate(f.home,f.candidate),/concurrent edit/);
  f.write(CONFIG,JSON.stringify({watcher:{enabled:false}},null,2));
  stageUpdate(f.home,f.candidate);assert.throws(()=>stageUpdate(f.home,f.candidate),/stable installed/);
});
test('restore recovers an interrupted staged update and keeps original stock backups',async t=>{
  const f=await setup(t);stageUpdate(f.home,f.candidate);
  await perform(f.home,{},'restore',f.restart,f.ops);
  assert.equal(fs.readFileSync(f.root+APP,'utf8'),'stock');
});
test('candidate tampering aborts before mutation and recovers previous installation',async t=>{
  const f=await setup(t);const u=stageUpdate(f.home,f.candidate);
  fs.writeFileSync(u.directory+'/candidate.js','tampered');
  await assert.rejects(perform(f.home,{},'update',f.restart,f.ops),/candidate changed/);
  assert.deepEqual(fs.readFileSync(f.root+APP),f.previous);
});
test('native can be reapplied after stock restore without losing stock cache recovery',async t=>{
  const f=await setup(t);
  await perform(f.home,{},'restore',f.restart,f.ops);
  stageUpdate(f.home,f.candidate);await perform(f.home,{},'update',f.restart,f.ops);
  assert.equal(f.home.load().phase,'installed');
  await perform(f.home,{},'restore',f.restart,f.ops);
  assert.equal(fs.readFileSync(f.root+APP,'utf8'),'stock');
  assert.equal(fs.readFileSync(f.root+CACHE+'/compiled_js/original','utf8'),'stock-cache');
});
test('failed reapplication preserves restored state, not a false installed state',async t=>{
  const f=await setup(t);await perform(f.home,{},'restore',f.restart,f.ops);
  stageUpdate(f.home,f.candidate);let calls=0;
  const fail=async op=>{const engine=await f.restart(op);if(++calls===1)throw Error('crash');return engine;};
  await assert.rejects(perform(f.home,{},'update',fail,f.ops),/crash/);
  assert.equal(f.home.load().phase,'restored');assert.equal(fs.readFileSync(f.root+APP,'utf8'),'stock');
});
