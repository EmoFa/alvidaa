'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const create=require('./native-web-compat.js');
function adapter(){return create({setTimeout:()=>1,clearTimeout(){}},{},{assets:{colors:[],symbols:[]},assetBase:''});}
const local='file:///hisenseUI/var/local/free-my-tv/media/photo-raw.jpg';
test('unavailable original artwork falls back to a prepared local rendition of the same photo',()=>{
 const native=adapter();native.accept({version:1,media:{},images:{'w1280:/photo.jpg':local}});
 assert.equal(native.image('/photo.jpg','original'),local);
 assert.equal(native.image('/different.jpg','original'),'');
 native.accept({version:1,media:{},images:{'original:/photo.jpg':'https://evil.test/photo.jpg','w1280:/photo.jpg':local}});
 assert.equal(native.image('/photo.jpg','original'),local);
 native.accept({version:1,media:{},images:{'original:/photo.jpg':'file:///hisenseUI/var/local/free-my-tv/../private.jpg'}});
 assert.equal(native.image('/photo.jpg','original'),'');native.dispose();
});
test('image mapping changes invalidate cards even if metadata is unchanged',()=>{
 const native=adapter();let refreshes=0;native.refreshMedia=()=>refreshes++;
 const media={[local]:{src:local,width:1280,height:720}};
 native.accept({version:1,media,images:{}});assert.equal(refreshes,1);
 native.accept({version:1,media,images:{'original:/photo.jpg':local}});assert.equal(refreshes,2);
 native.accept({version:1,media,images:{'original:/photo.jpg':local}});assert.equal(refreshes,2);
 native.dispose();native.accept({version:1,media,images:{}});assert.equal(refreshes,2);
});
