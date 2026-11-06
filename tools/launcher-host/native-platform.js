/* Native VIDAA data adapter. No browser/bridge transport.
 * Not wired into the installed N02 module: see FREE-MY-TV-NATIVE-PORT.md.
 * Contracts are source-verified; hardware validation is still required.
 */
(function (root) {
  "use strict";
  function createNativePlatform(sdk, onUpdate) {
    var events = [
      "o2n://sdk/init-finished",
      "o2n://app-service/all-apps-changed",
      "o2n://all-inputs/inputs-data-changed",
      "o2n://sdk/str-resuming"
    ];
    var delays = [250, 500, 1000, 2000, 4000, 8000];
    var apps = [], sources = [], running = false, reading = false, timer = null, attempt = 0;

    function readList(module, key, argument) {
      var response = sdk.me.req(module).getData(key, argument);
      if (!response || !Array.isArray(response.result)) {
        throw new Error(module + "." + key + " did not return a list");
      }
      return response.result.slice();
    }
    function cancelTimer() {
      clearTimeout(timer);
      timer = null;
    }
    function refresh() {
      if (!running) return;
      cancelTimer();
      var errors = [];
      reading = true;
      // Keep the last good list on a failed read, but accept a successful empty
      // list (e.g. all apps removed). One failed service must not hide the other.
      try { apps = readList("app-service", "getCurrentShowApps", "Launcher"); }
      catch (error) { errors.push("Apps: " + error.message); }
      try { sources = readList("all-inputs", "getAllInputsData"); }
      catch (error) { errors.push("Inputs: " + error.message); }
      reading = false;
      var waiting = errors.length > 0 || apps.length === 0 || sources.length === 0;
      var retrying = waiting && attempt < delays.length;
      if (retrying) timer = setTimeout(refresh, delays[attempt++]);
      onUpdate({ apps: apps.slice(), sources: sources.slice(), errors: errors,
        waiting: waiting, retrying: retrying });
    }
    function changed() {
      if (!running || reading) return;
      // Coalesce notifications. Ignore synchronous notifications caused by our
      // own reads: otherwise lazy initialization can reset the retry budget.
      attempt = 0;
      cancelTimer();
      timer = setTimeout(refresh, 0);
    }
    function stop() {
      if (!running) return;
      running = false;
      cancelTimer();
      events.forEach(function (event) { sdk.message.off(event, changed); });
    }
    return {
      start: function () {
        if (running) return;
        running = true;
        attempt = 0;
        try {
          events.forEach(function (event) { sdk.message.on(event, changed); });
          refresh();
        } catch (error) { stop(); throw error; }
      },
      stop: stop,
      refresh: changed,
      openSettings: function () {
        return sdk.me.req("setting").open("settings", { vk: "T" });
      },
      launchApp: function (appId) {
        if (!apps.some(function (app) { return app && String(app.appId) === String(appId); })) {
          throw new Error("App is not in the current native app list");
        }
        var response = sdk.me.req("app-service").getData("getAppInfoByAppId",
          { appId: String(appId), url: "", checkRange: 1 });
        var app = response && response.result;
        if (!app || String(app.appId) !== String(appId)) throw new Error("App is unavailable or restricted");
        // APC owns parental PIN, EULA and hotel-mode checks. Never propagate
        // bypass flags from a UI record or invoke the lower-level app service.
        return sdk.apc.start({ name: app.appName || "", appId: app.appId,
          url: app.url || "", storeType: app.storeType,
          startMethod: sdk.apc.CMDMETHOD.REMOTECONTROL, typeCode: "600002" });
      },
      changeSource: function (sourceId) {
        var validId = (typeof sourceId === "string" && sourceId.trim() !== "") ||
          (typeof sourceId === "number" && isFinite(sourceId));
        if (!validId || !sources.some(function (source) { return source && source.sourceId === sourceId; })) {
          throw new Error("Input is not in the current native source list");
        }
        return sdk.me.req("all-inputs").invoke("changeSourceTo", sourceId, "launcher");
      }
    };
  }
  if (typeof module !== "undefined" && module.exports) module.exports = createNativePlatform;
  else root.AlvidaaNativePlatform = createNativePlatform;
}(typeof self !== "undefined" ? self : this));
