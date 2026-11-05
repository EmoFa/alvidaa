# The two launcher lanes

alvidaa now maintains **two independent delivery paths** for the same
launcher UX. Both are live and both must keep working: Lane 1 is the safe,
reversible, unrooted path (the product lane — any VIDAA set of this
generation can run it); Lane 2 is the rooted, fully self-contained path
(the 2.0 end state — the TV becomes a standalone appliance).

Owned by the launcher lane; the root plumbing underneath Lane 2 is recorded
in `docs/models/50A51HUV/09.01O.P0813/findings/` and LAUNCHER_V2.md.

## At a glance

| Dimension | Lane 1 — external server (unrooted) | Lane 2 — native on-TV (rooted) |
|---|---|---|
| TV prerequisites | paired cert + tokens only | root hook (`/var/local/otaTest.sh` v11) |
| Bridge host | Pi / Mac / PC (`server/vidaa_server.py`) | on-TV Go daemon (`bridge/` → `alvidaa-bridge`) |
| MQTT link | LAN TLS to `tv:36669`, paired identity | loopback `127.0.0.1:36669` |
| HTTP/WS endpoint | `http://<server>:8770` | `127.0.0.1:8770` (hook passes `-addr 0.0.0.0:8770`) |
| Screen takeover | installed "Home" web app → Chromium "odin" browser loads the server page | same mechanism — installed web app → odin renders from `127.0.0.1:8770` |
| Home mechanism | **watcher enabled** (on the external server) — polls `statetype == remote_launcher`, bounces the TV browser to the server | **watcher enabled** (inside the on-TV bridge) — bounces to the web app pointing at the TV's own loopback |
| External dependency | the server box must be up, forever | none — TV is a standalone appliance |
| Reversibility | uninstall the web app / stop the server | `hook.off` kill-switch; overlay is append-only, pristine HTML kept in `.alvidaa-bak` |

## Lane 1 — external server (unrooted)

- `server/vidaa_server.py` (port 8770 prod, 8765 dev) does everything: MQTT/TLS
  bridge to RemoteNow (token auth + auto-refresh), HTTP static + WebSocket,
  `/icon/*` proxy, config-driven allowlist, and the home watcher.
- The TV gets one installed web app ("Home") whose URL points at the server.
  When the watcher sees the VIDAA home state it (re)launches that app, so the
  browser lands on the launcher page. The ~1s stock-home flash before the
  bounce is inherent to this lane.
- `server/config.json` drives it; **`watcher.enabled: true` is what makes the
  home bounce work**. Config keys: `only`, `hidden`, `rename`, `shortcuts`,
  `watcher` (`app`, `interval`, `cooldown`).
- This lane is what the pairing flow (`server/pair.py`) exists for, and what
  `docs/DEPLOY.md` describes end to end.

## Lane 2 — native on-TV (rooted)

Boot chain (hook v13 in repo — template + installer; the running TV hook
is v12 until redeploy, all under
`/var/local/`): network wait → `tvtools`
(static busybox/dropbear) → dropbear on :2222 → **`alvidaa-bridge`**
(`bridge/`, static armv7 Go, `tools/build-bridge.sh`): HTTP static + WS hub
+ MQTT TLS client + icon cache, config at `/var/local/alvidaa/config.json`,
keys at `/var/local/alvidaa/keys/`, assets at `/var/local/alvidaa/launcher/`,
log at `/var/local/alvidaa/bridge.log`. Full API parity with the Python
server (`/api/health`, `/api/state`, `/api/launch`, `/api/source`, `/api/open`).

The screen path is the **browser** (odin), not the home engine: this Cobalt
build ships no `HTMLCanvasElement` at all (findings 12 §7), so canvas
overlays inside `hisenseUI` are impossible on this model. The shell
(`/APPS/channelA/hisenseUI/index.html`) must stay **pristine** (pristine
copy kept in `index.html.alvidaa-bak`) — any injected script there runs in
every web context and, once dead, darkens home and all apps until reboot.
`tools/deploy-overlay.sh` remains as a recovery/retired tool.

Takeover works like Lane 1, hosted entirely on the TV: the installed web
app ("Home", appId `vidaa-home`, registered in `/APPS/websdk/Appinfo.json`)
points at `http://127.0.0.1:8770/`; the bridge's watcher (enabled) sees
`statetype == remote_launcher` and launches that app, so odin lands on the
launcher. `bridge/state.go launchHome` prefers the loopback URL explicitly,
so a stale external-server entry carrying the same port can never win.
Note the TV framework caches its app list across installs — an
`INSTALL AS APP` re-point only takes effect after a reboot.

`watcher.enabled: true` in `/var/local/alvidaa/config.json` is **required**
in this lane. The 2026-11-04 "gray screen" incident was the old Pi-pointed
entry winning the launch after the external server died; the loopback-pref
matcher plus a re-pointed web app is the fix.

## Shared asset: `launcher/alvidaa-remote.js`

One script powers the launcher page in both lanes (external server or on-TV
bridge — the page is identical). A change must land in **two** places to
take effect on the TV:

1. repo `launcher/alvidaa-remote.js` (source of truth, commit + push),
2. `/var/local/alvidaa/launcher/alvidaa-remote.js` (on-TV bridge assets).

Nothing goes into the `hisenseUI` shell anymore (see findings 12 §7). And
because the Cobalt compiled-JS cache is stale-by-URL, any script change on
the TV needs `rm -rf /var/local/hisenseUI/cobalt_home/*` + reboot — even
though the launcher itself renders in odin, the home engine also compiles
what it loads.

Bridge constraint: **XHR is banned** in any home-engine page (Cobalt deadlocks
after a CORS preflight — findings 12 §3); all control data flows over the
WebSocket. Keep the WS retry loop (`≤8s`, forever) intact — the bridge comes
up well after the home engine loads at boot, so the overlay must out-wait it.

## Maintenance rules

- **One MQTT session per credential set** (both lanes — client_id is baked
  into the `his$…` auth). Never run the Python server and the on-TV bridge
  with the same identity at the same time.
- Never edit TV files in place on the device; always fetch → patch → push →
  md5-verify (`tools/deploy-overlay.sh` does this for the overlay lane).
- Reboots go through `/var/local/tvtools/busybox reboot -f` (findings 12 §4).
- On boot, `hisenseUI` loads at t≈5s; hook v12 starts the bridge early
  (~t≈15s, before the LAN wait — loopback MQTT needs no network). The
  framework's app list populates when the UI stack is ready, so the first
  Home press after a cold boot may precede the first successful bounce;
  the watcher (1s poll) bounces from then on. VIDAA resumes the last
  active input on boot, so the auto-bounce only fires once you actually
  enter home.
