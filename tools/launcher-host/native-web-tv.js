/* VIDAA implementation of the pinned Free My TV web TV interface.
 * Presentation stays upstream-owned; this adapter only maps native contracts.
 */
(function (root) {
  "use strict";
  function createWebTV(sdk, options) {
    options = options || {};
    var createPlatform = options.createPlatform || root.AlvidaaNativePlatform;
    if (typeof createPlatform !== "function") throw new Error("Native SDK platform is required");
    if (typeof options.back !== "function" || typeof options.holdScreenSaver !== "function") {
      throw new Error("Native Back and screensaver lifecycle adapters are required");
    }
    var apps = [], inputs = [], appIds = {}, sourceIds = {};
    var running = false, releaseSaver = null, signature = "";
    var keys = sdk.key.KEYMAP;

    function validId(value) {
      return (typeof value === "string" && value.trim() !== "") ||
        (typeof value === "number" && isFinite(value));
    }
    function icon(app) {
      var values = [app.img, app.presetImg, app.icon, app.appIcon];
      for (var i = 0; i < values.length; i++) {
        var value = values[i];
        if (typeof value !== "string" || /[\x00-\x1f\\]/.test(value)) continue;
        if (/(^|\/)\.\.(\/|$)/.test(value) || /%2e|%2f|%5c/i.test(value)) continue;
        if (/^var\/local\/storeAppIcon\//.test(value)) return "file:///hisenseUI/" + value;
        if (/^file:\/\/\//.test(value) || /^\/(?!\/)/.test(value)) return value;
        if (/^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(value) && value.length <= 1048576) return value;
      }
      return "";
    }
    function sourceName(input) {
      var name = (typeof input.rename === "string" && input.rename.trim() && input.rename) ||
        (typeof input.name === "string" && input.name.trim() && input.name) || String(input.sourceId);
      if (/^[A-Z]{2,4}[0-9]{4,}$/.test(name) && sdk.i18n && sdk.i18n.t) {
        try { var translated = sdk.i18n.t(name); return translated && translated !== name ? translated : input.name || name; }
        catch { return input.name || name; }
      }
      return name;
    }
    function update(data) {
      if (!running) return;
      appIds = Object.create(null); sourceIds = Object.create(null);
      apps = [];
      data.apps.forEach(function (app) {
        if (!app || !validId(app.appId) || typeof app.appName !== "string" || !app.appName.trim()) return;
        var nativeId = String(app.appId), id = "app:" + nativeId;
        if (!nativeId || nativeId === "206" || nativeId === "vidaa-home" || id in appIds) return;
        appIds[id] = nativeId;
        apps.push({ id: id, title: app.appName, icon: icon(app),
          color: /^#[0-9a-f]{6}$/i.test(app.bgColor || "") ? app.bgColor : "" });
      });
      inputs = [];
      data.sources.forEach(function (input) {
        if (!input || !validId(input.sourceId)) return;
        var nativeId = input.sourceId, id = "source:" + nativeId;
        if (nativeId === "vidaahome" || id in sourceIds) return;
        sourceIds[id] = nativeId;
        var live = nativeId === "TV", hdmi = /^HDMI\d+$/i.test(String(nativeId));
        inputs.push({ id: id, key: live ? "live" : String(nativeId).toLowerCase(),
          label: sourceName(input), symbol: live ? "live_tv" : hdmi ? "hdmi" : "tv",
          connected: input.hasSignal !== false && input.hasSignal !== 0 });
      });
      var next = JSON.stringify([apps, inputs]);
      if (next !== signature) {
        signature = next;
        if (options.onChange) options.onChange();
      }
    }
    var platform = createPlatform(sdk, update);
    function action(fn, done) {
      if (!running) { if (done) done(false); return; }
      var result;
      try { result = fn(); }
      catch { if (done) done(false); return; }
      // An accepted SDK request is not proof that an app rendered or played.
      Promise.resolve(result).then(function (value) { if (done) done(value !== false); },
        function () { if (done) done(false); });
    }
    function releaseHold() {
      var release = releaseSaver;
      releaseSaver = null;
      if (release) release();
    }
    function hold(predicate) {
      if (typeof predicate !== "function") throw new Error("Screensaver hold requires a predicate");
      if (!running) return;
      releaseHold();
      // Upstream asks dynamically: a sheet or missing photos must not suppress
      // native protection. Fail open to the vendor screensaver on any error.
      var release = options.holdScreenSaver(function () {
        if (!running) return false;
        try { return !!predicate(); } catch { return false; }
      });
      if (typeof release !== "function") throw new Error("Screensaver registration must provide cleanup");
      releaseSaver = release;
    }
    return {
      name: "vidaa",
      keys: { left: keys.LEFT, up: keys.UP, right: keys.RIGHT, down: keys.DOWN,
        ok: keys.ENTER, back: keys.BACK == null ? keys.BACKSPACE : keys.BACK },
      start: function () {
        if (running) return;
        running = true;
        try { platform.start(); }
        catch (error) { running = false; platform.stop(); throw error; }
      },
      stop: function () {
        if (!running) return;
        try { releaseHold(); }
        finally { running = false; platform.stop(); }
      },
      apps: function (done) { done(apps.map(function (app) { return Object.assign({}, app); })); },
      inputs: function (done) { done(inputs.map(function (input) { return Object.assign({}, input); })); },
      launch: function (id, _params, done) {
        action(function () {
          if (Object.prototype.hasOwnProperty.call(sourceIds, id)) return platform.changeSource(sourceIds[id]);
          if (Object.prototype.hasOwnProperty.call(appIds, id)) return platform.launchApp(appIds[id]);
          throw new Error("Unknown or removed native app/input");
        }, done);
      },
      settings: function (done) { action(function () { return platform.openSettings(); }, done); },
      holdScreenSaver: hold,
      back: function () { if (running) options.back(); },
      zone: function () { return typeof options.timeZone === "function" ? options.timeZone() : options.timeZone || ""; }
    };
  }
  if (typeof module !== "undefined" && module.exports) module.exports = createWebTV;
  else root.AlvidaaNativeWebTV = createWebTV;
}(typeof self !== "undefined" ? self : this));
