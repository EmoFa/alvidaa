'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {hash,APP}=require('./native-trial.cjs');
const {verify,relative,file,inspect,restoreFiles,transaction,manage,verifyShared,ownsPendingUpdate,REQUIRED}=require('./native-web-release.cjs');
function fixture(t){
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'fmtv-release-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const revision='f2d984c51edca1544e39f2d44cdf86b75b0b6703',font=Buffer.from('/* font fixture */');
 const assets=Buffer.from(JSON.stringify({upstream:revision,files:{'fonts.css':hash(font)}})),assetId=hash(assets).slice(0,20),files={};
 for(const name of REQUIRED)files['runtime/'+name]=Buffer.from('// fixture '+name);
 const data=Buffer.from('// upstream fixture');files['runtime/third-party/free-my-tv/upstream/data.js']=data;
 files['runtime/third-party/free-my-tv/upstream/MANIFEST.json']=Buffer.from(JSON.stringify({revision,files:{'data.js':hash(data)}}));
 files['assets/'+assetId+'/fonts.css']=font;
 files['runtime/candidate.js']=Buffer.from('/* ALVIDAA_FREE_MY_TV_NATIVE_V1 ALVIDAA_FREE_MY_TV_WEB_PARITY_V2 */');
 files['runtime/native-image']=Buffer.from([127,69,76,70,1,1,0,0,0,0,0,0,0,0,0,0,0,0,40,0]);
 files['assets/'+assetId+'/assets.json']=assets;
 const manifest={version:1,upstream:'f2d984c51edca1544e39f2d44cdf86b75b0b6703',assetId,candidate:hash(files['runtime/candidate.js']),files:{}};
 const save=()=>fs.writeFileSync(path.join(root,'RELEASE.json'),JSON.stringify(manifest));
 function put(name,data){
  const target=path.join(root,name);fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,data);
  manifest.files[name]={sha256:hash(data),size:data.length};save();
 }
 for(const [name,data]of Object.entries(files))put(name,data);
 return {root,manifest,save,put};
}
test('release verification is read-only and covers the recovery controller, helper and content-addressed assets',t=>{
 const f=fixture(t),before=fs.readFileSync(path.join(f.root,'RELEASE.json'));
 assert.equal(verify(f.root).manifest.candidate,f.manifest.candidate);
 assert.deepEqual(fs.readFileSync(path.join(f.root,'RELEASE.json')),before);
 assert.ok(!fs.existsSync(path.join(f.root,'state.json')));
});
test('release refuses missing recovery code, altered bytes and writable code',t=>{
 const f=fixture(t),name='runtime/native-web-release.cjs',entry=f.manifest.files[name];
 delete f.manifest.files[name];f.save();assert.throws(()=>verify(f.root),/Missing runtime/);
 f.manifest.files[name]=entry;f.save();fs.appendFileSync(path.join(f.root,name),'changed');assert.throws(()=>verify(f.root),/mismatch/);
 f.put(name,Buffer.from('// restored'));fs.chmodSync(path.join(f.root,name),0o666);assert.throws(()=>verify(f.root),/permissions/);
});
test('release refuses path traversal, symlink parents and unsupported members',t=>{
 const f=fixture(t);
 for(const bad of ['../keys/token','/etc/passwd','runtime//file','runtime/./file','runtime\\file'])assert.throws(()=>relative(bad),/Unsafe/);
 fs.renameSync(path.join(f.root,'runtime'),path.join(f.root,'real-runtime'));
 fs.symlinkSync('real-runtime',path.join(f.root,'runtime'));assert.throws(()=>verify(f.root),/symlink/);
 assert.throws(()=>file(f.root,'runtime/missing/deeper/file',true),/symlink/);
 fs.unlinkSync(path.join(f.root,'runtime'));fs.renameSync(path.join(f.root,'real-runtime'),path.join(f.root,'runtime'));
 f.put('public/keys.json',Buffer.from('{}'));assert.throws(()=>verify(f.root),/Unexpected release/);
});
test('release refuses malformed JSON, invalid JavaScript and the wrong architecture',t=>{
 const f=fixture(t);fs.writeFileSync(path.join(f.root,'RELEASE.json'),'{');assert.throws(()=>verify(f.root),/Invalid release JSON/);f.save();
 const bad=Buffer.from('/* ALVIDAA_FREE_MY_TV_WEB_PARITY_V2 */ function {');f.put('runtime/candidate.js',bad);f.manifest.candidate=hash(bad);f.save();assert.throws(()=>verify(f.root),SyntaxError);
 const good=Buffer.from('/* ALVIDAA_FREE_MY_TV_WEB_PARITY_V2 */');f.put('runtime/candidate.js',good);f.manifest.candidate=hash(good);f.save();
 const binary=fs.readFileSync(path.join(f.root,'runtime/native-image'));binary[18]=62;f.put('runtime/native-image',binary);assert.throws(()=>verify(f.root),/ARM32/);
});
function rollbackFixture(t){
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'fmtv-rollback-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const runtime=path.join(root,'runtime'),journal=path.join(root,'journal');fs.mkdirSync(runtime);fs.mkdirSync(path.join(journal,'before'),{recursive:true});
 fs.writeFileSync(path.join(runtime,'worker.cjs'),'after');fs.writeFileSync(path.join(runtime,'added.cjs'),'added');fs.writeFileSync(path.join(runtime,'origin.storage'),'untouched');
 fs.writeFileSync(path.join(journal,'before/worker.cjs'),'before');
 const plan={runtime,files:[{name:'worker.cjs',before:hash('before'),after:hash('after'),uid:process.getuid(),gid:process.getgid(),mode:0o640},{name:'added.cjs',before:null,after:hash('added')}]};
 return {root,runtime,journal,plan};
}
test('rollback restores exact bytes and modes, removes only owned new files, and is repeatable',t=>{
 const f=rollbackFixture(t);restoreFiles(f.journal,f.plan);restoreFiles(f.journal,f.plan);
 assert.equal(fs.readFileSync(path.join(f.runtime,'worker.cjs'),'utf8'),'before');
 assert.equal(fs.statSync(path.join(f.runtime,'worker.cjs')).mode&0o777,0o640);
 assert.ok(!fs.existsSync(path.join(f.runtime,'added.cjs')));assert.equal(fs.readFileSync(path.join(f.runtime,'origin.storage'),'utf8'),'untouched');
 inspect(f.runtime,f.plan.files,'before');
});
test('rollback refuses concurrent edits before touching any runtime member',t=>{
 const f=rollbackFixture(t);fs.writeFileSync(path.join(f.runtime,'added.cjs'),'another session');
 assert.throws(()=>restoreFiles(f.journal,f.plan),/Concurrent runtime edit/);
 assert.equal(fs.readFileSync(path.join(f.runtime,'worker.cjs'),'utf8'),'after');
});
test('shared firmware is pinned without requiring the active Home to remain stock',t=>{
 const f=rollbackFixture(t),home={hashes:{'worker.cjs':hash('after'),[APP]:hash('stock')},p:name=>path.join(f.runtime,name)};
 verifyShared(home);fs.writeFileSync(path.join(f.runtime,'worker.cjs'),'different firmware');
 assert.throws(()=>verifyShared(home),/Shared firmware changed/);
 assert.equal(fs.readFileSync(path.join(f.runtime,'origin.storage'),'utf8'),'untouched');
});
test('rollback refuses altered backups and symlink targets',t=>{
 const f=rollbackFixture(t);fs.writeFileSync(path.join(f.journal,'before/worker.cjs'),'changed');
 assert.throws(()=>restoreFiles(f.journal,f.plan),/Recovery backup changed/);
 fs.unlinkSync(path.join(f.runtime,'worker.cjs'));fs.symlinkSync('origin.storage',path.join(f.runtime,'worker.cjs'));
 assert.throws(()=>restoreFiles(f.journal,f.plan),/symlink/);
 assert.equal(fs.readFileSync(path.join(f.runtime,'origin.storage'),'utf8'),'untouched');
});
function operations(failure,recoveryFailure){
 const calls=[],ops={phase:p=>calls.push(p)};
 for(const name of ['install','applyHome','restoreHome','restore'])ops[name]=()=>{calls.push(name);if(name===failure||name===recoveryFailure)throw Error(name+' failed');};
 return {calls,ops};
}
test('recovery recognizes its own interrupted forward and rollback updates, never foreign work',()=>{
 const plan={beforeStateObject:'before-state',restoreBeforeState:'rollback-state',beforeHome:'old',afterHome:'new'};
 assert.equal(ownsPendingUpdate(plan,{beforeHash:'before-state',candidateHash:'new'}),true);
 assert.equal(ownsPendingUpdate(plan,{beforeHash:'rollback-state',candidateHash:'old'}),true);
 assert.equal(ownsPendingUpdate(plan,{beforeHash:'foreign',candidateHash:'new'}),false);
 assert.equal(ownsPendingUpdate(plan,{beforeHash:'rollback-state',candidateHash:'new'}),false);
 delete plan.restoreBeforeState;assert.equal(ownsPendingUpdate(plan,{candidateHash:'old'}),false);
});
test('transaction installs runtime before Home and does not declare service health prematurely',async()=>{
 const f=operations();await transaction('apply',f.ops);assert.deepEqual(f.calls,['applying','install','applyHome','runtime-installed']);
});
for(const failure of ['install','applyHome'])test('transaction recovers '+failure+' failures in reverse ownership order',async()=>{
 const f=operations(failure);await assert.rejects(transaction('apply',f.ops),new RegExp(failure+' failed'));
 assert.deepEqual(f.calls.slice(-3),['restoreHome','restore','rolled-back']);
});
test('failed Home recovery prevents runtime replacement and leaves a recovery-needed journal',async()=>{
 const f=operations('applyHome','restoreHome');await assert.rejects(transaction('apply',f.ops),/recovery failed/);
 assert.equal(f.calls.at(-1),'recovery-needed');assert.ok(!f.calls.includes('restore'));
});
test('explicit rollback reports failures without claiming completion',async()=>{
 const f=operations('restore');await assert.rejects(transaction('rollback',f.ops),/restore failed/);
 assert.deepEqual(f.calls,['rolling-back','restoreHome','restore','recovery-needed']);
});
function lifecycle(options={}){
 let state={phase:'prepared',wasRunning:options.wasRunning!==false},starts=0;const calls=[];
 const worker={stop:async()=>{calls.push('stop');if(options.foreign)throw Error('foreign worker');},start:async()=>{
  calls.push('start');if(++starts===1&&options.failStart)throw Error('start failed');return {running:true,selected:true};
 }};
 const ops={load:()=>({...state}),save:value=>{state=value;calls.push(value.phase);},verifyBefore:()=>{calls.push('verify');if(options.concurrent)throw Error('concurrent edit');},
  run:action=>{calls.push(action);state.phase=action==='apply'?'runtime-installed':'rolled-back';
   if(action==='apply'&&options.crash){state.phase='applying';throw Error('child interrupted');}
   if(action==='rollback'&&options.failRollback){state.phase='recovery-needed';throw Error('rollback failed');}
  }};
 return {calls,worker,ops};
}
test('lifecycle declares installation only after starting the owned feed',async()=>{
 const f=lifecycle();await manage('apply',f.worker,f.ops);assert.deepEqual(f.calls,['stop','apply','start','installed']);
});
test('failed new feed startup rolls back before restarting the previous worker',async()=>{
 const f=lifecycle({failStart:true});await assert.rejects(manage('apply',f.worker,f.ops),/start failed/);
 assert.deepEqual(f.calls,['stop','apply','start','stop','rollback','verify','start']);
});
test('a previously stopped worker stays stopped after failed installation',async()=>{
 const f=lifecycle({failStart:true,wasRunning:false});await assert.rejects(manage('apply',f.worker,f.ops),/start failed/);
 assert.deepEqual(f.calls,['stop','apply','start','stop','rollback']);
});
test('interrupted child transactions recover without starting a mixed runtime',async()=>{
 const f=lifecycle({crash:true});await assert.rejects(manage('apply',f.worker,f.ops),/child interrupted/);
 assert.deepEqual(f.calls,['stop','apply','stop','rollback','verify','start']);
});
test('failed recovery and concurrent changes prevent feed restart',async()=>{
 for(const options of [{crash:true,failRollback:true},{crash:true,concurrent:true}]){
  const f=lifecycle(options);await assert.rejects(manage('apply',f.worker,f.ops),/rollback failed|concurrent edit/);assert.ok(!f.calls.includes('start'));
 }
});
test('foreign workers are never stopped through the release transaction',async()=>{
 const f=lifecycle({foreign:true});await assert.rejects(manage('apply',f.worker,f.ops),/foreign worker/);assert.deepEqual(f.calls,['stop']);
});
test('explicit rollback preserves a previously stopped feed',async()=>{
 const f=lifecycle({wasRunning:false});await manage('rollback',f.worker,f.ops);assert.deepEqual(f.calls,['stop','rollback']);
});
