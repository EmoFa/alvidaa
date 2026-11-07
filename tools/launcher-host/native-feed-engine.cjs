'use strict';
// Run the pinned upstream data logic off-browser; publish only its data caches.
const vm=require('node:vm');
const {readSources,dataSource}=require('./native-web-program.cjs');
const {canonical,requestJson}=require('./native-feed-http.cjs');
const CACHE_KEYS=new Set(['fmtv.weather','fmtv.prices','fmtv.recs']);
function createEngine(options){
  const sources=options.sources||readSources();
  const context=options.context;
  if(!context||!Array.isArray(context.apps)||context.apps.length>512)throw Error('Invalid native feed context');
  const apps=context.apps.map(app=>{
    if(typeof app.id!=='string'||app.id.length>256||typeof app.title!=='string'||app.title.length>512)throw Error('Invalid native app metadata');
    return {id:app.id,title:app.title};
  });
  let stopped=false,pending=0;
  const values=Object.create(null),timers=new Set();
  for(const key of CACHE_KEYS){
    const value=options.cache&&options.cache[key];
    if(typeof value==='string'&&value.length<=2*1024*1024)values[key]=value;
  }
  values['fmtv.prefs']=typeof context.prefs==='string'?context.prefs:'{}';
  const token=options.token||'';
  let sandbox;
  function changed(){if(!stopped&&options.onChange)options.onChange();}
  function XHR(){this.readyState=0;this.status=0;this.responseText='';this.cancelled=false;}
  XHR.prototype.open=function(method,url){if(method!=='GET')throw Error('Feed method rejected');this.endpoint=canonical(url);};
  XHR.prototype.setRequestHeader=function(){}; // Authentication comes from private worker configuration only.
  XHR.prototype.abort=function(){this.cancelled=true;};
  XHR.prototype.send=function(){
    const xhr=this;
    if(stopped)return;
    pending++;
    const endpoint=xhr.endpoint;
    const knownZone=!!sandbox.window.ZONES[context.zone];
    const allowed=endpoint.service==='prices'||knownZone;
    Promise.resolve().then(()=>allowed?(options.request||requestJson)(endpoint.key,{token}):{status:503,body:null}).then(result=>{
      if(stopped||xhr.cancelled)return;
      xhr.status=result.status; xhr.responseText=result.body?JSON.stringify(result.body):'';xhr.readyState=4;
      if(xhr.onreadystatechange)xhr.onreadystatechange();
    }).catch(()=>{
      if(stopped||xhr.cancelled)return;
      xhr.status=503;xhr.readyState=4;if(xhr.onerror)xhr.onerror();
    }).finally(()=>{pending--;changed();});
  };
  const window={CONFIG:{tmdbKey:token,tmdbRegion:'',latitude:'',longitude:'',city:'',language:'auto',
    currency:'',temperature:'auto',showCrypto:true,hideAnimation:false,hideApps:[],shelfApps:[]}};
  sandbox={window,document:{documentElement:{}},navigator:{language:context.language||'en-AU'},
    TV:{zone:()=>context.zone||''},XMLHttpRequest:XHR,
    localStorage:{getItem:key=>values[key]||null,setItem:(key,value)=>{
      if(!CACHE_KEYS.has(key))return;
      if(typeof value!=='string'||value.length>2*1024*1024)throw Error('Feed cache exceeds size limit');
      if(token&&value.includes(token))throw Error('Credential-bearing feed cache rejected');
      values[key]=value;changed();
    }},setTimeout:(callback,delay)=>{
      const id=setTimeout(()=>{timers.delete(id);if(!stopped)callback();},delay);timers.add(id);return id;
    },clearTimeout:id=>{clearTimeout(id);timers.delete(id);}};
  vm.createContext(sandbox);
  const code=[sources['i18n.js'],sources['strings.js'],sources['zones.js'],'window.ZONES=ZONES;',dataSource(sources['data.js']),
    'I18N.set(Prefs.language());'].join('\n');
  new vm.Script(code,{filename:'pinned-free-my-tv-data.js'}).runInContext(sandbox,{timeout:3000});
  sandbox.Data.setApps(apps);
  sandbox.Data.onChange(changed);
  return {
    refresh(){if(!stopped)sandbox.Data.refresh();},
    snapshot(){
      const cache={};
      for(const key of CACHE_KEYS){
        if(!values[key]||(token&&values[key].includes(token)))continue;
        if(key==='fmtv.recs'){
          try{
            const recs=JSON.parse(values[key]);
            if(typeof recs.stamp!=='string'||!/^native:[A-Z]{2}(:no-animation)?[01]{11}$/.test(recs.stamp))delete recs.stamp;
            cache[key]=JSON.stringify(recs);
          }catch{/* Do not publish malformed persisted cache data. */}
        }else cache[key]=values[key];
      }
      return {version:1,keyConfigured:!!token,locationKnown:!!window.ZONES[context.zone],
        city:sandbox.Place.city,cache,error:sandbox.Data.recsError(),pending};
    },
    stop(){stopped=true;for(const id of timers)clearTimeout(id);timers.clear();}
  };
}
module.exports={createEngine,CACHE_KEYS};
