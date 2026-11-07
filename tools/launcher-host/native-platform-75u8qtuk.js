/* Native VIDAA data adapter for 75U8QTUK / V0000.09.60I.Q0813.
 *
 * Contracts are source-verified against the private vendor copies in
 * firmware/75u8qtuk/ (launcher app.js chunks + operationui app-service and
 * systemui 861.js/sdk.js). They differ from the 55A7KAU adapter:
 *   - apps come from getAppList({sceneCode:"launcher"}), not getCurrentShowApps
 *   - storeType is the app record's storeType/openMode, not a separate service
 *   - settings opens with open("settings") and no vk argument
 *   - app launch goes through sdk.apc.start (=== the stock MP) with
 *     CMDMETHOD.LAUNCHER_RECOMMEND ("52") and typeCode "600002"
 *
 * APC still owns parental PIN, EULA and hotel-mode checks. getAppInfo with
 * checkRange:1 is an extra availability gate, never a bypass.
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
      var value = response && response.result;
      if (!Array.isArray(value)) {
        throw new Error(module + "." + key + " did not return a list");
      }
      return value.slice();
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
      // list. One failed service must not hide the other.
      try { apps = readList("app-service", "getAppList", { sceneCode: "launcher" }); }
      catch (error) { errors.push("Apps: " + error.message); }
      try { sources = readList("all-inputs", "getAllInputsData"); }
      catch (error) { errors.push("Inputs: " + error.message); }
      reading = false;
      var waiting = errors.length > 0 || apps.length === 0 || sources.length === 0;
      var retrying = waiting && attempt < delays.length;
      if (retrying) timer = setTimeout(refresh, delays[attempt++]);
      try {
        onUpdate({ apps: apps.slice(), sources: sources.slice(), errors: errors,
          waiting: waiting, retrying: retrying });
      } catch (_) { /* a consumer throw must not leave `reading` stuck */ }
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
    function command(name, fallback) {
      var cm = sdk.apc && sdk.apc.CMDMETHOD;
      return (cm && cm[name]) || fallback;
    }
    function has(object, key) {
      return Object.prototype.hasOwnProperty.call(object, key);
    }
    function pick(primary, secondary, key, fallback) {
      if (primary && has(primary, key) && primary[key] != null) return primary[key];
      if (secondary && has(secondary, key) && secondary[key] != null) return secondary[key];
      return fallback;
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
        return sdk.me.req("setting").open("settings");
      },
      launchApp: function (appId) {
        var item = apps.filter(function (app) {
          return app && String(app.appId) === String(appId);
        })[0];
        if (!item) throw new Error("App is not in the current native app list");
        // Same availability/detail query the stock launcher uses (1aWR.xi).
        var response = sdk.me.req("app-service").getData("getAppInfo",
          { appId: String(appId), url: "", checkRange: 1 });
        var info = response && response.result;
        if (!info) throw new Error("App is unavailable or restricted");
        if (typeof info === "object" && info.appId != null &&
            String(info.appId) !== String(appId)) {
          throw new Error("App details do not match the requested app");
        }
        var detail = typeof info === "object" && info ? info : {};
        // Mirrors the stock tileOpenAction/MP.start object shape. No bypass
        // flags: APC performs its own PIN/EULA/hotel checks.
        return sdk.apc.start({
          name: String(pick(detail, item, "appName", "")),
          appId: pick(detail, item, "appId", String(appId)),
          url: String(pick(detail, item, "url", "")),
          storeType: pick(detail, item, "storeType", pick(detail, item, "openMode", 0)),
          startMethod: command("LAUNCHER_RECOMMEND", "52"),
          typeCode: String(pick(detail, item, "typeCode", "600002")),
          rateInfo: ""
        });
      },
      changeSource: function (sourceId) {
        var validId = (typeof sourceId === "string" && sourceId.trim() !== "") ||
          (typeof sourceId === "number" && isFinite(sourceId));
        if (!validId || !sources.some(function (source) {
          return source && source.sourceId === sourceId;
        })) {
          throw new Error("Input is not in the current native source list");
        }
        return sdk.me.req("all-inputs").invoke("changeSourceTo", sourceId, "launcher");
      }
    };
  }
  if (typeof module !== "undefined" && module.exports) module.exports = createNativePlatform;
  else root.AlvidaaNativePlatform = createNativePlatform;
}(typeof self !== "undefined" ? self : this));
