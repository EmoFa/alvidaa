#!/usr/bin/env node
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const {STOCK_HASH}=require('./build-native.cjs');
const {buildProgram}=require('./native-web-program.cjs');
function hash(data){return crypto.createHash('sha256').update(data).digest('hex');}
function bundle(assetsDirectory){
  const bytes=fs.readFileSync(path.join(assetsDirectory,'assets.json'));
  let assets;
  try{assets=JSON.parse(bytes);}catch{throw Error('Invalid native asset manifest');}
  for(const [name,digest] of Object.entries(assets.files)){
    assert.ok(!path.isAbsolute(name)&&!name.split('/').includes('..'),'Unsafe asset path');
    assert.equal(hash(fs.readFileSync(path.join(assetsDirectory,name))),digest,'Native asset integrity mismatch');
  }
  const assetId=hash(bytes).slice(0,20);
  const assetBase='file:///hisenseUI/var/local/free-my-tv/assets/'+assetId+'/';
  const p=buildProgram();
  const fontCSS=fs.readFileSync(path.join(assetsDirectory,'fonts.css'),'utf8').replace(/url\(([^)]+)\)/g,(_all,url)=>'url("'+assetBase+url+'")');
  const data={tree:p.tree,css:p.css,fontCSS,assetBase,assetId,assets:{colors:assets.colors,symbols:assets.symbols}};
  return {assetId,source:'self.AlvidaaNativeWebBundle='+JSON.stringify(data)+';\nself.AlvidaaNativeWebBundle.run='+p.source+';\n'};
}
function build(stockFile,assetsDirectory,output){
  const stock=fs.readFileSync(stockFile);assert.equal(hash(stock),STOCK_HASH,'Wrong original firmware launcher');
  const web=bundle(assetsDirectory);
  const license=fs.readFileSync(path.join(__dirname,'third-party/free-my-tv/LICENSE'),'utf8');
  const files=['native-platform.js','native-web-tv.js','native-web-screensaver.js','native-web-scope.js','native-web-compat.js','native-web-runtime.js','native-settings-theme.js','native-entry.js'];
  const candidate='/* ALVIDAA_FREE_MY_TV_NATIVE_V1; ALVIDAA_FREE_MY_TV_WEB_PARITY_V2\n'+license+'\n*/\n'+stock+'\n;\n'+web.source+
    files.map(file=>fs.readFileSync(path.join(__dirname,file),'utf8')).join('\n;\n');
  new vm.Script(candidate,{filename:'native-web-candidate.js'});
  if(output){
    const target=path.resolve(output),privateRoot=path.resolve(__dirname,'../../firmware')+path.sep;
    assert.ok(target.startsWith(privateRoot)||target.startsWith('/tmp/'),'Firmware-containing output must remain private');
    fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,candidate,{mode:0o600});fs.chmodSync(target,0o600);
  }
  return {candidate,assetId:web.assetId,sha256:hash(candidate)};
}
if(require.main===module){
  const [stock,assets,output]=process.argv.slice(2);
  assert.ok(stock&&assets&&output,'Usage: build-native-web.cjs private-stock.js asset-directory private-output.js');
  const result=build(stock,assets,output);console.log('Built upstream web candidate:',result.sha256,'assets:',result.assetId);
}
module.exports={build,bundle};
