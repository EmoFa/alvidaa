'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {EventEmitter}=require('node:events');
const {canonical,requestJson,LIMIT}=require('./native-feed-http.cjs');
const TOKEN='fake-test-token-not-real';
const MOVIE='https://api.themoviedb.org/3/movie/123?language=en-AU&append_to_response=watch/providers,images&include_image_language=null,en,en';
const WEATHER='https://api.open-meteo.com/v1/forecast?latitude=-27.47&longitude=153.02&current=temperature_2m,weather_code,is_day&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset&hourly=temperature_2m,weather_code,is_day&timezone=auto&forecast_days=2';
function fake(status,text,inspect=()=>{}){
  let destroyed=false;
  const get=(url,options,callback)=>{
    inspect(url,options);
    const req=new EventEmitter();req.destroy=()=>{destroyed=true;};
    queueMicrotask(()=>{
      const res=new EventEmitter();res.statusCode=status;res.destroy=()=>{destroyed=true;};
      callback(res);
      if(!destroyed){res.emit('data',Buffer.from(text));if(!destroyed)res.emit('end');}
    });return req;
  };
  return {get,destroyed:()=>destroyed};
}
test('accepts actual upstream read-only requests with canonical credential-free cache keys',()=>{
  for(const url of [MOVIE,WEATHER,
    'https://api.themoviedb.org/3/watch/providers/movie?language=en-AU&watch_region=AU',
    'https://api.themoviedb.org/3/trending/tv/week?language=en-US',
    'https://api.themoviedb.org/3/discover/movie?vote_count.gte=30&primary_release_date.gte=2025-01-01&primary_release_date.lte=2026-01-01&with_watch_providers=8%7C9&watch_region=AU&include_adult=false&sort_by=popularity.desc&with_watch_monetization_types=flatrate',
    'https://api.binance.com/api/v3/ticker/24hr?type=MINI&symbols=%5B%22BTCUSDT%22,%22ETHUSDT%22%5D'])assert.ok(canonical(url).ttl>0);
  const value=canonical(MOVIE+'&api_key=must-not-persist');
  assert.ok(!value.key.includes('must-not-persist'));assert.ok(!value.key.includes('api_key'));
});
test('rejects arbitrary hosts, accounts, redirects, query expansion and malformed coordinates',()=>{
  for(const url of ['http://api.themoviedb.org/3/movie/1',
    'https://api.themoviedb.org.evil.invalid/3/movie/1','https://user:password@api.themoviedb.org/3/movie/1',
    'https://api.themoviedb.org:444/3/movie/1','https://api.themoviedb.org/3/account/1',
    MOVIE+'&callback=evil',MOVIE+'&language=fr',MOVIE+'#fragment',
    WEATHER.replace('latitude=-27.47','latitude=91'),WEATHER+'&extra=1',
    'https://api.binance.com/api/v3/ticker/24hr?type=FULL&symbols=%5B%22BTCUSDT%22%5D']) {
    assert.throws(()=>canonical(url),/policy/);
  }
});
test('private token is sent only as a TMDB Authorization header, never in the URL or result',async()=>{
  const f=fake(200,'{"results":[]}',(url,options)=>{
    assert.equal(options.headers.Authorization,'Bearer '+TOKEN);
    assert.ok(!url.href.includes(TOKEN));assert.ok(!url.searchParams.has('api_key'));
  });
  const result=await requestJson(MOVIE+'&api_key=caller-secret',{token:TOKEN,get:f.get});
  assert.equal(result.status,200);assert.ok(!JSON.stringify(result).includes(TOKEN));
  const weather=fake(200,'{}',(_url,options)=>assert.equal(options.headers.Authorization,undefined));
  await requestJson(WEATHER,{token:TOKEN,get:weather.get});
});
test('missing TMDB credentials cause no network request',async()=>{
  await assert.rejects(requestJson(MOVIE,{get(){throw Error('must not execute');}}),/not configured/);
});
test('redirects and provider errors are not followed and their bodies are discarded',async()=>{
  for(const status of [301,302,401,451,500]){
    const f=fake(status,TOKEN);const result=await requestJson(MOVIE,{token:TOKEN,get:f.get});
    assert.equal(result.status,status);assert.equal(result.body,null);assert.equal(f.destroyed(),true);
  }
});
test('oversized, malformed and credential-bearing responses are rejected',async()=>{
  for(const [text,message] of [['x'.repeat(LIMIT+1),/size limit/],['not JSON',/not JSON/],
    ['42',/invalid shape/],[JSON.stringify({reflected:TOKEN}),/Credential-bearing/]]){
    const f=fake(200,text);await assert.rejects(requestJson(MOVIE,{token:TOKEN,get:f.get}),message);
    assert.equal(f.destroyed(),true);
  }
});
test('network failures are redacted and slow requests have an absolute deadline',async()=>{
  await assert.rejects(requestJson(MOVIE,{token:TOKEN,get(){throw Error(TOKEN);}}),error=>error.message==='Feed request failed');
  let cancelled=false;
  const get=()=>{const req=new EventEmitter();req.destroy=()=>{cancelled=true;};return req;};
  await assert.rejects(requestJson(MOVIE,{token:TOKEN,get,timeout:5}),/timed out/);
  assert.equal(cancelled,true);
});
