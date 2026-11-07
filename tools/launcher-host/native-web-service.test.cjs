'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {service,MARKER}=require('./native-web-service.cjs');
const helper=process.env.NATIVE_IMAGE_HELPER;
function fixture(t){
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'fmtv-service-'));
 const paths={worker:path.join(__dirname,'native-feed-worker.cjs'),processor:helper,phoenix:process.execPath,
  home:path.join(root,'app.js'),ipc:path.join(root,'ipc'),media:path.join(root,'media'),icons:path.join(root,'icons'),
  credentials:path.join(root,'server/keys/feed.json'),lock:path.join(root,'feed.flock'),log:path.join(root,'worker.log')};
 for(const dir of [paths.ipc,path.join(root,'vendor-cache'),path.dirname(paths.credentials)])fs.mkdirSync(dir,{recursive:true});
 // Match the TV's vendor-owned storeAppIcon symlink without changing it.
 fs.symlinkSync(path.join(root,'vendor-cache'),paths.icons,'dir');
 fs.writeFileSync(paths.home,MARKER);fs.writeFileSync(paths.credentials,JSON.stringify({tmdb_token:'eyJ.fixture-only'}),{mode:0o600});
 fs.writeFileSync(path.join(paths.ipc,'context.json'),JSON.stringify({version:1,apps:[],zone:'',prefs:'{"quotes":false,"weather":false}'}));
 const controller=service({paths});
 t.after(async()=>{if(controller.status().running)await controller.stop();fs.rmSync(root,{recursive:true,force:true});});
 return {paths,controller};
}
test('service starts idempotently, survives stale PID records, and stops only its group',{skip:!helper},async t=>{
 const {paths,controller}=fixture(t);
 fs.writeFileSync(paths.lock+'.pid','2147483647');
 const [first,second]=await Promise.all([controller.start(),controller.start()]);
 assert.ok(first.running);assert.equal(first.pid,second.pid);assert.equal(first.group,first.pid);
 assert.equal((await controller.start()).pid,first.pid);
 assert.equal((await controller.stop()).running,false);
 assert.equal(fs.existsSync(paths.lock+'.pid'),false);
});
test('restoring a non-web Home makes the worker exit without touching Home or its cached snapshot',{skip:!helper},async t=>{
 const {paths,controller}=fixture(t);
 await controller.start();await new Promise(resolve=>setTimeout(resolve,500));
 const snapshot=fs.readFileSync(path.join(paths.ipc,'snapshot.json'),'utf8');
 fs.writeFileSync(paths.home,'original stock fixture');
 for(let i=0;i<30&&controller.status().running;i++)await new Promise(resolve=>setTimeout(resolve,100));
 assert.equal(controller.status().running,false);assert.equal(controller.status().selected,false);
 assert.equal(fs.readFileSync(paths.home,'utf8'),'original stock fixture');
 assert.equal(fs.readFileSync(path.join(paths.ipc,'snapshot.json'),'utf8'),snapshot);
 assert.equal((await controller.start()).running,false);
 fs.writeFileSync(paths.home,MARKER);assert.equal((await controller.start()).running,true);
});
test('an unrelated live PID is never signalled',async t=>{
 const {paths,controller}=fixture(t);fs.writeFileSync(paths.lock+'.pid',String(process.pid));
 assert.equal(controller.status().conflict,true);
 await assert.rejects(controller.stop(),/unrelated/);await assert.rejects(controller.start(),/Another process/);
});
