'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const install=require('./native-settings-theme.js');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{execFileSync}=require('node:child_process');
function host(factory){
 const nodes=new Map();const head={appendChild(node){nodes.set(node.id,node);node.parentNode=head;},removeChild(node){nodes.delete(node.id);}};
 return {_V_M_:factory?{setting:factory}:{},document:{head,createElement(){return {};},getElementById(id){return nodes.get(id);}},AlvidaaNativeWebBundle:{fontCSS:'/* test font faces */'}};
}
test('settings skin preserves factory identity, route guards, native children and handlers',async()=>{
 const children=[{component:'first-level'},{component:'high-level'}],handler=()=>{},guard=()=>{},init=()=>{};
 const component={name:'settings',methods:{handleKeydown:handler},render(){return {data:{class:['settingContent',{settingMainMove:true}],on:{'key-down':handler}},children};}};
 const originalRender=component.render,other=()=>Promise.resolve({});
 const exported={};Object.defineProperty(exported,'default',{get:()=>component});
 const loader=()=>Promise.resolve(exported),meta={vk:'T'};
 const route={path:'/setting/settings',component:loader,beforeEnter:guard,meta};
 const stock={init,route:[route,{path:'/media/Subtitle',component:other}]};
 const factory=()=>stock,h=host(factory),theme=install(h);
 assert.equal(h._V_M_.setting(),stock);assert.equal(stock.init,init);assert.equal(route.beforeEnter,guard);assert.equal(route.meta,meta);
 assert.equal(stock.route[1].component,other);assert.equal(await route.component(),exported);
 const node=component.render();assert.equal(node.children,children);assert.equal(node.children.length,2);
 assert.equal(node.data.on['key-down'],handler);assert.equal(component.methods.handleKeydown,handler);
 assert.deepEqual(node.data.class,[['settingContent',{settingMainMove:true}],'fmtv-advanced',{'fmtv-light':false}]);
 const css=h.document.getElementById('alvidaa-settings-style').textContent;
 assert.ok(css.includes('FMTVWeb32'));assert.ok(!/\b(?:display|visibility|position|transform|opacity|width|height|z-index)\s*:/.test(css));
 assert.ok(css.includes('.v-c1:not([class*="v-c-"]):not([class*="error"]):not([class*="warn"]):not([style*="color"]){color:#202428!important;}'));
 assert.ok(!css.includes('color:inherit!important'),'generic text roles must not mask semantic colors');
 for(const match of css.replace(/\/\*[\s\S]*?\*\//g,'').matchAll(/([^{}]+)\{[^{}]*\}/g)){
  for(const selector of match[1].split(','))assert.ok(selector.includes('body.v-normal-contrast'),'native high contrast must bypass the skin');
 }
 assert.ok(!css.includes('.fmtv-advanced.fmtv-advanced.fmtv-advanced{background:'),'do not put an opaque surface behind native transparency');
 theme.remove();assert.equal(route.component,loader);assert.equal(component.render,originalRender);assert.equal(h._V_M_.setting,factory);
 assert.equal(h.document.getElementById('alvidaa-settings-style'),undefined);
});
test('desktop CSS cascade preserves semantic colors, transparency and native high contrast',{skip:!fs.existsSync('/usr/bin/chromium')},async t=>{
 const component={render(){return {data:{},children:[]};}},route={path:'/setting/settings',component:()=>Promise.resolve(component)};
 const h=host(()=>({route:[route]})),theme=install(h);t.after(()=>theme.remove());
 h._V_M_.setting();await route.component();component.render();
 const css=h.document.getElementById('alvidaa-settings-style').textContent;
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'fmtv-settings-css-'));t.after(()=>fs.rmSync(directory,{recursive:true,force:true}));
 const html=`<!doctype html><style>
 .v-c1{color:#f3f4f5}.v-bg1{background:#0f1110}.v-opacity-low{opacity:.95}
 .v-c-error,.warning{color:rgb(200,0,0)}#disabled{opacity:.5}
 .v-high-contrast .v-c1{color:white}.v-high-contrast .v-bg1{background:black}
 </style><style>${css}</style><body class="v-normal-contrast">
 <div id="root" class="fmtv-advanced fmtv-light"><div id="panel" class="highLevelContent v-bg1 v-opacity-low">
 <span id="primary" class="item__txt v-c1">Primary</span><span id="error" class="item__txt v-c1 v-c-error v-c-highlight v-i-selected">Error</span>
 <span id="warning" class="item__txt v-c1 warning v-i-selected">Warning</span><span id="inline" class="item__txt v-c1" style="color:rgb(0,80,200)">Semantic inline</span>
 <span id="disabled" class="item__txt v-c1">Disabled</span></div></div><script>
 function state(){const out={};for(const id of ['root','panel','primary','error','warning','inline','disabled']){const s=getComputedStyle(document.getElementById(id));out[id]={color:s.color,background:s.backgroundColor,image:s.backgroundImage,opacity:s.opacity};}return out;}
 const normal=state();document.body.className='v-high-contrast';const high=state();document.body.innerHTML='<pre>'+JSON.stringify({normal,high})+'</pre>';
 </script>`;
 const source=path.join(directory,'index.html');fs.writeFileSync(source,html);
 const output=execFileSync('/usr/bin/chromium',['--headless=new','--disable-gpu','--disable-background-networking','--no-first-run','--no-proxy-server','--host-resolver-rules=MAP * ~NOTFOUND','--user-data-dir='+path.join(directory,'profile'),'--dump-dom','file://'+source],{encoding:'utf8',timeout:20000,maxBuffer:1024*1024,stdio:['ignore','pipe','ignore']});
 const match=output.match(/<pre>([^<]+)<\/pre>/);assert.ok(match,'browser did not return computed styles');
 let result;try{result=JSON.parse(match[1]);}catch{assert.fail('browser returned invalid style data');}
 assert.equal(result.normal.primary.color,'rgb(32, 36, 40)');
 assert.equal(result.normal.error.color,'rgb(200, 0, 0)');assert.equal(result.normal.warning.color,'rgb(200, 0, 0)');
 assert.equal(result.normal.inline.color,'rgb(0, 80, 200)');assert.equal(result.normal.disabled.opacity,'0.5');
 assert.equal(result.normal.panel.opacity,'0.95');assert.equal(result.normal.root.background,'rgba(0, 0, 0, 0)');
 assert.equal(result.high.primary.color,'rgb(255, 255, 255)');assert.equal(result.high.panel.background,'rgb(0, 0, 0)');assert.equal(result.high.panel.image,'none');
});
test('late-loaded settings factories keep their calling convention and survive teardown',async()=>{
 const h=host(),theme=install(h);let received;
 const component={render(){return {children:[]};}},stock={route:[{path:'/setting/settings',component:()=>Promise.resolve(component)}]};
 function factory(value){received=[this,value];return stock;}
 h._V_M_.setting=factory;assert.equal(h._V_M_.setting('native'),stock);assert.deepEqual(received,[h._V_M_,'native']);
 await stock.route[0].component();assert.ok(component.render().data.class.includes('fmtv-advanced'));
 theme.remove();assert.equal(h._V_M_.setting,factory);assert.equal(Object.getOwnPropertyDescriptor(h._V_M_,'setting').get,undefined);
});
test('an in-flight local module load cannot reapply the theme after teardown',async()=>{
 let resolve;const promise=new Promise(r=>{resolve=r;});const component={render(){return {children:[]};}},original=component.render;
 const stock={route:[{path:'/setting/settings',component:()=>promise}]},h=host(()=>stock),theme=install(h);
 const pending=stock.route[0].component();theme.remove();resolve({default:component});await pending;
 assert.equal(component.render,original);assert.equal(h.document.getElementById('alvidaa-settings-style'),undefined);
});
test('all owned settings routes are decorated lazily without loading other dialogs',async()=>{
 let calls=0;
 const component={render(){return {data:{class:'native-dialog'},children:[]};}};
 const lazy=()=>{calls++;return Promise.resolve(component);};
 const relative={path:'PinDialog',component:lazy};
 const route={path:'/Setting/network/details',component:lazy,children:[relative]};
 const h=host(()=>({route:[route]})),theme=install(h);
 assert.equal(calls,0,'unvisited dialogs must not be loaded at startup');
 await relative.component();assert.equal(calls,1);
 assert.ok(component.render().data.class.includes('fmtv-advanced'));
 theme.remove();assert.equal(relative.component,lazy);assert.equal(route.component,lazy);
});
test('light/dark preferences and shared cached VNodes remain scoped to Settings',async()=>{
 const vnode={data:{class:'vendor'},children:[]},component={render(){return vnode;}},original=component.render;
 const route={path:'/setting/dialog',component:()=>Promise.resolve(component)};
 const h=host(()=>({route:[route]})),theme=install(h);let current='/setting/dialog',mode='light';
 theme.configure({route:()=>current,preferences:()=>JSON.stringify({theme:mode})});
 await route.component();component.render();assert.equal(vnode.data.class[2]['fmtv-light'],true);
 mode='dark';component.render();assert.deepEqual(vnode.data.class,['vendor','fmtv-advanced',{'fmtv-light':false}]);
 mode='auto';theme.setNightResolver(()=>false);component.render();assert.equal(vnode.data.class[2]['fmtv-light'],true);
 current='/launcher';component.render();assert.equal(vnode.data.class,'vendor');
 current='/setting/dialog';component.render();theme.remove();assert.equal(vnode.data.class,'vendor');assert.equal(component.render,original);
});
test('unknown registry descriptors are left untouched',()=>{
 const h=host();Object.defineProperty(h._V_M_,'setting',{value:()=>({}),configurable:false});
 assert.equal(install(h),null);
});
