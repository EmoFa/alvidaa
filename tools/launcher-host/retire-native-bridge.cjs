#!/usr/bin/env node
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const assert = require('node:assert/strict');
const { NativeHome, acquire } = require('./native-home.cjs');
const { APP, hash, atomicWrite } = require('./native-trial.cjs');
const PACKAGE = '/APPS/installer.ipk';
const RUNTIMES = ['/var/local/alvidaa/alvidaa-bridge', '/APPS/launcher/server.js'];
function archive(data) {
  assert.equal(data.subarray(0,8).toString(), '!<arch>\n');
  const result = {};
  for (let offset=8; offset<data.length;) {
    const header=data.subarray(offset,offset+60), name=header.subarray(0,16).toString().trim().replace(/\/$/,'');
    const size=Number(header.subarray(48,58).toString().trim());
    assert.ok(header.length===60 && header.subarray(58).toString()==='`\n' && Number.isSafeInteger(size) && size>=0 && !result[name], 'bad ar archive');
    result[name]=data.subarray(offset+60,offset+60+size);
    assert.equal(result[name].length,size);offset+=60+size+size%2;
  }
  return result;
}
function controlFiles(compressed) {
  const data=zlib.gunzipSync(compressed), found={};
  for(let offset=0;offset+512<=data.length;){
    const header=data.subarray(offset,offset+512), name=header.subarray(0,100).toString().split('\0')[0];
    if(!name)break;
    const size=parseInt(header.subarray(124,136).toString().replace(/\0/g,'').trim(),8)||0;
    assert.ok(Number.isSafeInteger(size)&&size>=0&&offset+512+size<=data.length,'bad tar archive');
    const type=header[156],key=name.replace(/^\.\//,'');
    if(type!==120&&type!==103){
      assert.ok((type===0||type===48)&&!found[key],'unexpected control archive entry');
      found[key]={body:data.subarray(offset+512,offset+512+size),metadata:header.subarray(100,124).toString()};
    }
    offset+=512+Math.ceil(size/512)*512;
  }
  assert.ok(found.postinst,'missing postinst');return found;
}
function postinst(compressed){return controlFiles(compressed).postinst.body.toString();}
function validatePatch(before, after) {
  const old=archive(before), next=archive(after);
  assert.deepEqual(Object.keys(next),Object.keys(old),'IPK member layout changed');
  for(const key of Object.keys(old))if(key!=='control.tar.gz')assert.ok(old[key].equals(next[key]),'root payload changed');
  const oldControl=controlFiles(old['control.tar.gz']),nextControl=controlFiles(next['control.tar.gz']);
  assert.deepEqual(Object.keys(nextControl),Object.keys(oldControl),'control member layout changed');
  for(const key of Object.keys(oldControl)){
    assert.equal(nextControl[key].metadata,oldControl[key].metadata,'control permissions changed');
    if(key!=='postinst')assert.ok(nextControl[key].body.equals(oldControl[key].body),'package metadata changed');
  }
  const source=postinst(old['control.tar.gz']);
  const start='echo "--- step: launcher host ---"',end='echo "--- step: phone home ---"';
  const a=source.indexOf(start),b=source.indexOf(end);
  assert.ok(a>=0&&b>a&&source.lastIndexOf(start)===a&&source.lastIndexOf(end)===b,'unknown bootstrap revision');
  const block=source.slice(a,b);RUNTIMES.forEach(file=>assert.ok(block.includes(file),'missing launcher runtime path'));
  const expected=source.slice(0,a)+'echo "--- native Home: no extra launcher server ---"\n  '+source.slice(b);
  assert.equal(postinst(next['control.tar.gz']),expected,'unexpected root bootstrap edits');
}
function json(file) {
  try{return JSON.parse(fs.readFileSync(file,'utf8'));}
  catch(error){throw new Error('Cannot read retirement manifest: '+error.message);}
}
function ready() {
  const tcp=fs.readFileSync('/proc/net/tcp','utf8').split('\n').map(line=>line.trim().split(/\s+/));
  assert.ok(tcp.some(row=>row[3]==='0A'&&row[1].endsWith(':1F48')),'root SSH must be listening');
  assert.ok(!tcp.some(row=>row[3]==='0A'&&row[1].endsWith(':2242')),'stop and validate without the bridge first');
}
function save(dir,m) {atomicWrite(path.join(dir,'state.json'),JSON.stringify(m,null,2),{uid:process.getuid(),gid:process.getgid(),mode:0o600});}
function restore(home) {
  const dir=path.join(home.state,'retired-bridge'),m=json(path.join(dir,'state.json'));
  for(const e of m.files){
    assert.equal(hash(fs.readFileSync(e.backup)),e.original,'retirement backup corrupt');
    const target=home.p(e.file);
    if(fs.existsSync(target)){
      const st=fs.lstatSync(target);assert.ok(st.isFile()&&!st.isSymbolicLink(),'unexpected active file type');
      const current=hash(fs.readFileSync(target));assert.ok(current===e.original||current===e.retired,'concurrent retirement edit');
    }else assert.notEqual(e.file,PACKAGE,'root installer disappeared');
  }
  for(const e of m.files)atomicWrite(home.p(e.file),fs.readFileSync(e.backup),e);
  m.phase='restored';save(dir,m);
  return m.phase;
}
function retire(home,candidate,expected,check=ready) {
  check();
  const installation=home.load();assert.equal(installation.phase,'installed');
  const current=fs.readFileSync(home.p(APP));
  assert.equal(hash(current),installation.files.find(e=>e.file===APP).trial,'Home changed');
  assert.ok(current.includes('ALVIDAA_FREE_MY_TV_NATIVE_V1'),'installed UI still needs bridge');
  const before=fs.readFileSync(home.p(PACKAGE)),after=fs.readFileSync(candidate);
  assert.equal(hash(before),expected,'root installer changed since inspection');validatePatch(before,after);
  const dir=path.join(home.state,'retired-bridge');fs.mkdirSync(dir,{mode:0o700});
  const m={phase:'prepared',files:[]};
  for(const file of [PACKAGE,...RUNTIMES]){
    const target=home.p(file);if(!fs.existsSync(target))continue;
    const st=fs.lstatSync(target);assert.ok(st.isFile()&&!st.isSymbolicLink(),'unexpected runtime path');
    const data=fs.readFileSync(target),backup=path.join(dir,String(m.files.length)+'.orig');
    const fd=fs.openSync(backup,'wx',0o600);try{fs.writeFileSync(fd,data);fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
    m.files.push({file,backup,uid:st.uid,gid:st.gid,mode:st.mode,original:hash(data),retired:file===PACKAGE?hash(after):null});
  }
  save(dir,m);
  try{
    // Recheck after copying; never delete a runtime another session replaced.
    for(const e of m.files)assert.equal(hash(fs.readFileSync(home.p(e.file))),e.original,'concurrent runtime edit');
    atomicWrite(home.p(PACKAGE),after,m.files[0]);
    for(const e of m.files.slice(1))fs.unlinkSync(home.p(e.file));
    m.phase='retired';save(dir,m);return m.phase;
  }catch(error){
    try{restore(home);}catch(recovery){throw new Error(error.message+'; retirement recovery failed: '+recovery.message);}
    throw error;
  }
}
function main(){
  assert.equal(process.getuid(),0,'root SSH required');
  const [command,candidate,expected]=process.argv.slice(2),home=new NativeHome();
  if(command==='status'){console.log(json(path.join(home.state,'retired-bridge/state.json')).phase);return;}
  const release=acquire(home.state);
  try{
    if(command==='retire')console.log(retire(home,candidate,expected));
    else if(command==='restore')console.log(restore(home)+'; services not started');
    else throw new Error('Use retire patched.ipk original-sha256, restore, or status');
  }finally{release();}
}
if(require.main===module){try{main();}catch(error){console.error(error.stack);process.exit(1);}}
module.exports={retire,restore,validatePatch,archive,controlFiles,postinst,PACKAGE,RUNTIMES};
