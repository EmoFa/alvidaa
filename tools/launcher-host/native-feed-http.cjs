'use strict';
// Off-browser, read-only feed transport. No arbitrary URL proxy or redirects.
const https = require('node:https');
const LIMIT = 2 * 1024 * 1024;
const TMDB = new Set(['language','watch_region','append_to_response','include_image_language',
  'vote_count.gte','primary_release_date.gte','primary_release_date.lte','air_date.gte','air_date.lte',
  'with_watch_monetization_types','include_adult','sort_by','with_watch_providers','without_genres']);
const WEATHER = {current:'temperature_2m,weather_code,is_day',
  daily:'temperature_2m_max,temperature_2m_min,sunrise,sunset',hourly:'temperature_2m,weather_code,is_day',
  timezone:'auto',forecast_days:'2'};
function reject() { throw new Error('Feed request rejected by endpoint policy'); }
function canonical(input) {
  let url;
  try { url = new URL(input); } catch { reject(); }
  if (url.protocol !== 'https:' || url.username || url.password || url.port || url.hash || String(input).includes('\\')) reject();
  const seen = new Set();
  for (const [key,value] of url.searchParams) {
    if (seen.has(key) || value.length > 2048) reject();
    seen.add(key);
  }
  let service, ttl;
  if (url.hostname === 'api.themoviedb.org') {
    if (!/^\/3\/(watch\/providers\/movie|trending\/(movie|tv)\/week|discover\/(movie|tv)|(movie|tv)\/[1-9][0-9]{0,10})$/.test(url.pathname)) reject();
    url.searchParams.delete('api_key'); // Never persist caller credentials in cache keys.
    for (const [key,value] of url.searchParams) {
      if (!TMDB.has(key)) reject();
      if (key === 'language' && !/^[a-z]{2,3}(-[A-Z]{2})?$/.test(value)) reject();
      if (key === 'watch_region' && !/^[A-Z]{2}$/.test(value)) reject();
      if (key === 'append_to_response' && value !== 'watch/providers,images') reject();
      if (key === 'include_image_language' && !/^(null|[a-z]{2})(,(null|[a-z]{2})){0,3}$/.test(value)) reject();
      if (key === 'include_adult' && value !== 'false') reject();
      if (key === 'sort_by' && value !== 'popularity.desc') reject();
      if (key === 'with_watch_monetization_types' && value !== 'flatrate') reject();
      if (['with_watch_providers','without_genres'].includes(key) && !/^[0-9]{1,8}([|,][0-9]{1,8}){0,49}$/.test(value)) reject();
      if (key === 'vote_count.gte' && !/^[0-9]{1,4}$/.test(value)) reject();
      if (/^(primary_release_date|air_date)\./.test(key) && !/^\d{4}-\d{2}-\d{2}$/.test(value)) reject();
    }
    service = 'picks'; ttl = 4 * 3600000;
  } else if (url.hostname === 'api.open-meteo.com' && url.pathname === '/v1/forecast') {
    if (seen.size !== 7) reject();
    for (const [key,value] of Object.entries(WEATHER)) if (url.searchParams.get(key) !== value) reject();
    for (const [key,max] of [['latitude',90],['longitude',180]]) {
      const value = url.searchParams.get(key);
      if (!/^-?\d{1,3}(\.\d{1,8})?$/.test(value || '') || Math.abs(Number(value)) > max) reject();
    }
    service = 'weather'; ttl = 30 * 60000;
  } else if (['api.binance.com','api.binance.us'].includes(url.hostname) && url.pathname === '/api/v3/ticker/24hr') {
    if (seen.size !== 2 || url.searchParams.get('type') !== 'MINI') reject();
    let symbols;
    try { symbols = JSON.parse(url.searchParams.get('symbols')); } catch { reject(); }
    if (!Array.isArray(symbols) || !symbols.length || symbols.length > 4 ||
        !symbols.every(s=>typeof s === 'string' && /^(BTC|ETH|SOL|USDT)[A-Z]{3,5}$/.test(s))) reject();
    service = 'prices'; ttl = 5 * 60000;
  } else reject();
  url.searchParams.sort();
  return {key:url.href,url,service,ttl};
}
function requestJson(input, options = {}) {
  const endpoint = canonical(input);
  const token = options.token || '';
  if (endpoint.service === 'picks' && (!token || /[\r\n]/.test(token))) {
    return Promise.reject(new Error('TMDB read token is not configured correctly'));
  }
  const get = options.get || https.get;
  const timeout = options.timeout || 10000;
  return new Promise((resolve,rejectPromise)=>{
    let request, response, settled = false;
    const timer = setTimeout(()=>finish(new Error('Feed request timed out')),timeout);
    function finish(error, value) {
      if (settled) return;
      settled = true; clearTimeout(timer);
      if (error) { if (response) response.destroy(); if (request) request.destroy(); rejectPromise(error); }
      else resolve(value);
    }
    const headers = {Accept:'application/json','User-Agent':'alvidaa-free-my-tv/native'};
    if (endpoint.service === 'picks') headers.Authorization = 'Bearer ' + token;
    try {
      request = get(endpoint.url,{headers},res=>{
        response = res;
        if (settled) { res.destroy(); return; }
        res.on('error',()=>finish(new Error('Feed response failed')));
        res.on('aborted',()=>finish(new Error('Feed response interrupted')));
        const status = res.statusCode || 502;
        if (status !== 200) {
          // Discard error/redirect bodies: they can echo credentials or contain HTML.
          finish(null,{key:endpoint.key,service:endpoint.service,status,body:null}); res.destroy(); return;
        }
        const chunks = []; let size = 0;
        res.on('data',chunk=>{
          size += chunk.length;
          if (size > LIMIT) { finish(new Error('Feed response exceeds size limit')); return; }
          chunks.push(chunk);
        });
        res.on('end',()=>{
          if (settled) return;
          const text = Buffer.concat(chunks).toString('utf8');
          if (token && text.includes(token)) { finish(new Error('Credential-bearing feed response rejected')); return; }
          let body;
          try { body = JSON.parse(text); } catch { finish(new Error('Feed response is not JSON')); return; }
          if (!body || typeof body !== 'object') { finish(new Error('Feed response has an invalid shape')); return; }
          finish(null,{key:endpoint.key,service:endpoint.service,status,body,ttl:endpoint.ttl});
        });
      });
      request.on('error',()=>finish(new Error('Feed request failed')));
    } catch { finish(new Error('Feed request failed')); }
  });
}
module.exports = {canonical,requestJson,LIMIT};
