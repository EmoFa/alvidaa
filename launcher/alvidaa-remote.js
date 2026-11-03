(function () {
  "use strict";
  // alvidaa overlay v1 — loaded by the appended bootstrap in the stock home's
  // index.html. Builds the launcher as a fixed overlay; the stock system
  // (sdk.js, phoenix services) keeps running beneath. Idempotent.
  if (document.getElementById("alvidaa")) return;
  var BRIDGE = "http://192.168.0.85:8770";

  var st = document.createElement("style");
  st.textContent = "#app { display: none !important; }";
  document.head.appendChild(st);

  var ov = document.createElement("div");
  ov.id = "alvidaa";
  ov.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;" +
    "background:#0a0d12;z-index:2147483647;overflow:hidden;" +
    "font-family:sans-serif;color:#e8eaee";
  ov.innerHTML =
    '<img id="av-bg" alt="" style="position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover">' +
    '<div style="position:absolute;top:0;left:0;width:100%;height:100%;background:rgba(5,8,12,0.35)"></div>' +
    '<div style="position:relative;height:100%">' +
    '  <div id="av-clock" style="position:absolute;top:30px;left:48px;font-size:56px;font-weight:bold">--:--</div>' +
    '  <div id="av-date" style="position:absolute;top:96px;left:50px;font-size:20px;color:#8a8f98"></div>' +
    '  <div id="av-status" style="position:absolute;top:30px;right:52px;font-size:14px;color:#8a8f98"></div>' +
    '  <div style="position:absolute;left:48px;top:164px;font-size:13px;color:#7d8590">INPUTS</div>' +
    '  <div id="av-r0" style="position:absolute;left:48px;right:24px;top:182px;height:96px;display:flex;gap:12px;overflow:hidden"></div>' +
    '  <div style="position:absolute;left:48px;top:298px;font-size:13px;color:#7d8590">APPS</div>' +
    '  <div id="av-r1" style="position:absolute;left:48px;right:24px;top:316px;height:96px;display:flex;gap:12px;overflow:hidden"></div>' +
    '  <div id="av-toast" style="position:absolute;bottom:14px;width:100%;text-align:center;font-size:20px"></div>' +
    '  <div style="position:absolute;bottom:14px;left:48px;font-size:13px;color:#3d4552">navigate · OK open · ▲▼ rows</div>' +
    "</div>";
  document.body.appendChild(ov);

  var S = { apps: null, sources: null, state: null, online: false, hello: false,
            row: 1, col: 0, busy: false };
  var ICONS = {};

  function g(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;"); }

  function renderStatus() {
    g("av-status").innerHTML = S.online
      ? '<span style="color:#4ade80">●</span> <span style="color:#8a8f98">' +
        esc(S.state === "remote_launcher" ? "vidaa home" : (S.state || "tv")) + "</span>"
      : '<span style="color:#f87171">server offline</span>';
  }
  function renderClock() {
    var n = new Date();
    function p2(v) { return (v < 10 ? "0" : "") + v; }
    g("av-clock").textContent = p2(n.getHours()) + ":" + p2(n.getMinutes());
    var days = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
    var mons = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    g("av-date").textContent = days[n.getDay()] + ", " + mons[n.getMonth()] + " " + n.getDate();
  }
  setInterval(renderClock, 1000);

  function items(row) {
    if (row === 0) return (S.sources || []).map(function (s) {
      return { label: s.name || s.id, sub: s.signal ? "signal" : "no signal",
               sig: s.signal, icon: s.icon || "", val: s.id };
    });
    return (S.apps || []).map(function (a) {
      return { label: a.name, sub: "", icon: a.icon || "", val: a.name };
    });
  }
  function rowCount() { return 2; }
  function clampFocus() {
    if (S.row >= rowCount()) S.row = rowCount() - 1;
    if (S.row < 0) S.row = 0;
    var n = items(S.row).length;
    if (S.col >= n) S.col = Math.max(0, n - 1);
  }
  function rowStart(idx) {
    var n = items(idx).length, PAGE = 5;
    if (n <= PAGE) return 0;
    return Math.max(0, Math.min(S.col - 2, n - PAGE));
  }
  function preloadIcons() {
    (S.apps || []).forEach(function (a) {
      if (!a.icon || ICONS[a.icon]) return;
      var im = new Image();
      im.onload = renderRows; im.src = a.icon; ICONS[a.icon] = im;
    });
  }

  function renderRows() {
    for (var r = 0; r < 2; r++) {
      var row = g("av-r" + r);
      var list = items(r), n = list.length, start = rowStart(r);
      var end = Math.min(n, start + 5);
      var html = "";
      if (!S.hello && S.online) {
        html = '<div style="color:#555;padding-top:40px">loading…</div>';
      } else if (n === 0) {
        html = '<div style="color:#3d4552;padding-top:40px">' +
               (r === 0 ? "no inputs reported" : "no apps reported") + "</div>";
      }
      for (var i = start; i < end; i++) {
        var it = list[i];
        var focused = (S.row === r && S.col === i);
        var hasIcon = it.icon && ICONS[it.icon] && ICONS[it.icon].complete && ICONS[it.icon].naturalWidth;
        html += '<div style="flex:0 0 160px;width:160px;height:96px;border-radius:12px;' +
          (focused
            ? "background:#182028;outline:3px solid #f2f4f8;border-radius:14px;box-shadow:0 4px 14px rgba(0,0,0,0.5);"
            : "background:#1a2027;") + 'position:relative;overflow:hidden;margin-right:12px">' +
          (it.sub ? '<div style="position:absolute;top:10px;right:10px;font-size:12px;color:' +
             (it.sig ? "#4ade80" : "#6b7280") + '">' + it.sub + "</div>" : "") +
          (hasIcon
            ? '<img src="' + it.icon + '" alt="" style="position:absolute;top:6px;left:10px;max-width:140px;max-height:52px;object-fit:contain">'
            : '<div style="position:absolute;top:20px;left:0;width:100%;text-align:center;font-size:34px;color:rgba(232,234,238,0.3)">' +
              esc((it.label || "?").charAt(0).toUpperCase()) + "</div>") +
          '<div style="position:absolute;bottom:8px;left:0;width:100%;text-align:center;font-size:14px;color:#e8eaee;white-space:nowrap;overflow:hidden">' +
          esc(it.label || "?") + "</div></div>";
      }
      row.innerHTML = html;
      row.style.transform = "translateX(" + (-start * 172) + "px)";
    }
    renderStatus();
  }

  // ---------------------------------------------------------------- ws
  var ws = null, wsRetry = 0;
  function connect() {
    try { ws = new WebSocket("ws://192.168.0.85:8770/ws"); } catch (e) { schedule(); return; }
    ws.onopen = function () { S.online = true; wsRetry = 0; renderStatus(); };
    ws.onmessage = function (ev) {
      var m; try { m = JSON.parse(ev.data); } catch (e) { return; }
      if (m.t === "hello") {
        S.hello = true; S.online = true;
        S.apps = m.apps || []; S.sources = m.sources || []; S.state = m.state;
        S.busy = false; clampFocus(); preloadIcons(); renderRows(); renderStatus();
      } else if (m.t === "tvstate") { S.state = m.state; renderStatus(); }
      else if (m.t === "sources") { S.sources = m.sources || S.sources; clampFocus(); renderRows(); }
      else if (m.t === "apps") { S.apps = m.apps || S.apps; clampFocus(); preloadIcons(); renderRows(); }
    };
    ws.onclose = function () { S.online = false; schedule(); renderStatus(); };
    ws.onerror = function () { try { ws.close(); } catch (e) {} };
  }
  function schedule() { setTimeout(connect, Math.min(8000, 1000 * Math.pow(2, wsRetry++))); }
  function send(o) { if (S.online && ws && ws.readyState === 1) ws.send(JSON.stringify(o)); }
  function act(type, val) {
    if (S.busy) return;
    S.busy = true; g("av-toast").textContent = "…";
    send({ t: type === "launch" ? "launch" : "source", name: val, id: val });
  }

  // ---------------------------------------------------------------- input
  function activate(row, col) {
    var it = items(row)[col];
    if (it) act(row === 0 ? "source" : "launch", it.val);
  }
  document.addEventListener("keydown", function (e) {
    var list = items(S.row);
    if (e.key === "ArrowRight") { if (S.col < list.length - 1) { S.col++; renderRows(); } }
    else if (e.key === "ArrowLeft") { if (S.col > 0) { S.col--; renderRows(); } }
    else if (e.key === "ArrowUp") { if (S.row > 0) { S.row--; clampFocus(); renderRows(); } }
    else if (e.key === "ArrowDown") { if (S.row < 1) { S.row++; clampFocus(); renderRows(); } }
    else if (e.key === "Enter") {
      var it = items(S.row)[S.col];
      if (it) act(S.row === 0 ? "source" : "launch", it.val);
    }
    e.preventDefault();
  });
  document.addEventListener("click", function (e) {
    // pointer mode: D-pad moves the cursor, OK clicks
    var node = e.target;
    while (node && node.parentNode && node.parentNode.id !== "av-r0" && node.parentNode.id !== "av-r1") {
      node = node.parentNode;
      if (!node || node === document.body) return;
    }
    if (!node || !node.dataset) return;
    var r = parseInt(node.dataset.r, 10), c = parseInt(node.dataset.c, 10);
    if (isNaN(r) || isNaN(c)) return;
    S.row = r; S.col = c; renderRows();
    var it = items(r)[c];
    if (it) act(r === 0 ? "source" : "launch", it.val);
  });

  // ---------------------------------------------------------------- boot
  (function () {
    var bg = g("av-bg");
    bg.onload = renderRows;
    bg.src = BRIDGE + "/bg/bg" + (new Date().getDate() % 3 + 1) + ".png";
  })();
  var boot = document.getElementById("alvidaa-boot");
  if (boot) boot.remove();
  connect();
  renderClock();
  renderRows();
})();
