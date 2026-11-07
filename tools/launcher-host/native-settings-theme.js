/* Presentation only: retain the vendor settings component, children, routes,
 * model bindings, focus handlers, PINs and confirmations. No SDK replacement. */
(function(root){
  'use strict';
  function install(host){
    var registry=host._V_M_,descriptor=registry&&Object.getOwnPropertyDescriptor(registry,'setting');
    if(!registry||(descriptor&&(!descriptor.configurable||!descriptor.writable||descriptor.get||descriptor.set)))return null;
    var current=descriptor&&descriptor.value,wrapped=null,original=null,entries=[],routes=[],disposed=false;
    // Native high-contrast mode wins over this presentation layer immediately.
    var prefix='body.v-normal-contrast .fmtv-advanced.fmtv-advanced.fmtv-advanced',context={},nightResolver=null;
    function owned(path){return typeof path==='string'&&(/^\/setting(?:\/|$)/i.test(path)||path.length>0&&path.charAt(0)!=='/');}
    function active(){try{return !context.route||/^\/setting(?:\/|$)/i.test(context.route()||'');}catch{return false;}}
    function night(){
      try{
        var raw=context.preferences&&context.preferences(),prefs=typeof raw==='string'&&raw.length<=65536?JSON.parse(raw):raw;
        if(prefs&&prefs.theme==='light')return false;if(prefs&&prefs.theme==='dark')return true;
        if(nightResolver)return !!nightResolver();
      }catch{/* Preserve native Settings even when optional preferences are unavailable. */}
      return true;
    }
    function corners(radius){return ['top-left','top-right','bottom-right','bottom-left'].map(function(c){return 'border-'+c+'-radius:'+radius+';';}).join('');}
    var semantic=':not([class*="error"]):not([class*="warn"]):not([style*="color"])';
    var css=prefix+'{color:#f5f5f7;}'+
      // Color the native surfaces, not their transparent parent. Native menu
      // opacity classes therefore still reveal the content behind the panel.
      prefix+'.v-bg1,'+prefix+' .v-bg1{background:linear-gradient(135deg,#1c2228,#15191e)!important;}'+
      prefix+' .firstLevelFrame{background:linear-gradient(135deg,#242c33,#1c232a)!important;}'+
      prefix+' .highLevelFrame:before,'+prefix+' .highLevelFrame:after{background-color:rgba(255,255,255,.09)!important;}'+
      prefix+' .edgeshadow{box-shadow:none!important;}'+
      ['.firstText','.highLevelTitle','.item__txt','.s_item_title','.s_double_title_2','.explainTxt','.esntext'].map(function(selector){return prefix+' '+selector+'{font-family:"FMTVWeb32",sans-serif!important;}';}).join('')+
      prefix+' .highLevelTitle{font-weight:700;letter-spacing:-.01em;}'+
      prefix+' #v-focus{background:rgba(255,255,255,.11)!important;box-shadow:inset 0 0 0 2px rgba(255,255,255,.28)!important;'+corners('18px')+'}'+
      prefix+' .v-i-selected'+semantic+'{color:#31d5b2;}';
    var light=prefix+'.fmtv-light';
    var neutral=':not([class*="v-c-"])'+semantic;
    css+=light+'{color:#202428;}'+
      light+' .firstLevelFrame{background:linear-gradient(135deg,#edf1f5,#e4eaf0)!important;}'+
      light+' .highLevelFrame:before,'+light+' .highLevelFrame:after{background-color:rgba(0,0,0,.09)!important;}'+
      light+' #v-focus{background:rgba(0,0,0,.06)!important;box-shadow:inset 0 0 0 2px rgba(0,0,0,.22)!important;}'+
      // Native BUI controls carry their own neutral color/background classes;
      // inheriting only from the page leaves white text on a light surface.
      // Keep semantic error/warning classes and native disabled opacity intact.
      light+'.v-c1'+neutral+','+light+' .v-c1'+neutral+'{color:#202428!important;}'+
      light+'.v-c2'+neutral+','+light+' .v-c2'+neutral+'{color:#4d565e!important;}'+
      light+'.v-c3'+neutral+','+light+' .v-c3'+neutral+'{color:#626d75!important;}'+
      light+'.v-bg1,'+light+' .v-bg1{background:linear-gradient(135deg,#f7f9fc,#edf1f5)!important;}'+
      light+'.v-bg2,'+light+' .v-bg2{background:#e7ebef!important;}'+
      light+'.v-bg3,'+light+' .v-bg3{background:#dde3e9!important;}'+
      light+' .v-i-selected'+semantic+','+light+' .v-c-highlight'+semantic+'{color:#0d745f!important;}';
    function ensureStyle(){
      if(disposed||host.document.getElementById('alvidaa-settings-style'))return;
      var style=host.document.createElement('style');style.id='alvidaa-settings-style';
      style.textContent=(!host.document.getElementById('alvidaa-web-styles')&&host.AlvidaaNativeWebBundle?host.AlvidaaNativeWebBundle.fontCSS:'')+css;
      host.document.head.appendChild(style);
    }
    function writable(object,key){var d=Object.getOwnPropertyDescriptor(object,key);return d?d.writable===true:Object.isExtensible(object);}
    function clearClass(vnode){
      var own=vnode&&vnode._alvidaaSettingsClass;
      if(own&&vnode.data&&vnode.data.class===own.after&&writable(vnode.data,'class'))vnode.data.class=own.before;
    }
    function decorate(component){
      if(disposed||!component)return component;
      if(component.default){decorate(component.default);return component;}
      var options=component.options||component;
      if(typeof options.render!=='function'||!writable(options,'render')||entries.some(function(e){return e.options===options;}))return component;
      var before=options.render,entry={options:options,before:before,after:null,node:null};
      function render(){
        var vnode=before.apply(this,arguments);clearClass(vnode);entry.node=vnode;
        if(vnode&&active()&&writable(vnode,'_alvidaaSettingsClass')&&
          (vnode.data?writable(vnode.data,'class'):writable(vnode,'data'))){
          ensureStyle();vnode.data=vnode.data||{};
          var classes=[vnode.data.class,'fmtv-advanced',{'fmtv-light':!night()}];
          vnode._alvidaaSettingsClass={before:vnode.data.class,after:classes};vnode.data.class=classes;
        }
        return vnode;
      }
      options.render=render;entry.after=render;entries.push(entry);
      if(options._Ctor)Object.keys(options._Ctor).forEach(function(key){decorate(options._Ctor[key]);});
      return component;
    }
    function wrap(factory){
      if(typeof factory!=='function')return factory;
      if(original===factory)return wrapped;
      original=factory;
      wrapped=function(){
        var stock=factory.apply(this,arguments);
        function visit(route){
          if(!route||!owned(route.path))return;
          (route.children||[]).forEach(visit);
          if(routes.some(function(e){return e.route===route;})||!writable(route,'component'))return;
          var before=route.component;
          function load(){
            var value=before.apply(this,arguments);
            return value&&typeof value.then==='function'?value.then(decorate):decorate(value);
          }
          if(typeof before==='function'&&!before.options){
            if(before.resolved)decorate(before.resolved);
            route.component=load;routes.push({route:route,before:before,after:load});
          }else decorate(before);
        }
        (stock&&stock.route||[]).forEach(visit);
        return stock;
      };
      return wrapped;
    }
    function get(){return wrap(current);}
    Object.defineProperty(registry,'setting',{configurable:true,enumerable:descriptor?descriptor.enumerable:true,get:get,set:function(value){current=value;}});
    // A previously loaded factory returns its cached module; decorate that same
    // route object too, rather than replacing a controller already registered.
    if(typeof current==='function'){
      wrap(current)();
      // The router may already have copied the original lazy-loader reference.
      // Resolve that same local module and decorate its exported component;
      // this mounts nothing and leaves all route guards in place.
      routes.forEach(function(entry){
        // Do not eagerly load every native dialog just to style it. New routes
        // are decorated on demand; already resolved constructors are covered above.
        if(entry.route.path!=='/setting/settings')return;
        try{
          var value=entry.before();
          if(value&&typeof value.then==='function')value.then(decorate,function(){});
          else decorate(value);
        }catch{/* Keep native routing available; a later load can retry. */}
      });
    }
    return {configure:function(value){if(!disposed)context=value||{};},
      setNightResolver:function(value){if(!disposed)nightResolver=value;},remove:function(){
      if(disposed)return;disposed=true;context={};nightResolver=null;
      routes.forEach(function(e){if(e.route.component===e.after&&writable(e.route,'component'))e.route.component=e.before;});
      entries.forEach(function(e){clearClass(e.node);if(e.options.render===e.after&&writable(e.options,'render'))e.options.render=e.before;});
      var own=Object.getOwnPropertyDescriptor(registry,'setting');
      if(own&&own.get===get){
        if(descriptor)Object.defineProperty(registry,'setting',{configurable:descriptor.configurable,enumerable:descriptor.enumerable,writable:descriptor.writable,value:current});
        else if(current===undefined)delete registry.setting;
        else Object.defineProperty(registry,'setting',{configurable:true,enumerable:true,writable:true,value:current});
      }
      var style=host.document.getElementById('alvidaa-settings-style');if(style&&style.parentNode)style.parentNode.removeChild(style);
    }};
  }
  if(typeof module!=='undefined'&&module.exports)module.exports=install;
  else root.AlvidaaNativeSettingsTheme=install(root);
}(typeof self!=='undefined'?self:this));
