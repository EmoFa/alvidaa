/* Free My TV native Cobalt frontend, adapted from felipericardo/tv-launcher
 * web/home.css and its offline clock/shelf design, revision f2d984c.
 * MIT: see third-party/free-my-tv/LICENSE and README.md.
 * Vue replaces the browser renderer. No canvas, CDN, network data or global CSS.
 */
(function (root) {
  "use strict";
  root.AlvidaaFreeMyTV = function (sdk) {
    var keys = sdk.key.KEYMAP;
    function id(app) { return String(app.appId); }
    function load() {
      try {
        var value = sdk.storage.get("alvidaa.freeMyTV");
        if (typeof value === "string") value = JSON.parse(value);
        return value && typeof value === "object" ? value : {};
      } catch (_) { return {}; }
    }
    return {
      name: "Launcher",
      data: function () {
        var prefs = load();
        return { apps: [], sources: [], view: "home", zone: "shelf", index: 0,
          now: new Date(), width: root.innerWidth || 1920, status: "Starting native services…",
          theme: ["auto", "dark", "light"].indexOf(prefs.theme) >= 0 ? prefs.theme : "auto",
          favorites: Array.isArray(prefs.favorites) ? prefs.favorites.map(String) : null,
          moving: false };
      },
      mounted: function () { this.start(); },
      activated: function () { this.start(); this.routeFocus(); },
      deactivated: function () { this.stop(); },
      beforeDestroy: function () { this.stop(); },
      watch: { "$route": function () { this.routeFocus(); } },
      methods: {
        start: function () {
          if (this._running) return;
          this._running = true;
          var vm = this;
          this._platform = root.AlvidaaNativePlatform(sdk, function (data) {
            vm.apps = data.apps.filter(function (app) {
              return app && app.appId != null && typeof app.appName === "string" &&
                app.appName.trim() && id(app) !== "vidaa-home" && id(app) !== "206";
            });
            vm.sources = data.sources.filter(function (input) { return input && input.sourceId != null; });
            vm.status = data.errors.length ? data.errors.join("; ") :
              data.waiting ? "Waiting for TV data…" : "Native · " + vm.apps.length + " apps · " + vm.sources.length + " inputs";
            vm.clamp();
          });
          this._platform.start();
          this._clock = setInterval(function () { vm.now = new Date(); }, 1000);
          this._resize = function () { vm.width = root.innerWidth || 1920; };
          if (root.addEventListener) root.addEventListener("resize", this._resize);
          this.routeFocus();
          // Consume handled Home keys during bubbling, before document-level
          // defaults. Dialogs can consume them first; unrelated keys pass through.
          this._keyDown = function (event) {
            if (sdk.router.isCurrentPathEqualTo("/Launcher") && vm.handleKey(event.keyCode)) {
              event.stopPropagation();
              vm.announce();
            }
          };
          if (root.document && root.document.body) root.document.body.addEventListener("key-down", this._keyDown);
          root.AlvidaaNativeActive = this;
        },
        announce: function () {
          if (!sdk.tts || !sdk.tts.isEnable() || !sdk.router.isCurrentPathEqualTo("/Launcher")) return;
          var item = this.zone === "top" ? ["Home", "All apps", "Inputs", "TV Settings", "Preferences"][this.index] : this.list()[this.index];
          var label = typeof item === "string" ? item : item && (this.view === "inputs" ? this.sourceName(item) : item.appName);
          if (label) sdk.tts.speak((this.moving ? "Moving " : "") + label);
        },
        stop: function () {
          this._running = false;
          if (this._platform) this._platform.stop();
          clearInterval(this._clock);
          if (root.document && root.document.body) root.document.body.removeEventListener("key-down", this._keyDown);
          if (root.removeEventListener) root.removeEventListener("resize", this._resize);
          if (root.AlvidaaNativeActive === this) root.AlvidaaNativeActive = null;
        },
        routeFocus: function () {
          var q = this.$route && this.$route.query || {};
          if (q.focusArea === "input" || Number(q.value) === keys.SOURCE || Number(q.value) === keys.KEYPAD_INPUT ||
              q.startLauncherFrom === sdk.apc.CMDMETHOD.KEY_INPUT_START) this.show("inputs");
          else { this.view = "home"; this.zone = "shelf"; this.index = 0; this.moving = false; }
        },
        save: function () {
          try { sdk.storage.set("alvidaa.freeMyTV", { theme: this.theme, favorites: this.favorites }); }
          catch (error) { this.status = "Could not save preferences: " + error.message; }
        },
        localIcon: function (app) {
          var candidates = [app.img, app.presetImg, app.icon, app.appIcon];
          var icon = candidates.filter(function (value) {
            return typeof value === "string" && /^(var\/local\/storeAppIcon\/|file:\/\/\/|\/(?!\/)|data:image\/(png|jpeg|webp);base64,)/i.test(value);
          })[0] || "";
          return icon.indexOf("var/local/storeAppIcon/") === 0 ? "file:///hisenseUI/" + icon : icon;
        },
        sourceName: function (input) {
          var label = input.rename || input.name || String(input.sourceId);
          if (/^[A-Z]{2,4}[0-9]{4,}$/.test(label) && sdk.i18n && sdk.i18n.t) {
            try { var translated = sdk.i18n.t(label); if (translated && translated !== label) return translated; }
            catch { return input.name || label; }
            return input.name || label;
          }
          return label;
        },
        shelf: function () {
          var apps = this.apps;
          if (this.favorites === null) return apps.slice(0, 8);
          return this.favorites.map(function (key) {
            return apps.filter(function (app) { return id(app) === key; })[0];
          }).filter(Boolean);
        },
        list: function () {
          if (this.view === "inputs") return this.sources;
          if (this.view === "apps" || this.view === "edit") return this.apps;
          if (this.view === "prefs") return ["TV Settings", "Theme: " + this.theme, "Manage shelf", "Reorder shelf", "Refresh apps & inputs", "About / licenses"];
          if (this.view === "about") return ["Back"];
          return this.shelf();
        },
        clamp: function () {
          var count = this.zone === "top" ? 5 : this.list().length;
          this.index = Math.max(0, Math.min(this.index, count - 1));
        },
        show: function (view) { this.view = view; this.zone = "shelf"; this.index = 0; this.moving = false; },
        run: function (action) {
          var vm = this;
          try {
            var result = action();
            if (result && typeof result.then === "function") result.catch(function (error) { vm.status = "Action failed: " + error.message; });
          } catch (error) { this.status = "Action failed: " + error.message; }
        },
        select: function () {
          var vm = this;
          if (this.zone === "top") {
            if (this.index === 3) this.run(function () { return vm._platform.openSettings(); });
            else this.show(["home", "apps", "inputs", "", "prefs"][this.index]);
            return;
          }
          var item = this.list()[this.index];
          if (item == null) return;
          if (this.view === "inputs") this.run(function () { return vm._platform.changeSource(item.sourceId); });
          else if (this.view === "prefs") {
            if (this.index === 0) this.run(function () { return vm._platform.openSettings(); });
            else if (this.index === 1) { this.theme = ["auto", "dark", "light"][( ["auto", "dark", "light"].indexOf(this.theme) + 1) % 3]; this.save(); }
            else if (this.index === 2) this.show("edit");
            else if (this.index === 3) this.show("reorder");
            else if (this.index === 4) this._platform.refresh();
            else this.show("about");
          } else if (this.view === "about") this.show("prefs");
          else if (this.view === "edit") {
            var favoriteIds = this.shelf().map(id), at = favoriteIds.indexOf(id(item));
            if (at < 0) favoriteIds.push(id(item)); else favoriteIds.splice(at, 1);
            this.favorites = favoriteIds; this.save();
          } else if (this.view === "reorder") this.moving = !this.moving;
          else this.run(function () { return vm._platform.launchApp(item.appId); });
        },
        handleKey: function (code) {
          if (code === keys.BACK || code === keys.RETURN) {
            if (this.moving) { this.moving = false; return true; }
            if (this.view !== "home" || this.zone !== "shelf") { this.show("home"); return true; }
            return false; // Let the vendor own Back from the main Home screen.
          }
          if (code === keys.ENTER) { this.select(); return true; }
          if ([keys.LEFT, keys.RIGHT, keys.UP, keys.DOWN].indexOf(code) < 0) return false;
          if (this.moving) {
            var ids = this.shelf().map(id), delta = code === keys.LEFT ? -1 : code === keys.RIGHT ? 1 : 0;
            var to = Math.max(0, Math.min(ids.length - 1, this.index + delta));
            if (ids.length && to !== this.index) { var item = ids.splice(this.index, 1)[0]; ids.splice(to, 0, item); this.index = to; this.favorites = ids; this.save(); }
            return true;
          }
          if (this.zone === "top") {
            if (code === keys.DOWN) { this.zone = "shelf"; this.index = 0; }
            else if (code === keys.LEFT) this.index--; else if (code === keys.RIGHT) this.index++;
          } else if (code === keys.UP) {
            if (["apps", "edit", "inputs"].indexOf(this.view) >= 0 && this.index >= 6) this.index -= 6;
            else if (this.view === "prefs" && this.index > 0) this.index--;
            else { this.zone = "top"; this.index = 0; }
          } else if (code === keys.DOWN) {
            if (this.view === "home") this.show("inputs");
            else if (["apps", "edit", "inputs"].indexOf(this.view) >= 0) this.index += 6;
            else if (this.view === "prefs") this.index++;
          } else if (code === keys.LEFT) this.index--; else if (code === keys.RIGHT) this.index++;
          this.clamp(); return true;
        }
      },
      render: function (h) {
        var vm = this, scale = this.width / 1920;
        var dark = this.theme === "dark" || (this.theme === "auto" && (this.now.getHours() >= 18 || this.now.getHours() < 7));
        var ink = dark ? "#F5F5F7" : "#1D1D1F", muted = dark ? "#a5a5ad" : "#6E6E73";
        function box(x, y, w, height, more) {
          var s = { position: "absolute", left: x * scale + "px", top: y * scale + "px" };
          if (w != null) s.width = w * scale + "px";
          if (height != null) s.height = height * scale + "px";
          Object.keys(more || {}).forEach(function (key) { s[key] = typeof more[key] === "number" ? more[key] * scale + "px" : more[key]; });
          return s;
        }
        function text(x, y, size, value, color) { return h("div", { style: box(x,y,null,null,{fontSize:size,color:color || ink}) }, [value]); }
        function button(label, x, y, w, height, focused, click, extra, children) {
          return h("div", { attrs: { role: "button", "aria-label": label, tabindex: focused ? "0" : "-1" },
            style: box(x,y,w,height,Object.assign({borderRadius:22,backgroundColor: focused ? "#F5F5F7" : dark ? "#28282c" : "#e2e2e7",
              color: focused ? "#1D1D1F" : ink, border: (focused ? 3 : 1)*scale+"px solid "+(focused ? "#79a9ff" : dark ? "#44444a" : "#d1d1d6"),
              fontSize:28,overflow:"hidden",textAlign:"center",lineHeight:height},extra || {})),
            on:{click:click} },children || [label]);
        }
        var nodes = [text(76,52,76,"For You")];
        ["Home", "All apps", "Inputs", "TV Settings", "Preferences"].forEach(function (label,i) {
          nodes.push(button(label,76+i*340,172,310,64,vm.zone==="top" && vm.index===i,function(){vm.zone="top";vm.index=i;vm.select();}));
        });
        var items = this.list(), start = Math.floor(this.index / (this.view === "home" || this.view === "reorder" ? 8 : 18)) * (this.view === "home" || this.view === "reorder" ? 8 : 18);
        var shelf = this.view === "home" || this.view === "reorder";
        if (shelf) {
          var time = ("0"+this.now.getHours()).slice(-2)+":"+("0"+this.now.getMinutes()).slice(-2);
          nodes.push(text(76,300,176,time),text(82,510,40,this.now.toDateString(),muted));
          nodes.push(text(82,610,28,this.view === "reorder" ? "OK picks up / drops an app · Left / Right moves it" : "Your apps. Your TV. No feeds, no ads.",muted));
          nodes.push(h("div",{style:box(60,814,1800,206,{borderRadius:62,backgroundColor:dark?"#17171b":"#ececf0",border:"1px solid "+(dark?"#38383c":"#ffffff")})}));
        } else if (this.view === "about") {
          nodes.push(text(76,300,44,"Free My TV · native VIDAA port"),text(76,380,28,"Design: felipericardo/tv-launcher · f2d984c · MIT",muted),
            text(76,440,28,"Native integration: alvidaa · vendor TV Settings and remote handlers retained",muted),
            text(76,500,26,"No extra launcher server. Original vendor services remain.",muted),
            text(76,560,24,"MIT license and upstream attribution accompany the source and TV bundle.",muted));
        } else nodes.push(text(76,270,38,{apps:"All apps",inputs:"Inputs",edit:"Manage shelf · OK adds/removes a favorite",prefs:"Launcher preferences"}[this.view] || "",muted));
        var favoriteIds = this.shelf().map(id);
        items.slice(start,start+(shelf?8:this.view==="prefs"?6:18)).forEach(function(item,i){
          var index=start+i, isApp=typeof item==="object" && item.appId!=null && vm.view!=="inputs";
          var label=typeof item==="string"?item:vm.view==="inputs"?vm.sourceName(item):item.appName;
          if(vm.view==="edit" && favoriteIds.indexOf(id(item))>=0) label="✓ "+label;
          var x=shelf?100+i*218:vm.view==="prefs"?76:76+(i%6)*298;
          var y=shelf?854:vm.view==="prefs"?340+i*100:vm.view==="about"?720:370+Math.floor(i/6)*185;
          var w=shelf?190:vm.view==="prefs"?1000:270, height=shelf?126:vm.view==="prefs"?76:140;
          var color = isApp ? (/netflix/i.test(label)?"#b20710":/youtube/i.test(label)?"#c4302b":/prime|amazon/i.test(label)?"#17689c":/plex/i.test(label)?"#5b4822":"#293c5b") : null;
          var focused=vm.zone==="shelf" && vm.index===index;
          var icon=isApp && vm.localIcon(item);
          var local=!!icon;
          var children=null;
          // The img-node path failed to paint cached icons on this Cobalt build.
          if(local) children=[h("div",{style:box(18,12,w-36,height-55,{backgroundImage:"url("+JSON.stringify(icon)+")",backgroundSize:"contain",backgroundPosition:"center",backgroundRepeat:"no-repeat"})}),h("div",{style:box(8,height-42,w-16,36,{fontSize:23,lineHeight:36})},[label])];
          nodes.push(button(label,x,y,w,height,focused,function(){vm.zone="shelf";vm.index=index;vm.select();},color && !focused?{backgroundColor:color,color:"#fff"}:null,children));
        });
        if(!items.length) nodes.push(text(90,shelf?870:400,30,"Nothing here yet · All apps and TV Settings remain above",muted));
        nodes.push(text(76,1040,20,this.status+(this.moving?" · MOVING":""),muted));
        return h("div",{attrs:{id:"fmtv-native"},style:{position:"absolute",left:"0",top:"0",width:"100%",height:"100%",overflow:"hidden",backgroundColor:dark?"#0B0B0D":"#F5F5F7",color:ink,fontFamily:"Arial, sans-serif"}},nodes);
      }
    };
  };
}(self));
