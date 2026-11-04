(function () {
  "use strict";
  // alvidaa v2 overlay: 1080p HiDPI Canvas (no layered DOM/CSS).
  // Cobalt Starboard renders 2D canvas via Mali GPU hardware acceleration.
  // Instant frame-1 cold cache (localStorage), 1-9 hotkeys, signal indicators,
  // remote D-pad + click hit-testing, and auto-switch countdown.
  if (document.getElementById("alvidaa-cv")) return;

  var BRIDGE = "http://127.0.0.1:8770";
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
    st.textContent = "#app { display: none !important; } html, body { margin: 0; padding: 0; background: #07080c !important; overflow: hidden; height: 100%; }";
    document.head.appendChild(st);
  }

  // 2. Create the HiDPI Canvas
  var cv = document.createElement("canvas");
  cv.id = "alvidaa-cv";
  var W = 960, H = 540, SCALE = 2;
  cv.width = W * SCALE;
  cv.height = H * SCALE;
  cv.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;z-index:2147483647;display:block;background:#07080c";
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
    clock: "300 58px -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif",
    mid: "500 16px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    small: "500 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    tiny: "600 9px -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace",
    label: "600 11px -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif",
    letter: "600 20px -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif"
  };

  function tileW() { return 160; }
  function tileH() { return 88; }
  function gap() { return 12; }
  function left() { return 56; }

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
    var scale = focused ? 1 + 0.08 * easeOut(focusAnim) : 1;
    ctx.save();
    if (scale !== 1) {
      var cx = x + tileW() / 2, cy = y + tileH() / 2;
      ctx.translate(cx, cy); ctx.scale(scale, scale); ctx.translate(-cx, -cy);
    }

    // 1. Shadow & Glow
    if (focused) {
      // Ambient bloom glow behind focused card (soft, diffused Apple TV bloom)
      var glow = ctx.createRadialGradient(
        x + tileW() / 2, y + tileH() / 2, tileW() * 0.15,
        x + tileW() / 2, y + tileH() / 2, tileW() * 0.75
      );
      glow.addColorStop(0, "rgba(255, 255, 255, 0.16)");
      glow.addColorStop(0.5, "rgba(148, 163, 184, 0.06)");
      glow.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = glow;
      roundRect(x - 14, y - 10, tileW() + 28, tileH() + 20, 20);
      ctx.fill();

      // Focused drop shadow
      ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
      roundRect(x, y + 6, tileW(), tileH(), 16);
      ctx.fill();

      // Crisp luminous white border
      ctx.fillStyle = "#ffffff";
      roundRect(x - 2, y - 2, tileW() + 4, tileH() + 4, 16);
      ctx.fill();
    } else {
      // Rest state: subtle card shadow
      ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
      roundRect(x, y + 4, tileW(), tileH(), 14);
      ctx.fill();

      // Subtle 1px rest border
      ctx.fillStyle = "rgba(255, 255, 255, 0.07)";
      roundRect(x - 1, y - 1, tileW() + 2, tileH() + 2, 15);
      ctx.fill();
    }

    // 2. Card Background Gradient
    var fullIcon = resolveUrl(it.icon);
    var base = fullIcon && ICONS[fullIcon] && ICONS[fullIcon].complete && ICONS[fullIcon].naturalWidth;

    var cardGrad = ctx.createLinearGradient(x, y, x, y + tileH());
    if (focused) {
      cardGrad.addColorStop(0, "#232a36");
      cardGrad.addColorStop(1, "#141822");
    } else {
      cardGrad.addColorStop(0, base ? "#161b24" : "hsl(" + hue(it.label) + ", 18%, 13%)");
      cardGrad.addColorStop(1, "#0d1017");
    }
    ctx.fillStyle = cardGrad;
    roundRect(x, y, tileW(), tileH(), 14);
    ctx.fill();

    // 3. Subtle 1px Specular Highlight at top edge of tiles
    ctx.beginPath();
    ctx.moveTo(x + 14, y + 1);
    ctx.lineTo(x + tileW() - 14, y + 1);
    ctx.strokeStyle = focused ? "rgba(255, 255, 255, 0.28)" : "rgba(255, 255, 255, 0.12)";
    ctx.lineWidth = 1;
    ctx.stroke();

    // 4. Hotkey Numeral Keycap (1-9) in top-right
    if (hotkeyNum >= 1 && hotkeyNum <= 9) {
      var hkW = 16, hkH = 16;
      var hkX = x + tileW() - hkW - 8, hkY = y + 8;
      ctx.fillStyle = focused ? "rgba(255, 255, 255, 0.16)" : "rgba(255, 255, 255, 0.05)";
      roundRect(hkX, hkY, hkW, hkH, 4);
      ctx.fill();
      ctx.strokeStyle = focused ? "rgba(255, 255, 255, 0.28)" : "rgba(255, 255, 255, 0.08)";
      ctx.lineWidth = 1;
      roundRect(hkX, hkY, hkW, hkH, 4);
      ctx.stroke();

      ctx.font = F.tiny;
      ctx.textAlign = "center";
      ctx.fillStyle = focused ? "#ffffff" : "rgba(148, 163, 184, 0.7)";
      ctx.fillText(String(hotkeyNum), hkX + hkW / 2, hkY + hkH / 2 + 3);
      ctx.textAlign = "left";
    }

    // 5. Clean, elegant emerald signal badge for active HDMI inputs (top-left)
    if (it.sub) {
      var hasSig = !!it.signal;
      var bx = x + 8, by = y + 8;
      var bw = hasSig ? 44 : 58, bh = 17;

      ctx.fillStyle = hasSig ? "rgba(16, 185, 129, 0.16)" : "rgba(255, 255, 255, 0.04)";
      roundRect(bx, by, bw, bh, 8.5);
      ctx.fill();

      ctx.strokeStyle = hasSig ? "rgba(16, 185, 129, 0.35)" : "rgba(255, 255, 255, 0.08)";
      ctx.lineWidth = 1;
      roundRect(bx, by, bw, bh, 8.5);
      ctx.stroke();

      var dotX = bx + 7, dotY = by + bh / 2;
      if (hasSig) {
        ctx.fillStyle = "rgba(16, 185, 129, 0.35)";
        ctx.beginPath();
        ctx.arc(dotX, dotY, 4.5, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "#10b981";
        ctx.beginPath();
        ctx.arc(dotX, dotY, 2.5, 0, Math.PI * 2);
        ctx.fill();
      } else {
        ctx.fillStyle = "#64748b";
        ctx.beginPath();
        ctx.arc(dotX, dotY, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.font = "600 9px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
      ctx.fillStyle = hasSig ? (focused ? "#6ee7b7" : "#34d399") : (focused ? "#94a3b8" : "#64748b");
      ctx.fillText(hasSig ? "LIVE" : "STANDBY", dotX + 6, dotY + 3);
    }

    // 6. Tile Graphic: Preloaded Icon, Custom Glyph, Hardware Display Icon, or Typographic Badge
    if (base) {
      var im = ICONS[fullIcon];
      var boxW = tileW() - 32, boxH = 38;
      var s = Math.min(boxW / im.naturalWidth, boxH / im.naturalHeight);
      var dw = im.naturalWidth * s, dh = im.naturalHeight * s;
      ctx.drawImage(im, x + (tileW() - dw) / 2, y + 14 + (boxH - dh) / 2, dw, dh);
    } else if (it.glyph) {
      ctx.font = "26px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
      ctx.textAlign = "center";
      ctx.fillStyle = focused ? "#ffffff" : "#cbd5e1";
      ctx.fillText(it.glyph, x + tileW() / 2, y + 42);
      ctx.textAlign = "left";
    } else if (it.sub) {
      // Elegant minimalist hardware display icon for inputs without custom glyph
      var mw = 28, mh = 17, mx = x + (tileW() - mw) / 2, my = y + 23;
      ctx.strokeStyle = focused ? "rgba(255, 255, 255, 0.9)" : "rgba(148, 163, 184, 0.6)";
      ctx.lineWidth = 1.5;
      roundRect(mx, my, mw, mh, 3);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(mx + mw / 2, my + mh);
      ctx.lineTo(mx + mw / 2, my + mh + 4);
      ctx.moveTo(mx + mw / 2 - 5, my + mh + 4);
      ctx.lineTo(mx + mw / 2 + 5, my + mh + 4);
      ctx.stroke();
    } else {
      // Beautiful, crisp typographic app letter badge fallback
      var bSize = 36;
      var bx = x + (tileW() - bSize) / 2;
      var by = y + 14;
      var br = 9;
      var h = hue(it.label);

      ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
      roundRect(bx, by + 2, bSize, bSize, br);
      ctx.fill();

      var bGrad = ctx.createLinearGradient(bx, by, bx, by + bSize);
      bGrad.addColorStop(0, "hsl(" + h + ", 65%, 46%)");
      bGrad.addColorStop(1, "hsl(" + h + ", 75%, 30%)");
      ctx.fillStyle = bGrad;
      roundRect(bx, by, bSize, bSize, br);
      ctx.fill();

      // 1px specular top highlight on badge
      ctx.beginPath();
      ctx.moveTo(bx + br, by + 1);
      ctx.lineTo(bx + bSize - br, by + 1);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.35)";
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.fillStyle = "#ffffff";
      ctx.font = F.letter;
      ctx.textAlign = "center";
      ctx.fillText((it.label || "?").charAt(0).toUpperCase(), bx + bSize / 2, by + bSize / 2 + 7);
      ctx.textAlign = "left";
    }

    // 7. Label text with ellipsis truncation
    ctx.fillStyle = focused ? "#ffffff" : "#94a3b8";
    ctx.font = F.small;
    var label = it.label || "";
    while (label.length > 3 && ctx.measureText(label).width > tileW() - 18) label = label.slice(0, -1);
    ctx.textAlign = "center";
    ctx.fillText(label, x + tileW() / 2, y + tileH() - 12);
    ctx.textAlign = "left";

    ctx.restore();
  }

  function drawRow(idx, y, title) {
    var list = items(idx);
    var n = list.length;
    var start = rowStart(idx);
    var end = Math.min(n, start + PAGE);

    ctx.font = F.label;
    ctx.fillStyle = "#64748b";
    ctx.fillText(title, left(), y - 12);

    // Minimal pagination counter on right
    if (n > PAGE) {
      ctx.textAlign = "right";
      ctx.font = "500 11px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
      ctx.fillStyle = "#475569";
      ctx.fillText((start + 1) + "–" + end + " of " + n, left() + PAGE * tileW() + (PAGE - 1) * gap(), y - 12);
      ctx.textAlign = "left";
    }

    if (!S.hello && S.online) {
      ctx.font = F.mid; ctx.fillStyle = "#64748b";
      ctx.fillText("loading…", left(), y + 44);
      return;
    }
    if (n === 0) {
      ctx.font = F.mid; ctx.fillStyle = "#475569";
      ctx.fillText(idx === 0 ? "no inputs reported" : "no apps reported", left(), y + 44);
      return;
    }

    var rowActive = (S.row === idx);
    for (var i = start; i < end; i++) {
      var x = left() + (i - start) * (tileW() + gap());
      var focused = (rowActive && S.col === i);
      var hk = rowActive && i < 9 ? (i + 1) : 0;
      if (!focused) drawTile(x, y, false, list[i], hk);
      HIT.push({ x: x, y: y, w: tileW(), h: tileH(), row: idx, col: i });
    }
    if (rowActive && S.col >= start && S.col < end) {
      drawTile(left() + (S.col - start) * (tileW() + gap()), y, true, list[S.col], S.col < 9 ? S.col + 1 : 0);
    }
  }

  var lastDrawnMinute = -1;

  function draw() {
    HIT = [];
    ctx.setTransform(SCALE, 0, 0, SCALE, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";

    var key = S.row + ":" + S.col;
    if (key !== lastFocusKey) { lastFocusKey = key; focusAnim = 0; }

    // Deep OLED Obsidian Base
    ctx.fillStyle = "#07080c";
    ctx.fillRect(0, 0, W, H);

    if (BG && BG.complete && BG.naturalWidth) {
      var sc = Math.max(W / BG.naturalWidth, H / BG.naturalHeight);
      ctx.drawImage(BG, (W - BG.naturalWidth * sc) / 2, (H - BG.naturalHeight * sc) / 2,
                    BG.naturalWidth * sc, BG.naturalHeight * sc);
      ctx.fillStyle = "rgba(6, 8, 12, 0.6)";
      ctx.fillRect(0, 0, W, H);
    } else {
      // Ultra-subtle ethereal ambient bloom from top
      var amb = ctx.createRadialGradient(W / 2, -20, 20, W / 2, 120, W * 0.75);
      amb.addColorStop(0, "rgba(56, 189, 248, 0.05)");
      amb.addColorStop(0.45, "rgba(99, 102, 241, 0.025)");
      amb.addColorStop(1, "rgba(7, 8, 12, 0)");
      ctx.fillStyle = amb;
      ctx.fillRect(0, 0, W, H);
    }

    // Soft perimeter vignette
    var vig = ctx.createRadialGradient(W / 2, H / 2, W * 0.35, W / 2, H / 2, W * 0.75);
    vig.addColorStop(0, "rgba(0, 0, 0, 0)");
    vig.addColorStop(1, "rgba(0, 0, 0, 0.45)");
    ctx.fillStyle = vig;
    ctx.fillRect(0, 0, W, H);

    // Refined Header: Light typography clock with hours/minutes hierarchy & clean uppercase date
    var now = new Date();
    lastDrawnMinute = now.getMinutes();
    function p2(n) { return (n < 10 ? "0" : "") + n; }

    var hh = p2(now.getHours());
    var mm = p2(now.getMinutes());

    ctx.font = F.clock;
    ctx.fillStyle = "#ffffff";
    ctx.fillText(hh, left(), 78);
    var hw = ctx.measureText(hh).width;

    ctx.fillStyle = "rgba(255, 255, 255, 0.35)";
    ctx.fillText(":", left() + hw + 2, 76);
    var cw = ctx.measureText(":").width;

    ctx.fillStyle = "rgba(255, 255, 255, 0.92)";
    ctx.fillText(mm, left() + hw + cw + 4, 78);

    ctx.font = "600 11px -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif";
    ctx.fillStyle = "#8e9ab0";
    var days = ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"];
    var mons = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"];
    var dateStr = days[now.getDay()] + " · " + mons[now.getMonth()] + " " + now.getDate();
    ctx.fillText(dateStr, left() + 2, 98);

    // Top-Right Glass Capsule Status Pill
    var pillW = 132, pillH = 26, pillX = W - left() - pillW, pillY = 54;
    ctx.fillStyle = "rgba(255, 255, 255, 0.04)";
    roundRect(pillX, pillY, pillW, pillH, 13);
    ctx.fill();

    ctx.strokeStyle = "rgba(255, 255, 255, 0.1)";
    ctx.lineWidth = 1;
    roundRect(pillX, pillY, pillW, pillH, 13);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(pillX + 13, pillY + 1);
    ctx.lineTo(pillX + pillW - 13, pillY + 1);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.16)";
    ctx.lineWidth = 1;
    ctx.stroke();

    var dotColor = S.online ? "#10b981" : (S.hello ? "#f59e0b" : "#ef4444");
    var dotGlow = S.online ? "rgba(16, 185, 129, 0.28)" : "rgba(239, 68, 68, 0.28)";

    ctx.fillStyle = dotGlow;
    ctx.beginPath();
    ctx.arc(pillX + 14, pillY + pillH / 2, 5, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = dotColor;
    ctx.beginPath();
    ctx.arc(pillX + 14, pillY + pillH / 2, 2.5, 0, Math.PI * 2);
    ctx.fill();

    ctx.font = "600 10px -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif";
    ctx.fillStyle = S.online ? "rgba(255, 255, 255, 0.85)" : "rgba(148, 163, 184, 0.8)";
    ctx.fillText(S.online ? "ALVIDAA · LIVE" : (S.hello ? "RECONNECTING" : "OFFLINE"), pillX + 26, pillY + pillH / 2 + 3.5);

    drawRow(0, 168, "INPUTS & SOURCES");
    drawRow(1, 298, "APPS & CHANNELS");

    // Floating Glass HUD for Auto-switch countdown & toasts
    var nowMs = Date.now();
    if (S.autoSwitchAt > nowMs && S.autoSwitchId) {
      var rem = Math.max(1, Math.ceil((S.autoSwitchAt - nowMs) / 1000));
      var msg = "Switching to " + S.autoSwitchName + " in " + rem + "s… (press any key to stay)";
      ctx.font = "500 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
      var mw = ctx.measureText(msg).width;
      var bx = (W - mw) / 2 - 20, by = H - 42, bw = mw + 40, bh = 28;

      ctx.fillStyle = "rgba(0, 0, 0, 0.45)";
      roundRect(bx, by + 3, bw, bh, 14);
      ctx.fill();

      ctx.fillStyle = "rgba(18, 22, 32, 0.94)";
      roundRect(bx, by, bw, bh, 14);
      ctx.fill();

      ctx.strokeStyle = "rgba(56, 189, 248, 0.35)";
      ctx.lineWidth = 1;
      roundRect(bx, by, bw, bh, 14);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(bx + 14, by + 1);
      ctx.lineTo(bx + bw - 14, by + 1);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.2)";
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.fillStyle = "#38bdf8";
      ctx.textAlign = "center";
      ctx.fillText(msg, W / 2, by + 18);
      ctx.textAlign = "left";
    } else if (nowMs < S.toastUntil && S.toast) {
      var tmsg = S.toast === "…" ? "working…" : S.toast;
      ctx.font = "500 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
      var tmw = ctx.measureText(tmsg).width;
      var tbx = (W - tmw) / 2 - 20, tby = H - 42, tbw = tmw + 40, tbh = 28;

      ctx.fillStyle = "rgba(0, 0, 0, 0.45)";
      roundRect(tbx, tby + 3, tbw, tbh, 14);
      ctx.fill();

      ctx.fillStyle = "rgba(18, 22, 32, 0.94)";
      roundRect(tbx, tby, tbw, tbh, 14);
      ctx.fill();

      ctx.strokeStyle = "rgba(255, 255, 255, 0.12)";
      ctx.lineWidth = 1;
      roundRect(tbx, tby, tbw, tbh, 14);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(tbx + 14, tby + 1);
      ctx.lineTo(tbx + tbw - 14, tby + 1);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.2)";
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.fillStyle = "#f8fafc";
      ctx.textAlign = "center";
      ctx.fillText(tmsg, W / 2, tby + 18);
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
