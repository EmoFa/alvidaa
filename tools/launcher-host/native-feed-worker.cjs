#!/usr/bin/env node
'use strict';
// On-TV polling worker: no listener, browser token, PC service or MQTT session.
const fs=require('node:fs');
const path=require('node:path');
const {createEngine}=require('./native-feed-engine.cjs');
const {createMedia,atomic}=require('./native-feed-images.cjs');
function readJSON(file,limit){
 const stat=fs.lstatSync(file);if(!stat.isFile()||stat.size>limit)throw Error('Invalid worker input file');
 try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{throw Error('Invalid worker JSON');}
}
function readToken(file){
 const resolved=fs.realpathSync(file);
 if(!resolved.includes(path.sep+'server'+path.sep+'keys'+path.sep))throw Error('Credentials must remain in server/keys');
 const stat=fs.lstatSync(file);if(!stat.isFile()||(stat.mode&0o077)!==0)throw Error('Private credential permissions required');
 const value=readJSON(file,16384).tmdb_token;
 if(typeof value==='string'&&!value.trim())return ''; // Explicit offline/no-TMDB configuration.
 if(typeof value!=='string'||value.length>4096||!value.trim().startsWith('eyJ')||/[\r\n]/.test(value.trim()))throw Error('A private TMDB read token is required');
 return value.trim();
}
function start(options){
 const directory=path.resolve(options.directory),token=readToken(options.credentials);
 fs.mkdirSync(directory,{recursive:true,mode:0o755});
 const lockPath=process.env.ALVIDAA_NATIVE_FEED_LOCK_PATH;
 const descriptor=Number(process.env.ALVIDAA_NATIVE_FEED_LOCK_FD);
 if(!lockPath||!Number.isInteger(descriptor)||descriptor<3)throw Error('Start worker through native-image lock-run');
 const held=fs.fstatSync(descriptor),expected=fs.statSync(lockPath);
 if(!held.isFile()||held.dev!==expected.dev||held.ino!==expected.ino)throw Error('Worker lock descriptor was not inherited');
 const lock=lockPath+'.pid';
 atomic(lock,String(process.pid),0o600);
 let stopped=false,engine=null,media=null,context=null,signature='',lastRefresh=0,writing=null,polling=null;
 let imageBusy=false,imageAgain=false,lastPublished='',homeStamp='',render={images:{},media:{},imageFailures:0};
 let old={};try{old=readJSON(path.join(directory,'snapshot.json'),8*1024*1024);}catch{/* First start or damaged cache. */}
 if(old.version===1)render={images:old.images||{},media:old.media||{},imageFailures:old.imageFailures||0};
 function publish(){
  writing=null;if(stopped||!engine)return;
  try{
   const encoded=JSON.stringify({...engine.snapshot(),...render,workerPid:process.pid});
   if(encoded!==lastPublished){atomic(path.join(directory,'snapshot.json'),encoded);lastPublished=encoded;}
  }
  catch{/* Preserve the last good snapshot on disk failures; keep local Home alive. */}
 }
 function schedule(){if(!stopped&&writing===null)writing=setTimeout(publish,200);}
 async function images(){
  if(stopped||!media||!engine)return;
  if(imageBusy){imageAgain=true;return;}
  imageBusy=true;imageAgain=false;
  const owner=media,current=engine,currentContext=context;
  try{
   const state=current.snapshot();
   const cache=state.keyConfigured?state.cache:{...state.cache,'fmtv.recs':null};
   const value=await owner.update(currentContext,cache);
   if(!stopped&&media===owner&&value){render=value;owner.collect();schedule();}
  }catch{/* Retain previous usable image mappings on processing failures. */}
  finally{imageBusy=false;if(imageAgain&&!stopped)void images();}
 }
 function changed(){schedule();if(engine&&engine.snapshot().pending===0)void images();}
 function poll(){
  if(stopped)return;
  if(options.homePath){
   try{
    const st=fs.statSync(options.homePath),stamp=[st.ino,st.size,st.mtimeMs,st.ctimeMs].join(':');
    if(stamp!==homeStamp){
     if(!fs.readFileSync(options.homePath,'utf8').includes('ALVIDAA_FREE_MY_TV_WEB_PARITY_V2')){stop();return;}
     homeStamp=stamp;
    }
   }catch{stop();return;}
  }
  try{
   const next=readJSON(path.join(directory,'context.json'),1024*1024);
   if(next.version!==1||!Array.isArray(next.apps)||next.apps.length>512||typeof next.zone!=='string'||next.zone.length>100||
      typeof next.prefs!=='string'||next.prefs.length>65536)throw Error('Invalid native context');
   const nextSignature=JSON.stringify(next);
   if(nextSignature!==signature){
    const cache=engine?engine.snapshot().cache:old.cache;
    // Construct the new engine before releasing a usable old one.
    const replacement=createEngine({token,context:next,cache,onChange:changed});
    let owner;
    try{
     owner=createMedia({directory:options.mediaDirectory||path.join(directory,'media'),iconRoot:options.iconRoot,processor:options.processor,
      previousImages:render.images,uriBase:'file:///hisenseUI/var/local/free-my-tv/media/',onChange:value=>{if(!stopped&&media===owner){render=value;schedule();}}});
    }catch(error){replacement.stop();throw error;}
    if(engine)engine.stop();if(media)media.stop();
    // Only a zone from the pinned public timezone catalogue reaches TZ. This
    // changes this worker's date calculations, never the TV's preferences.
    if(replacement.snapshot().locationKnown)process.env.TZ=next.zone;
    engine=replacement;context=next;signature=nextSignature;
    media=owner;lastRefresh=0;old={};imageAgain=true;
   }
   if(engine&&Date.now()-lastRefresh>=30000){
    lastRefresh=Date.now();engine.refresh();schedule();
    if(engine.snapshot().pending===0)void images();
   }
  }catch{/* A partially written context never replaces the last good one. */}
  polling=setTimeout(poll,1000);
 }
 function stop(){
  if(stopped)return;stopped=true;
  if(polling!==null)clearTimeout(polling);if(writing!==null)clearTimeout(writing);
  if(engine)engine.stop();if(media)media.stop();
  try{if(fs.readFileSync(lock,'utf8')===String(process.pid))fs.unlinkSync(lock);}catch{/* No longer our lock. */}
  if(options.onStop)options.onStop();
 }
 try{poll();}catch(error){stop();throw error;}
 return {stop};
}
if(require.main===module){
 const [directory,credentials,processor,iconRoot,mediaDirectory,homePath]=process.argv.slice(2);
 if(!directory||!credentials||!processor||!iconRoot){console.error('Usage: native-feed-worker.cjs state-dir private-key-file image-helper icon-root [media-dir] [home-file]');process.exit(2);}
 else try{
  const worker=start({directory,credentials,processor,iconRoot,mediaDirectory,homePath,onStop:()=>process.exit(0)});
  for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>{worker.stop();process.exit(0);});
 }catch{console.error('Native feed worker could not start; check private configuration and worker ownership');process.exit(1);}
}
module.exports={start,readToken,readJSON};
