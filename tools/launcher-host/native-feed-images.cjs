'use strict';
const fs=require('node:fs');
const path=require('node:path');
const https=require('node:https');
const crypto=require('node:crypto');
const {execFile}=require('node:child_process');
const {promisify}=require('node:util');
const run=promisify(execFile);
const digest=value=>crypto.createHash('sha256').update(value).digest('hex');
const ICON_URI='file:///hisenseUI/var/local/storeAppIcon/';
function photoURL(file,size){
 if(!['w300','w500','w780','w1280','original'].includes(size)||typeof file!=='string'||!/^\/[A-Za-z0-9_-]+\.(jpg|png|svg)$/.test(file))throw Error('Invalid TMDB image reference');
 // TMDB documents PNG equivalents of SVG assets at the same basename.
 return 'https://image.tmdb.org/t/p/'+size+file.replace(/\.svg$/,'.png');
}
function download(url,get=https.get){
 // Callers must use photoURL; never pass arbitrary snapshot URLs to this client.
 if(!/^https:\/\/image\.tmdb\.org\/t\/p\/(w300|w500|w780|w1280|original)\/[A-Za-z0-9_-]+\.(jpg|png)$/.test(url))return Promise.reject(Error('Image endpoint rejected'));
 return new Promise((resolve,reject)=>{
  let req,res,done=false,size=0;const chunks=[];
  const timer=setTimeout(()=>finish(Error('Image request timed out')),10000);
  function finish(error,value){if(done)return;done=true;clearTimeout(timer);if(error){if(res)res.destroy();if(req)req.destroy();reject(error);}else resolve(value);}
  try{req=get(url,{headers:{Accept:'image/jpeg,image/png','User-Agent':'alvidaa-free-my-tv/native'}},response=>{
   res=response;if(done){res.destroy();return;}
   res.on('error',()=>finish(Error('Image response failed')));res.on('aborted',()=>finish(Error('Image response interrupted')));
   if(res.statusCode!==200){finish(Error('Image HTTP request failed'));return;}
   res.on('data',chunk=>{size+=chunk.length;if(size>8*1024*1024){finish(Error('Image exceeds size limit'));return;}chunks.push(chunk);});
   res.on('end',()=>finish(null,Buffer.concat(chunks)));
  });req.on('error',()=>finish(Error('Image request failed')));}catch{finish(Error('Image request failed'));}
 });
}
function atomic(file,data,mode=0o644){
 const temp=file+'.tmp-'+process.pid;
 try{fs.writeFileSync(temp,data,{mode});fs.chmodSync(temp,mode);fs.renameSync(temp,file);}
 finally{try{fs.unlinkSync(temp);}catch{/* Renamed or never created. */}}
}
function createMedia(options){
 const directory=path.resolve(options.directory),iconRoot=fs.realpathSync(options.iconRoot);
 const base=options.uriBase;
 fs.mkdirSync(directory,{recursive:true,mode:0o755});
 const processor=digest(fs.readFileSync(options.processor));
 const media={},images={},active=new Set(),abort=new AbortController();let stopped=false;
 function uri(file){return base+path.basename(file);}
 async function prepare(key,bytes,mode){
  const name=digest(processor+'\n'+key),prefix=path.join(directory,name);
  active.add(name);
  const format=bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))?'.png':
   bytes[0]===255&&bytes[1]===216&&bytes[2]===255?'.jpg':null;
  if(!format)throw Error('Unsupported cached image format');
  const input=prefix+'-raw'+format,rawHash=digest(bytes);
  let info;
  try{
   const saved=JSON.parse(fs.readFileSync(prefix+'-meta.json','utf8'));
   if(saved.rawHash===rawHash&&fs.existsSync(input)&&Number.isInteger(saved.info.width)&&Number.isInteger(saved.info.height)&&
      saved.info.width>0&&saved.info.height>0&&saved.info.width*saved.info.height<=16000000&&
      (mode!=='photo'||fs.existsSync(prefix+'-thumb.png'))&&(!saved.info.lift||fs.existsSync(prefix+'-logo.png')))info=saved.info;
  }catch{/* First preparation or damaged metadata. */}
  if(!info){
   const space=fs.statfsSync(directory);if(space.bavail*space.bsize<64*1024*1024+bytes.length)throw Error('Insufficient image cache headroom');
   atomic(input,bytes);
   const result=await run(options.processor,[input,prefix,mode],{timeout:10000,maxBuffer:16384,signal:abort.signal});
   try{info=JSON.parse(result.stdout);}catch{throw Error('Invalid image processor response');}
   if(!Number.isInteger(info.width)||!Number.isInteger(info.height)||info.width<=0||info.height<=0)throw Error('Invalid processed image dimensions');
   atomic(prefix+'-meta.json',JSON.stringify({rawHash,format,info}));
  }
  const value={src:uri(input),width:info.width,height:info.height};
  if(mode==='photo')value.thumb=uri(prefix+'-thumb.png');
  if(info.lift){
   value.lift={src:uri(prefix+'-logo.png'),bg:info.lift.bg,ink:info.lift.ink,width:info.lift.width,height:info.lift.height};
   media[value.lift.src]={src:value.lift.src,width:info.lift.width,height:info.lift.height};
  }
  media[value.src]=value;return value;
 }
 async function icon(source){
  if(stopped||typeof source!=='string'||!source.startsWith(ICON_URI))return;
  const relative=source.slice(ICON_URI.length);
  if(!relative||relative.includes('%')||relative.split('/').includes('..')||/[\\\x00-\x1f]/.test(relative))return;
  const file=fs.realpathSync(path.resolve(iconRoot,relative));
  if(!file.startsWith(iconRoot+path.sep))return;
  const stat=fs.statSync(file);if(!stat.isFile()||stat.size>8*1024*1024)return;
  const bytes=fs.readFileSync(file),value=await prepare('icon:'+digest(bytes),bytes,'icon');
  if(!stopped)media[source]=value;
 }
 function cachedBytes(name){
  try{
   if(!/^[a-f0-9]{64}$/.test(name))return null;
   const metadata=path.join(directory,name+'-meta.json'),st=fs.lstatSync(metadata);
   if(!st.isFile()||st.size>16384)return null;
   const saved=JSON.parse(fs.readFileSync(metadata,'utf8'));
   if(!['.png','.jpg'].includes(saved.format))return null;
   const file=path.join(directory,name+'-raw'+saved.format),raw=fs.lstatSync(file);
   if(!raw.isFile()||raw.size>8*1024*1024)return null;
   const bytes=fs.readFileSync(file);return saved.rawHash===digest(bytes)?bytes:null;
  }catch{return null;}
 }
 async function photo(file,size){
  if(stopped||!file)return;
  const url=photoURL(file,size),name=digest(processor+'\n'+url);
  let bytes=cachedBytes(name);
  // Processor upgrades must remain usable offline. Reuse only a bounded,
  // hash-checked raw image from the previous snapshot's exact local cache URI.
  const previous=options.previousImages&&options.previousImages[size+':'+file];
  if(!bytes&&typeof previous==='string'&&previous.startsWith(base)){
   const match=/^([a-f0-9]{64})-raw\.(png|jpg)$/.exec(previous.slice(base.length));
   if(match)bytes=cachedBytes(match[1]);
  }
  if(!bytes)bytes=await (options.download||download)(url);
  const value=await prepare(url,bytes,'photo');if(!stopped)images[size+':'+file]=value.src;
 }
 async function update(context,cache){
  active.clear();let failures=0;
  for(const app of context.apps){try{await icon(app.icon);}catch{failures++;}if(stopped)return;}
  let picks=[];try{picks=JSON.parse(cache['fmtv.recs']||'{}').picks||[];}catch{/* No usable cached picks. */}
  const wanted=new Map();
  for(const pick of picks.slice(0,64)){
   if(pick.backdrop){
    for(const size of ['w1280','w780','w300','original'])wanted.set(size+':'+pick.backdrop,[pick.backdrop,size]);
   }
   if(pick.logo)wanted.set('w500:'+pick.logo,[pick.logo,'w500']);
  }
  for(const args of wanted.values()){
   try{await photo(...args);}catch{failures++;}if(stopped)return;
   if(options.onChange)options.onChange({images:{...images},media:{...media},imageFailures:failures});
  }
  return {images:{...images},media:{...media},imageFailures:failures};
 }
 function collect(){
  // Keep the current generation plus at most 80 MiB of inactive cached files.
  const files=fs.readdirSync(directory).filter(name=>/^[a-f0-9]{64}-(raw\.(png|jpg)|logo\.png|thumb\.png|meta\.json)$/.test(name)).map(name=>{
   const file=path.join(directory,name),stat=fs.lstatSync(file);return {file,name,stat};
  }).filter(item=>item.stat.isFile());
  let size=files.reduce((total,item)=>total+item.stat.size,0);
  const groups=new Map();
  for(const item of files){const key=item.name.slice(0,64);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(item);}
  const ordered=[...groups.entries()].sort((a,b)=>Math.max(...a[1].map(x=>x.stat.mtimeMs))-Math.max(...b[1].map(x=>x.stat.mtimeMs)));
  let remaining=groups.size;
  for(const [key,group] of ordered){
   if(size<=80*1024*1024&&remaining<=512)break;
   if(!active.has(key)){for(const item of group){fs.unlinkSync(item.file);size-=item.stat.size;}remaining--;}
  }
  for(const [key,value] of Object.entries(media))if(!fs.existsSync(path.join(directory,path.basename(value.src))))delete media[key];
  for(const [key,value] of Object.entries(images))if(!fs.existsSync(path.join(directory,path.basename(value))))delete images[key];
 }
 return {update,collect,stop(){stopped=true;abort.abort();}};
}
module.exports={photoURL,download,atomic,createMedia};
