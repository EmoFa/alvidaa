#!/usr/bin/env node
'use strict';
// Upgrade an already configured native-web TV. Bootstrap/root provisioning is
// deliberately separate; this controller never installs firmware or credentials.
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),assert=require('node:assert/strict');
const {NativeHome,perform,acquire}=require('./native-home.cjs');
const {APP,hash,atomicWrite}=require('./native-trial.cjs');
const {stageUpdate,rollbackUpdate}=require('./native-update.cjs');
const {captureContext,restartEngine,vendorOps}=require('./stock-ui-restart.cjs');
const {service}=require('./native-web-service.cjs');
const boot=require('./native-web-boot.cjs');
const REVISION='f2d984c51edca1544e39f2d44cdf86b75b0b6703';
const RUNTIME='/var/local/alvidaa/native-web-v3';
const ASSETS='/APPS/channelA/hisenseUI/var/local/free-my-tv/assets';
const CONTROL=['native-web-release.cjs','native-home.cjs','native-trial.cjs','native-update.cjs','stock-ui-restart.cjs','native-web-service.cjs','native-web-boot.cjs','native-feed-boot.sh','retire-native-bridge.cjs'];
const REQUIRED=[...CONTROL,'native-feed-worker.cjs','native-feed-engine.cjs','native-feed-http.cjs','native-feed-images.cjs','native-web-program.cjs','native-web-locale.cjs','native-image','candidate.js','third-party/free-my-tv/LICENSE','third-party/free-my-tv/upstream/MANIFEST.json'];
const privateMode={uid:process.getuid(),gid:process.getgid(),mode:0o600};
function relative(name){
 assert.ok(typeof name==='string'&&/^[a-zA-Z0-9_./-]+$/.test(name)&&!name.startsWith('/')&&
  name.split('/').every(part=>part&&part!=='.'&&part!=='..'),'Unsafe release path');return name;
}
function file(root,name,missing=false){
 const parts=relative(name).split('/');let current=path.resolve(root);
 assert.ok(fs.lstatSync(current).isDirectory(),'Expected a real release directory');
 for(let i=0;i<parts.length;i++){
  current=path.join(current,parts[i]);let st;
  try{st=fs.lstatSync(current);}catch(error){if(missing&&error.code==='ENOENT')return current+parts.slice(i+1).map(x=>path.sep+x).join('');throw error;}
  assert.ok(!st.isSymbolicLink(),'Release symlink refused');
  assert.ok(i===parts.length-1?st.isFile():st.isDirectory(),'Unexpected release entry');
 }
 return current;
}
function read(fileName,max=64*1024*1024){
 const st=fs.lstatSync(fileName);assert.ok(st.isFile()&&!st.isSymbolicLink()&&st.size<=max,'Invalid or oversized release file');return fs.readFileSync(fileName);
}
function json(fileName){
 const bytes=read(fileName,2*1024*1024);
 try{return JSON.parse(bytes);}catch{throw new Error('Invalid release JSON: '+path.basename(fileName));}
}
function verify(directory){
 directory=path.resolve(directory);
 for(const entry of [directory,file(directory,'RELEASE.json')]){
  const st=fs.lstatSync(entry);assert.ok(st.uid===process.getuid()&&(st.mode&0o022)===0,'Release ownership/permissions changed');
 }
 const manifest=json(file(directory,'RELEASE.json'));
 assert.equal(manifest.version,1);assert.equal(manifest.upstream,REVISION);
 assert.match(manifest.assetId,/^[a-f0-9]{20}$/);assert.match(manifest.candidate,/^[a-f0-9]{64}$/);
 assert.ok(manifest.files&&Object.keys(manifest.files).length<=10000,'Invalid release inventory');
 let total=0;
 for(const [name,entry]of Object.entries(manifest.files)){
  relative(name);
  assert.ok(/^runtime\/(?:[a-z0-9-]+\.(?:cjs|sh)|candidate\.js|native-image)$/.test(name)||
   /^runtime\/third-party\/free-my-tv\//.test(name)||name.startsWith('assets/'+manifest.assetId+'/'),'Unexpected release member');
  assert.match(entry.sha256,/^[a-f0-9]{64}$/);assert.ok(Number.isSafeInteger(entry.size)&&entry.size>=0&&entry.size<=64*1024*1024);
  total+=entry.size;assert.ok(total<=256*1024*1024,'Release exceeds safety bound');
  const source=file(directory,name),st=fs.lstatSync(source);
  assert.ok(st.uid===process.getuid()&&(st.mode&0o022)===0,'Release member ownership/permissions changed');
  const bytes=read(source);assert.equal(bytes.length,entry.size,'Release size mismatch: '+name);
  assert.equal(hash(bytes),entry.sha256,'Release hash mismatch: '+name);
 }
 for(const name of REQUIRED)assert.ok(manifest.files['runtime/'+name],'Missing runtime member: '+name);
 const pinned=json(file(directory,'runtime/third-party/free-my-tv/upstream/MANIFEST.json'));assert.equal(pinned.revision,REVISION);
 for(const [name,digest]of Object.entries(pinned.files)){
  relative(name);assert.equal(manifest.files['runtime/third-party/free-my-tv/upstream/'+name]?.sha256,digest,'Incomplete pinned source: '+name);
 }
 assert.ok(Object.keys(manifest.files).filter(n=>n.startsWith('runtime/')).length<=1000,'Too many runtime members');
 assert.ok(manifest.files['assets/'+manifest.assetId+'/assets.json'],'Missing asset manifest');
 const candidate=read(file(directory,'runtime/candidate.js'));
 new (require('node:vm').Script)(candidate.toString('utf8'),{filename:'release candidate'});
 assert.equal(hash(candidate),manifest.candidate);assert.ok(candidate.includes('ALVIDAA_FREE_MY_TV_WEB_PARITY_V2'),'Not a web Home');
 const assets=read(file(directory,'assets/'+manifest.assetId+'/assets.json'));
 assert.equal(hash(assets).slice(0,20),manifest.assetId,'Asset identity mismatch');
 const assetManifest=json(file(directory,'assets/'+manifest.assetId+'/assets.json'));assert.equal(assetManifest.upstream,REVISION);
 for(const [name,digest]of Object.entries(assetManifest.files)){
  relative(name);assert.ok(['fonts.css','OFL.txt','LICENSE-material-symbols.txt'].includes(name)||/^fonts\/[a-zA-Z0-9_.-]+\.ttf$/.test(name)||/^symbols\/[a-zA-Z0-9_.-]+\.png$/.test(name),'Unexpected public asset');
  assert.equal(manifest.files['assets/'+manifest.assetId+'/'+name]?.sha256,digest,'Incomplete public assets: '+name);
 }
 for(const name of Object.keys(manifest.files).filter(n=>n.startsWith('assets/'))){
  const member=name.slice(('assets/'+manifest.assetId+'/').length);
  assert.ok(member==='assets.json'||Object.hasOwn(assetManifest.files,member),'Unlisted public asset');
 }
 const binary=read(file(directory,'runtime/native-image'));
 assert.ok(binary.length>=20&&binary.subarray(0,6).equals(Buffer.from([127,69,76,70,1,1]))&&binary.readUInt16LE(18)===40,'Expected ARM32 helper');
 return {directory,manifest,total};
}
function save(directory,plan){atomicWrite(path.join(directory,'state.json'),JSON.stringify(plan),privateMode);}
function load(directory){
 assert.ok(path.isAbsolute(directory)&&directory.startsWith('/var/local/alvidaa/native-home/web-releases/release-'),'Unexpected recovery directory');
 const state=file(directory,'state.json'),st=fs.lstatSync(state);
 assert.ok(st.uid===process.getuid()&&(st.mode&0o077)===0,'Recovery journal must remain operator-private');
 const plan=json(state);assert.equal(plan.version,1);assert.equal(plan.runtime,RUNTIME);
 assert.ok(['prepared','applying','runtime-installed','installed','rolling-back','rolled-back','recovery-needed'].includes(plan.phase),'Invalid recovery phase');
 assert.equal(typeof plan.wasRunning,'boolean');assert.ok(path.isAbsolute(plan.stage));assert.match(plan.manifestHash,/^[a-f0-9]{64}$/);
 assert.match(plan.helperHash,/^[a-f0-9]{64}$/);
 for(const name of CONTROL)assert.match(plan.control[name],/^[a-f0-9]{64}$/);
 assert.match(plan.beforeHome,/^[a-f0-9]{64}$/);assert.match(plan.afterHome,/^[a-f0-9]{64}$/);
 assert.ok(Array.isArray(plan.files)&&plan.files.length<=1000,'Invalid recovery inventory');
 for(const entry of plan.files){relative(entry.name);assert.match(entry.after,/^[a-f0-9]{64}$/);if(entry.before!==null){assert.match(entry.before,/^[a-f0-9]{64}$/);assert.ok(['uid','gid','mode'].every(k=>Number.isSafeInteger(entry[k])&&entry[k]>=0));}}
 return plan;
}
function inspect(root,entries,side){
 for(const entry of entries){
  const target=file(root,entry.name,true);let actual=null;
  try{actual=hash(read(target));}catch(error){if(error.code!=='ENOENT')throw error;}
  assert.ok(side==='either'?actual===entry.before||actual===entry.after:actual===entry[side],'Concurrent runtime edit: '+entry.name);
 }
}
function restoreFiles(directory,plan){
 inspect(plan.runtime,plan.files,'either');
 for(const entry of plan.files){
  const target=file(plan.runtime,entry.name,true);
  if(entry.before===null){if(fs.existsSync(target)){assert.equal(hash(read(target)),entry.after);fs.unlinkSync(target);}continue;}
  const bytes=read(file(directory,'before/'+entry.name));assert.equal(hash(bytes),entry.before,'Recovery backup changed');
  atomicWrite(target,bytes,entry);
 }
}
function verifyShared(home){
 for(const [name,digest]of Object.entries(home.hashes))if(name!==APP)assert.equal(hash(read(home.p(name))),digest,'Shared firmware changed: '+name);
}
function prepare(directory,expected,home,worker){
 verifyShared(home);
 const release=verify(directory),{manifest}=release;
 assert.match(expected,/^[a-f0-9]{64}$/);assert.equal(hash(read(home.p(APP))),expected,'Home changed since inspection');
 assert.equal(home.load().phase,'installed','An installed native Home is required');
 assert.ok(!home.load().update,'Recover the pending Home update first');
 const bootState=json(path.join(home.state,'web-feed-boot/state.json'));
 assert.equal(bootState.phase,'installed','Configure the existing feed boot hook before using release upgrades');
 assert.equal(hash(read(home.p('/APPS/installer.ipk'))),bootState.updated,'Boot hook changed');
 assert.ok(!directory.startsWith(RUNTIME+path.sep)&&directory!==RUNTIME,'Stage outside the live runtime');
 const owner=fs.lstatSync(directory);assert.ok(owner.uid===process.getuid()&&(owner.mode&0o022)===0,'Stage must belong to the operator and not be writable by others');
 const running=worker.status();assert.ok(!running.conflict,'Unrelated worker PID record');
 const parent=path.join(home.state,'web-releases');fs.mkdirSync(parent,{recursive:true,mode:0o700});
 const journal=fs.mkdtempSync(path.join(parent,'release-'));fs.chmodSync(journal,0o700);
 const plan={version:1,phase:'prepared',runtime:RUNTIME,stage:directory,manifestHash:hash(read(file(directory,'RELEASE.json'))),
  beforeState:hash(read(path.join(home.state,'state.json'))),beforeStateObject:hash(JSON.stringify(home.load())),
  beforeHome:expected,afterHome:manifest.candidate,wasRunning:running.running,files:[]};
 let budget=release.total;
 for(const name of Object.keys(manifest.files).filter(name=>name.startsWith('runtime/'))){
  const relativeName=name.slice(8),target=file(RUNTIME,relativeName,true),entry={name:relativeName,after:manifest.files[name].sha256,before:null};
  if(fs.existsSync(target)){
   const st=fs.lstatSync(target);assert.ok(st.uid===process.getuid()&&(st.mode&0o022)===0,'Runtime ownership changed');
   const bytes=read(target);Object.assign(entry,{before:hash(bytes),uid:st.uid,gid:st.gid,mode:st.mode});budget+=bytes.length;
  }
  plan.files.push(entry);
 }
 for(const root of [journal,ASSETS]){const space=fs.statfsSync(root);assert.ok(space.bavail*space.bsize>=budget+64*1024*1024,'Insufficient release headroom');}
 for(const entry of plan.files)if(entry.before!==null){
  const target=path.join(journal,'before',entry.name);fs.mkdirSync(path.dirname(target),{recursive:true,mode:0o700});
  const bytes=read(file(RUNTIME,entry.name));assert.equal(hash(bytes),entry.before);atomicWrite(target,bytes,privateMode);
 }
 const previous=read(home.p(APP));assert.equal(hash(previous),expected,'Home changed while preparing recovery');
 atomicWrite(path.join(journal,'previous-home.js'),previous,privateMode);
 fs.mkdirSync(path.join(journal,'control'),{mode:0o700});plan.control={};
 for(const name of CONTROL){
  const bytes=read(file(directory,'runtime/'+name));plan.control[name]=manifest.files['runtime/'+name].sha256;
  assert.equal(hash(bytes),plan.control[name],'Recovery controller changed');atomicWrite(path.join(journal,'control',name),bytes,privateMode);
 }
 const helper=read(file(directory,'runtime/native-image'));plan.helperHash=manifest.files['runtime/native-image'].sha256;
 assert.equal(hash(helper),plan.helperHash,'Recovery helper changed');atomicWrite(path.join(journal,'lock-helper'),helper,{...privateMode,mode:0o755});
 save(journal,plan);return journal;
}
function installFiles(plan){
 assert.equal(hash(read(file(plan.stage,'RELEASE.json'))),plan.manifestHash,'Release manifest changed');
 const {manifest}=verify(plan.stage);inspect(plan.runtime,plan.files,'before');
 // Content-addressed assets are never overwritten or removed during rollback.
 for(const [name,entry]of Object.entries(manifest.files))if(name.startsWith('assets/')){
  const relativeName=name.slice(7),target=file(ASSETS,relativeName,true);
  if(fs.existsSync(target)){assert.equal(hash(read(target)),entry.sha256,'Existing public asset changed');continue;}
  fs.mkdirSync(path.dirname(target),{recursive:true,mode:0o755});
  atomicWrite(target,read(file(plan.stage,name)),{...privateMode,mode:0o644});
 }
 for(const entry of plan.files){
  const target=file(plan.runtime,entry.name,true);fs.mkdirSync(path.dirname(target),{recursive:true,mode:0o700});
  const bytes=read(file(plan.stage,'runtime/'+entry.name));assert.equal(hash(bytes),entry.after);
  atomicWrite(target,bytes,{...privateMode,mode:entry.name==='native-image'?0o755:0o600});
 }
}
async function transaction(action,ops){
 if(action==='apply'){
  ops.phase('applying');
  try{ops.install();await ops.applyHome();ops.phase('runtime-installed');}
  catch(error){
   try{await ops.restoreHome();ops.restore();ops.phase('rolled-back');}
   catch(recovery){ops.phase('recovery-needed');throw new Error(error.message+'; recovery failed: '+recovery.message);}
   throw error;
  }
 }else if(action==='rollback'){
  ops.phase('rolling-back');
  try{await ops.restoreHome();ops.restore();ops.phase('rolled-back');}
  catch(error){ops.phase('recovery-needed');throw error;}
 }else throw new Error('Unknown release transaction');
}
function ownsPendingUpdate(plan,update){
 return update.beforeHash===plan.beforeStateObject&&update.candidateHash===plan.afterHome||
  typeof plan.restoreBeforeState==='string'&&update.beforeHash===plan.restoreBeforeState&&update.candidateHash===plan.beforeHome;
}
function assertWorkerLock(worker){
 const fd=Number(process.env.ALVIDAA_NATIVE_FEED_LOCK_FD);
 assert.equal(process.env.ALVIDAA_NATIVE_FEED_LOCK_PATH,worker.config.lock,'Worker lock required');
 assert.ok(Number.isSafeInteger(fd)&&fd>2,'Inherited lock descriptor required');
 const held=fs.fstatSync(fd),lock=fs.statSync(worker.config.lock);assert.ok(held.dev===lock.dev&&held.ino===lock.ino,'Wrong inherited lock');
}
async function commit(action,directory){
 const plan=load(directory),worker=service({release:RUNTIME});assertWorkerLock(worker);
 if(action==='apply')assert.equal(plan.phase,'prepared','Release is already applied or needs recovery');
 const home=new NativeHome(),release=acquire(home.state);
 try{
  const current=hash(read(home.p(APP)));assert.ok(current===plan.beforeHome||current===plan.afterHome,'Concurrent Home edit');
  if(action==='apply'){
   assert.equal(hash(read(path.join(home.state,'state.json'))),plan.beforeState,'Concurrent Home controller operation');
   assert.ok(home.load().phase==='installed'&&!home.load().update,'Another Home operation is pending');
  }else if(['installed','runtime-installed'].includes(plan.phase)){
   assert.equal(hash(read(path.join(home.state,'state.json'))),plan.afterState,'Home state changed after release installation');
  }
  const context=home.engines().length?captureContext():json(path.join(home.state,'context.json'));
  atomicWrite(path.join(home.state,'context.json'),JSON.stringify(context),privateMode);
  async function restoreHome(){
   if(home.load().update){
    assert.ok(ownsPendingUpdate(plan,home.load().update),'Another Home update needs recovery');
    const engine=await restartEngine(vendorOps(context,()=>rollbackUpdate(home)));
    const state=home.load();state.enginePid=engine.pid;home.save(state);
   }
   if(hash(read(home.p(APP)))===plan.beforeHome){
    if(!home.engines().length){const engine=await restartEngine(vendorOps(context));const state=home.load();state.enginePid=engine.pid;home.save(state);}
    return;
   }
   const previous=file(directory,'previous-home.js');assert.equal(hash(read(previous)),plan.beforeHome);
   // Record ownership before staging, so an interrupted rollback is itself recoverable.
   plan.restoreBeforeState=hash(JSON.stringify(home.load()));save(directory,plan);
   stageUpdate(home,previous);await perform(home,context,'update');
  }
  await transaction(action,{phase:phase=>{plan.phase=phase;save(directory,plan);},
   install:()=>installFiles(plan),applyHome:async()=>{stageUpdate(home,file(plan.stage,'runtime/candidate.js'));await perform(home,context,'update');plan.afterState=hash(read(path.join(home.state,'state.json')));},
   restoreHome,restore:()=>restoreFiles(directory,plan)});
 }finally{release();}
}
function child(action,directory){
 const plan=load(directory);assert.equal(hash(read(file(directory,'lock-helper'))),plan.helperHash,'Recovery helper changed');
 for(const name of CONTROL)assert.equal(hash(read(file(directory,'control/'+name))),plan.control[name],'Recovery controller changed');
 const worker=service({release:RUNTIME}),result=cp.spawnSync(path.join(directory,'lock-helper'),
  ['lock-run',worker.config.lock,process.execPath,path.join(directory,'control/native-web-release.cjs'),'commit',action,directory],
  {stdio:'inherit',env:{...process.env,LD_LIBRARY_PATH:'/lib:/usr/local/lib:/basic/lib'}});
 if(result.error)throw result.error;assert.equal(result.status,0,'Release transaction failed; retain its journal');
}
async function uninstall(expectedHome,expectedBoot){
 const worker=service({release:RUNTIME});assertWorkerLock(worker);
 const home=new NativeHome(),release=acquire(home.state);
 try{
  assert.equal(hash(read(home.p(APP))),expectedHome,'Concurrent Home edit');
  assert.equal(hash(read(home.p('/APPS/installer.ipk'))),expectedBoot,'Concurrent bootstrap edit');
  verifyShared(home);
  const state=home.load();assert.ok(['installed','restored'].includes(state.phase)&&!state.update,'Recover pending Home work first');
  const entry=state.files.find(item=>item.file===APP);
  assert.equal(expectedHome,state.phase==='installed'?entry.trial:entry.original,'Home is not owned by the controller');
  // Root/SSH provisioning remains in place; only the owned feed hook is undone.
  if(state.phase==='restored'){home.restore();boot.restore(home);return;}
  const context=home.engines().length?captureContext():json(path.join(home.state,'context.json'));
  atomicWrite(path.join(home.state,'context.json'),JSON.stringify(context),privateMode);
  boot.restore(home);await perform(home,context,'restore');
 }finally{release();}
}
async function manage(action,worker,ops){
 await worker.stop();
 try{
  ops.run(action);
  const plan=ops.load();
  if(action==='apply'||plan.wasRunning){
   const started=await worker.start();assert.ok(started.running&&started.selected,'The expected web feed did not start');
  }
  if(action==='apply'){plan.phase='installed';ops.save(plan);}
 }catch(error){
  const plan=ops.load();
  if(action==='apply'&&['applying','runtime-installed','recovery-needed'].includes(plan.phase)){
   await worker.stop();ops.run('rollback');
  }
  const recovered=ops.load();
  if(recovered.wasRunning&&['prepared','rolled-back'].includes(recovered.phase)){
   ops.verifyBefore(recovered);await worker.start();
  }
  throw error;
 }
}
async function main(){
 const [action,arg,expected]=process.argv.slice(2);
 if(action==='verify'){const r=verify(arg);console.log(JSON.stringify({candidate:r.manifest.candidate,assetId:r.manifest.assetId,files:Object.keys(r.manifest.files).length}));return;}
 assert.equal(process.getuid(),0,'Root-local control required');
 if(action==='commit'){await commit(arg,expected);return;}
 if(action==='uninstall-worker'){await uninstall(arg,expected);return;}
 const home=new NativeHome(),worker=service({release:RUNTIME});let directory;
 if(action==='uninstall'){
  const homeHash=hash(read(home.p(APP))),bootHash=hash(read(home.p('/APPS/installer.ipk'))),before=worker.status();
  const helper=fs.lstatSync(worker.config.processor);
  assert.ok(helper.isFile()&&helper.uid===process.getuid()&&(helper.mode&0o022)===0,'Untrusted lock helper');
  await worker.stop();
  try{
   const result=cp.spawnSync(worker.config.processor,['lock-run',worker.config.lock,process.execPath,__filename,'uninstall-worker',homeHash,bootHash],
    {stdio:'inherit',env:{...process.env,LD_LIBRARY_PATH:'/lib:/usr/local/lib:/basic/lib'}});
   if(result.error)throw result.error;assert.equal(result.status,0,'Teardown failed; inspect the existing Home/boot journals');
  }catch(error){if(before.running&&hash(read(home.p(APP)))===homeHash)await worker.start();throw error;}
  console.log(JSON.stringify({phase:home.load().phase,worker:worker.status(),retained:'keys, origin storage, caches and recovery backups'}));return;
 }
 if(action==='apply'){
  const release=acquire(home.state);try{directory=prepare(path.resolve(arg),expected,home,worker);}finally{release();}
 }else if(action==='rollback'){directory=path.resolve(arg);load(directory);}
 else throw new Error('Usage: native-web-release.cjs verify stage | apply stage expected-home-sha256 | rollback journal | uninstall');
 console.log('Recovery journal: '+directory);
 await manage(action,worker,{run:operation=>child(operation,directory),load:()=>load(directory),save:plan=>save(directory,plan),
  verifyBefore:plan=>{inspect(plan.runtime,plan.files,'before');assert.equal(hash(read(home.p(APP))),plan.beforeHome,'Home needs manual recovery');}});
 console.log(JSON.stringify({phase:load(directory).phase,worker:worker.status()}));
}
if(require.main===module)main().then(()=>process.exit(0),error=>{console.error('Native web release: '+error.message);process.exit(1);});
module.exports={verify,relative,file,inspect,restoreFiles,transaction,manage,verifyShared,ownsPendingUpdate,CONTROL,REQUIRED};
