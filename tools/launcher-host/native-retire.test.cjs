'use strict';
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),zlib=require('node:zlib'),cp=require('node:child_process');
const test=require('node:test'),assert=require('node:assert/strict');
const {NativeHome}=require('./native-home.cjs');
const {APP,hash}=require('./native-trial.cjs');
const {retire,restore,validatePatch,archive,postinst,PACKAGE,RUNTIMES}=require('./retire-native-bridge.cjs');
function tarFile(name,body){
  body=Buffer.from(body);const h=Buffer.alloc(512);h.write(name);h.write('0000755\0',100);h.write('0000000\0',108);h.write('0000000\0',116);
  h.write(body.length.toString(8).padStart(11,'0')+'\0',124);h.write('00000000000\0',136);h.fill(32,148,156);h[156]=48;h.write('ustar\0',257);h.write('00',263);
  const sum=h.reduce((a,b)=>a+b,0);h.write(sum.toString(8).padStart(6,'0')+'\0 ',148);
  return Buffer.concat([h,body,Buffer.alloc((512-body.length%512)%512)]);
}
function ipk(data='ROOT PAYLOAD',script){
  script=script||'#!/bin/sh\necho root-start\n  echo "--- step: launcher host ---"\necho /var/local/alvidaa/alvidaa-bridge\necho /APPS/launcher/server.js\n  echo "--- step: phone home ---"\necho root-end\n';
  const control=zlib.gzipSync(Buffer.concat([tarFile('./control','Package: fixture\n'),tarFile('./postinst',script),Buffer.alloc(1024)]));
  const parts=[Buffer.from('!<arch>\n')];
  for(const [name,body] of [['debian-binary',Buffer.from('2.0\n')],['control.tar.gz',control],['data.tar.gz',Buffer.from(data)]]){
    const h=(name+'/').padEnd(16)+'0'.padEnd(12)+'0'.padEnd(6)+'0'.padEnd(6)+'100644'.padEnd(8)+String(body.length).padEnd(10)+'`\n';
    assert.equal(h.length,60);parts.push(Buffer.from(h),body);if(body.length%2)parts.push(Buffer.from('\n'));
  }
  return Buffer.concat(parts);
}
function patch(data){
  const script='import importlib.util,sys\nspec=importlib.util.spec_from_file_location("patch",sys.argv[1])\nm=importlib.util.module_from_spec(spec)\nspec.loader.exec_module(m)\nsys.stdout.buffer.write(m.patch(sys.stdin.buffer.read()))';
  return cp.execFileSync('python3',['-c',script,path.join(__dirname,'patch-native-bootstrap.py')],{input:data});
}
function setup(t){
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'native-retire-test-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const home=new NativeHome({root});fs.mkdirSync(home.state,{recursive:true});
  function write(file,data){fs.mkdirSync(path.dirname(home.p(file)),{recursive:true});fs.writeFileSync(home.p(file),data,{mode:0o755});}
  write(APP,'/* ALVIDAA_FREE_MY_TV_NATIVE_V1 */');home.save({phase:'installed',files:[{file:APP,trial:hash(fs.readFileSync(home.p(APP)))}]});
  const before=ipk(),after=patch(before);write(PACKAGE,before);RUNTIMES.forEach(file=>write(file,'old runtime '+file));write('/patched.ipk',after);
  return {home,write,before,after,candidate:home.p('/patched.ipk')};
}
test('bootstrap patch changes only launcher block and preserves root payload',()=>{
  const before=ipk(),after=patch(before);validatePatch(before,after);
  assert.ok(archive(before)['data.tar.gz'].equals(archive(after)['data.tar.gz']));
  const script=postinst(archive(after)['control.tar.gz']);assert.match(script,/root-start/);assert.match(script,/root-end/);assert.doesNotMatch(script,/alvidaa-bridge|server.js/);
  assert.throws(()=>validatePatch(before,patch(ipk('DIFFERENT ROOT PAYLOAD'))),/root payload changed/);
});
test('retirement archives both runtimes, patches boot and restores exactly',t=>{
  const f=setup(t);let checks=0;
  assert.equal(retire(f.home,f.candidate,hash(f.before),()=>checks++),'retired');assert.equal(checks,1);
  RUNTIMES.forEach(file=>assert.ok(!fs.existsSync(f.home.p(file))));
  assert.deepEqual(fs.readFileSync(f.home.p(PACKAGE)),f.after);
  assert.equal(restore(f.home),'restored');assert.deepEqual(fs.readFileSync(f.home.p(PACKAGE)),f.before);
  RUNTIMES.forEach(file=>{assert.equal(fs.readFileSync(f.home.p(file),'utf8'),'old runtime '+file);assert.equal(fs.statSync(f.home.p(file)).mode&0o777,0o755);});
});
test('retirement refuses changed installer and restore refuses another session edits',t=>{
  const f=setup(t);assert.throws(()=>retire(f.home,f.candidate,'wrong',()=>{}),/installer changed/);
  retire(f.home,f.candidate,hash(f.before),()=>{});f.write(RUNTIMES[0],'other agent');
  assert.throws(()=>restore(f.home),/concurrent retirement edit/);assert.equal(fs.readFileSync(f.home.p(RUNTIMES[0]),'utf8'),'other agent');
});
test('partial runtime removal failure restores package and prior runtime files',t=>{
  const f=setup(t),unlink=fs.unlinkSync;
  t.mock.method(fs,'unlinkSync',file=>{if(file===f.home.p(RUNTIMES[1]))throw new Error('injected unlink error');return unlink(file);});
  assert.throws(()=>retire(f.home,f.candidate,hash(f.before),()=>{}),/injected unlink/);
  assert.deepEqual(fs.readFileSync(f.home.p(PACKAGE)),f.before);
  RUNTIMES.forEach(file=>assert.ok(fs.existsSync(f.home.p(file))));
});
