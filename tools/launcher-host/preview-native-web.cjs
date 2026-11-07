#!/usr/bin/env node
'use strict';
// Local-only visual comparison harness. Does not contact the TV or read keys.
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const http=require('node:http');
const {execFile}=require('node:child_process');
const {promisify}=require('node:util');
const {bundle}=require('./build-native-web.cjs');
const {readSources}=require('./native-web-program.cjs');
const {fixture}=require('./native-web-fixture.cjs');
const run=promisify(execFile);
function harness(native,view,snapshot){return `
window.addEventListener('error',function(e){if(!document.documentElement.hasAttribute('data-test-error'))document.documentElement.setAttribute('data-test-error',e.message);});
window.fixtureSnapshot=${JSON.stringify(snapshot||{version:1,keyConfigured:false,cache:{},media:{},images:{}})};
var RealDate=Date;window.Date=class extends RealDate{constructor(...args){super(...(args.length?args:[Date.UTC(2026,10,7,14,30)]));}static now(){return Date.UTC(2026,10,7,14,30);}};
window.XMLHttpRequest=function(){this.headers={};};
XMLHttpRequest.prototype.open=function(method,url){this.url=url;};
XMLHttpRequest.prototype.setRequestHeader=function(){};
XMLHttpRequest.prototype.abort=function(){};
XMLHttpRequest.prototype.send=function(){var x=this;setTimeout(function(){
 x.status=x.url.indexOf('localhost:9009')>=0?200:503;x.readyState=4;
 x.responseText=JSON.stringify({ret:true,msg:JSON.stringify(window.fixtureSnapshot)});
 if(x.onreadystatechange)x.onreadystatechange();},0);};
localStorage.clear();localStorage.setItem('fmtv.prefs',JSON.stringify({theme:${JSON.stringify(view.endsWith('night')?'dark':'auto')}}));
Object.keys(window.fixtureSnapshot.cache).forEach(function(key){localStorage.setItem(key,window.fixtureSnapshot.cache[key]);});
window.previewNative=${native};Math.random=function(){return 0;};
// Static comparison only: compositor transitions are not deterministic under
// Chromium's virtual clock. Motion is a separate on-device acceptance gate.
var freeze=document.createElement('style');freeze.textContent='*{transition:none!important;animation:none!important}';document.head.appendChild(freeze);`;
}
function finish(view){return `
function key(code){var target=window.previewNative?document.body:document;var e=new Event(window.previewNative?'key-down':'keydown',{bubbles:true,cancelable:true});Object.defineProperty(e,'keyCode',{value:code});target.dispatchEvent(e);}
function id(name){return document.getElementById((window.previewNative?'fmtv-web-':'')+name);}
document.fonts.ready.then(function(){setTimeout(function(){
 try{
  var view=${JSON.stringify(view)};
  if(!id('buttons')||!id('buttons').children.length)throw Error('Home controls did not mount');
  if(view.indexOf('live-')===0){
   if(id('cards').children.length!==3)throw Error('Live fixture must render three cards');
   view=view.slice(5);
   if(view==='movies'||view==='shows')id('tabs').children[view==='movies'?1:2].click();
  }
  if(view==='saver'){
   var control=window.previewNative?window.previewControl:window.FreeMyTV;
   control.showSaver();if(!id('saver'))throw Error('Screensaver did not mount');
  }
  if(['settings','language','shelf'].indexOf(view)>=0)id('buttons').lastElementChild.click();
  if(view==='language'||view==='shelf'){
   var rows=id('settings').querySelectorAll('.row');
   var found=Array.from(rows).find(function(row){return view==='language'?/^Language/.test(row.textContent):/shelf/i.test(row.textContent);});
   if(!found)throw Error('Requested settings row not found');found.click();
  }
  if(view==='drawer'||view==='apps'){key(40);
   var body=window.previewNative?document.getElementById('alvidaa-web-home'):document.body;
   if((' '+body.className+' ').indexOf(' drawer-open ')<0)throw Error('Drawer did not open');
   if(view==='apps'){
   var keys=id('drawer').querySelectorAll('.key');var all=Array.from(keys).find(function(node){return node.textContent==='All Apps';});
   if(!all)throw Error('All Apps control not found');all.click();
  }}
  setTimeout(function(){
   var canvas=!window.previewNative&&document.querySelector('#sky canvas.on');
   if(canvas)document.documentElement.setAttribute('data-test-canvas',canvas.toDataURL());
   document.documentElement.setAttribute('data-test-ready','true');
  },500);
 }catch(e){if(!document.documentElement.hasAttribute('data-test-error'))document.documentElement.setAttribute('data-test-error',e.message);}
},100);});`;
}
function page(native,view,sources,web,snapshot){
 const setup=harness(native,view,snapshot);
 const scripts=['config.js','coins.js','i18n.js','strings.js','tv.js','zones.js','data.js','home.js'];
 if(!native){
  let html=sources['index.html'].replace('<head>','<head><script>'+setup+'</script>');
  for(const file of scripts){
   let code=sources[file]+(file==='tv.js'?"\nTV.zone=function(){return 'Australia/Brisbane';};":'');
   if(snapshot&&file==='config.js')code+="\nCONFIG.tmdbKey='synthetic-fixture-only';";
   if(snapshot&&file==='data.js')code+="\nData.refresh=function(){};Data.image=function(p){return p?'/fixtures/'+p.slice(1):'';};";
   html=html.replace('<script src="'+file+'"></script>',()=>'<script>'+code.replace(/<\/script/gi,'<\\/script')+'</script>');
  }
  return html.replace('</body>','<script>'+finish(view)+'</script></body>');
 }
 const adapterFiles=['native-web-tv.js','native-web-screensaver.js','native-web-scope.js','native-web-compat.js','native-web-runtime.js'];
 const adapters=adapterFiles.map(file=>{
  let source=fs.readFileSync(path.join(__dirname,file),'utf8');
  // Chromium cannot read the TV's file scheme from a localhost page. Rebase
  // that one allowlisted prefix in this preview copy only, never production.
  if(file==='native-web-compat.js'){
   const from=String.raw`^file:\/\/\/hisenseUI\/var\/local\/(free-my-tv|storeAppIcon)\/`;
   if(source.split(from).length!==2)throw Error('Native media prefix anchor changed');
   source=source.replace(from,String.raw`^\/fixture-media\/`);
  }
  return source;
 }).join('\n');
 const bootstrap=`
 var originalTV=TV,values={'alvidaa.freeMyTV':{theme:${JSON.stringify(view.endsWith('night')?'dark':'auto')}}};
 window.modeljs={getIntValue:function(){return 1;}};
 window.AlvidaaNativePlatform=function(_sdk,update){return {start:function(){originalTV.apps(function(apps){originalTV.inputs(function(inputs){update({apps:apps.map(function(a){return {appId:a.id,appName:a.title,img:'',bgColor:a.color};}),sources:inputs.map(function(s,i){return {sourceId:i?'HDMI'+i:'TV',name:s.label,hasSignal:s.connected};})});});});},stop:function(){},launchApp:function(){return true;},changeSource:function(){return true;},openSettings:function(){return true;}};};
 var sdk={key:{KEYMAP:{LEFT:37,UP:38,RIGHT:39,DOWN:40,ENTER:13,BACK:8,SOURCE:505,KEYPAD_INPUT:610}},
 router:{isCurrentPathEqualTo:function(){return true;}},message:{on:function(){},off:function(){},emit:function(){}},
 storage:{get:function(k){return values[k];},set:function(k,v){values[k]=v;}},tts:{isEnable:function(){return false;}},apc:{CMDMETHOD:{KEY_INPUT_START:'input'}},i18n:{t:function(v){return v;}}};
 var run=AlvidaaNativeWebBundle.run;
 AlvidaaNativeWebBundle.run=function(){var program=run.apply(this,arguments);window.previewControl=program.control;return program;};
 var component=AlvidaaFreeMyTV(sdk),instance={$el:document.getElementById('alvidaa-web-home'),$route:{query:{}}};
 Object.keys(component.methods).forEach(function(k){instance[k]=component.methods[k];});component.mounted.call(instance);
 `;
 return '<!doctype html><html><head><meta charset="utf-8"><script>'+setup+'</script></head><body>'+
  '<div id="alvidaa-web-home" style="position:absolute;left:0;top:0;width:1920px;height:1080px"></div><script>'+
  [sources['tv.js'],web,adapters,bootstrap,finish(view)].join('\n').replace(/<\/script/gi,'<\\/script')+'</script></body></html>';
}
async function main(){
 const assets=path.resolve(process.argv[2]||''),output=process.argv[3]||fs.mkdtempSync(path.join(os.tmpdir(),'fmtv-visual-'));
 fs.mkdirSync(output,{recursive:true});
 const sources=readSources(),built=bundle(assets);
 const live=process.env.NATIVE_IMAGE_HELPER?await fixture(path.join(output,'fixture-media'),process.env.NATIVE_IMAGE_HELPER):null;
 const web=built.source.replaceAll('file:///hisenseUI/var/local/free-my-tv/assets/'+built.assetId+'/','/assets/');
 const server=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://127.0.0.1');
  if(url.pathname==='/preview'){
   const view=url.searchParams.get('view')||'home';
   res.setHeader('Content-Type','text/html; charset=utf-8');res.end(page(url.searchParams.get('native')==='1',view,sources,web,view.startsWith('live-')&&live?live.snapshot:null));return;
  }
  if(url.pathname.startsWith('/fixtures/')||url.pathname.startsWith('/fixture-media/')){
   const name=path.basename(url.pathname);
   try{
    const data=url.pathname.startsWith('/fixtures/')?live&&live.originals[name]:/^[a-f0-9]{64}[-a-z]*\.png$/.test(name)?fs.readFileSync(path.join(output,'fixture-media',name)):null;
    if(!data)throw Error('Unknown fixture');res.setHeader('Content-Type','image/png');res.end(data);
   }catch{res.writeHead(404);res.end();}return;
  }
  const name=url.pathname.startsWith('/assets/')?url.pathname.slice(8):url.pathname.slice(1);
  const base=url.pathname.startsWith('/assets/')?assets:path.join(__dirname,'third-party/free-my-tv/upstream');
  if(!/^[a-zA-Z0-9_./-]+$/.test(name)||name.split('/').includes('..')){res.writeHead(404);res.end();return;}
  const target=path.join(base,name);
  try{
   const data=fs.readFileSync(target);res.setHeader('Content-Type',name.endsWith('.css')?'text/css':name.endsWith('.ttf')?'font/ttf':name.endsWith('.png')?'image/png':'text/javascript');res.end(data);
  }catch{res.writeHead(404);res.end();}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{
  const views=['home','settings','drawer','apps','language','shelf','night'];
  if(live)views.push('live-home','live-movies','live-shows','live-drawer','live-settings','live-night','live-saver');
  const selected=process.argv[4]?process.argv[4].split(','):views;
  if(selected.some(view=>!views.includes(view)))throw Error('Unknown or unavailable comparison view');
  for(const view of selected)for(const native of [false,true]){
   const label=(native?'native-':'reference-')+view,profile=fs.mkdtempSync(path.join(os.tmpdir(),'fmtv-chrome-'));
   const target=path.join(output,label+'.png');
   const {stdout}=await run('/usr/bin/chromium',['--headless=new','--disable-gpu','--no-proxy-server','--no-first-run',
    '--user-data-dir='+profile,'--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1',
    '--window-size=1920,1080','--force-device-scale-factor=1','--hide-scrollbars','--virtual-time-budget=3000',
    '--screenshot='+target,'--dump-dom','http://127.0.0.1:'+server.address().port+'/preview?native='+(native?'1':'0')+'&view='+view],
    {timeout:30000,maxBuffer:4*1024*1024,env:{...process.env,TZ:'UTC'}});
   const canvas=/data-test-canvas="data:image\/png;base64,([A-Za-z0-9+/=]+)"/.exec(stdout);
   if(canvas)fs.writeFileSync(path.join(output,label+'.canvas.png'),Buffer.from(canvas[1],'base64'));
   const error=/data-test-error="([^"]+)"/.exec(stdout);
   if(error||!stdout.includes('data-test-ready="true"')||!fs.existsSync(target))throw Error(label+': '+(error?error[1]:'render readiness missing'));
   fs.rmSync(profile,{recursive:true,force:true});
   console.log(label+' rendered');
  }
  console.log('Visual artifacts: '+output);
 }finally{server.close();}
}
if(require.main===module)main().catch(error=>{console.error(error.message);process.exitCode=1;});
module.exports={page};
