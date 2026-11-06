/* Historical N02 prototype, retained for regression tests and old backups.
 * Its bridge dependency is retired. For the current native frontend use
 * build-native.cjs and NATIVE-LAUNCHER.md. The old trial CLI is DISABLED.
 */
(function (root) {
  "use strict";
  root._V_M_ = root._V_M_ || {};
  root._V_M_.launcher = function () {
    var sdk = new root._V_SDK_.vre.SDK("launcher", { storagePrefix: "Alvidaa" });
    var biz = root._V_SDK_.biz;
    var keys = sdk.key.KEYMAP;
    var active = null;
    var logger = new biz.Logger("alvidaa-native");
    function report(stage) { logger.always("alvidaa-native: " + stage); }
    report("factory");

    function allowed() { return !biz.kidsMode.getKidsMode(); }
    function open(query) {
      if (!allowed()) return Promise.reject(new Error("Kids mode is unsupported by this candidate"));
      return sdk.router.push({ path: "/Launcher", query: query || {} });
    }
    function unsupported() {
      return Promise.reject(new Error("Kids/game launcher is unsupported by this candidate"));
    }
    function clock() {
      var now = new Date();
      return ("0" + now.getHours()).slice(-2) + ":" + ("0" + now.getMinutes()).slice(-2);
    }
    var component = {
      name: "Launcher", // Shared shell's keep-alive list uses this name.
      data: function () {
        return { apps: [], sources: [], row: 0, col: 0, time: clock(), status: "Connecting to local bridge" };
      },
      mounted: function () { this.start(); },
      activated: function () { this.start(); },
      deactivated: function () { this.stop(); },
      beforeDestroy: function () { this.stop(); },
      methods: {
        start: function () {
          if (this._running) return;
          this._running = true;
          active = this;
          report("active");
          var vm = this;
          this.time = clock();
          this._clock = setInterval(function () { vm.time = clock(); }, 1000);
          this.connect();
        },
        stop: function () {
          this._running = false;
          if (active === this) active = null;
          clearInterval(this._clock);
          clearTimeout(this._retry);
          clearTimeout(this._connectTimeout);
          if (this._socket) {
            this._socket.onopen = this._socket.onmessage = this._socket.onclose = this._socket.onerror = null;
            this._socket.close();
            this._socket = null;
          }
        },
        connect: function () {
          var vm = this;
          if (!this._running) return;
          var socket;
          function retry() {
            if (!vm._running) return;
            vm.status = "Bridge unavailable; retrying";
            clearTimeout(vm._retry);
            vm._retry = setTimeout(function () { vm.connect(); }, 2000);
          }
          try { socket = new root.WebSocket("ws://127.0.0.1:8770/ws"); }
          catch (error) { retry(); return; }
          this._socket = socket;
          this._connectTimeout = setTimeout(function () {
            if (vm._socket === socket) socket.close();
          }, 10000);
          socket.onopen = function () {
            clearTimeout(vm._connectTimeout);
            vm.status = "Connected";
            report("bridge connected");
          };
          socket.onmessage = function (event) {
            if (!vm._running || vm._socket !== socket) return;
            var msg;
            try { msg = JSON.parse(event.data); } catch (error) { report("Invalid bridge message: " + error.message); return; }
            if (!msg || typeof msg !== "object") return;
            if (msg.t === "hello") {
              vm.apps = Array.isArray(msg.apps) ? msg.apps.filter(function (a) {
                return a && typeof a.name === "string" && a.name.trim() !== "" && a.appId !== "vidaa-home";
              }) : [];
              vm.sources = Array.isArray(msg.sources) ? msg.sources.filter(function (s) {
                return s && (typeof s.id === "string" || (typeof s.id === "number" && isFinite(s.id))) &&
                  typeof s.name === "string";
              }).map(function (s) { return { id: String(s.id), name: s.name }; }) : [];
              vm.clamp();
            } else if (msg.ok === false) vm.status = "Action failed";
          };
          socket.onerror = function () { socket.close(); };
          socket.onclose = function () {
            if (vm._socket === socket) {
              clearTimeout(vm._connectTimeout);
              vm._socket = null;
              retry();
            }
          };
        },
        items: function () { return this.row === 0 ? this.sources : this.apps; },
        clamp: function () { this.col = Math.max(0, Math.min(this.col, this.items().length - 1)); },
        move: function (code) {
          if (code === keys.LEFT) this.col--;
          else if (code === keys.RIGHT) this.col++;
          else if (code === keys.UP) this.row = 0;
          else if (code === keys.DOWN) this.row = 1;
          else if (code === keys.ENTER) { this.activate(); return; }
          this.clamp();
        },
        activate: function () {
          var item = this.items()[this.col];
          if (!item) return;
          if (!this._socket || this._socket.readyState !== 1) { this.status = "Bridge unavailable"; return; }
          var msg = this.row === 0 ? { t: "source", id: item.id } : { t: "launch", name: item.name };
          try { this._socket.send(JSON.stringify(msg)); this.status = "Opening " + item.name; }
          catch (error) { this.status = "Action failed"; report(error.message); }
        }
      },
      render: function (h) {
        var vm = this;
        var children = [h("div", { style: { position: "absolute", left: "3rem", top: "2rem", fontSize: "2rem", color: "#ffcc00" } }, ["ALVIDAA — NATIVE TEST N02"]),
          h("div", { style: { position: "absolute", right: "3rem", top: "2rem", fontSize: "2rem" } }, [this.time])];
        [this.sources, this.apps].forEach(function (items, row) {
          var top = 150 + row * 220;
          children.push(h("div", { style: { position: "absolute", left: "3rem", top: (top / 20) + "rem" } }, [row === 0 ? "Inputs" : "Apps"]));
          var start = row === vm.row ? Math.floor(vm.col / 6) * 6 : 0;
          items.slice(start, start + 6).forEach(function (item, i) {
            var col = start + i;
            children.push(h("div", {
              key: row + ":" + col,
              style: { position: "absolute", left: ((60 + i * 190) / 20) + "rem", top: ((top + 50) / 20) + "rem",
                width: "8.25rem", height: "6rem", padding: "0.4rem", fontSize: "1.2rem",
                overflow: "hidden",
                backgroundColor: row === vm.row && col === vm.col ? "#285ea8" : "#26303e" },
              on: { click: function () { vm.row = row; vm.col = col; vm.activate(); } }
            }, [item.name]));
          });
        });
        children.push(h("div", { style: { position: "absolute", left: "3rem", bottom: "2rem", fontSize: "1.1rem" } }, [this.status]));
        return h("div", { style: { position: "absolute", left: "0", top: "0", width: "100%", height: "100%",
          color: "#ffffff", backgroundColor: "#0a0d12", fontSize: "1.4rem" } }, children);
      }
    };
    return {
      name: "Launcher", version: "1.0.0", meta: {},
      route: [{ path: "/Launcher", component: component,
        meta: { isBgRecord: true, isBgTshift: false, isFull: true,
          sourceInfo: { sourceStatus: "HIDE", appId: "206" }, pathBelong: "launcher" },
        beforeEnter: function (_to, _from, next) { next(allowed()); } }],
      page: { launcherHome: open, kidsLauncherHome: unsupported, gameLauncherHome: unsupported },
      data: {
        launcherAppVersion: "alvidaa-local-prototype",
        get launcherDisableCecChange() { return sdk.router.isCurrentPathEqualTo("/Launcher"); }
      },
      key: { keydown: { groups: [
        { keys: [keys.HOME, keys.LAUNCHER], handler: function () {
          return open().catch(function (error) { report("Home rejected: " + error.message); });
        } },
        { keys: [keys.UP, keys.DOWN, keys.LEFT, keys.RIGHT, keys.ENTER], handler: function (event) {
          if (active && sdk.router.isCurrentPathEqualTo("/Launcher")) active.move(event.keyCode);
        } }
      ] } },
      init: function () { report("init"); },
      reset: function () {}
    };
  };
}(self));
