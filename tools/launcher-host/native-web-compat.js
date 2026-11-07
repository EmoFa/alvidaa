/* Cobalt equivalents for unsupported web drawing APIs. No external image URLs. */
(function(root){
  'use strict';
  function create(host, element, options){
    var stopped=false,paintTimer=null,snapshot={images:{},media:{}},api=null;
    var base=options.assetBase,colors=options.assets.colors;
    function local(uri){
      return typeof uri==='string' && /^file:\/\/\/hisenseUI\/var\/local\/(free-my-tv|storeAppIcon)\//.test(uri) &&
        !/[\x00-\x20\\"')]/.test(uri) && !/(^|\/)\.\.(\/|$)|%2e|%2f|%5c/i.test(uri);
    }
    function meta(uri){return snapshot.media&&snapshot.media[uri];}
    function imageURL(uri){var info=meta(uri);return info&&local(info.src)?info.src:local(uri)?uri:'';}
    function LocalImage(){
      var object=this, image=new host.Image(), source='';
      Object.defineProperty(object,'src',{get:function(){return source;},set:function(uri){
        source=uri;var resolved=imageURL(uri);
        if(!resolved){if(object.onerror)object.onerror();return;}
        image.src=resolved;
      }});
      image.onload=function(){if(!stopped&&object.onload)object.onload();};
      image.onerror=function(){if(!stopped&&object.onerror)object.onerror();};
    }
    function imageElement(){
      var node=host.document.createElement('div'),image=new LocalImage(),source='';
      var widthOwned=false,heightOwned=false;
      node.setAttribute('data-fmtv-image','true');
      node.style.backgroundPosition='center';node.style.backgroundRepeat='no-repeat';node.style.backgroundSize='contain';
      Object.defineProperty(node,'src',{get:function(){return source;},set:function(uri){
        source=uri;
        if(widthOwned)node.style.width='';if(heightOwned)node.style.height='';
        widthOwned=false;heightOwned=false;
        image.src=uri;
      }});
      image.onerror=function(){if(!stopped&&node.onerror)node.onerror();};
      image.onload=function(){
        if(stopped)return;
        var info=meta(source),style=host.getComputedStyle(node);
        if(!parseFloat(style.width)){
          if(!info||!info.width){if(node.onerror)node.onerror();return;}
          node.style.width=info.width+'px';widthOwned=true;
        }
        if(!parseFloat(style.height)){
          if(!info||!info.height){if(node.onerror)node.onerror();return;}
          node.style.height=info.height+'px';heightOwned=true;
        }
        node.style.backgroundImage='url("'+imageURL(source)+'")';
        if(node.onload)node.onload();
      };
      return node;
    }
    function raster(name,parent,size,vector){
      if(options.assets.symbols.indexOf(name)<0)throw Error('Unknown native raster symbol');
      var node=host.document.createElement('span'),ink=host.document.createElement('span');
      node.className=vector?'':'sym';node.setAttribute(vector?'data-fmtv-vector':'data-fmtv-symbol',name);
      if(vector)node.style.display='inline-block';
      node.style.backgroundColor='transparent';
      if(size){node.style.width=size+'px';node.style.height=size+'px';}
      ink.style.display='block';ink.style.width='100%';ink.style.height='100%';
      ink.style.backgroundRepeat='no-repeat';ink.style.backgroundSize='contain';ink.style.backgroundPosition='center';
      node.appendChild(ink);parent.appendChild(node);invalidate();return node;
    }
    function tint(node){
      var color=host.getComputedStyle(node).color;
      var match=/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([.\d]+))?\s*\)/.exec(color);
      if(!match)return;
      var hex='';for(var i=1;i<=3;i++)hex+=('0'+Number(match[i]).toString(16)).slice(-2);
      if(colors.indexOf(hex)<0)throw Error('Unbuilt symbol color: '+hex);
      var name=node.getAttribute('data-fmtv-symbol')||node.getAttribute('data-fmtv-vector');
      var uri=base+'symbols/'+name+'-'+hex+'.png',ink=node.firstChild;
      if(ink._fmtvURI!==uri){ink.style.backgroundImage='url("'+uri+'")';ink._fmtvURI=uri;}
      ink.style.opacity=match[4]===undefined?'1':match[4];
    }
    function paint(){
      paintTimer=null;if(stopped)return;
      var nodes=element.querySelectorAll('*');
      for(var i=0;i<nodes.length;i++){
        var node=nodes[i];
        if(node.hasAttribute('data-fmtv-symbol')||node.hasAttribute('data-fmtv-vector'))tint(node);
        if(node.firstChild&&node.firstChild.nodeType===3){
          var size=parseFloat(host.getComputedStyle(node).fontSize);
          if(isFinite(size)){
            var family='FMTVWeb'+Math.max(14,Math.min(32,Math.round(size)));
            if(node._fmtvFont!==family){node.style.fontFamily=family;node._fmtvFont=family;}
          }
        }
      }
    }
    function invalidate(){if(!stopped&&paintTimer===null)paintTimer=host.setTimeout(paint,0);}
    var native={
      TV:options.TV,Image:LocalImage,imageElement:imageElement,
      symbol:function(name,parent,size){return raster(name,parent,size,false);},
      coin:function(index,parent){return raster('coin-'+index,parent,0,true);},
      lift:function(image){var info=meta(image.src);return info&&info.lift||false;},
      backdrop:function(node,uri){
        var info=meta(uri);if(!info||!local(info.thumb))return;
        node.style.backgroundImage='url("'+info.thumb+'")';node.style.backgroundSize='100% 100%';
      },
      image:function(path,size){
        // Original artwork can exceed the decoder's safety bound. Use an
        // already-prepared rendition of the same image instead of a blank saver.
        var sizes=[size,'w1280','w780','w500','w300','original'];
        for(var i=0;i<sizes.length;i++){
          var uri=snapshot.images&&snapshot.images[sizes[i]+':'+path];if(local(uri))return uri;
        }
        return '';
      },
      context:options.context,attach:function(value){api=value;},invalidate:invalidate,
      accept:function(next){
        if(stopped||!next||next.version!==1)return;
        var mediaChanged=JSON.stringify(snapshot.media)!==JSON.stringify(next.media)||
          JSON.stringify(snapshot.images)!==JSON.stringify(next.images);
        snapshot=next;
        if(api)api.Data.nativeSnapshot(next.cache||{},next.error||'',next.keyConfigured);
        if(mediaChanged&&native.refreshMedia)native.refreshMedia();
        invalidate();
      },
      dispose:function(){stopped=true;if(paintTimer!==null)host.clearTimeout(paintTimer);paintTimer=null;api=null;}
    };
    return native;
  }
  if(typeof module!=='undefined'&&module.exports)module.exports=create;
  else root.AlvidaaNativeWebCompat=create;
}(typeof self!=='undefined'?self:this));
