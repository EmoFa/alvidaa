'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const {spawn,spawnSync}=require('node:child_process');
const {photoURL,download,createMedia}=require('./native-feed-images.cjs');
const {readToken,readJSON}=require('./native-feed-worker.cjs');
const processor=process.env.NATIVE_IMAGE_HELPER;
test('image URLs only permit fixed TMDB raster endpoints',async()=>{
 assert.equal(photoURL('/logo.svg','w500'),'https://image.tmdb.org/t/p/w500/logo.png');
 assert.equal(photoURL('/photo.jpg','w1280'),'https://image.tmdb.org/t/p/w1280/photo.jpg');
 for(const value of ['/../key.png','https://evil.test/x.png','/x.png?token=secret','/x%2f.png','//x.png'])assert.throws(()=>photoURL(value,'w500'));
 assert.equal(photoURL('/x.png','original'),'https://image.tmdb.org/t/p/original/x.png');
 assert.throws(()=>photoURL('/x.png','w42'));
 await assert.rejects(download('http://localhost:9009/service/hiutils'));
});
test('worker only reads bounded JSON and a mode-private server/keys token',t=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'fmtv-key-test-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const keys=path.join(dir,'server/keys');fs.mkdirSync(keys,{recursive:true});const file=path.join(keys,'feed.json');
 fs.writeFileSync(file,JSON.stringify({tmdb_token:'eyJ.fake-test-token'}),{mode:0o600});
 assert.equal(readToken(file),'eyJ.fake-test-token');assert.throws(()=>readJSON(file,1));
 fs.writeFileSync(file,JSON.stringify({tmdb_token:''}));assert.equal(readToken(file),'');
 fs.chmodSync(file,0o644);assert.throws(()=>readToken(file),/permissions/);
 const link=path.join(keys,'link.json');fs.symlinkSync(file,link);assert.throws(()=>readToken(link));
});
test('kernel lock survives Node exec, rejects a second owner, and releases on exit',{skip:!processor},async t=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'fmtv-lock-test-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const lock=path.join(dir,'worker.lock');
 const source="const fs=require('node:fs');const a=fs.fstatSync(+process.env.ALVIDAA_NATIVE_FEED_LOCK_FD),b=fs.statSync(process.env.ALVIDAA_NATIVE_FEED_LOCK_PATH);if(a.ino!==b.ino||a.dev!==b.dev)process.exit(2);console.log('locked');setInterval(()=>{},1000)";
 const child=spawn(processor,['lock-run',lock,process.execPath,'-e',source],{stdio:['ignore','pipe','pipe']});
 t.after(()=>{if(child.exitCode===null)child.kill();});
 await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('lock start timeout')),5000);child.stdout.once('data',()=>{clearTimeout(timer);resolve();});child.once('exit',()=>{clearTimeout(timer);reject(Error('lock owner exited early'));});});
 assert.equal(spawnSync(processor,['lock-run',lock,process.execPath,'-e','process.exit(0)']).status,1);
 child.kill();await new Promise(resolve=>child.once('exit',resolve));
 assert.equal(spawnSync(processor,['lock-run',lock,process.execPath,'-e','process.exit(0)']).status,0);
});
test('native image cache prepares local assets and repairs missing generated files',{skip:!processor},async t=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'fmtv-images-test-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const icons=path.join(dir,'icons');fs.mkdirSync(icons);
 // Public pinned PNG fixture, not device data or a credential-bearing response.
 const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=','base64');
 fs.writeFileSync(path.join(icons,'test.png'),png);
 let requests=0;const cache=createMedia({directory:path.join(dir,'media'),iconRoot:icons,processor,
  uriBase:'file:///hisenseUI/var/local/free-my-tv/media/',download:async()=>{requests++;return png;}});
 t.after(()=>cache.stop());
 const context={apps:[{icon:'file:///hisenseUI/var/local/storeAppIcon/test.png'}]};
 const data={'fmtv.recs':JSON.stringify({picks:[{backdrop:'/test.jpg'}]})};
 const first=await cache.update(context,data);
 assert.equal(first.imageFailures,0);assert.equal(requests,4);assert.equal(Object.keys(first.images).length,4);
 assert.ok(first.images['original:/test.jpg'],'screensaver original must be available locally');
 const photo=first.media[first.images['w1280:/test.jpg']];assert.equal(photo.width,1);assert.match(photo.src,/-raw\.png$/);
 fs.unlinkSync(path.join(dir,'media',path.basename(photo.thumb)));
 const second=await cache.update(context,data);assert.equal(second.imageFailures,0);assert.equal(requests,4);
 assert.ok(fs.existsSync(path.join(dir,'media',path.basename(photo.thumb))));
 cache.collect();
 // A changed helper must reprocess cached raw bytes without contacting TMDB.
 const upgradedProcessor=path.join(dir,'new-helper');
 fs.copyFileSync(processor,upgradedProcessor);fs.appendFileSync(upgradedProcessor,'\n');fs.chmodSync(upgradedProcessor,0o755);
 const upgraded=createMedia({directory:path.join(dir,'media'),iconRoot:icons,processor:upgradedProcessor,
  previousImages:second.images,uriBase:'file:///hisenseUI/var/local/free-my-tv/media/',download:async()=>{throw Error('Offline fixture');}});
 t.after(()=>upgraded.stop());
 const third=await upgraded.update(context,data);
 assert.equal(third.imageFailures,0);assert.notEqual(third.images['original:/test.jpg'],second.images['original:/test.jpg']);
 assert.equal(requests,4);
});
test('worker publishes locally, retains a good snapshot on broken IPC, and cleans its PID',{skip:!processor},async t=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'fmtv-worker-test-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const directory=path.join(dir,'public'),icons=path.join(dir,'icons'),keys=path.join(dir,'server/keys');
 for(const folder of [directory,icons,keys])fs.mkdirSync(folder,{recursive:true});
 const credentials=path.join(keys,'feed.json'),lock=path.join(dir,'worker.flock');
 fs.writeFileSync(credentials,JSON.stringify({tmdb_token:'eyJ.fake-test-token'}),{mode:0o600});
 // Unknown timezone blocks location-dependent requests; prices are disabled.
 fs.writeFileSync(path.join(directory,'context.json'),JSON.stringify({version:1,zone:'',apps:[],prefs:JSON.stringify({quotes:false,weather:false})}));
 const child=spawn(processor,['lock-run',lock,process.execPath,path.join(__dirname,'native-feed-worker.cjs'),directory,credentials,processor,icons],{stdio:'ignore'});
 t.after(()=>{if(child.exitCode===null)child.kill();});
 const file=path.join(directory,'snapshot.json');let snapshot;
 for(let i=0;i<60;i++){
  try{snapshot=JSON.parse(fs.readFileSync(file,'utf8'));break;}catch{await new Promise(resolve=>setTimeout(resolve,100));}
 }
 assert.ok(snapshot,'worker did not publish a snapshot');assert.equal(snapshot.version,1);assert.equal(snapshot.locationKnown,false);
 assert.equal(snapshot.workerPid,child.pid);assert.equal(fs.statSync(file).mode&0o777,0o644);
 assert.ok(!fs.readFileSync(file,'utf8').includes('eyJ.fake-test-token'));
 const before=fs.readFileSync(file,'utf8');fs.writeFileSync(path.join(directory,'context.json'),'{');
 await new Promise(resolve=>setTimeout(resolve,1200));assert.equal(fs.readFileSync(file,'utf8'),before);
 child.kill();await new Promise(resolve=>child.once('exit',resolve));assert.equal(fs.existsSync(lock+'.pid'),false);
});
