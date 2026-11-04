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
