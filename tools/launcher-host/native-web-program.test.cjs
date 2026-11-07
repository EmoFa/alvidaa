'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const {buildProgram,templateTree,scopeCSS,dataSource,readSources}=require('./native-web-program.cjs');
const {createEngine}=require('./native-feed-engine.cjs');
test('compiles actual upstream presentation with isolated IDs and a safe static DOM tree',()=>{
 const p=buildProgram();assert.equal(typeof new vm.Script('('+p.source+')').runInNewContext(),'function');
 assert.equal(p.tree.length,1);assert.equal(p.tree[0].attrs.id,'fmtv-web-stage');
 assert.ok(p.source.includes('function renderSettings()'));assert.ok(p.source.includes('function renderShelfEdit()'));
 assert.ok(!p.html.includes('<canvas'));assert.ok(p.css.includes('#alvidaa-web-home.night #fmtv-web-sky'));
 assert.ok(p.css.includes('[data-fmtv-vector]'));assert.ok(!p.css.includes("font-family: 'Inter'"));
 assert.ok(!p.source.includes('KEY.slice(-6)'));assert.ok(p.source.includes('st.zone === Z.APPS'));
});
test('the autonomous web screensaver cannot start under another native route',()=>{
 const source=buildProgram().source,start=source.indexOf('  function showSaver() {'),end=source.indexOf('  function hideSaver()',start);
 assert.ok(start>=0&&end>start);
 const saver=new vm.Script(source.slice(start,end)+'\nshowSaver();');
 assert.doesNotThrow(()=>saver.runInNewContext({document:{hidden:true}}));
 assert.throws(()=>saver.runInNewContext({document:{hidden:false}}),/saverPhotos/);
});
test('CSS scoping preserves image class selectors and root clock states',()=>{
 const css=scopeCSS('.card .img {height: 500px;} .card img {width: 100%;} .no-picks #clock {display:block;}');
 assert.ok(css.includes('#alvidaa-web-home .card .img{height: 500px;}'));
 assert.ok(css.includes('.card [data-fmtv-image]'));assert.ok(!css.includes('.[data-fmtv-image]'));
 assert.ok(css.includes('#alvidaa-web-home.no-picks #fmtv-web-clock'));
});
test('template compiler refuses executable or unbalanced markup',()=>{
 for(const html of ['<script></script>','<div onclick="bad()"></div>','<div><span></div>','<div>unexpected</div>'])assert.throws(()=>templateTree(html));
 assert.throws(()=>scopeCSS('@media screen {body{color:red}}'),/at-rule/);
});
test('source cache stamp never includes even a token suffix',()=>{
 const source=dataSource(readSources()['data.js']);
 assert.ok(source.includes("var s = 'native:' + REGION"));assert.ok(!source.includes('KEY.slice(-6)'));
});
test('off-browser engine uses upstream filtering and publishes no credential fragments',async()=>{
 const token='eyJ.fake.private.secret-X9Y8Z7',requests=[];
 const engine=createEngine({token,context:{zone:'Australia/Brisbane',language:'en-AU',prefs:'{}',apps:[{id:'app:1',title:'Netflix'}]},
  request:async(url,options)=>{
   requests.push(url);assert.equal(options.token,token);assert.ok(!url.includes(token));
   if(url.includes('open-meteo'))return {status:503,body:null};
   if(url.includes('binance'))return {status:400,body:null};
   if(url.includes('/watch/providers/'))return {status:200,body:{results:[{provider_id:8,provider_name:'Netflix'}]}};
   return {status:200,body:{results:[]}};
  }});
 engine.refresh();await new Promise(resolve=>setImmediate(resolve));
 const state=engine.snapshot();assert.equal(state.pending,0);assert.equal(state.city,'Brisbane');
 assert.ok(requests.some(url=>url.includes('with_watch_providers=8')));
 assert.ok(state.cache['fmtv.recs']);assert.ok(!JSON.stringify(state).includes(token));
 assert.ok(!JSON.stringify(state).includes('X9Y8Z7'));engine.stop();
});
test('unknown TV timezone does not silently request New York weather or US picks',async()=>{
 const requests=[];const engine=createEngine({token:'eyJ.fake',context:{zone:'',apps:[],prefs:'{"quotes":false}'},request:async url=>{
  requests.push(url);return {status:200,body:{results:[]}};
 }});
 engine.refresh();await new Promise(resolve=>setImmediate(resolve));
 assert.deepEqual(requests,[]);assert.equal(engine.snapshot().locationKnown,false);engine.stop();
});
test('legacy upstream token-suffix stamps are removed before publishing cached recommendations',()=>{
 const engine=createEngine({token:'eyJ.fake',context:{zone:'Australia/Brisbane',apps:[]},
  cache:{'fmtv.recs':JSON.stringify({picks:[],stamp:'500:SECRET:AU11111111111'})}});
 assert.ok(!engine.snapshot().cache['fmtv.recs'].includes('SECRET'));engine.stop();
});
