# alvidaa v2 — launcher replacement on rooted VIDAA

Status: planning (root landed Oct 2026 — see FINDINGS.md §10 for the recon
story; §10.12 for the toolbox inventory). This document is the launcher-side
plan and the design for moving alvidaa from a Pi-hosted web app to a native
boot-time home. Ownership: this document and everything under `launcher/` +
`server/` belongs to the launcher lane; the firmware/telemetry digging
(binaries, Ghidra, endpoint mapping) lives in the other session.

## Where v1.3 stands (the baseline v2 builds on)

- Server: Python (`server/vidaa_server.py`) on the Pi (`alvidaa.service`,
  port 8770) — MQTT/TLS bridge to RemoteNow (token auth + auto-refresh),
  HTTP static + WebSocket + `/icon/*` proxy, config-driven allowlist/renames/
  glyphs/`autoSwitch`, event-driven + 3s poll home watcher, and guards against
  transient empty `applist`/`sourcelist` payloads during boot churn.
- TV side (`launcher/index.html`, v1.3):
  - **1080p HiDPI canvas**: renders at `1920×1080` (`SCALE = 2` over logical `960×540` layout coordinates, with `?540p` fallback for older sets).
  - **0ms cold-paint cache (`localStorage`)**: renders cached inputs, apps, and shortcuts on frame 1 before `/ws` connects, showing `cached · reconnecting…` if the server is restarting.
  - **Smart initial focus & optional auto-switch**: automatically focuses the first HDMI input with `signal: true` (or the last-launched tile from `localStorage`). When `"autoSwitch": true` in `server/config.json` (or `?autosource` in the URL) and a single HDMI input has active signal on cold boot, starts a 3.5s countdown toast (`Switching to <Input> in 3s… (press any key to stay)`).
  - **Remote number hotkeys (`1`–`9`)**: pressing `1`–`9` on the remote focuses and activates that tile in the active row; `0` / `Home` resets focus to `row 0, col 0`.
  - **Idle GPU throttling**: only redraws the canvas when the clock minute changes, a toast expires, or focus/state changes (1 redraw/min idle instead of 60/min).
- Known limitations v2 (native modification) kills: ~1s stock-home flash before the watcher
  relaunches; Pi dependency when not running the server on-TV; stock home UI still
  loading in the background Cobalt process.

## v1 operational lessons the v2 port must honor

These cost us real debugging time; the on-TV port inherits them as requirements:

1. **Wildcard MQTT subscriptions are denied** (SUBACK Unspecified error) —
   subscribe to exact topics only.
2. **Client identity is part of the credential** — client_id is baked into
   `his$…` auth and topic paths; two processes sharing a client_id kick each
   other off the broker. One session per TV.
3. **applist/sourcelist are JSON arrays**, state/token are objects — don't
   filter payloads by shape or you drop half the traffic.
4. **Token lifecycle**: access token 2 days, refresh token 30 days, refresh via
   `platform_service/data/gettoken` with `{"refreshtoken": …}`. Refresh must be
   re-entrant (mid-run expiry recovery) — a 2-day-old process will hit it.
5. **PIN dialogs rotate on re-trigger** — never poll `vidaa_app_connect`.
6. **Reboot/`pm`-state churn empties applist transiently** — treat an empty
   applist as "keep the previous one", never overwrite cache with `[]`.
7. **The browser D-pad is a pointer** — tiles are click hit-tested; keyboard
   events are secondary.
8. **Web-app browser on a modest GPU** (Chromium 111 "odin" on this firmware;
   older VIDAA sets run Chrome 77): one canvas at 960×540, no offscreen canvases
   (they render empty), no layered DOM/CSS, ES2018-compatible syntax, `Cache-Control:
   no-store` on everything.
9. **app TTL 60s**: TV-side installs/uninstalls must surface within a minute.

## R-phases

### R0 — hook v4: guardrails before anything else (other session + this doc)

1. **OTA freeze at the kernel layer**: iptables rules (hook-owned) dropping the
   firmware-update endpoints. Exact endpoints TBD from the binaries/firmware
   dump — candidate list goes to FINDINGS §10 when mapped. An update that
   reseals the root hole mid-project is the only unrecoverable setback.
2. **2323 lockdown**: `telnetd -l /bin/sh` is an unauthenticated root shell on
   the LAN. The hook adds `iptables -A INPUT -p tcp --dport 2323 ! -s
   <trusted-ips> -j DROP` before starting the listener; longer term, stage a
   static dropbear and use key auth instead of telnet entirely.
3. **Kill-switch**: if `/var/local/otaTest.off` exists, hook exits 0 untouched.
   Gives us a one-write disable for every future iteration.
4. **Idempotency + lineage**: every hook revision is versioned, keeps the
   previous as `.bak` (pattern set by `otaTest.v1.bak`), and is verified by
   readback before the reboot that activates it.

### R1 — shell persistence (in flight)

Plug pull → hook v3 fires → static busybox lands → `telnet <tv> 2323` as root.
Immediately after: `reboot` binary test (remote reboots from here on), then the
partition dump (`dd if=/dev/mmcblk0pN | tar/nc → Pi`) for the Ghidra lane.

### R2 — map the home plumbing (needs R1)

Questions the map must answer before any patching:

- What does boot actually launch into the home? (§10.7 boot map +
  `/APPS/channelA` UI tree; `preset.txt` vs `Appinfo.json` vs the kilby
  service that assembles the home.)
- Where is the HOME key handled (which process consumes the remote's HOME and
  what does it start)?
- What is rw vs ro under `/APPS/`, `/usr/local/varlocal/`, `/var/local/`?
- `phoenix` runtime: node version, bundled modules (mqtt? ws? fs write paths),
  how its apps/services are registered and restarted.
- Where the stock home's ad/sponsored components render from
  (`/APPS/channelA` rw — candidate for R6 strip).

Deliverable: a map section in FINDINGS (other session's file — coordinate)
plus a written "writable, read-only, do-not-touch" inventory.

### R3 — telemetry + ads at the kernel/service layer

- iptables rules (hook-owned, persistent) for every endpoint the mapping
  surfaces. Log-first for a few days (`iptables -j LOG`) to see what actually
  phones home, then block everything that isn't the opkg/app_upgrade channel.
- Service-level suppression of `hi_logreport_service`, `mdharvester`,
  `write_stat`, `bizm` — stop + disable autostart in whatever service config
  is rw (kilby configs / init scripts). Network blocks without process
  suppression are half a win.
- AdGuard Home per-client rules (LAN layer) stay as defense-in-depth; with the
  kernel layer in place they become redundancy, not the only line.

### R4 — alvidaa on the TV (the native port — ACHIEVED)

Rather than relying on the uncertain and unpinned `phoenix` Node runtime, the
bridge and static server were ported directly to a **standalone, statically linked
Go binary (`bridge/` -> `alvidaa-bridge-armv7`)** cross-compiled for Linux `armv7l`.
Zero libc dependencies, zero external npm packages, instant startup (<10MB RSS),
launchable directly from `/var/local/otaTest.sh` at boot.

Port architecture (`bridge/`):

| Component | Implementation | Notes |
|---|---|---|
| MQTT TLS Client | Standard library `crypto/tls` + net connection | Exact-topic subs, client cert TLS, auto-token refresh on rejection (`rc=5`) |
| Loopback HTTP Server | Go `net/http` on `127.0.0.1:8770` | Serves overlay assets from `-assets`, `Cache-Control: no-store`, CORS `*` |
| WebSocket Bridge (`/ws`) | Hand-rolled RFC 6455 framing | Translates Cobalt client messages (`launch`, `source`) to MQTT commands |
| Icon Proxy (`/icon/*`) | Streaming HTTP proxy + disk cache | Caches app icons locally under `-assets/iconcache/` |
| Health & State API | `/api/health`, `/api/state`, `/api/launch`, `/api/source`, `/api/open` | Full parity with `server/vidaa_server.py` |

The daemon runs on loopback `127.0.0.1:8770`, binds only to loopback for security,
and connects to the TV's mosquitto broker on `127.0.0.1:36669`. The Pi server
retires to a development / remote management tool.

### R5 — stock home suppressed at the source

Once R2 answers where boot/home selection lives: point the boot/home slot at
alvidaa (Appinfo/preset patch in rw space), remap HOME at the OS level. The
watcher stays deployed as a fallback but should never fire. Success metric:
power-on and HOME land on alvidaa with zero stock-home flash.

### R6 — strip the ad components from the home UI code

`/APPS/channelA` is rw and loads into the home screen — remove the
sponsored/ad components at the source instead of hiding tiles. Do this only
after R2's map and with a file-level backup on the Pi; this is the most
invasive rw-space edit in the plan.

## Coordination

- Launcher lane (this repo, this session): `launcher/`, `server/`, config,
  this document, the v1 wiki pages.
- Root/firmware lane (other session): FINDINGS.md recon sections, hook
  versions, binaries/Ghidra, endpoint mapping, telemetry inventory.
- Shared: `docs/models/50A51HUV/09.01O.P0813/FINDINGS.md` — recon sections are the other lane's; launcher
  sections (this file, v1 sections) are ours. Don't reformat across lanes.
- Never commit: `server/keys/` (certs, tokens), `server/iconcache/`.

## Immediate next actions

1. (User) Plug pull → hook v3 activates → `telnet <tv-ip> 2323`.
2. (Root lane) 2323 firewall rule + dropbear swap; OTA endpoint freeze.
3. (Launcher lane, now) this document committed; R4 port skeleton prepared
   behind a flag so it can start the moment R2 reports phoenix's runtime shape.

## R2 map — the home boot chain (mapped 2026-10-30, live root)

```
boot → /usr/local/scripts/hisense_stage0.sh
     → /usr/local/bin/tvmain -D &                      (main TV service)
     → /opt/hisenseUI/startgui.sh &                    (THE shim point)
         cd /opt/hisenseUI
         exec ./bin/hisenseUI --remote_debugging_port=9666 \
              --webdriver_port=4445 --url=file:///hisenseUI/index.html
```

- `bin/hisenseUI` is an **embedded Cobalt-based web engine** (its own exe,
  uid UhisUI, PID stays alive for the whole boot session) — the "browser"
  and the home UI are one process.
- `file:///hisenseUI/index.html` is **not** a filesystem path (no /hisenseUI
  at root, no bind mount in the engine's namespace) — the engine maps it to
  the content tree at **`/APPS/channelA/hisenseUI/`** (index.html + static/ +
  shared/ + process.env.json). `/APPS` = `/dev/mmcblk0p41`, ext4 **rw**,
  whole-partition mode 777.
- The stock home is a webpack SPA: `index.html` (493 bytes, 6-line loader) →
  `vendor.dll.js`, `sdk.js`, chunk js, `app.js`. Plain editable web code.
- `--remote_debugging_port=9666` is in the launch line but **not honored**
  (refused on loopback at boot; no listener) — dead end for live DevTools.
- Boot-time persistence of channel edits: normal boots never re-extract the
  channel (deploy.sh fires only on an OTA upgradeversionflag) — but an OTA
  wipes `/APPS/channelA` entirely (`rm -rf` + re-extract). OTA freeze is the
  precondition for everything here (R0).
- Boot-time DAC: `security-dac-partition-apps.sh` chowns channelA to
  `UhisApp:UGhisApp` and chmods 750 each boot — keep edits readable by that
  uid.

### Canary (in place, pending reboot)

`index.html.alvidaa-bak` on the TV + `alvidaa_backups/hisenseUI_index.html`
on the Pi hold the original 493-byte loader. A visible `#alvidaa-canary` chip
(fixed, top-left, crimson) is appended after `</html>`. If it renders on the
home screen after a reboot, the shim path is proven: edits to this file are
what the stock home executes at boot.

### Strategy verdict & Native Launcher Modification Roadmap

We follow a phased hybrid roadmap so every step is reversible (`index.html.alvidaa-bak` on the TV + full `/APPS/channelA/hisenseUI/` backup on the Pi):

1. **Stage 1 — Loader Shim (`R5`, zero stock-UI flash):**
   - `/opt/hisenseUI/startgui.sh` launches Cobalt (`bin/hisenseUI`) pointing at `file:///hisenseUI/index.html`, which resolves to `/APPS/channelA/hisenseUI/index.html` (493 bytes, `ext4 rw`).
   - Once the `#alvidaa-canary` chip is verified on reboot, replace or shim `index.html` so boot and the physical `HOME` key render **alvidaa** directly inside the `hisenseUI` Cobalt process (`uid UhisUI`), eliminating the stock home flash entirely.
2. **Stage 2 — In-Place Stock `hisenseUI` Surgery (`R6`, stripped native launcher):**
   - Because `hisenseUI` also hosts system overlays and native VIDAA lifecycle hooks in `vendor.dll.js` / `sdk.js` / `app.js`, we can alternatively patch `/APPS/channelA/hisenseUI/static/` in place:
     - Stub out ad-slot fetchers (`layout-ui-eu.vidaahub.com`, `recommend-ui.vidaahub.com`) and promo-video autoplayers (`file-dl-test.../promovod/`) in `sdk.js`.
     - Strip sponsored app row injection and forced telemetry beacons (`hi_logreport_service` / `127.0.0.1:1969`) while preserving native HDMI/settings hooks.
     - Keep `security-dac-partition-apps.sh` ownership (`UhisApp:UGhisApp`, `chmod 750`) intact and freeze OTA in `otaTest.sh` (`R0`) so `deploy.sh` never wipes `/APPS/channelA`.
3. **Stage 3 — Self-Contained On-TV Daemon (`R4`, retiring the Pi — BUILT):**
   - Run the MQTT/WebSocket bridge directly on the TV (`127.0.0.1:8770`) via the static Go daemon (`bridge/dist/alvidaa-bridge-armv7`) started from `/var/local/otaTest.sh`, reading credentials from `/var/local/alvidaa/keys/` and `config.json` from `/var/local/alvidaa/config.json`. Zero external dependencies.

## R2b — the native service gateway (2026-10-30, from sdk.js analysis)

The stock home's backend is a **local phoenix service gateway at
`http://localhost:9009`**. Everything the home does — app launches, sources,
settings, ads, EPG, the home screen itself — is HTTP to this gateway. No MQTT
required for an on-TV launcher; the Pi's control role evaporates.

- Client (decoded from sdk.js): GET/POST `http://localhost:9009/{service|faas}/<path>`
  with `args` as URL-encoded JSON (GET params) or JSON body (POST); handle
  paths are namespaced `basic|system|normal/...`. Gateway responds JSON with
  `ret`/`msg` and sends **`Access-Control-Allow-Origin: *`** — any page
  (including our file:// loader) can call it, CORS-free.
- Raw GET currently returns `{"ret":false,"msg":"service register failed"}` —
  the exact request shape (registration/session) is being recovered from
  live traffic; `/var/log/log.txt` (ui-biz log) is the source.
- Service catalog so far (from `me.req("<name>")` in sdk.js): **launcher**
  (`open("launcherHome", {focusArea: "heroBanner"...})` — the HOME key itself!),
  **ads** (`startUpAds`, `heroBanner` — the startup/banner ads), **apc-service**
  (`getAppStartParam`, power-on app restore), **setting**, **live-tv**, **epg**,
  **kids-mode**, **hotel-mode**, **vidaa-plus**, plus cloud endpoints all on
  `*.vidaahub.com` (voice, recommend-ui, ota-tv, odinstore, oauth-auth) —
  the complete R0 iptables/AdGuard target list.
- The home engine injects native globals into pages it loads: `log`,
  `modeljs`, `guijs`, and the `hisense.*` bridge (`hisense.file.write` seen
  in sdk.js) — our index.html runs in the same context and inherits them.
- UI log: `/var/log/log.txt` (ui-biz lines; root-readable).
- UI engine restart (for picking up index.html edits without full reboot):
  TBD — `kill <pidof hisenseUI>` should trigger a supervisor restart; test
  before relying on it.

### Consequence for v2

The launcher page can be fully self-sufficient **on the TV**: UI from
`file:///hisenseUI/index.html` (our file), control via `localhost:9009`
gateway calls, files via the `hisense.file` bridge. The Pi's remaining role
shrinks to nothing for day-to-day operation; the bridge-on-Pi stays only as
a remote-management convenience.

## R2c — the apm config: we ARE the launcher app (2026-10-30, firmware mining)

The firmware artifacts (41 partition images + opensource seed on fx505,
`~/alvidaa-backup/`) settle the modify-vs-replace question at the config level.
`usr-local/etc/apm/application-config-na-sa.ini` defines the launcher app:

```ini
[launcher]
path = /opt/hisenseUI/startgui.sh    ; the shim point we already control
receive_focus = true
key_priority = 25000                 ; HOME key delivery priority
app_type = virtualapp
isKeepAlive = true
restore_time_when_crash = 10         ; the auto-restart we observed
```

The TV's own app framework defines "the launcher" as `startgui.sh` → the
Cobalt engine → `/APPS/channelA/hisenseUI/index.html`. Consequences:

1. **Our index.html is the launcher app's UI by the TV's own config** — HOME
   key focus, keep-alive, and crash-restore all apply to it automatically.
   No binary patching, no service replacement.
2. The HOME key likely arrives as a key event *inside the page* (key_priority
   routing) — the page can listen and treat it as "I'm already home".
3. **R6 ad-strip becomes trivial**: the ads render because the stock
   `app.js`/sdk.js runs. When our loader is in place, that code never
   executes — the `ads` phoenix service is simply never called.
4. The seed tar ("pristine vendor state") was captured post-experiments: it
   contains `channelA/hisenseUI/index.html.alvidaa-bak`. Harmless, but the
   root lane should know its pristine tag includes that leftover.
5. Partition map: p26 tvconfig, p37 usrfs, p38 **optfs** (engine + cobalt),
   p39 varlfs, p40 serialdata, p41 **apps** (channelA). `debugfs` reads them
   without mounting; `LauncherService` (`/usr/local/bin`) is the native
   service behind MQTT launchapp.

Sole remaining blocker for full native replacement: the black-screen bug on
the inlined page. `launcher/probe.html` (staged) reports the engine's
capability matrix (HTML/JS/UTF8/WS/XHR/img/external-script + native globals
`log`/`modeljs`/`guijs`/`hisense`) on the next experiment reboot.

## Write-minimization law (2026-10-30, user directive)

The p42 dump hang (wedged eMMC controller under sustained IO, recovered by
power cycle — see root lane FINDINGS) plus the user's call: **minimal TV
writes from now on, batched, even though the flash tested healthy.** Reads
are free (wear is program/erase); writes are the budget.

Launcher-lane rules that follow:

1. Every TV write is batched: one write + one reboot per experiment window,
   authorized by the user beforehand. No iterate-and-see deploys.
2. Results are collected over the network (probe pages POST to
   `/api/probe` on the bridge; reads are unlimited) — never by extra TV
   writes.
3. Steady-state launcher writes on TV: zero (logs to the bridge, config on
   the Pi, icon cache server-side).

## Canvas hypothesis (black-screen root cause, pending probe)

Pattern across all boots: every page that rendered (canary div, redirect
trampoline, the stock home itself) is **DOM/CSS**; every page that went black
(both inline launcher attempts) is **canvas-based**. The stock home runs
heavy JS with zero canvas, so it's not size or JS capability.

Working hypothesis: this Cobalt build has **2D canvas disabled** (Cobalt is
built per-platform with feature flags). Consequence if confirmed: the native
launcher is a DOM implementation (divs + CSS, like the stock home), not a
canvas painter — a UI rewrite, not a bugfix.

`launcher/probe2.html` (staged, not deployed) tests this in one reboot:
DOM-based self-reporting (never draws), stages for HTML/JS/UTF8/viewport/
canvas-presence/native-globals (log, modeljs, guijs, hisense,
HiUtils_createRequest, Hisense_*)/WS/XHR/img/external-script, every result
mirrored to the bridge. `probe-report` lands on the Pi via `/api/probe`
(ACAO: * now enabled server-side), so the window needs no user reading and
no TV writes for collection.

Restore state after the last experiment: original loader restored
(md5 fe34aa5d…), watcher re-enabled, TV functional — user watching.

## Recovery runbook — black home screen (validated 2026-10-30/11-02)

The one failure mode we've produced and recovered from twice. Symptoms: TV
boots to a black screen on the home input; sources and the webview apps may
still work.

**Root cause:** the Cobalt engine caches the home page in its profile
(`/var/local/hisenseUI/cobalt_home`, set by `startgui.sh`). A broken
`index.html` deploy poisons that cache — restoring `index.html` alone does
NOT fix the screen; the cache must be cleared in the same batch.

**Recovery (validated twice):** from the root shell (dropbear 2222, key
`server/keys/tv_root_ed25519`):

```sh
cp /APPS/channelA/hisenseUI/index.html.alvidaa-bak \
   /APPS/channelA/hisenseUI/index.html
rm -rf /var/local/hisenseUI/cobalt_home/*
reboot
```

Original loader is also mirrored at `fx505:~/alvidaa_backups/hisenseUI_index.html`
and `m1` seed (`alvidaa-firmware` repo, `index.html.alvidaa-bak`).

**Access notes:**
- Deep standby = the whole network stack is down: no ping, no 2222, no 36669.
  Only a physical power-on recovers it; allow ~60–90 s after power-on before
  SSH answers (the hook's network wait runs first).
- If the TV is on an HDMI source when you need the home to load, the home
  page fetch happens on HOME press / power-on-to-home — the engine process
  starts at boot but the page loads when the launcher app activates.

**Deployment law (updated):** every `index.html` deploy MUST batch
`rm -rf /var/local/hisenseUI/cobalt_home/*` + reboot in the same write
window — an edit without a cache clear silently serves the stale page.

## Post-mortem + final deploy tool (2026-11-03)

The flash-kill deploy broke the home: the on-TV `sed` edits scrambled the
one-line minified `index.html` (script tag landed before the doctype).
Lesson codified: **never edit files in place on the TV — build locally,
push, verify md5.** `tools/deploy-overlay.sh` now does exactly that:
fetches the pristine loader from the TV's own `.alvidaa-bak`, builds the
final file locally (head flash-kill style + bootstrap script), pushes with
md5 verification, clears the Cobalt cache, reboots. One command, one write,
one reboot, idempotent.

Also discovered: the TV is **dual-homed** (WiFi `.11` + Ethernet `.25` at
various times) — DHCP shuffles its address, which broke the bridge twice.
Static reservations for both TV MACs (WiFi `bc:5c:17:bc:46:88`, Ethernet
`88:b8:63:c8:3a:a5`) are required router-side.

Final architecture (all validated):
- stock `index.html.alvidaa-bak` + head flash-kill style + one bootstrap
  `<script src>` → overlay launcher (`alvidaa-remote.js`) served by the bridge
- stock system intact beneath (sdk.js boots, services run, keys route)
- stock UI hidden via CSS; ads never render; the `ads` service never called
- UI updates = edit `alvidaa-remote.js` on the Pi, zero TV writes
- HOME from any app returns to the overlay (key_priority 25000 routing)

### Cobalt XHR deadlock (probe finding, 2026-11-03 — loader constraint)

The capability probe isolated why the "self-healing" bootstrap froze the
home engine: **Cobalt's XHR deadlocks the page after a CORS preflight.**
Evidence: the probe's stages stop exactly at the first XHR — the preflight
(OPTIONS) reaches the server and returns 200 with correct ACAO headers, but
the actual POST is never sent and the page never executes another line
(no WS, no img, no later stages). The plain `<script src>` loader has no
preflight and is the only reliable data-free load path; all control data
must flow over the WebSocket (no preflight) — XHR is banned in the overlay.

Consequence recorded for the record: the self-healing bootstrap variant
(boot div + retrying script loader) also reproducibly froze the engine, so
the deploy tool ships the plain script tag only. Do not reintroduce XHR
into any page that runs in the home engine.
