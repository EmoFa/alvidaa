'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),cp=require('node:child_process');
const {validate,apply,restore}=require('./native-web-boot.cjs');
const {archive,postinst,PACKAGE}=require('./retire-native-bridge.cjs');
const {NativeHome}=require('./native-home.cjs');
const {APP,hash}=require('./native-trial.cjs');
function fixturePackage(payload='root payload'){
 return cp.execFileSync('python3',['-c',`import io,tarfile,sys
s=b'#!/bin/sh\\necho root-start\\n  echo "--- native Home: no extra launcher server ---"\\n  echo "--- step: phone home ---"\\necho root-end\\n'
b=io.BytesIO()
with tarfile.open(fileobj=b,mode='w:gz') as t:
 for name,data in [('control',b'Package: fixture\\n'),('postinst',s)]:
  i=tarfile.TarInfo('./'+name);i.mode=0o755;i.size=len(data);t.addfile(i,io.BytesIO(data))
out=bytearray(b'!<arch>\\n')
for name,data in [('debian-binary',b'2.0\\n'),('control.tar.gz',b.getvalue()),('data.tar.gz',sys.argv[1].encode())]:
 h=(name+'/').ljust(16)+'0'.ljust(12)+'0'.ljust(6)+'0'.ljust(6)+'100644'.ljust(8)+str(len(data)).ljust(10)+'\x60\\n'
 out.extend(h.encode()+data+(b'\\n' if len(data)%2 else b''))
sys.stdout.buffer.write(out)`,payload]);
}
function patch(bytes,remove=false){
 return cp.execFileSync('python3',['-c','import importlib.util,sys; s=importlib.util.spec_from_file_location("p",sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); sys.stdout.buffer.write(m.patch(sys.stdin.buffer.read(),sys.argv[2]=="remove"))',path.join(__dirname,'patch-native-feed-bootstrap.py'),remove?'remove':'install'],{input:bytes});
}
function setup(t){
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'fmtv-boot-test-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const home=new NativeHome({root});fs.mkdirSync(home.state,{recursive:true});
 for(const file of [APP,PACKAGE])fs.mkdirSync(path.dirname(home.p(file)),{recursive:true});
 fs.writeFileSync(home.p(APP),'ALVIDAA_FREE_MY_TV_WEB_PARITY_V2');
 home.save({phase:'installed',files:[{file:APP,trial:hash(fs.readFileSync(home.p(APP)))}]});
 const before=fixturePackage(),after=patch(before),candidate=path.join(root,'candidate.ipk');
 fs.writeFileSync(home.p(PACKAGE),before,{mode:0o640});fs.writeFileSync(candidate,after);
 return {home,before,after,candidate};
}
test('feed fragment is reversible and cannot change the root payload',()=>{
 const before=fixturePackage(),after=patch(before);validate(before,after);
 assert.deepEqual(archive(before)['data.tar.gz'],archive(after)['data.tar.gz']);
 const reverted=patch(after,true);assert.equal(postinst(archive(reverted)['control.tar.gz']),postinst(archive(before)['control.tar.gz']));
 assert.throws(()=>validate(before,patch(fixturePackage('changed root payload'))),/Root payload/);
});
test('bootstrap installation retains a private original and restores exact bytes and mode',t=>{
 const f=setup(t);assert.equal(apply(f.home,f.candidate,hash(f.before)),'installed');
 assert.deepEqual(fs.readFileSync(f.home.p(PACKAGE)),f.after);
 assert.equal(fs.statSync(path.join(f.home.state,'web-feed-boot/installer.orig')).mode&0o777,0o600);
 assert.equal(restore(f.home),'restored');assert.deepEqual(fs.readFileSync(f.home.p(PACKAGE)),f.before);
 assert.equal(fs.statSync(f.home.p(PACKAGE)).mode&0o777,0o640);assert.equal(restore(f.home),'restored');
 assert.equal(apply(f.home,f.candidate,hash(f.before)),'installed');
 assert.equal(apply(f.home,f.candidate,hash(f.after)),'installed');
 assert.deepEqual(fs.readFileSync(path.join(f.home.state,'web-feed-boot/installer.orig')),f.before);
});
test('stale hashes and concurrent edits never get overwritten',t=>{
 const f=setup(t);assert.throws(()=>apply(f.home,f.candidate,'wrong'),/Bootstrap changed/);
 assert.equal(fs.existsSync(path.join(f.home.state,'web-feed-boot')),false);
 apply(f.home,f.candidate,hash(f.before));fs.writeFileSync(f.home.p(PACKAGE),'another session');
 assert.throws(()=>restore(f.home),/concurrently/);assert.equal(fs.readFileSync(f.home.p(PACKAGE),'utf8'),'another session');
});
test('invalid recovery journal is rejected without touching the installer',t=>{
 const f=setup(t);apply(f.home,f.candidate,hash(f.before));fs.writeFileSync(path.join(f.home.state,'web-feed-boot/state.json'),'{');
 assert.throws(()=>restore(f.home),/recovery journal/);assert.deepEqual(fs.readFileSync(f.home.p(PACKAGE)),f.after);
});
