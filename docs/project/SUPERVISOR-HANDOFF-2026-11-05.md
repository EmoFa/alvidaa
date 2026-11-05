# Supervisor handoff — zcode-bee3 → ds41 (2026-11-05)

Operational handoff. Read this before directing the bees; every claim here
was verified live on the device during the 11-04 session unless marked
otherwise.

## Team state

- Goal: `alvidaa repo maintenance, inventory tracking and launcher updates.
  working towards 2.0`.
- Roster: **ds41** (supervisor, you), **zcode-bee3** (this pane; also ran the
  11-04 TV lane under the name `super`), **zcode-bee1**, **zcode-bee2**.
  agy1/crouton/zcode-bee1-3 originals all cycled out during 11-04 — mentions
  to them bounce; check the roster before @mentioning.
- Open tasks: 2b1f25eb (this handoff), 6e9fbd75 (catalogue correctness pass,
  claimed), 9d67d051 (root debug/status page, bee1), 9b72249e (R6 UI-bundle
  RE, bee2), 48f254f6 (2.0 roadmap tracking — unassigned).

## LIVE DEVICE STATE (TV 50A51HUV, 09.01O.P0813, 192.168.0.11)

- **The launcher is LIVE and owner-approved**: dark-glass redesign rendered
  by **odin** (the TV's Chromium browser), reached via **watcher bounce**
  (bridge polls `statetype == remote_launcher` at 1s and launches the
  installed web app `vidaa-home` → `http://127.0.0.1:8770/`).
- **The home shell is PRISTINE.** `/APPS/channelA/hisenseUI/index.html` is
  stock; nothing may be injected into it (findings 12 §7: this Cobalt build
  has **no `HTMLCanvasElement`** — canvas overlays are impossible, and any
  injected script that dies darkens home AND every app until reboot).
- **Bridge**: `alvidaa-bridge` (Go, static armv7, `bridge/`), loopback MQTT
  `127.0.0.1:36669`, HTTP/WS `0.0.0.0:8770` (hook flag), assets
  `/var/local/alvidaa/launcher/`, config `/var/local/alvidaa/config.json`
  (watcher enabled, interval 1s), log `/var/local/alvidaa/bridge.log`.
  bee2 deployed the combined binary on 11-05: directory-URL fix (v1.0-48
  lineage) + cache-first `serveIcon` + iconcache default moved to
  `<assets>/iconcache` + Spotify icon. Verify 5/5 icons + `GET /icon/vidaa-recon`
  → 200 after their window.
- **Hook**: `otaTest.sh` **v12** on the TV (early bridge start ~15s into
  boot, before the LAN wait; late start pidof-guarded). Captured into the
  repo by bee1 (bf53bd3; `launcher/hookinstall.html` embeds HOOK_V12).
  Known v13 candidates: the watchdog `pgrep` bug (line ~54: pgrep missing →
  `kill -9 $(pidof dropbear)` runs every 30s for 20min post-boot, murdering
  SSH sessions mid-command), and the tvtools fetch hardcoding 192.168.0.85.

### Reversibility anchors (all verified on the TV)

| What | Where |
|---|---|
| Pristine home shell | `/APPS/channelA/hisenseUI/index.html.alvidaa-bak` |
| Previous launcher design | `/var/local/alvidaa/launcher/index.dac1122.bak` (+ `alvidaa-remote.dac1122.bak`) |
| Previous hook | `/var/local/otaTest.v11.bak` (md5 aa6198627…) |
| Previous bridge binaries | `/var/local/alvidaa/alvidaa-bridge.bak*` |
| Kill-switch for the whole hook | `touch /var/local/hook.off` + reboot |

### Recovery recipe (launcher dark, TV reachable)

`cp /APPS/channelA/hisenseUI/index.html.alvidaa-bak /APPS/channelA/hisenseUI/index.html`
→ `rm -rf /var/local/hisenseUI/cobalt_home/*` → ensure bridge running →
`/var/local/tvtools/busybox sync` → reboot `-f`. The watcher then bounces.

## Traps a new supervisor will get wrong

1. **Standby looks like an outage.** Deep standby drops the TV off the LAN
   entirely (no ARP, all ports closed). On 11-05 this caused a false
   "launcher is dark" alarm — power it on and hook v12 self-heals (verified:
   watcher auto-bounced at wake, 10:08:19). Diagnose reachability FIRST.
2. **Cobalt compiled-JS cache is stale-by-URL.** Re-pushing a script under
   the same filename runs the OLD code. Every script deploy needs
   `rm -rf /var/local/hisenseUI/cobalt_home/*` + reboot.
3. **No canvas in the home engine.** `HTMLCanvasElement` does not exist
   (probe-verified, findings 12 §7). Native launcher work is DOM-only.
4. **The shell is shared.** `hisenseUI/index.html` is the only home page;
   anything injected there runs once per page-load — a dying script =
   dark home + dark apps. Append-only + fail-open, or don't.
5. **One MQTT identity per TV.** The bridge and `server/vidaa_server.py`
   share the paired client identity — never both at once.
6. **`console.log` does not reach syslog.** The stock UI logs via an SDK
   `jsplugins print()` path. In-engine diagnostics = per-stage localStorage
   markers (flushes ~10ms; a wedge loses everything after the last flush —
   storage is SQLite-backed with explicit commit points, findings 12 §8).
7. **`ps` is unreliable** — a bare `ps w` lists only getty. Use
   `/proc/<pid>` or `/var/local/tvtools/busybox ps`. `pidof` also misses the
   engine sometimes; the engine's comm is `UIMainWebModule` (plus a `FRAME`
   sibling), uid `UhisUI:UGhisUI`.
8. **The framework caches its app list across installs** — an
   `INSTALL AS APP` re-point takes effect only after a reboot
   (`/APPS/websdk/Appinfo.json` is the ground truth on disk).
9. **TV egress is kill-listed** — the icon pipeline must serve from the
   local cache (`/icon/*`), never fetch from the network at runtime.
10. **SSH sessions die mid-command** during ~20min post-boot (the pgrep
    watchdog bug above). Keep remote commands short, use busybox full paths
    (`tail`, `sed` etc. are not on PATH).

## In flight / next

- bee1: root debug/status page (9d67d051) — `/debug.html` + `/api/debug` +
  launcher tile; surfaces bridge/watcher/kill-list state so outages stop
  being guesswork. Also: polish pass landed (diagnostics behind `?debug`,
  three bg wallpapers via `tools/make_bg.py`).
- bee2: R6 groundwork (9b72249e) — static RE of the six UI bundles toward a
  **native DOM launcher inside the home engine** (no odin, no watcher, no
  flash — the stock home proves Cobalt renders DOM fine). This is the 2.0
  strategic line; findings 12 §7/§8 are required context.
- bee3 (me): catalogue correctness pass (6e9fbd75) after this doc.
- Issue #10 (09.60A.Q0707): your tokens.json/rc=135 analysis matches what
  the TV lane knows — the per-app write gate closing that lane is the
  fourth such unit. No contradiction.
- Watch item: the bridge restarted by itself overnight (pid 3085→25645,
  cause unknown, recovered cleanly) — the debug page's "last restart" field
  exists to make this visible.

## 2.0 prioritisation

1. Stabilise the odin lane (icons 5/5, backgrounds, debug page) — shipping.
2. R6: UI-bundle RE → append-only DOM surgery on the stock home (strip
   ads/sponsored) → native DOM launcher in-engine. The UI-RE doc is the gate.
3. Lane 1 (unrooted) maintenance continues via inventory/PRs — it is the
   product lane and the root lane must never break it.
