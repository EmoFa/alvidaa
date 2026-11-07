'use strict';
// Build-time changes to the pinned web presentation. Keep upstream files pristine.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const vm=require('node:vm');
const ROOT='#alvidaa-web-home';
const PREFIX='fmtv-web-';
const DIR=path.join(__dirname,'third-party/free-my-tv/upstream');
function replaceOnce(source,before,after){
  if(source.split(before).length!==2)throw Error('Pinned upstream compatibility anchor changed');
  return source.replace(before,after);
}
function readSources(){
  let manifest;
  try { manifest=JSON.parse(fs.readFileSync(path.join(DIR,'MANIFEST.json'),'utf8')); }
  catch { throw Error('Cannot read pinned upstream manifest'); }
  const sources={};
  for(const [name,digest] of Object.entries(manifest.files)){
    const bytes=fs.readFileSync(path.join(DIR,name));
    if(crypto.createHash('sha256').update(bytes).digest('hex')!==digest)throw Error('Upstream integrity mismatch: '+name);
    if(/\.(js|html|css)$/.test(name))sources[name]=bytes.toString('utf8');
  }
  return sources;
}
function scopeCSS(input){
  let css=input.replace(/\/\*[\s\S]*?\*\//g,'').replace(/@font-face\s*\{[^}]*\}/g,'');
  if(css.includes('@'))throw Error('Unexpected upstream CSS at-rule');
  css=css.replace(/([^{}]+)\{([^{}]*)\}/g,(_rule,selectors,body)=>{
    const scoped=selectors.trim().split(',').map(value=>{
      let selector=value.trim().replace(/#([\w-]+)/g,'#'+PREFIX+'$1')
        .replace(/(^|[\s>+~,(])(img|svg|canvas)(?=$|[\s.#:[>+~,])/g,(_m,boundary,tag)=>
          boundary+{'img':'[data-fmtv-image]','svg':'[data-fmtv-vector]','canvas':'[data-fmtv-backdrop]'}[tag]);
      if(/^(html|body)\b/.test(selector))return selector.replace(/^(html|body)\b/,ROOT);
      if(/^\.(night|drawer-open|no-picks)\b/.test(selector))return ROOT+selector;
      return ROOT+' '+selector;
    });
    return [...new Set(scoped)].join(',')+'{'+body.replace(/'Inter'/g,"'FMTVWeb32'")
      .replace(/object-fit\s*:/g,'background-size:').replace(/\bfill\s*:/g,'color:')
      .replace(/border-radius\s*:\s*([^;]+);/g,(_m,radius)=>['top-left','top-right','bottom-right','bottom-left'].map(corner=>'border-'+corner+'-radius:'+radius+';').join(''))+'}';
  });
  return css;
}
function template(input){
  const start=input.indexOf('<div id="stage">'),end=input.indexOf('<script src="config.js">');
  if(start<0||end<start)throw Error('Upstream body boundary changed');
  return input.slice(start,end).trim().replace(/id="([\w-]+)"/g,'id="'+PREFIX+'$1"')
    .replace(/<canvas id="([^"]+)" width="48" height="27"><\/canvas>/g,'<div id="$1" data-fmtv-backdrop="true"></div>');
}
function templateTree(html){
  const roots=[],stack=[{children:roots}];
  const tags=new Set(['div','span','h1','h2']);
  let end=0;
  for(const match of html.matchAll(/<(\/?)([a-z0-9]+)([^>]*)>/g)){
    if(html.slice(end,match.index).trim())throw Error('Unexpected template text');
    end=match.index+match[0].length;
    const [,closing,tag,raw]=match;
    if(!tags.has(tag))throw Error('Unexpected template element');
    if(closing){if(raw.trim()||stack.length<2||stack.pop().tag!==tag)throw Error('Unbalanced template');continue;}
    const attrs={};
    const remainder=raw.replace(/([a-z][a-z0-9-]*)="([^"]*)"/g,(_all,key,value)=>{
      if(!['id','class','data-fmtv-backdrop'].includes(key))throw Error('Unexpected template attribute');
      attrs[key]=value;return '';
    });
    if(remainder.trim())throw Error('Malformed template attribute');
    const node={tag,attrs,children:[]};stack[stack.length-1].children.push(node);stack.push(node);
  }
  if(stack.length!==1||html.slice(end).trim())throw Error('Unbalanced template');
  return roots;
}
function dataSource(source){
  // Upstream persists a token suffix in its cache stamp. Do not copy even a
  // partial credential into browser-readable cache files.
  return replaceOnce(source,"KEY.length + ':' + KEY.slice(-6) + ':' + REGION","'native:' + REGION");
}
const HYDRATE=`
    nativeSnapshot: function (values, error, keyConfigured) {
      KEY = keyConfigured ? 'eyJ.native-worker' : '';
      function read(key) { try { return JSON.parse(values['fmtv.' + key] || 'null'); } catch (e) { return null; } }
      var w = read('weather'), p = read('prices'), r = read('recs');
      if (w && w.place === PLACE) { weather = parseWeather(w.body); weatherAt = w.at; }
      if (p && p.quote === QUOTE && parsePrices(p.body)) pricesAt = p.at;
      if (r) { picks = r.picks || []; listAt = r.listAt || 0; period = r.period; listLang = r.lang || ''; stamp = r.stamp || ''; }
      recsError = error || ''; changed();
    },
`;
function buildProgram(){
  const s=readSources();
  const {buildLocales,localizer}=require('./native-web-locale.cjs');
  const localeSource='var NativeLocale=('+localizer.toString()+')('+JSON.stringify(buildLocales(s))+');';
  let strings=s['strings.js'];
  strings=replaceOnce(strings,'  function name(d, loc, options) {','  function name(d, loc, options) { return NativeLocale.dateName(d, loc, options);');
  strings=replaceOnce(strings,'  function month(d, loc, withDay) {','  function month(d, loc, withDay) { return NativeLocale.month(d, loc, withDay);');
  strings=replaceOnce(strings,'  function dayPeriod(d, loc) {','  function dayPeriod(d, loc) { return NativeLocale.period(d, loc);');
  let data=dataSource(s['data.js']);
  data=replaceOnce(data,'v.toLocaleString(I18N.locale(), {minimumFractionDigits: digits, maximumFractionDigits: digits})','NativeLocale.number(v, digits, I18N.locale())');
  data=replaceOnce(data,'    COINS: COINS,',HYDRATE+'    COINS: COINS,');
  let home=s['home.js'];
  for(const [before,after] of [
    ['  function sym(name, parent, size) {','  function sym(name, parent, size) {\n    if (Native) return Native.symbol(name, parent, size);'],
    ['  function coin(i, parent) {','  function coin(i, parent) {\n    if (Native) return Native.coin(i, parent);'],
    ['  function lift(img) {','  function lift(img) {\n    if (Native) return Native.lift(img);'],
    ['  function showSaver() {','  function showSaver() {\n    if (document.hidden) return;'],
    ["      var canvas = $(next), ctx = canvas.getContext('2d');\n      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);",
     "      var canvas = $(next);\n      Native.backdrop(canvas, url);"],
    ["      w.id = 'weather';","      w.id = '"+PREFIX+"weather';"],
    ["      q.id = 'prices';","      q.id = '"+PREFIX+"prices';"],
    ['  function setClass(e, c, on) {','  function setClass(e, c, on) {\n    if (Native) Native.invalidate();']
  ])home=replaceOnce(home,before,after);
  home=replaceOnce(home,'  // For the browser preview and tests.',
    `  Native.refreshMedia = function () { cards = []; renderCards(); renderShelf(); renderDrawer(); if (st.zone === Z.APPS) renderApps(); updateFocus(); };
  Native.refreshApps = function () { loadApps(function () { st.shelf = Math.min(st.shelf, Math.max(0, shelf.length - 1)); st.grid = Math.min(st.grid, Math.max(0, others.length - 1)); renderAll(); if (st.zone === Z.APPS) renderApps(); Data.refresh(); }); };
  Native.openInputs = function () { reset(); openDrawer(); st.drawer = 0; updateFocus(); };
  // For the browser preview and tests.`);
  const prelude=`function(window, Native) {
    var document=window.document, navigator=window.navigator, localStorage=window.localStorage;
    var Image=window.Image, XMLHttpRequest=window.XMLHttpRequest;
    var setTimeout=window.setTimeout, clearTimeout=window.clearTimeout;
    var setInterval=window.setInterval, clearInterval=window.clearInterval;
    var TV=Native.TV;
  `;
  const wiring=`
    var nativeApps = [], originalSetApps = Data.setApps;
    Data.setApps = function(apps) { nativeApps=apps; originalSetApps(apps); };
    Data.refresh = function() { Native.context({apps:nativeApps, zone:TV.zone(),
      language:navigator.language, prefs:localStorage.getItem('fmtv.prefs') || '{}'}); };
    Data.settingsChanged = function() { Data.refresh(); };
    Data.image = function(path, size) { return Native.image(path, size || 'w1280'); };
    Native.attach({Data:Data, Prefs:Prefs, I18N:I18N});
  `;
  const source=prelude+[localeSource,s['coins.js'],s['i18n.js'],strings,s['zones.js'],'window.ZONES=ZONES;',data,wiring,home].join('\n')+
    '\nreturn {Data:Data, Prefs:Prefs, I18N:I18N, control:window.FreeMyTV};\n}';
  new vm.Script('('+source+')');
  const html=template(s['index.html']);
  return {source,css:scopeCSS(s['home.css']),html,tree:templateTree(html)};
}
module.exports={buildProgram,scopeCSS,template,templateTree,dataSource,readSources,replaceOnce};
