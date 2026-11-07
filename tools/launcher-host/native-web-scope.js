/* Isolated browser-like globals for the upstream web scripts inside native Home.
 * This is an ownership boundary, not a security sandbox for arbitrary scripts.
 */
(function (root) {
  "use strict";
  function createScope(host, element, options) {
    if (!options || !options.keys || !options.storage || typeof options.isActive !== "function" ||
        typeof options.XMLHttpRequest !== "function" || typeof options.Image !== "function") {
      throw new Error("Scoped route, cache-only XHR and local-image adapters are required");
    }
    var prefix = options.idPrefix || "fmtv-web-";
    var disposed = false, forward = false;
    var timers = new Map(), listeners = Object.create(null), nativeListeners = [];
    var keys = options.keys;
    var ownedKeys = [keys.left, keys.up, keys.right, keys.down, keys.ok, keys.back, 8, 27];
    function active() { return !disposed && options.isActive(); }
    function add(name, callback) {
      if (disposed || typeof callback !== "function") return;
      var list = listeners[name] || (listeners[name] = []);
      if (list.indexOf(callback) < 0) list.push(callback);
    }
    function remove(name, callback) {
      var list = listeners[name], index = list ? list.indexOf(callback) : -1;
      if (index >= 0) list.splice(index, 1);
    }
    function emit(name, event) {
      if (disposed) return;
      (listeners[name] || []).slice().forEach(function (fn) { fn(event || { type: name }); });
    }
    function track(interval, callback, delay) {
      if (disposed) return null;
      if (typeof callback !== "function") throw new Error("String timers are not supported");
      var id, args = Array.prototype.slice.call(arguments, 3);
      function run() {
        if (!interval) timers.delete(id);
        if (!disposed) callback.apply(window, args);
      }
      id = interval ? host.setInterval(run, delay) : host.setTimeout(run, delay);
      timers.set(id, interval);
      return id;
    }
    function clear(id) {
      if (!timers.has(id)) return;
      if (timers.get(id)) host.clearInterval(id); else host.clearTimeout(id);
      timers.delete(id);
    }
    function selector(value) {
      return value.replace(/#([A-Za-z][A-Za-z0-9_-]*)/g, function (_all, id) { return "#" + prefix + id; });
    }
    var document = {
      body: element, documentElement: element,
      createElement: function (tag) {
        if (/^img$/i.test(tag)) {
          if (typeof options.imageElement !== "function") throw new Error("Native image element adapter is required");
          return options.imageElement();
        }
        if (/^(script|iframe|canvas|style|link)$/i.test(tag)) throw new Error("Element requires an explicit native adapter: " + tag);
        return host.document.createElement(tag);
      },
      createTextNode: function (text) { return host.document.createTextNode(text); },
      createElementNS: function () { throw new Error("Vector assets must be prepared for Cobalt"); },
      getElementById: function (id) {
        if (!/^[A-Za-z][A-Za-z0-9_-]*$/.test(id)) return null;
        return element.querySelector("#" + prefix + id);
      },
      querySelector: function (value) { return element.querySelector(selector(value)); },
      querySelectorAll: function (value) { return element.querySelectorAll(selector(value)); },
      addEventListener: add, removeEventListener: remove
    };
    Object.defineProperty(document, "hidden", { get: function () { return !active(); } });
    var window = {
      document: document, navigator: { language: options.language || host.navigator.language },
      localStorage: options.storage, XMLHttpRequest: options.XMLHttpRequest, Image: options.Image,
      addEventListener: add, removeEventListener: remove,
      setTimeout: function () { return track.apply(null, [false].concat(Array.prototype.slice.call(arguments))); },
      setInterval: function () { return track.apply(null, [true].concat(Array.prototype.slice.call(arguments))); },
      clearTimeout: clear, clearInterval: clear
    };
    window.window = window; window.self = window;
    Object.defineProperty(window, "innerWidth", { get: function () { return host.innerWidth; } });
    Object.defineProperty(window, "innerHeight", { get: function () { return host.innerHeight; } });
    function listen(target, name, fn) {
      target.addEventListener(name, fn);
      nativeListeners.push(function () { target.removeEventListener(name, fn); });
    }
    listen(host, "resize", function (event) { if (active()) emit("resize", event); });
    listen(element, "mousemove", function (event) { if (active()) emit("mousemove", event); });
    return {
      window: window, document: document, emit: emit,
      forwardKey: function () { forward = true; },
      key: function (event) {
        if (!active()) return false;
        var prevented = false;
        forward = false;
        emit("keydown", { type: "keydown", keyCode: event.keyCode, repeat: event.repeat,
          preventDefault: function () { prevented = true; } });
        // A custom saver may wake on Volume, but must not consume that native
        // action. Back at the Home root explicitly forwards to the firmware.
        return prevented && !forward && ownedKeys.indexOf(event.keyCode) >= 0;
      },
      dispose: function () {
        if (disposed) return;
        disposed = true;
        timers.forEach(function (_interval, id) { clear(id); });
        nativeListeners.forEach(function (off) { off(); });
        nativeListeners = [];
        listeners = Object.create(null);
      }
    };
  }
  if (typeof module !== "undefined" && module.exports) module.exports = createScope;
  else root.AlvidaaNativeWebScope = createScope;
}(typeof self !== "undefined" ? self : this));
