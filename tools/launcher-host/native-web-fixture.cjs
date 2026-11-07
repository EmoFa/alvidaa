'use strict';
// Synthetic artwork and caches only: no credentials, live responses or copyrighted stills.
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib');
const {createMedia}=require('./native-feed-images.cjs');
const NOW=Date.UTC(2026,10,7,14,30);
function png(seed){
 const width=640,height=360,raw=Buffer.alloc((width*4+1)*height);
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){
  const offset=y*(width*4+1)+1+x*4;
  raw[offset]=(seed*47+Math.floor(x*96/width))%256;
  raw[offset+1]=(seed*61+Math.floor(y*96/height))%256;
  raw[offset+2]=(Math.floor(x/80)+Math.floor(y/60))%2?160:64;raw[offset+3]=255;
 }
 function chunk(name,data){
  const bytes=Buffer.concat([Buffer.from(name),data]);let crc=0xffffffff;
  for(const byte of bytes){crc^=byte;for(let bit=0;bit<8;bit++)crc=(crc>>>1)^((crc&1)?0xedb88320:0);}
  const header=Buffer.alloc(4),tail=Buffer.alloc(4);header.writeUInt32BE(data.length);tail.writeUInt32BE((crc^0xffffffff)>>>0);
  return Buffer.concat([header,bytes,tail]);
 }
 const header=Buffer.alloc(13);header.writeUInt32BE(width);header.writeUInt32BE(height,4);header[8]=8;header[9]=6;
 return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),chunk('IHDR',header),chunk('IDAT',zlib.deflateSync(raw)),chunk('IEND',Buffer.alloc(0))]);
}
async function fixture(directory,processor){
 if(!processor)throw Error('Live-content comparisons require NATIVE_IMAGE_HELPER (host build)');
 fs.mkdirSync(directory,{recursive:true});
 const originals={},picks=[];
 for(let index=0;index<6;index++){
  const name='fixture-'+index+'.png';originals[name]=png(index+1);
  picks.push({id:'fixture-'+index,kind:index<3?'movie':'tv',title:['Aurora','Harbour','Orbit','Woodland','Meridian','Voyage'][index],
   meta:'2026 · Adventure · 1h 42m',backdrop:'/'+name,app:'netflix',detailed:false});
 }
 const cache={
  'fmtv.recs':JSON.stringify({picks,listAt:NOW,period:1,lang:'en',stamp:'fixture'}),
  'fmtv.weather':JSON.stringify({place:'-27.47,153.03',at:NOW,body:{utc_offset_seconds:0,
   current:{temperature_2m:24.6,weather_code:2,is_day:1},
   daily:{temperature_2m_max:[29],temperature_2m_min:[18],sunrise:['2026-11-07T06:00'],sunset:['2026-11-07T18:00']},
   hourly:{time:[15,16,17,18,19,20].map(hour=>'2026-11-07T'+hour+':00'),temperature_2m:[25,26,24,22,21,20],weather_code:[2,3,61,63,0,1],is_day:[1,1,1,0,0,0]}}}),
  'fmtv.prices':JSON.stringify({quote:'USDT',at:NOW,body:[
   {symbol:'BTCUSDT',lastPrice:'112345.67',openPrice:'110000'},
   {symbol:'ETHUSDT',lastPrice:'3456.78',openPrice:'3600'},
   {symbol:'SOLUSDT',lastPrice:'123.45',openPrice:'123.45'}]})
 };
 const media=createMedia({directory,iconRoot:directory,processor,uriBase:'/fixture-media/',download:async url=>{
  let parsed;try{parsed=new URL(url);}catch{throw Error('Invalid fixture image URL');}
  const value=originals[path.basename(parsed.pathname)];if(!value)throw Error('Unknown fixture image');return value;
 }});
 try{
  const rendered=await media.update({apps:[]},cache);
  if(rendered.imageFailures)throw Error('Fixture image processing failed');
  return {originals,snapshot:{version:1,keyConfigured:true,locationKnown:true,cache,...rendered}};
 }finally{media.stop();}
}
module.exports={fixture,png,NOW};
