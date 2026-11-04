(function () {
  "use strict";
  // alvidaa v2 overlay: 1080p HiDPI Canvas (no layered DOM/CSS).
  // Cobalt Starboard renders 2D canvas via Mali GPU hardware acceleration.
  // Instant frame-1 cold cache (localStorage), 1-9 hotkeys, signal indicators,
  // remote D-pad + click hit-testing, and auto-switch countdown.
  if (document.getElementById("alvidaa-cv")) return;

  var BRIDGE = "http://192.168.0.85:8770";
  function resolveUrl(u) {
    if (!u) return "";
    if (/^(https?:|data:)/.test(u)) return u;
    return BRIDGE + (u.charAt(0) === "/" ? "" : "/") + u;
  }

  // 1. Ensure stock home is hidden
  var st = document.getElementById("alvidaa-cv-style");
  if (!st) {
    st = document.createElement("style");
    st.id = "alvidaa-cv-style";
    st.textContent = "#app { display: none !important; } html, body { margin: 0; padding: 0; background: #0a0d12 !important; overflow: hidden; height: 100%; }";
    document.head.appendChild(st);
  }

  // 2. Create the HiDPI Canvas
  var cv = document.createElement("canvas");
  cv.id = "alvidaa-cv";
  var W = 960, H = 540, SCALE = 2;
  cv.width = W * SCALE;
  cv.height = H * SCALE;
  cv.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;z-index:2147483647;display:block;background:#0a0d12";
  (document.body || document.documentElement).appendChild(cv);

  var ctx = cv.getContext("2d");
  var CACHE_KEY = "alvidaa_cache_v1";
  var LAST_KEY = "alvidaa_last_v1";

  // ---------------------------------------------------------------- state
  var S = {
    apps: null, sources: null, shortcuts: [], state: null,
    online: false, hello: false,
    row: 0, col: 0,
    toast: "", toastUntil: 0,
    busy: false,
    focusPicked: false, liveReceived: false, userInteracted: false,
    autoSwitchId: null, autoSwitchName: "", autoSwitchAt: 0
  };

  function loadCache() {
    try {
      var raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return;
      var c = JSON.parse(raw);
      if (c && (c.apps || c.sources)) {
        S.apps = c.apps || [];
        S.sources = c.sources || [];
        S.shortcuts = c.shortcuts || [];
        S.hello = true;
        preloadIcons();
        pickInitialFocus(false);
      }
    } catch (e) {}
  }

  function saveCache() {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({
        apps: S.apps,
        sources: S.sources,
        shortcuts: S.shortcuts
      }));
    } catch (e) {}
  }

  function saveLastUsed(row, val) {
    if (!val) return;
    try { localStorage.setItem(LAST_KEY, JSON.stringify({ row: row, val: val })); } catch (e) {}
  }
  function getLastUsed() {
    try { var raw = localStorage.getItem(LAST_KEY); return raw ? JSON.parse(raw) : null; } catch (e) { return null; }
  }

  var PAGE = 5;

  function pickInitialFocus(fromLiveHello) {
    if (S.focusPicked && !fromLiveHello) return;
    var srcs = S.sources || [];
    var activeIdx = -1, activeCount = 0;
    for (var i = 0; i < srcs.length; i++) {
      if (srcs[i].signal) {
        if (activeIdx < 0) activeIdx = i;
        activeCount++;
      }
    }
    if (activeIdx >= 0) {
      S.row = 0; S.col = activeIdx; S.focusPicked = true;
      if (fromLiveHello && activeCount === 1 && !S.autoSwitchAt && S.autoSwitchCfg) {
        S.autoSwitchId = srcs[activeIdx].id;
        S.autoSwitchName = srcs[activeIdx].name || srcs[activeIdx].id;
        S.autoSwitchAt = Date.now() + 3500;
      }
      return;
    }
    var last = getLastUsed();
    if (last) {
      var list = items(last.row);
      for (var j = 0; j < list.length; j++) {
        if (list[j].val === last.val || list[j].shortcut === last.val) {
          S.row = last.row; S.col = j; S.focusPicked = true; return;
        }
      }
    }
    clampFocus();
  }

  function cancelAutoSwitch() {
    if (S.autoSwitchAt) {
      S.autoSwitchAt = 0; S.autoSwitchId = null;
      S.toast = "auto-switch cancelled"; S.toastUntil = Date.now() + 1800;
      draw();
    }
  }

  // ---------------------------------------------------------------- websocket
  var ws = null, wsRetry = 0;
  function connect() {
    var wsUrl = BRIDGE.replace(/^http/, "ws") + "/ws";
    try { ws = new WebSocket(wsUrl); } catch (e) { scheduleReconnect(); return; }
    ws.onopen = function () { S.online = true; wsRetry = 0; draw(); };
    ws.onmessage = function (ev) {
      var m; try { m = JSON.parse(ev.data); } catch (e) { return; }
      if (m.t === "hello") {
        var firstLive = !S.liveReceived;
        S.liveReceived = true;
        S.hello = true;
        S.apps = m.apps || S.apps || [];
        S.shortcuts = m.shortcuts || S.shortcuts || [];
        S.sources = m.sources || S.sources || [];
        S.state = m.state;
        S.autoSwitchCfg = !!m.autoSwitch;
        S.busy = false;
        preloadIcons();
        pickInitialFocus(firstLive);
        saveCache();
        draw();
      } else if (m.t === "tvstate") {
        S.state = m.state; draw();
      } else if (m.t === "sources") {
        S.sources = m.sources || S.sources || [];
        clampFocus(); saveCache(); draw();
      } else if (m.t === "apps") {
        S.apps = m.apps || S.apps || [];
        preloadIcons(); clampFocus(); saveCache(); draw();
      }
    };
    ws.onclose = function () {
      S.online = false;
      if (S.busy) { S.busy = false; S.toast = ""; }
      scheduleReconnect(); draw();
    };
    ws.onerror = function () { try { ws.close(); } catch (e) {} };
  }
  function scheduleReconnect() {
    setTimeout(connect, Math.min(8000, 1000 * Math.pow(2, wsRetry++)));
  }

  function send(obj) {
    if (!S.online || !ws || ws.readyState !== 1) return false;
    try { ws.send(JSON.stringify(obj)); return true; } catch (e) { return false; }
  }
  function act(type, val) {
    if (S.busy) return;
    if (!send({ t: type === "launch" ? "launch" : "source", name: val, id: val })) {
      S.toast = "server offline · reconnecting";
      S.toastUntil = Date.now() + 2500;
      draw();
      return;
    }
    S.busy = true;
    saveLastUsed(type === "source" ? 0 : 1, val);
    S.toast = "…"; S.toastUntil = Date.now() + 2500;
    draw();
  }

  // ---------------------------------------------------------------- icons
  var ICONS = {};
  function preloadIcons() {
    var list = S.apps || [];
    for (var i = 0; i < list.length; i++) {
      var raw = list[i].icon;
      if (!raw) continue;
      var src = resolveUrl(raw);
      if (ICONS[src]) continue;
      var im = new Image();
      im.onload = function () { draw(); };
      im.src = src;
      ICONS[src] = im;
    }
  }

  // ---------------------------------------------------------------- layout
  var F = {
    clock: "600 56px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    mid: "500 20px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    small: "500 14px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    tiny: "600 11px monospace",
    label: "600 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    letter: "600 44px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
  };

  function tileW() { return 160; }
  function tileH() { return 88; }
  function gap() { return 12; }
  function left() { return 48; }

  function items(row) {
    if (row === 0) {
      return (S.sources || []).map(function (s) {
        return { label: s.name || s.id, sub: s.signal ? "signal" : "no signal",
                 signal: s.signal, glyph: s.glyph || "", val: s.id };
      });
    }
    var out = (S.apps || []).map(function (a) {
      return { label: a.name, sub: "", icon: a.icon, val: a.name };
    });
    var scs = S.shortcuts || [];
    for (var i = 0; i < scs.length; i++) {
      out.push({ label: scs[i].name, glyph: scs[i].glyph || "\u2605",
                 shortcut: scs[i].url, sub: "", val: null });
    }
    return out;
  }

  function clampFocus() {
    if (S.row >= 2) S.row = 1;
    if (S.row < 0) S.row = 0;
    var n = items(S.row).length;
    if (S.col >= n) S.col = Math.max(0, n - 1);
  }

  function rowStart(idx) {
    var n = items(idx).length;
    if (n <= PAGE) return 0;
    return Math.max(0, Math.min(S.col - 2, n - PAGE));
  }

  function hue(s) {
    var h = 0;
    for (var i = 0; i < (s || "").length; i++) h = (h * 31 + s.charCodeAt(i)) % 360;
    return h;
  }

  function roundRect(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  var BG = null;
  var bgim = new Image();
  bgim.onload = function () { BG = bgim; draw(); };
  bgim.src = resolveUrl("/bg/bg" + (new Date().getDate() % 3 + 1) + ".png");

  var HIT = [];
  var focusAnim = 1, lastFocusKey = "";
  var rafPending = false;
  function easeOut(t) { return 1 - Math.pow(1 - t, 3); }
  function bumpFocus() {
    if (rafPending) return;
    rafPending = true;
    function tick() {
      focusAnim = Math.min(1, focusAnim + 0.14);
      draw();
      if (focusAnim < 1) requestAnimationFrame(tick);
      else rafPending = false;
    }
    requestAnimationFrame(tick);
  }

  function drawTile(x, y, focused, it, hotkeyNum) {
    var scale = focused ? 1 + 0.07 * easeOut(focusAnim) : 1;
    ctx.save();
    if (scale !== 1) {
      var cx = x + tileW() / 2, cy = y + tileH() / 2;
      ctx.translate(cx, cy); ctx.scale(scale, scale); ctx.translate(-cx, -cy);
    }
    if (focused) {
      ctx.fillStyle = "rgba(0,0,0,0.45)";
      roundRect(x + 1, y + 5, tileW(), tileH(), 14);
      ctx.fill();
      ctx.fillStyle = "#f2f4f8";
      roundRect(x - 2, y - 2, tileW() + 4, tileH() + 4, 14);
      ctx.fill();
    }
    var fullIcon = resolveUrl(it.icon);
    var base = fullIcon && ICONS[fullIcon] && ICONS[fullIcon].complete && ICONS[fullIcon].naturalWidth;
    ctx.fillStyle = focused ? "#182028" : (base ? "#1a2027" : "hsl(" + hue(it.label) + ",30%," + (focused ? 22 : 14) + "%)");
    roundRect(x, y, tileW(), tileH(), 12);
    ctx.fill();
    if (focused) {
      ctx.fillStyle = "#4cc2ff";
      roundRect(x + 14, y + tileH() - 6, tileW() - 28, 3, 1.5);
      ctx.fill();
    }
    if (hotkeyNum >= 1 && hotkeyNum <= 9) {
      ctx.font = F.tiny;
      ctx.textAlign = "right";
      ctx.fillStyle = focused ? "rgba(242,244,248,0.55)" : "rgba(174,180,189,0.28)";
      ctx.fillText(String(hotkeyNum), x + tileW() - 8, y + 14);
      ctx.textAlign = "left";
    }
    if (it.glyph) {
      ctx.font = "38px sans-serif";
      ctx.textAlign = "center";
      ctx.fillStyle = focused ? "#f2f4f8" : "#c8cdd4";
      ctx.fillText(it.glyph, x + tileW() / 2, y + tileH() / 2 + 8);
      ctx.textAlign = "left";
    } else if (base) {
      var im = ICONS[fullIcon];
      var boxW = tileW() - 24, boxH = tileH() - (it.sub ? 40 : 28);
      var s = Math.min(boxW / im.naturalWidth, boxH / im.naturalHeight);
      var dw = im.naturalWidth * s, dh = im.naturalHeight * s;
      ctx.drawImage(im, x + (tileW() - dw) / 2, y + (boxH - dh) / 2 + 4, dw, dh);
    } else {
      ctx.fillStyle = focused ? "rgba(232,234,238,0.85)" : "rgba(232,234,238,0.25)";
      ctx.font = F.letter;
      ctx.textAlign = "center";
      ctx.fillText((it.label || "?").charAt(0).toUpperCase(), x + tileW() / 2, y + tileH() / 2 + 12);
      ctx.textAlign = "left";
    }
    ctx.fillStyle = focused ? "#f2f4f8" : "#aeb4bd";
    ctx.font = F.small;
    var label = it.label || "";
    while (label.length > 3 && ctx.measureText(label).width > tileW() - 18) label = label.slice(0, -1);
    ctx.textAlign = "center";
    ctx.fillText(label, x + tileW() / 2, y + tileH() - 8);
    ctx.textAlign = "left";
    if (it.sub) {
      ctx.fillStyle = it.signal ? "#4ade80" : "#6b7280";
      ctx.beginPath();
      ctx.arc(x + 16, y + tileH() - 24, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillText(it.sub, x + 26, y + tileH() - 20);
    }
    ctx.restore();
  }

  function drawRow(idx, y, title) {
    ctx.font = F.label;
    ctx.fillStyle = "#7d8590";
    ctx.fillText(title, left(), y - 12);
    var list = items(idx);
    var n = list.length;
    if (!S.hello && S.online) {
      ctx.font = F.mid; ctx.fillStyle = "#555";
      ctx.fillText("loading…", left(), y + 44);
      return;
    }
    if (n === 0) {
      ctx.font = F.mid; ctx.fillStyle = "#3d4552";
      ctx.fillText(idx === 0 ? "no inputs reported" : "no apps reported", left(), y + 44);
      return;
    }
    var start = rowStart(idx);
    var rowActive = (S.row === idx);
    for (var i = start; i < Math.min(n, start + PAGE); i++) {
      var x = left() + (i - start) * (tileW() + gap());
      var focused = (rowActive && S.col === i);
      var hk = rowActive && i < 9 ? (i + 1) : 0;
      if (!focused) drawTile(x, y, false, list[i], hk);
      HIT.push({ x: x, y: y, w: tileW(), h: tileH(), row: idx, col: i });
    }
    if (rowActive && S.col >= start && S.col < Math.min(n, start + PAGE)) {
      drawTile(left() + (S.col - start) * (tileW() + gap()), y, true, list[S.col], S.col < 9 ? S.col + 1 : 0);
    }
    ctx.font = F.small;
    ctx.fillStyle = "#565e69";
    var end = Math.min(n, start + PAGE);
    if (start > 0) ctx.fillText("‹ " + start, left() - 2, y + 24);
    if (end < n) ctx.fillText((n - end) + " ›", left() + PAGE * (tileW() + gap()) - 30, y + 24);
  }

  var lastDrawnMinute = -1;

  function draw() {
    HIT = [];
    ctx.setTransform(SCALE, 0, 0, SCALE, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";

    var key = S.row + ":" + S.col;
    if (key !== lastFocusKey) { lastFocusKey = key; focusAnim = 0; }
    if (BG && BG.complete && BG.naturalWidth) {
      var sc = Math.max(W / BG.naturalWidth, H / BG.naturalHeight);
      ctx.drawImage(BG, (W - BG.naturalWidth * sc) / 2, (H - BG.naturalHeight * sc) / 2,
                    BG.naturalWidth * sc, BG.naturalHeight * sc);
      ctx.fillStyle = "rgba(5,8,12,0.35)";
      ctx.fillRect(0, 0, W, H);
    } else {
      var g = ctx.createLinearGradient(0, 0, 0, H);
      g.addColorStop(0, "#141a24");
      g.addColorStop(1, "#0a0d12");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);
    }

    var now = new Date();
    lastDrawnMinute = now.getMinutes();
    function p2(n) { return (n < 10 ? "0" : "") + n; }
    ctx.fillStyle = "#e8eaee";
    ctx.font = F.clock;
    ctx.fillText(p2(now.getHours()) + ":" + p2(now.getMinutes()), left(), 82);
    ctx.font = F.mid;
    ctx.fillStyle = "#8a8f98";
    var days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
    var mons = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    ctx.fillText(days[now.getDay()] + ", " + mons[now.getMonth()] + " " + now.getDate(), left(), 110);

    ctx.font = F.small;
    ctx.textAlign = "right";
    if (S.online) {
      ctx.fillStyle = "#4ade80";
      ctx.fillText("●", W - 52, 46);
      ctx.fillStyle = "#7d8590";
      ctx.fillText(S.state === "remote_launcher" ? "vidaa home" : (S.state || "tv"), W - 62, 46);
    } else {
      ctx.fillStyle = S.hello ? "#fbbf24" : "#f87171";
      ctx.fillText(S.hello ? "cached · reconnecting…" : "server offline", W - 52, 46);
    }
    ctx.textAlign = "left";

    drawRow(0, 170, "INPUTS");
    drawRow(1, 300, "APPS");

    var nowMs = Date.now();
    if (S.autoSwitchAt > nowMs && S.autoSwitchId) {
      var rem = Math.max(1, Math.ceil((S.autoSwitchAt - nowMs) / 1000));
      ctx.font = F.mid;
      ctx.fillStyle = "#4cc2ff";
      ctx.textAlign = "center";
      ctx.fillText("Switching to " + S.autoSwitchName + " in " + rem + "s… (press any key to stay)", W / 2, H - 14);
      ctx.textAlign = "left";
    } else if (nowMs < S.toastUntil && S.toast) {
      ctx.font = F.mid;
      ctx.fillStyle = "#e8eaee";
      ctx.textAlign = "center";
      ctx.fillText(S.toast === "…" ? "working…" : S.toast, W / 2, H - 14);
      ctx.textAlign = "left";
    }
  }

  // Idle timer: 1 redraw/min idle
  setInterval(function () {
    var now = new Date();
    var nowMs = now.getTime();
    if (S.autoSwitchAt) {
      if (nowMs >= S.autoSwitchAt) {
        var sid = S.autoSwitchId;
        S.autoSwitchAt = 0; S.autoSwitchId = null;
        act("source", sid);
      } else { draw(); }
      return;
    }
    if (S.toast && nowMs >= S.toastUntil) {
      S.toast = ""; S.busy = false; draw();
      return;
    }
    if (now.getMinutes() !== lastDrawnMinute) {
      draw();
    }
  }, 1000);

  // ---------------------------------------------------------------- input
  function activate(row, col) {
    var it = items(row)[col];
    if (!it) return;
    if (it.shortcut) {
      saveLastUsed(row, it.shortcut);
      location.href = it.shortcut;
      return;
    }
    act(row === 0 ? "source" : "launch", it.val);
  }

  document.addEventListener("keydown", function (e) {
    S.userInteracted = true;
    if (S.autoSwitchAt) { cancelAutoSwitch(); e.preventDefault(); return; }
    var list = items(S.row);
    if (e.key === "ArrowRight") { S.focusPicked = true; if (S.col < list.length - 1) { S.col++; bumpFocus(); draw(); } }
    else if (e.key === "ArrowLeft") { S.focusPicked = true; if (S.col > 0) { S.col--; bumpFocus(); draw(); } }
    else if (e.key === "ArrowUp") { S.focusPicked = true; if (S.row > 0) { S.row--; clampFocus(); bumpFocus(); draw(); } }
    else if (e.key === "ArrowDown") { S.focusPicked = true; if (S.row < 1) { S.row++; clampFocus(); bumpFocus(); draw(); } }
    else if (e.key === "Enter") { activate(S.row, S.col); }
    else if (e.key >= "1" && e.key <= "9") {
      var idx = e.key.charCodeAt(0) - 49;
      if (idx < list.length) {
        S.focusPicked = true; S.col = idx;
        bumpFocus(); draw();
        activate(S.row, idx);
      }
    } else if (e.key === "0" || e.key === "Home") {
      S.focusPicked = true;
      S.row = 0; S.col = 0; bumpFocus(); draw();
    }
    e.preventDefault();
  });

  function hitAt(cx, cy) {
    var r = cv.getBoundingClientRect();
    var x = (cx - r.left) * (W / r.width);
    var y = (cy - r.top) * (H / r.height);
    for (var i = 0; i < HIT.length; i++) {
      var t = HIT[i];
      if (x >= t.x && x <= t.x + t.w && y >= t.y && y <= t.y + t.h) return t;
    }
    return null;
  }
  cv.addEventListener("click", function (e) {
    S.userInteracted = true;
    if (S.autoSwitchAt) { cancelAutoSwitch(); return; }
    var t = hitAt(e.clientX, e.clientY);
    if (!t) return;
    S.focusPicked = true; S.row = t.row; S.col = t.col; draw();
    activate(t.row, t.col);
  });
  cv.addEventListener("mousemove", function (e) {
    var t = hitAt(e.clientX, e.clientY);
    if (t && (S.row !== t.row || S.col !== t.col)) {
      S.userInteracted = true;
      if (S.autoSwitchAt) cancelAutoSwitch();
      S.focusPicked = true; S.row = t.row; S.col = t.col; bumpFocus(); draw();
    }
  });

  // ---------------------------------------------------------------- kick off
  loadCache();
  draw();
  connect();
})();
