#!/usr/bin/env node
'use strict';
// Root-local lifecycle only. No HTTP listener or remote command interface.
const fs=require('node:fs');
const path=require('node:path');
const cp=require('node:child_process');
const assert=require('node:assert/strict');
const MARKER='ALVIDAA_FREE_MY_TV_WEB_PARITY_V2';
function service(options={}){
 const release=options.release||__dirname;
 const config={worker:path.join(release,'native-feed-worker.cjs'),processor:path.join(release,'native-image'),
  phoenix:'/opt/pkgs/tv.vidaa.app.phoenix/bin/phoenix',home:'/APPS/channelA/operation-ui/apps/launcher/js/app.js',
  ipc:'/APPS/free-my-tv',media:'/APPS/channelA/hisenseUI/var/local/free-my-tv/media',icons:'/APPS/channelA/hisenseUI/var/local/storeAppIcon',
  credentials:'/var/local/alvidaa/server/keys/free-my-tv.json',lock:'/var/local/alvidaa/native-home/free-my-tv-feed.flock',
  log:path.join(release,'worker.log'),...options.paths};
 function regular(file){const st=fs.lstatSync(file);assert.ok(st.isFile()&&!st.isSymbolicLink(),'Expected a regular service file');return st;}
 function selected(){try{return fs.readFileSync(config.home,'utf8').includes(MARKER);}catch{return false;}}
 function status(){
  let pid;try{pid=Number(fs.readFileSync(config.lock+'.pid','utf8'));}catch{return {running:false,selected:selected()};}
  if(!Number.isSafeInteger(pid)||pid<=1)return {running:false,conflict:true,selected:selected()};
  let args,stat;
  try{args=fs.readFileSync('/proc/'+pid+'/cmdline','utf8').split('\0');stat=fs.readFileSync('/proc/'+pid+'/stat','utf8');}
  catch{return {running:false,stale:true,selected:selected()};}
  const own=args[0]===config.phoenix&&args[1]===config.worker&&
   [config.ipc,config.credentials,config.processor,config.icons,config.media].every(value=>args.includes(value));
  const group=Number(stat.slice(stat.lastIndexOf(')')+2).split(' ')[2]);
  return {running:own,pid,group,conflict:!own,selected:selected()};
 }
 async function wait(check,message){
  for(let i=0;i<80;i++){if(check())return;await new Promise(resolve=>setTimeout(resolve,100));}
  throw Error(message);
 }
 async function start(){
  const before=status();assert.ok(!before.conflict,'Another process owns the worker PID record');
  if(!selected())return before;
  if(before.running)return before;
  for(const file of [config.worker,config.processor]){
   const st=regular(file);assert.ok(st.uid===process.getuid()&&(st.mode&0o022)===0,'Service code must belong to its operator and not be group/world writable');
  }
  // The read-only vendor runtime and Home retain their vendor ownership.
  [config.phoenix,config.home].forEach(regular);
  const credentials=regular(config.credentials);
  assert.ok(credentials.uid===process.getuid()&&(credentials.mode&0o077)===0,'Credential file must remain operator-private');
  for(const directory of [config.ipc,path.dirname(config.lock)])assert.ok(fs.lstatSync(directory).isDirectory(),'Missing service directory');
  // The firmware's storeAppIcon is a vendor symlink. Media reads independently
  // resolve it and enforce containment; do not change that vendor alias.
  assert.ok(fs.statSync(config.icons).isDirectory(),'Missing vendor icon directory');
  if(fs.existsSync(config.log))regular(config.log);
  const log=fs.openSync(config.log,'a',0o600);fs.fchmodSync(log,0o600);
  let child;
  try{
   child=cp.spawn(config.processor,['lock-run',config.lock,config.phoenix,config.worker,config.ipc,config.credentials,
    config.processor,config.icons,config.media,config.home],{detached:true,stdio:['ignore',log,log],
    env:{...process.env,LD_LIBRARY_PATH:'/lib:/usr/local/lib:/basic/lib'}});
   await new Promise((resolve,reject)=>{child.once('spawn',resolve);child.once('error',reject);});child.unref();
  }finally{fs.closeSync(log);}
  await wait(()=>status().running,'Worker did not acquire its lock');
  return status();
 }
 async function stop(){
  const before=status();assert.ok(!before.conflict,'Refusing to signal an unrelated process');
  if(!before.running)return before;
  assert.equal(before.group,before.pid,'Worker does not own its process group');
  process.kill(-before.pid,'SIGTERM');
  await wait(()=>{try{process.kill(-before.pid,0);return false;}catch(error){if(error.code==='ESRCH')return true;throw error;}},'Worker group did not stop');
  return status();
 }
 return {start,stop,status,config};
}
if(require.main===module){
 const action=process.argv[2]||'status';
 if(!['start','stop','status'].includes(action)){console.error('Usage: native-web-service.cjs start|stop|status');process.exit(2);}
 Promise.resolve().then(()=>service()[action]()).then(result=>{console.log(JSON.stringify(result));process.exit(0);},error=>{
  console.error('Native web service: '+error.message);process.exit(1);
 });
}
module.exports={service,MARKER};
