'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const {readSources}=require('./native-web-program.cjs');
const {buildLocales,localizer}=require('./native-web-locale.cjs');
const sources=readSources(),tables=buildLocales(sources),native=localizer(tables);
test('native date names and day periods match Intl for every pinned language',()=>{
 for(const locale of Object.keys(tables)){
  for(let month=0;month<12;month++){
   const date=new Date(2026,month,17,12);
   for(const length of ['short','long'])assert.equal(native.dateName(date,locale,{month:length}),date.toLocaleDateString(locale,{month:length}),locale);
   const plain=date.toLocaleDateString(locale,{month:'long'}),both=date.toLocaleDateString(locale,{month:'long',day:'numeric'});
   const rest=both.replace(/(^|\s)17\.?(?=\s|$)/,' ').trim();
   assert.equal(native.month(date,locale,true),!rest||rest===both||rest.split(/\s+/).includes(plain)?plain:rest,locale);
  }
  for(let day=0;day<7;day++){
   const date=new Date(2026,0,4+day,12);
   for(const length of ['short','long'])assert.equal(native.dateName(date,locale,{weekday:length}),date.toLocaleDateString(locale,{weekday:length}),locale);
  }
  for(let hour=0;hour<24;hour++){
   const date=new Date(2026,0,17,hour),parts=new Intl.DateTimeFormat(locale,{hour:'numeric',hour12:true}).formatToParts(date);
   assert.equal(native.period(date,locale),parts.find(p=>p.type==='dayPeriod')?.value||(hour<12?'AM':'PM'),locale);
  }
 }
});
test('scoped number formatting matches Intl rounding, grouping and localized separators',()=>{
 const values=[0,-0,1,-1,1.005,-1.005,1.9999,9.999,999.5,9999.999,1e-10,1e25,123456789.125,Infinity,-Infinity,NaN];
 for(let i=0;i<200;i++)values.push((i*1234567.12345)%98765.4321);
 for(const locale of Object.keys(tables))for(const value of values)for(const digits of [0,1,2])
  assert.equal(native.number(value,digits,locale),value.toLocaleString(locale,{minimumFractionDigits:digits,maximumFractionDigits:digits}),locale+' '+value+' '+digits);
});
test('locale adapter runs without Intl and does not change Date or Number prototypes',()=>{
 const sandbox={Intl:undefined,tables};vm.createContext(sandbox);
 const value=new vm.Script('var before=Date.prototype.toLocaleDateString;var n=('+localizer.toString()+')(tables);[n.dateName(new Date(2026,10,7),"en-US",{weekday:"long"}),n.number(1234.567,2,"en-US"),before===Date.prototype.toLocaleDateString]').runInContext(sandbox);
 assert.deepEqual(Array.from(value),['Saturday','1,234.57',true]);
});
