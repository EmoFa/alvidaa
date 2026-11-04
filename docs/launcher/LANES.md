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
| Screen takeover | installed "Home" web app → Chromium "odin" browser loads the server page | `<script>` appended to stock `hisenseUI/index.html` → Cobalt Starboard canvas overlay |
| Home mechanism | **watcher enabled** — polls `statetype == remote_launcher`, bounces the TV browser to the server | **watcher disabled** — overlay lives inside the stock home engine itself |
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

Boot chain (hook v11, all under `/var/local/`): network wait → `tvtools`
(static busybox/dropbear) → dropbear on :2222 → **`alvidaa-bridge`**
(`bridge/`, static armv7 Go, `tools/build-bridge.sh`): HTTP static + WS hub
+ MQTT TLS client + icon cache, config at `/var/local/alvidaa/config.json`,
keys at `/var/local/alvidaa/keys/`, assets at `/var/local/alvidaa/launcher/`,
log at `/var/local/alvidaa/bridge.log`. Full API parity with the Python
server (`/api/health`, `/api/state`, `/api/launch`, `/api/source`, `/api/open`).

The screen path never touches the browser: `tools/deploy-overlay.sh` fetches
the pristine `hisenseUI/index.html` (kept in `.alvidaa-bak`), appends a head
flash-kill style plus `<script src="./alvidaa-remote.js"></script>` **before
`</body>`**, and bundles `alvidaa-remote.js` to local flash
(`/APPS/channelA/hisenseUI/`, mode 644 `UhisApp:UGhisApp`) so a cold boot has
no network dependency (findings 12 §5). The stock home engine
(process `UIMainWebModule`) keeps running underneath; the overlay paints a
canvas over it and talks to the bridge on loopback.

`watcher.enabled: false` in `/var/local/alvidaa/config.json` is **required**
in this lane: with the watcher on, the bridge bounces the TV into the old
installed web app, and if the external server is gone that is a dead URL in
odin — the "gray screen" failure mode. (Watcher code: `bridge/state.go`,
`watcherLoop`.)

## Shared asset: `launcher/alvidaa-remote.js`

One script powers both lanes (standalone page in the browser, overlay in the
home engine). A change must land in **three** places to take effect on the TV:

1. repo `launcher/alvidaa-remote.js` (source of truth, commit + push),
2. `/APPS/channelA/hisenseUI/alvidaa-remote.js` (overlay, `UhisApp:UGhisApp 644`),
3. `/var/local/alvidaa/launcher/alvidaa-remote.js` (standalone assets).

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
- On boot, `hisenseUI` loads at t≈5s while the bridge may take 60–150s —
  any overlay feature must tolerate `offline` state on frame 1.
