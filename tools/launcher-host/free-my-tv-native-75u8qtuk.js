/* 75U8QTUK / V0000.09.60I.Q0813 adjustments to the shared native frontend.
 *
 * The shared free-my-tv-native.js is left untouched for the 55A7KAU lane.
 * Differences on this build, all source-verified against private vendor
 * copies in firmware/75u8qtuk/:
 *   - app icons are vendor HTTPS URLs on https://img.vidaahub.com/ (feed
 *     tiles) or app-service `img`/`httpIcon`/`icon_*` fields; the shared
 *     localIcon() rejects them, so every tile would lose its art.
 *   - KEYMAP.RETURN does not exist (BACK === BACKSPACE === 8); the shared
 *     handleKey comparison with undefined is harmless and stays as-is.
 *   - sdk.apc.CMDMETHOD / sdk.tts are populated by vendor services at
 *     runtime; guard the two shared methods that dereference them so a late
 *     or missing service degrades to a plain (silent) Home instead of a
 *     thrown key handler.
 *
 * Owner-requested customizations (2026-11-06, findings/10):
 *   - apps and inputs are merged into one list. Inputs are exposed as
 *     app-shaped tiles carrying `__alvidaaSource`, so the shared Vue render
 *     path (labels, icons, grid, focus) works unchanged; select() dispatches
 *     them to changeSource instead of launchApp. The Home shelf and the
 *     "All" tab both show the merged list; "Inputs" remains an input-only
 *     shortcut.
 *   - a CSS-gradient wallpaper picker in Preferences. Gradients are pure
 *     inline CSS: no files on the TV, no network, no canvas. A translucent
 *     overlay child is prepended to the root VNode, so theme-driven ink
 *     colours and all existing tiles stay readable and paint on top.
 */
(function (root) {
  "use strict";
  var base = root.AlvidaaFreeMyTV;
  if (typeof base !== "function") throw new Error("Shared native frontend is required");

  var LOCAL = /^(var\/local\/storeAppIcon\/|file:\/\/\/|\/(?!\/)|data:image\/(png|jpeg|webp);base64,)/i;
  var VENDOR_ICON = /^https:\/\/img\.vidaahub\.com\//i;

  // Low-alpha gradients: readable over both the dark and light solid bases,
  // and they add no files, requests or canvas work to the TV.
  var WALLPAPERS = [
    { id: "none", label: "None", css: "" },
    { id: "dusk", label: "Dusk", css: "linear-gradient(135deg, rgba(88,52,140,.38) 0%, rgba(36,40,92,.30) 48%, rgba(12,14,24,.14) 100%)" },
    { id: "ocean", label: "Ocean", css: "linear-gradient(160deg, rgba(16,96,132,.36) 0%, rgba(12,54,84,.28) 52%, rgba(8,20,32,.14) 100%)" },
    { id: "ember", label: "Ember", css: "linear-gradient(135deg, rgba(148,56,30,.34) 0%, rgba(88,34,48,.26) 52%, rgba(20,12,18,.12) 100%)" },
    { id: "aurora", label: "Aurora", css: "linear-gradient(150deg, rgba(20,112,92,.34) 0%, rgba(28,72,112,.28) 52%, rgba(10,18,28,.12) 100%)" }
  ];
  function wallpaper(id) {
    for (var i = 0; i < WALLPAPERS.length; i++) if (WALLPAPERS[i].id === id) return WALLPAPERS[i];
    return WALLPAPERS[0];
  }
  function nextWallpaper(id) {
    for (var i = 0; i < WALLPAPERS.length; i++) {
      if (WALLPAPERS[i].id === id) return WALLPAPERS[(i + 1) % WALLPAPERS.length].id;
    }
    return WALLPAPERS[0].id;
  }

  root.AlvidaaFreeMyTV = function (sdk) {
    var component = base(sdk);
    var methods = component.methods;
    var keys = sdk.key.KEYMAP;

    function prefs() {
      try {
        var value = sdk.storage.get("alvidaa.freeMyTV");
        if (typeof value === "string") value = JSON.parse(value);
        return value && typeof value === "object" ? value : {};
      } catch (_) { return {}; }
    }

    // --- vendor icon override ---
    methods.localIcon = function (app) {
      var candidates = [app.img, app.httpIcon, app.icon_web_url, app.icon_local_url,
        app.presetImg, app.icon, app.appIcon];
      for (var i = 0; i < candidates.length; i++) {
        var value = candidates[i];
        if (typeof value !== "string" || !value) continue;
        if (VENDOR_ICON.test(value)) return value;
        if (LOCAL.test(value)) {
          return value.indexOf("var/local/storeAppIcon/") === 0 ? "file:///hisenseUI/" + value : value;
        }
      }
      return "";
    };

    // --- guard vendor SDKs that are populated by services at runtime ---
    var announce = methods.announce;
    methods.announce = function () {
      try { return announce.call(this); } catch (_) { return undefined; }
    };
    var routeFocus = methods.routeFocus;
    methods.routeFocus = function () {
      try { return routeFocus.call(this); }
      catch (_) {
        this.view = "home";
        this.zone = "shelf";
        this.index = 0;
        this.moving = false;
      }
    };

    // --- merged apps + inputs ---
    function inputTile(vm, source) {
      return {
        appId: "__alvidaa_input__" + String(source.sourceId),
        appName: vm.sourceName(source),
        img: source.icon || "",
        __alvidaaSource: source
      };
    }
    function inputTiles(vm) {
      return vm.sources.map(function (source) { return inputTile(vm, source); });
    }
    function isInput(item) { return !!(item && item.__alvidaaSource); }

    var originalList = methods.list;
    methods.list = function () {
      if (this.view === "prefs") {
        var items = originalList.call(this);
        items[4] = "Wallpaper: " + wallpaper(this.wallpaper).label;
        return items;
      }
      if (this.view === "apps") return this.apps.concat(inputTiles(this));
      if (this.view === "home") return originalList.call(this).concat(inputTiles(this));
      return originalList.call(this);
    };

    var originalSelect = methods.select;
    methods.select = function () {
      if (this.zone === "shelf") {
        var item = this.list()[this.index];
        if (isInput(item)) {
          var vm = this, source = item.__alvidaaSource;
          this.run(function () { return vm._platform.changeSource(source.sourceId); });
          return;
        }
        if (this.view === "prefs" && this.index === 4) {
          this.wallpaper = nextWallpaper(this.wallpaper);
          this.save();
          // The old "Refresh apps & inputs" row becomes the wallpaper row;
          // OK still refreshes so no capability is lost.
          if (this._platform && this._platform.refresh) this._platform.refresh();
          return;
        }
      }
      return originalSelect.call(this);
    };

    var originalHandleKey = methods.handleKey;
    methods.handleKey = function (code) {
      if (code === keys.DOWN && !this.moving && this.view === "home" && this.zone === "shelf") {
        this.show("apps"); // the merged list, not the inputs-only view
        return true;
      }
      return originalHandleKey.call(this, code);
    };

    // --- wallpaper preference ---
    var originalData = component.data;
    component.data = function () {
      var state = originalData.call(this);
      state.wallpaper = wallpaper(prefs().wallpaper).id;
      return state;
    };
    methods.save = function () {
      try {
        sdk.storage.set("alvidaa.freeMyTV", {
          theme: this.theme, favorites: this.favorites, wallpaper: this.wallpaper
        });
      } catch (error) { this.status = "Could not save preferences: " + error.message; }
    };

    // --- render: translucent wallpaper overlay + relabel the merged tab ---
    function buttonText(node) {
      if (!node || !node.children || !node.children.length) return null;
      var first = node.children[0];
      if (typeof first === "string") return first;
      return first && typeof first.text === "string" ? first.text : null;
    }
    function setButtonText(node, label) {
      var first = node.children[0];
      if (typeof first === "string") node.children[0] = label;
      else if (first && typeof first.text === "string") first.text = label;
    }
    var originalRender = component.render;
    component.render = function (h) {
      var vnode = originalRender.call(this, h);
      var children = vnode && vnode.children;
      if (!children || !children.length) return vnode;
      for (var i = 0; i < children.length; i++) {
        var node = children[i];
        var attrs = node && node.data && node.data.attrs;
        if (attrs && attrs["aria-label"] === "All apps" && buttonText(node) === "All apps") {
          setButtonText(node, "All");
          attrs["aria-label"] = "All";
        }
      }
      var wp = wallpaper(this.wallpaper);
      if (wp.css) {
        children.unshift(h("div", { style: {
          position: "absolute", left: "0", top: "0", width: "100%", height: "100%",
          backgroundImage: wp.css, backgroundSize: "cover", backgroundPosition: "center",
          backgroundRepeat: "no-repeat", pointerEvents: "none"
        } }, []));
      }
      return vnode;
    };

    return component;
  };
}(self));
