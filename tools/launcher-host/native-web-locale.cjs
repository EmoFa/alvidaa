'use strict';
// Compile the pinned UI's supported locale primitives. Cobalt's Date/Number
// locale methods silently ignore options; never patch firmware prototypes.
const vm=require('node:vm');
function buildLocales(sources){
 const sandbox={window:{},navigator:{language:'en-US'},document:{documentElement:{}}};
 vm.createContext(sandbox);new vm.Script(sources['i18n.js']+'\n'+sources['strings.js']).runInContext(sandbox,{timeout:3000});
 const tables={};
 for(const language of sandbox.I18N.languages()){
  sandbox.I18N.set(language);const locale=sandbox.I18N.locale();
  const fmt=(date,options)=>date.toLocaleDateString(locale,{...options,timeZone:'UTC'});
  const months=[],shortMonths=[],formatMonths=[],weekdays=[],shortWeekdays=[],periods=[];
  for(let i=0;i<12;i++){
   const date=new Date(Date.UTC(2024,i,17,12)),plain=fmt(date,{month:'long'}),both=fmt(date,{month:'long',day:'numeric'});
   const rest=both.replace(/(^|\s)17\.?(?=\s|$)/,' ').trim();
   months.push(plain);shortMonths.push(fmt(date,{month:'short'}));
   formatMonths.push(!rest||rest===both||rest.split(/\s+/).includes(plain)?plain:rest);
  }
  for(let i=0;i<7;i++){
   const date=new Date(Date.UTC(2024,0,7+i,12));weekdays.push(fmt(date,{weekday:'long'}));shortWeekdays.push(fmt(date,{weekday:'short'}));
  }
  const period=new Intl.DateTimeFormat(locale,{timeZone:'UTC',hour:'numeric',hour12:true});
  for(let i=0;i<24;i++)periods.push(period.formatToParts(new Date(Date.UTC(2024,0,17,i))).find(p=>p.type==='dayPeriod')?.value||(i<12?'AM':'PM'));
  const nf=new Intl.NumberFormat(locale),parts=nf.formatToParts(1234567890123.25),groups=parts.filter(p=>p.type==='integer');
  const digitFormat=new Intl.NumberFormat(locale,{useGrouping:false});
  const value={months,shortMonths,formatMonths,weekdays,shortWeekdays,periods,
   decimal:parts.find(p=>p.type==='decimal')?.value||'.',group:parts.find(p=>p.type==='group')?.value||'',
   primary:groups.at(-1).value.length,secondary:groups.length>1?groups.at(-2).value.length:3,
   minimumGroup:nf.formatToParts(1000).some(p=>p.type==='group')?4:5,
   minus:nf.formatToParts(-1).find(p=>p.type==='minusSign')?.value||'-',infinity:nf.format(Infinity),nan:nf.format(NaN),
   digits:Array.from({length:10},(_,i)=>digitFormat.format(i))};
  tables[locale.toLowerCase()]=value;tables[language.toLowerCase()]=value;
 }
 return tables;
}
function localizer(tables){
 function table(locale){var key=String(locale).toLowerCase();var value=tables[key]||tables[key.split('-')[0]];if(!value)throw Error('Unsupported native locale');return value;}
 function zeros(n){return n>0?new Array(n+1).join('0'):'';}
 function increment(value){var chars=value.split(''),i=chars.length-1;for(;i>=0&&chars[i]==='9';i--)chars[i]='0';if(i<0)chars.unshift('1');else chars[i]=String(Number(chars[i])+1);return chars.join('');}
 return {
  dateName:function(date,locale,options){var t=table(locale);if(options.weekday)return (options.weekday==='long'?t.weekdays:t.shortWeekdays)[date.getDay()];if(options.month)return (options.month==='long'?t.months:t.shortMonths)[date.getMonth()];throw Error('Unsupported native date field');},
  month:function(date,locale,withDay){var t=table(locale);return (withDay?t.formatMonths:t.months)[date.getMonth()];},
  period:function(date,locale){return table(locale).periods[date.getHours()];},
  number:function(value,digits,locale){
   var t=table(locale),negative=value<0||1/value===-Infinity;
   if(isNaN(value))return t.nan;if(!isFinite(value))return (negative?t.minus:'')+t.infinity;
   if(digits<0||digits>20||Math.floor(digits)!==digits)throw Error('Unsupported native precision');
   var exp=String(Math.abs(value)).toLowerCase().split('e'),parts=exp[0].split('.');
   var raw=parts.join(''),point=parts[0].length+Number(exp[1]||0),cut=point+digits,scaled;
   if(cut<0)scaled='0';else if(cut===0)scaled=raw.charAt(0)>='5'?'1':'0';else{
    scaled=(raw+zeros(cut-raw.length)).slice(0,cut);if(raw.charAt(cut)>='5')scaled=increment(scaled);
   }
   scaled=scaled.replace(/^0+(?=\d)/,'');scaled=zeros(digits+1-scaled.length)+scaled;
   var whole=digits?scaled.slice(0,-digits):scaled,fraction=digits?scaled.slice(-digits):'',chunks=[];
   if(t.group&&whole.length>=t.minimumGroup){var width=t.primary;while(whole.length>width){chunks.unshift(whole.slice(-width));whole=whole.slice(0,-width);width=t.secondary;}chunks.unshift(whole);whole=chunks.join(t.group);}
   var result=whole+(digits?t.decimal+fraction:'');result=result.replace(/[0-9]/g,function(d){return t.digits[Number(d)];});
   return (negative?t.minus:'')+result;
  }
 };
}
module.exports={buildLocales,localizer};
