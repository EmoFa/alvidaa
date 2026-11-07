/* Own the upstream Home lifecycle inside the stock /Launcher component only. */
(function(root){
  'use strict';
  var STORE='alvidaa.freeMyTV.web.';
  function storage(sdk){
    function key(name){if(!/^fmtv\.[a-z0-9._-]+$/.test(name))throw Error('Unexpected preference key');return STORE+name;}
    var local={getItem:function(name){var value=sdk.storage.get(key(name));return value==null?null:String(value);},
      setItem:function(name,value){sdk.storage.set(key(name),String(value));},
      removeItem:function(name){sdk.storage.set(key(name),null);}};
    if(local.getItem('fmtv.prefs')===null){
      var old=sdk.storage.get('alvidaa.freeMyTV'),prefs={};
      if(typeof old==='string'){try{old=JSON.parse(old);}catch{old=null;}}
      if(old&&typeof old==='object'){
        if(['auto','light','dark'].indexOf(old.theme)>=0)prefs.theme=old.theme;
        if(Array.isArray(old.favorites))prefs.shelf=old.favorites.map(function(id){return 'app:'+String(id);});
        local.setItem('fmtv.prefs',JSON.stringify(prefs));
      }
    }
    return local;
  }
  function timezone(){
    // This builder is pinned to the Australian P1015 launcher. This is the
    // same state enumeration used by the native Australian Time Zone page.
    try {
      var index=root.modeljs.getIntValue('kilby.sl2.i32.basic.settings.tvset.location.australia');
      return ['Australia/Sydney','Australia/Brisbane','Australia/Adelaide','Australia/Darwin',
        'Australia/Perth','Australia/Melbourne','Australia/Hobart'][index]||'';
    }catch{return '';}
  }
  function mount(sdk,element,remount){
    var bundle=root.AlvidaaNativeWebBundle,ended=false,scope=null,native=null;
    var requests=[],pollTimer=null,writeTimer=null,lastContext='',pendingContext=null,program=null,lastSnapshot='';
    var local=storage(sdk);
    function active(){return !ended&&!root.document.hidden&&sdk.router.isCurrentPathEqualTo('/Launcher');}
    var lastActive=active(),initialZone=timezone();
    function rpc(api,args,done){
      if(ended)return;
      var xhr=new root.XMLHttpRequest();requests.push(xhr);
      xhr.open('POST','http://localhost:9009/service/hiutils',true);
      xhr.timeout=3000;xhr.setRequestHeader('Content-Type','application/json');
      function finish(value){var i=requests.indexOf(xhr);if(i<0)return;requests.splice(i,1);if(!ended)done(value);}
      xhr.onreadystatechange=function(){
        if(xhr.readyState!==4)return;
        var value=null;
        try{if(xhr.status===200&&xhr.responseText.length<8*1024*1024)value=JSON.parse(xhr.responseText);}catch{value=null;}
        finish(value);
      };
      xhr.onerror=xhr.ontimeout=function(){finish(null);};
      xhr.send(JSON.stringify({api:api,args:args}));
    }
    function context(value){
      value.version=1;value.zoneSource='native-australian-state';
      var encoded=JSON.stringify(value);if(encoded===lastContext||encoded.length>1024*1024)return;
      pendingContext=encoded;
      if(writeTimer!==null)return;
      writeTimer=root.setTimeout(function(){
        writeTimer=null;var sending=pendingContext;
        rpc('fileWrite',{path:'free-my-tv/context.json',mode:6,writedata:sending},function(value){
          if(value&&value.ret)lastContext=sending;
        });
      },100);
    }
    function poll(){
      var visible=active();
      // Place is initialized once by upstream. A TV timezone change while a
      // native overlay is open needs a fresh scope, not a stale city/weather pair.
      if(visible&&timezone()!==initialZone){
        pollTimer=root.setTimeout(function(){if(!ended)remount();},0);return;
      }
      if(visible!==lastActive){lastActive=visible;scope.emit('visibilitychange');}
      rpc('fileRead',{path:'free-my-tv/snapshot.json',mode:6},function(value){
        if(value&&value.ret&&typeof value.msg==='string'&&value.msg!==lastSnapshot){
          try{var next=JSON.parse(value.msg);if(next.version===1){native.accept(next);lastSnapshot=value.msg;}}
          catch{/* Keep the previous good snapshot while the worker replaces its file. */}
        }
        if(!ended)pollTimer=root.setTimeout(poll,1000);
      });
    }
    var tv=root.AlvidaaNativeWebTV(sdk,{back:function(){scope.forwardKey();},timeZone:timezone,
      holdScreenSaver:root.AlvidaaNativeWebScreenSaver(sdk),
      onChange:function(){if(native&&native.refreshApps)native.refreshApps();}});
    native=root.AlvidaaNativeWebCompat(root,element,{assetBase:bundle.assetBase,assets:bundle.assets,TV:tv,context:context});
    scope=root.AlvidaaNativeWebScope(root,element,{isActive:active,keys:tv.keys,storage:local,
      XMLHttpRequest:function(){throw Error('Direct browser feed requests are disabled');},
      Image:native.Image,imageElement:native.imageElement});
    scope.window.CONFIG={tmdbKey:'',latitude:'',longitude:'',language:'auto',showCrypto:true,hideApps:[],shelfApps:[]};
    function keyDown(event){
      if(!scope.key(event))return;
      if(event.preventDefault)event.preventDefault();if(event.stopPropagation)event.stopPropagation();
      try{
        if(sdk.tts&&sdk.tts.isEnable()){
          var focus=element.querySelector('.focus');
          if(focus){var label=focus.getAttribute('title')||focus.textContent;
            if(!label){var symbol=focus.querySelector('[data-fmtv-symbol]');label=symbol&&symbol.getAttribute('data-fmtv-symbol').replace(/_/g,' ');}
            if(label)sdk.tts.speak(String(label));}
        }
      }catch{/* Preserve navigation if optional speech is unavailable. */}
    }
    function stop(){
      if(ended)return;ended=true;
      if(pollTimer!==null)root.clearTimeout(pollTimer);
      if(writeTimer!==null)root.clearTimeout(writeTimer);
      requests.splice(0).forEach(function(xhr){xhr.abort();});
      root.document.body.removeEventListener('key-down',keyDown);
      tv.stop();scope.dispose();native.dispose();element.innerHTML='';
    }
    try{
      if(!root.document.getElementById('alvidaa-web-styles')){
        var style=root.document.createElement('style');style.id='alvidaa-web-styles';
        style.textContent=bundle.fontCSS+'\n'+bundle.css;root.document.head.appendChild(style);
      }
      function append(parent,nodes){
        nodes.forEach(function(spec){
          var node=root.document.createElement(spec.tag);
          Object.keys(spec.attrs).forEach(function(key){node.setAttribute(key,spec.attrs[key]);});
          parent.appendChild(node);append(node,spec.children);
        });
      }
      append(element,bundle.tree);
      if(local.getItem('fmtv.night')==='true')element.className='night';
      tv.start();program=bundle.run(scope.window,native);
      if(root.AlvidaaNativeSettingsTheme){
        var data=program.Data;
        root.AlvidaaNativeSettingsTheme.setNightResolver(function(){return data.isNight(Date.now());});
      }
      root.document.body.addEventListener('key-down',keyDown);
      native.invalidate();poll();
    }catch(error){stop();throw error;}
    return {stop:stop,route:function(query){
      scope.emit('visibilitychange');
      if(!active())return;
      var keys=sdk.key.KEYMAP;
      if(query.focusArea==='input'||Number(query.value)===keys.SOURCE||Number(query.value)===keys.KEYPAD_INPUT||
         query.startLauncherFrom===sdk.apc.CMDMETHOD.KEY_INPUT_START)native.openInputs();
      else if(program.control.back)scope.emit('appcontrol');
    }};
  }
  root.AlvidaaFreeMyTV=function(sdk){
    if(root.AlvidaaNativeSettingsTheme)root.AlvidaaNativeSettingsTheme.configure({
      preferences:function(){return sdk.storage.get(STORE+'fmtv.prefs');},
      route:function(){
        var next=typeof sdk.router.getChangingPage==='function'&&sdk.router.getChangingPage();
        var current=next&&typeof next.path==='string'?next:sdk.router.getCurrentPage();
        // SDK paths include a runtime namespace before /setting/... . Ask the
        // SDK which module owns the route; do not guess or widen CSS globally.
        var route=current&&sdk.router.parseRoute(current);
        return route&&route.moduleName==='setting'?'/setting':'';
      }
    });
    return {
    name:'Launcher',mounted:function(){this.start();},activated:function(){this.start();this.routeFocus();},
    deactivated:function(){this.stop();},beforeDestroy:function(){this.stop();},
    watch:{$route:function(){this.routeFocus();}},
    methods:{start:function(){if(!this._nativeWeb){var self=this;this._nativeWeb=mount(sdk,this.$el,function(){self.stop();self.start();});}},
      stop:function(){if(this._nativeWeb){this._nativeWeb.stop();this._nativeWeb=null;}},
      routeFocus:function(){if(this._nativeWeb)this._nativeWeb.route(this.$route&&this.$route.query||{});}},
    render:function(h){return h('div',{attrs:{id:'alvidaa-web-home'},style:{position:'absolute',left:'0',top:'0',width:'1920px',height:'1080px'}});}
  };};
  if(typeof module!=='undefined'&&module.exports)module.exports={storage:storage,timezone:timezone};
}(typeof self!=='undefined'?self:this));
