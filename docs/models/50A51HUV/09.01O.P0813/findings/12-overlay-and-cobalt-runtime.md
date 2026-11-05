# Findings 12 — Cobalt runtime, overlay traps, and boot-time network race

> Discovered 2026-11-03 during the native launcher overlay deployment on MTK9602 (VidaaOS 09.01).

## 1. `sdk.js` is load-bearing for the TV OS

Replacing `/APPS/channelA/hisenseUI/index.html` with a custom HTML bootstrap completely breaks the TV user interface. 

The vendor `index.html` contains:
```html
<script src="./static/js/vendor.dll.js"></script>
<script src="./static/js/sdk.js"></script>
<script src="./static/js/389.js"></script>
<script src="./static/js/537.js"></script>
<script src="./static/js/app.js"></script>
<script src="./static/js/style.js"></script>
```
`sdk.js` is not merely the UI frontend; it runs the DirectFB/Cobalt JavaScript message pump that routes hardware remote inputs, coordinates with `superwatch` and `phoenix`, and reports power and display state over MQTT to `mosquitto`. If `sdk.js` and `#app` do not initialize, the entire TV UI engine wedges, resulting in a persistent, unresponsive gray screen.

**Rule**: The stock loader must be preserved. Modifications must be strictly append-only.

## 2. Cobalt Starboard Parser Drops Post-`</html>` Tags

When injecting elements into `index.html`, string-appending tags at the end of the file places them after `</html>`. Modern desktop Chrome tolerates tags after the closing `</html>`, but **Cobalt's Starboard parser stops tokenizing at `</html>`**.

If `<style id="alvidaa-head-style">#app{display:none!important}html,body{background:#0a0d12!important}</style>` is injected into `<head>`, but `<script src="...">` is appended after `</html>`, Cobalt executes the CSS (hiding the stock UI and painting `#0a0d12`) while silently discarding the script tag.

**Rule**: All injected scripts must be inserted before `</body>`.

## 3. Cobalt XHR CORS Preflight Deadlock

Any attempt to make an `XMLHttpRequest` from `file:///hisenseUI/index.html` to an external HTTP server that requires a CORS preflight (`OPTIONS` $\to$ `POST`) results in a permanent thread deadlock.

The probe proved:
- Cobalt sends the `OPTIONS` request.
- The server responds `200 OK` with `Access-Control-Allow-Origin: *` and appropriate headers.
- Cobalt receives the response, but **never dispatches the subsequent `POST`**.
- The JavaScript execution thread halts on a spinlock, freezing the entire home UI.

**Rule**: `XMLHttpRequest` is strictly prohibited in any page running within the home engine. All communication must use WebSocket (`ws://` / `wss://`), which connects without CORS preflight.

## 4. Automated Dropbear SSH Reboot Stalling (`. /etc/profile` Hang)

Deploy scripts that attempted to issue a reboot via:
```bash
. /etc/profile >/dev/null 2>&1
/usr/local/bin/reboot
```
failed silently. Sourcing `/etc/profile` inside a non-interactive Dropbear session hangs on an unhandled iniparser call (`cannot open /hidata/factory/data/AutoGamma.ini`) or terminal setup. Because `/etc/profile` never returned, `/usr/local/bin/reboot` was never executed. When the SSH session disconnected, the hung process was reaped.

Furthermore, `/usr/local/bin/reboot` dynamically links against `/mslib/libdirect-1.4.so.0`, failing with `exit 127` if `LD_LIBRARY_PATH` is incomplete.

**Rule**: Always use the standalone static busybox binary with forced restart:
```bash
/var/local/tvtools/busybox reboot -f
```

## 5. Boot-Time Network Race Condition

On cold boot or wake from deep standby:
- The Linux kernel starts services, and `hisenseUI` (Cobalt) launches at $t \approx 5$ seconds.
- Wi-Fi association (`wpa_supplicant`) and DHCP lease acquisition (`udhcpc`) require 25 to 35 seconds.
- If `index.html` contains `<script src="http://<server-ip>:8770/..."></script>`, Cobalt initiates the HTTP fetch at $t=5$s when `wlan0` is still down.
- The request immediately fails (`ERR_NETWORK_UNREACHABLE`). Cobalt does not retry failed `<script>` tags.
- With the script failed and `#app` hidden by CSS, the TV is permanently locked on the dark background.

**Rule**: In-engine scripts must reside on local flash (e.g. `<script src="./alvidaa-remote.js"></script>`) with world-readable permissions (`644 UhisApp:UGhisApp`). The local script can then instantiate a WebSocket connection with backoff retries until the network interface is up.

## 6. Cobalt localStorage Ownership, Recreation, and Flush Traps

Discovered 2026-11-04 during the gray/black-screen hunt on the overlay.

- Storage lives at `/var/local/hisenseUI/cobalt_home/.starboard.<base64
  origin>.storage` — for the home page the origin key decodes to
  `file:///hisenseUI/index.html`. The directory is `UhisUI:UGhisUI`.
- **Ownership trap**: the file was found `root:root 0600` while the home
  engine (`UIMainWebModule`, syslog tag `hisenseUI`) runs as `netflix`.
  The engine could neither read nor write its own localStorage: the
  overlay's `alvidaa_cache_v1` never persisted, and every boot started
  cold. A manual `chmod 666` restored access; after the next engine
  crash + reboot the engine **recreated the file as `UhisUI:UGhisUI
  0600`** — so the engine self-manages storage it creates, and a
  root-owned fossil is the anomaly that permanently breaks it until
  manually fixed.
- **Data-loss trap**: storage recreation silently loses everything it
  held — including *stock-home layout customizations* (hidden/removed
  apps). Observed 2026-11-04: the user's hidden apps reappeared on the
  stock home after the file was recreated (29067 → 24718 bytes) during
  the engine crash loop. Losing this file resets the user's home.
- **Flush granularity**: on a healthy page, writes reach flash within
  ~10 ms (marker timestamps). On a wedge or crash, everything after the
  last flush is lost — in our traces only the first ~10 ms of markers
  survived, so localStorage is *not* a reliable crash black-box recorder.
- **Diagnostic technique that works on this engine**: per-key
  localStorage markers (one key per lifecycle stage, e.g.
  `alvidaa_d_<stage>`) plus a `window.onerror` hook — a poor man's
  console for a browser you cannot inspect. Cobalt masks uncaught errors
  from `file://` scripts as `Script error. @0:0` with no line/column,
  so per-stage markers, not stack traces, are the usable signal.

**Rules**: never leave cobalt storage root-owned after running the
engine from a root context; treat any storage-file recreation as a
data-loss event for both the overlay cache and the stock-home layout;
never keep the only copy of user-visible state in this storage.

## 7. The home engine has no canvas — the canvas-overlay path is impossible (2026-11-04)

Probe-verified on 09.01O.P0813 (MTK9602), after a clean boot with a cleared
`cobalt_home` cache:

- `typeof HTMLCanvasElement === "undefined"` — the global does not exist.
- `document.createElement("canvas")` returns a **generic element**: its
  prototype chain carries only `HTMLElement` members (`dir`, `dataset`,
  `tabIndex`, `style`, `on*` handlers) — no `width`/`height`,
  no `getContext`, no `toDataURL`.
- `typeof cv.getContext === "undefined"` → the string
  `"cv.getContext is not a function"` is the death point of every
  canvas-overlay script, in the home engine **and** in every web app that
  loads the shared `hisenseUI` shell.
- `<iframe>` is unsupported too (`contentDocument` is undefined) — no clean
  realm escape hatch.
- The stock page itself contains **zero** `<canvas>` elements (probe count
  includes only our injected one). Starboard on this build is DOM-only.

**Attribution correction**: the Nov 3 "framebuffer-verified overlay" was the
**odin browser** rendering the launcher page via the watcher bounce (the
watcher was enabled on Nov 3) — not a Cobalt canvas overlay. Every Cobalt
overlay attempt, before and since, died at the same missing-`getContext`
line. Chromium-based odin has full canvas; the standalone launcher page
renders fine there.

**Consequences**:

1. Canvas-in-home-engine overlays are **impossible on this model/firmware**.
   The launcher's screen path is the browser: on-TV bridge → watcher bounce
   → installed web app → odin renders from `127.0.0.1:8770`. Re-probe before
   ever designing around home-engine canvas on a new firmware.
2. The injected overlay script must stay **out of the shared shell**: with
   `#app` hidden by the injected style and the script dead, home and apps go
   dark and unresponsive until reboot. Pristine `index.html` + `.alvidaa-bak`
   restore is the recovery.
3. **Compiled-JS cache is stale-by-URL**: Cobalt serves scripts from
   `cobalt_home` without re-validating content — a re-push under the same
   filename runs the OLD code (observed: fresh markers absent, identical
   timestamps across three "new" builds). Every script deploy needs
   `rm -rf /var/local/hisenseUI/cobalt_home/*` **plus a reboot** — this is
   why `tools/deploy-overlay.sh` clears the cache in the same batch.

**Diagnostic techniques that worked here** (for the next hunt):

- Per-stage `localStorage` markers (`alvidaa_p_*`, one key per step) — the
  only crash recorder the engine has; storage flushes within ~10 ms but a
  wedge loses everything after the last flush.
- `window.onerror` fires but Cobalt masks file:// script errors as
  `"Script error. @0:0"` — no line/column. Wrap the whole body in a
  try/catch: caught errors carry real messages and stacks.
- Plain `console.log` does **not** reach `/var/log/log.txt` (the stock UI's
  `jsplugins print()` lines come from an SDK logger, not the console).
- Zero-visual-impact probing (1px canvas at 1% opacity, tiny style rule)
  names the killer op without black-screening the TV.

Hands-off reminder (cross-ref findings 03): never write to `/OAD` — the
fileOperation service reaches it (mode 7) and it holds update staging.

Stock-bundle internals reference:
[HOME-UI-INTERNALS.md](../../../../launcher/HOME-UI-INTERNALS.md) — static
pass over the vendor tree (load chain, service layer, key dispatch).

## 8. Engine lifecycle, the crash-evidence blackhole, and the uncaught-error exit path (2026-11-04)

Static rootfs dig (vendor tree `apps/opt-hisenseUI/{bin,lib}` +
`usr-local/{scripts,etc/apm}`) plus read-only `/proc` inspection of a live
stock-home engine. Explains why every overlay wedge leaves zero crash
evidence, and gives the launcher lane concrete verification steps.

### Launch chain (verified)

```
start-hisense.sh:278
  └─ /usr/local/bin/secure_exec hisenseUI /opt/hisenseUI/startgui.sh &
       (sets uid/gid/groups/caps from a process-label match table)
       └─ startgui.sh: cd /opt/hisenseUI; HOME=/var/local/hisenseUI/cobalt_home
          exec ./bin/hisenseUI --remote_debugging_port=9666 \
             --webdriver_port=4445 --url=file:///hisenseUI/index.html \
             >/dev/null 2>&1 &
```

- `stdout/stderr` go to `/dev/null` — the engine's only log route is syslog
  (tag `hisenseUI`). Combined with §7's finding that plain `console.log`
  does not reach syslog, in-engine printf debugging has **no** console
  channel: per-stage localStorage markers (§6/§7) remain the only recorder.
- **Two processes** appear at boot: pid A named `FRAME` (start ≈6.8 s) and
  pid B named `UIMainWebModule` (≈8.3 s) — same cmdline, both reparented to
  init, byte-identical VmRSS (~227 MB, 45 threads). `UIMainWebModule` is set
  by libcobalt itself; no literal `FRAME` exists in the wrapper or libcobalt
  (a linked lib sets it). Working model: wrapper main + its web-module child.
  "The engine dies" has so far meant the *page/module* dying — the pair was
  observed alive and healthy on stock home.
- The engine starts **at boot** (~7 s, consistent with §5's t≈5 s), not
  on-demand. Engine uid is `UhisUI:UGhisUI` (via `/proc/PID/exe` ownership) —
  §6's `netflix` attribution does not match the home-engine processes.
- **APM policy** (`usr-local/etc/apm/application-config-na-sa.ini`, section
  `[launcher]`): `path=/opt/hisenseUI/startgui.sh`, `isKeepAlive=true`,
  `restore_time_when_crash=10`, `app_type=virtualapp`,
  `key_priority=25000`. APM keeps the launcher alive and respawns it after a
  crash.

### The crash-evidence blackhole (all verified read-only)

Every hunt for a crash trace on this TV returns empty, by design:

1. **`/var/local/uartoff` exists** (0 bytes, factory-dated). `core_pattern`
   pipes cores to `/sbin/coredump.sh`, which in UART-off mode only `touch`es
   an **empty placeholder `.gz` and exits** — no core, no gdb backtrace,
   ever. `/var/crash` empty, `dmesg` clean.
2. Even with UART on, the script dumps **one core per executable** (guard
   flag `/var/run/his_corehelper`) and stages the core through **`/OAD`**
   (TV-side behaviour; reinforces the §3/§7 OAD hands-off rule).
3. The wrapper *does* log crash lines to syslog — `App hisenseUI exit !!!`,
   `onCrashHandler sigId:%d`, `segfault_post sigId:%d` (strings in
   `bin/hisenseUI`) — but the `/var/log/log.txt` ring rotates within ~4 min
   during the boot log storm, so any wedge trace is rotated out within
   minutes.
4. `ps` on this firmware is unreliable (a bare `ps w` lists only `getty`).
   Process discovery must use `/proc/<pid>` directly or
   `/var/local/tvtools/busybox ps`.

### Storage commit semantics (mechanism for §6's flush observation)

The wrapper implements Starboard storage itself over **SQLite**
(`libsqlite3.so.0`, `Sqlite3OpenFunc`, `commitChanges`,
`Committing changes failed with error code %d` in `bin/hisenseUI`). Writes
land at explicit commit points; an abrupt death between commit points loses
everything since the last one — the mechanism behind §6's "only the first
~10 ms of markers survive a wedge".

### Death-mechanism hypothesis (binary-evidenced; trigger is §7's verdict)

- libcobalt carries the `"Script error."` masking literal and
  `SbSystemRaisePlatformError`; the wrapper carries
  `cobalt::hisense::modeljs::notifyModelJsExecutionError`
  (`notifyExecutionError with name:%s,actionId:%d,errorCode:%d`) and the
  `App hisenseUI exit !!!` log line.
- Hypothesis: an uncaught error in the web module (§7: `cv.getContext is
  not a function`, or any other throw) reaches the platform-error path →
  the wrapper exits the app → APM `isKeepAlive` respawns (or the `FRAME`
  side relaunches the module) → `index.html` reloads → same throw →
  **crash loop** = dark screen, no WebSocket, no heartbeat, unresponsive
  until re-navigation or reboot. The masked `Script error. @0:0` is
  expected for *any* error in an injected `file://` script: Cobalt gives
  file:// scripts opaque origins, so even same-directory script errors are
  masked.
- **Open discriminator**: process-exit vs JS-thread wedge. One look
  decides — during a live wedge, `ls /proc/<engine pid>` (or
  `busybox ps`): `UIMainWebModule` gone → exit path confirmed; process
  alive with a dead page → thread wedge.

**Verification steps for a live deploy** (need TV-write coordination, none
executed for this study):

1. Live-follow syslog during a wedge:
   `/var/local/tvtools/busybox tail -f /var/log/log.txt | grep -E 'exit|CrashHandler|segfault|ExecutionError'`
   — `App hisenseUI exit !!!` within milliseconds of the first marker
   confirms the exit path.
2. **DevTools unlock (previously unrecorded)**: the engine runs with
   `--remote_debugging_port=9666` (and `--webdriver_port=4445`). Forward it
   over the root-key ssh session (`ssh -L 9222:127.0.0.1:9666`, TV-side
   loopback only) and attach Chrome DevTools to the home engine: real
   uncaught-error messages and stacks (no masking), a live console, and DOM
   inspection — everything §7's marker technique approximates.

   **Correction (2026-11-05): the flag is present but the port does not
   listen.** `netstat -lnt` on the TV shows only 2222 and 8770 open; 9666
   and 4445 are both closed, and an `ssh -L 9666:127.0.0.1:9666` forward
   returns nothing. So the cmdline advertises the debug port and the engine
   never binds it on this build. Treat the forward as a hypothesis to test
   on the specific unit, not as an available tool — the marker technique
   above remains the only verified route.
3. If in-engine work ever resumes post-pivot: the diag build's
   `window.onerror` handlers `return false`. Returning **true** marks the
   error handled and may suppress the platform-error exit — a one-line,
   zero-risk test that converts the death into a recoverable diagnostic
   state.

**Rules**: never hunt crash evidence via `/var/crash` or `dmesg` on this
firmware (both structurally empty); read process state from `/proc`, never
from `ps`; treat any wedge-window syslog grep as time-critical (ring
rotates in minutes); rely on the DevTools forward (port 9666) instead of
localStorage markers whenever a deploy can carry it.

## 9. Screen capture: every obvious route is closed (2026-11-05)

Measured while building a screenshot pipeline, so the next person does not
repeat it. Four routes, three dead, one viable.

**1. Framebuffer read returns nothing.** `/dev/fb0` exists and reports
`virtual_size=1920,3240`, `bits_per_pixel=32`, `stride=7680` (three 1080p
buffers). Writes work — that is how `doomgeneric` paints. Reads do not:

```sh
dd if=/dev/fb0 of=/tmp/f.raw bs=7680 count=1080   # -> 0 bytes
```

`/dev/fb1` behaves the same; `/dev/fb2` and `/dev/fb3` do not exist. The
display is composited through `mstar_fbdev_mi` + `mali_kbase_m7332`
(`/proc/modules`), so `fb0` is a legacy surface the compositor never fills.
This is the fb0-bypass case, confirmed rather than assumed.

**2. The DevTools port does not listen.** See the §8 correction: the engine
cmdline carries `--remote_debugging_port=9666 --webdriver_port=4445`, but
`netstat -lnt` shows only 2222 and 8770. An ssh forward to 9666 returns
nothing.

**3. `/usr/local/bin/screenshot` is a display-pipeline client — and it works.**
112 KB, dynamically linked, stripped, built from
`systools/app-screencapture/src/screenshot.cpp`. Strings show it starts an
`fsal2 tcp server`, registers a peer `dvbmain`, and calls `cmdCaptureScreen`,
reporting `Screenshot will be stored at : %s %s of type %d`.

**Correction (2026-11-05, same day): this route works and is the one in
use.** It takes **two** arguments — a directory and a name:

```sh
/usr/local/bin/screenshot /tmp alvidaa-shot.jpg
```

An earlier attempt passed a single argument (`screenshot shot1`) and
produced no file and no output, which was read as "needs a display service
that is not running". It does not: it needs the second argument. The HAL
writes **PNG bytes regardless of the `.jpg` name**, 1920x1080 RGBA, about
1.2 MB per frame, into the directory given. The RPC is asynchronous, so
poll for the file rather than assuming it exists on return.

`tools/screenshot.sh` wraps this: capture into TV `/tmp` (tmpfs, gone at
reboot), pull over the root-SSH lane, delete the TV copy. No persistent
writes, no remote interaction. This supersedes route 4 for whole-screen
capture.


**4. The launcher can capture itself, and that is the useful one.**
`launcher/index.html` renders everything into
`<canvas id="c" width="1920" height="1080">`. odin is Chromium 111, so
`canvas.toDataURL('image/png')` returns the exact pixels being displayed.
(The no-canvas limitation in §7 is Cobalt, the home engine — a different
process.) A `?shot` mode that renders, grabs the data URL, and POSTs it to
the bridge gives launcher verification with no framebuffer, no DevTools and
no vendor binary.

**Limits to state plainly**: route 4 captures the launcher page only. Not
the stock UI, not HDMI content, not Doom. For "does the launcher look
right" it is strictly better than a framebuffer grab, because it is the
pixels the TV is actually showing. Whole-screen capture remains unsolved.
