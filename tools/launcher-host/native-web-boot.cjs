#!/usr/bin/env node
'use strict';
// Change only the existing writable root bootstrap's owned feed fragment.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {archive,controlFiles,postinst,PACKAGE}=require('./retire-native-bridge.cjs');
const {NativeHome,acquire}=require('./native-home.cjs');
const {APP,hash,atomicWrite}=require('./native-trial.cjs');
const ANCHOR='echo "--- native Home: no extra launcher server ---"\n  ';
function validate(before,after,fragment=fs.readFileSync(path.join(__dirname,'native-feed-boot.sh'),'utf8')){
 const old=archive(before),next=archive(after);assert.deepEqual(Object.keys(next),Object.keys(old),'IPK layout changed');
 for(const key of Object.keys(old))if(key!=='control.tar.gz')assert.ok(old[key].equals(next[key]),'Root payload changed');
 const a=controlFiles(old['control.tar.gz']),b=controlFiles(next['control.tar.gz']);
 assert.deepEqual(Object.keys(b),Object.keys(a),'Control members changed');
 for(const key of Object.keys(a)){
  assert.equal(b[key].metadata,a[key].metadata,'Control ownership/permissions changed');
  if(key!=='postinst')assert.ok(a[key].body.equals(b[key].body),'Package metadata changed');
 }
 const source=postinst(old['control.tar.gz']);
 assert.equal(source.split(ANCHOR).length,2,'Unknown retirement marker');
 assert.ok(source.includes(ANCHOR+'echo "--- step: phone home ---"'),'Unknown adjacent bootstrap changes');
 assert.ok(!source.includes('ALVIDAA_NATIVE_WEB_FEED_V1'),'Feed hook already present');
 assert.equal(postinst(next['control.tar.gz']),source.replace(ANCHOR,ANCHOR+fragment+'  '),'Unexpected bootstrap changes');
}
function save(directory,value){const file=path.join(directory,'state.json');atomicWrite(file,Buffer.from(JSON.stringify(value,null,2)),{uid:process.getuid(),gid:process.getgid(),mode:0o600});}
function journal(directory){
 let m;
 try{m=JSON.parse(fs.readFileSync(path.join(directory,'state.json'),'utf8'));}
 catch{throw Error('Cannot read the bootstrap recovery journal');}
 assert.ok(m&&['prepared','installed','restored'].includes(m.phase)&&
  /^[a-f0-9]{64}$/.test(m.original)&&/^[a-f0-9]{64}$/.test(m.updated)&&
  ['uid','gid','mode'].every(key=>Number.isSafeInteger(m[key])&&m[key]>=0),'Invalid bootstrap recovery journal');
 return m;
}
function restore(home){
 const directory=path.join(home.state,'web-feed-boot'),m=journal(directory);
 const file=home.p(PACKAGE),current=hash(fs.readFileSync(file)),before=fs.readFileSync(path.join(directory,'installer.orig'));
 assert.equal(hash(before),m.original,'Bootstrap backup changed');
 assert.ok(current===m.original||current===m.updated,'Bootstrap changed concurrently');
 if(current!==m.original)atomicWrite(file,before,m);
 m.phase='restored';save(directory,m);return m.phase;
}
function apply(home,candidate,expected){
 const state=home.load();assert.equal(state.phase,'installed','Home must be stably installed');
 const currentHome=fs.readFileSync(home.p(APP));
 assert.equal(hash(currentHome),state.files.find(entry=>entry.file===APP).trial,'Home changed');
 assert.ok(currentHome.includes('ALVIDAA_FREE_MY_TV_WEB_PARITY_V2'),'Upstream web Home is not installed');
 const file=home.p(PACKAGE),st=fs.lstatSync(file),input=fs.lstatSync(candidate);
 assert.ok(st.isFile()&&!st.isSymbolicLink()&&input.isFile()&&!input.isSymbolicLink(),'Unexpected bootstrap file type');
 const before=fs.readFileSync(file),after=fs.readFileSync(candidate);assert.equal(hash(before),expected,'Bootstrap changed since inspection');
 const directory=path.join(home.state,'web-feed-boot');let m;
 if(fs.existsSync(directory)){
  m=journal(directory);const original=fs.readFileSync(path.join(directory,'installer.orig'));
  assert.equal(hash(original),m.original,'Bootstrap backup changed');validate(original,after);
  if(m.phase==='installed'&&hash(before)===m.updated&&hash(after)===m.updated)return m.phase;
  assert.equal(m.phase,'restored','A prior bootstrap operation needs recovery');
  assert.equal(hash(before),m.original,'Restored bootstrap changed');
  assert.ok(st.uid===m.uid&&st.gid===m.gid&&st.mode===m.mode,'Bootstrap permissions changed');
  m.phase='prepared';m.updated=hash(after);
 }else{
  validate(before,after);fs.mkdirSync(directory,{mode:0o700});
  const fd=fs.openSync(path.join(directory,'installer.orig'),'wx',0o600);
  try{fs.writeFileSync(fd,before);fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  m={phase:'prepared',original:hash(before),updated:hash(after),uid:st.uid,gid:st.gid,mode:st.mode};
 }
 save(directory,m);
 try{
  assert.equal(hash(fs.readFileSync(file)),m.original,'Concurrent bootstrap edit');
  atomicWrite(file,after,m);m.phase='installed';save(directory,m);return m.phase;
 }catch(error){restore(home);throw error;}
}
if(require.main===module){
 try{
  assert.equal(process.getuid(),0,'Root-local control required');
  const [action,candidate,expected]=process.argv.slice(2),home=new NativeHome(),release=acquire(home.state);
  try{
   if(action==='apply')console.log(apply(home,candidate,expected));
   else if(action==='restore')console.log(restore(home));
   else throw Error('Usage: native-web-boot.cjs apply patched.ipk expected-sha256 | restore');
  }finally{release();}
  process.exit(0);
 }catch(error){console.error('Native feed bootstrap: '+error.message);process.exit(1);}
}
module.exports={validate,apply,restore,ANCHOR};
