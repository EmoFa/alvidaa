# alvidaa findings — the MQTT bridge, the 2024 auth wall, and self-install

> Split from the original FINDINGS.md lab notebook. Canonical record; the blog and STORY.md draw from these.

## 1. Discovery

- SSDP M-SEARCH (`ssdp:all`) finds the TV: a DLNA **MediaRenderer** on a
  random port (e.g. `:38400/MediaServer/rendererdevicedesc.xml`). The device
  descriptor's `modelDescription` leaks a gold mine:
  `mac=`, `macWifi=`, `macEthernet=`, `region=`, `brand=his`,
  `vidaa_support=1`, `transport_protocol=3290`.
- `transport_protocol` predicts which auth generation the MQTT broker uses
  (3290 = modern, see §3).
- The TV answers SSDP/RemoteNow only while powered on; deep standby takes the
  network stack down completely.

## 2. RemoteNow control channel

- MQTT over TLS on **port 36669**, broker = built-in `hisenseservice`.
- The TV requests a **client certificate** at the TLS layer but (on our
  firmware) does not validate it — any cert completes the handshake. The
  identity check happens at MQTT CONNECT (§3).
- All traffic: publish actions to `/remoteapp/tv/<service>/<client_id>/actions/<action>`,
  receive pushes on `/remoteapp/mobile/<client_id>/data/<action>` and
  `/remoteapp/mobile/broadcast/...`.
- Useful actions: `gettvstate`, `sourcelist`, `applist`, `launchapp`,
  `changesource`, `sendkey`, `authenticationcode`.

## 3. The 2024 authentication gate (the big one)

Old guides use static MQTT credentials (`hisenseservice` / `multimqttservice`)
plus the 2018 RemoteNOW certificate. On 2024+ firmware that fails with
**MQTT rc 5 (Not authorized)** at CONNECT, and the TV pops
*"your TV mode is no longer compatible with the version of the app"*.

What actually matters, in order:

1. **Client certificate identity.** The broker checks the client cert's
   subject and only accepts the current app's cert:
   `CN=VidaaAppAndroidV01, OU=multimedia, O=hh` (issued by `CN=RemoteCA`,
   valid 2024→2034). TLS handshake succeeds with any cert — the refusal is at
   the MQTT layer, which is why the popup appears per attempt.
2. The cert lives inside the official **VIDAA Smart TV** Android APK
   (`com.universal.remote.multi`):
   - newer builds: `res/raw/client_mobile_android.p12` (un-obfuscated)
   - older builds: `res/El.p12` (obfuscated name, same 2565-byte keystore)
   - keystore password: `186e990688070325a1c4b0ce275d2388`
   - convert: `openssl pkcs12 -legacy -in client_mobile_android.p12 -passin pass:… -clcerts -nokeys -out cert.pem` (and `-nocerts -nodes` for the key). The `-legacy` flag matters — legacy RC2/3DES ciphers.
3. **Dynamic credentials** (per-connect):
   ```
   digest    = md5("38D65DC30F45109A369A86FCE866A85B$" + mac).upper()
   client_id = "<MAC>$his$" + digest[:6] + "_vidaacommon_001"
   username  = "his$" + (timestamp ^ 6239759785777146216)     # modern profile
   digit_sum = sum(int(d) for d in str(timestamp)) % 10
   salt_hash = md5("his" + digit_sum + "h!i@s#$v%i^d&a*a").upper()
   password  = md5(timestamp + "$" + salt_hash[:6]).upper()
   ```
   Older firmware generations use the same shape without the XOR mask and/or
   with the RemoteNOW salt `h*i&s%e!r^v0i1c9` — hence the 4-profile cascade
   in `pair.py`.
4. **After the PIN**, the TV issues real credentials
   (`platform_service/data/tokenissuance`): `accesstoken` (2 days) +
   `refreshtoken` (30 days). Subsequent CONNECTs use the dynamic username +
   access token as password; refresh via `platform_service/data/gettoken`
   with `{"refreshtoken": …}`.

**Reading the error code.** `paho-mqtt` 2.x — the version the server pins —
reports MQTT 3.1.1 CONNACK codes as v5 reason codes, so the "rc 5" above
arrives as **`rc=135`** (*Not authorized*); a bad username/password is
`rc=134`. Both mean the TV refused the **identity**, not the transport: the
TLS handshake and TCP connect already succeeded. Check
`server/keys/tokens.json` before anything else — with no token file the server
falls back to the legacy static login and is guaranteed to be rejected on
2024+ firmware. The server now names the code and prints the identity it
presented on every reject.

### 09.60 pairing report: controller identity

[Wing-Tsit-Chong reported](https://reddit.com/r/Hisense/comments/1xj3pc2/comment/19rx89p6gsqyq/)
pairing a 43A60LEVS (MTK9603, `V0000.09.60V.Q0612`) after their TV MAC was
rejected. On that set, an app-style MAC **with colons** in `TV_MAC` produced
the accepted client ID with the modern profile; a distinct locally administered
identity also worked in their test. They reported silent rc 5 for the rejected
attempts instead of the popup seen on 09.01. `pair.py` uses `TV_MAC` as the
client-identity input; keep the exact formatting, and avoid sharing a paired
identity with another active MQTT client.

This is a community report for one model and firmware, not a requirement
established for all 09.60 sets. Pairing and remote page loading were reported;
launcher installation and the root chain remain untested on that unit.

A separate, user-supplied 65U7H / U6 report describes successful PIN pairing
with a controller identity and the RemoteNOW credential profile, but no action
responses afterward. The researcher and public source still need attribution;
do not treat `transport_protocol=3160` alone as a verified profile selector.

## 4. Pairing flow quirks

- Trigger the PIN dialog with `ui_service/vidaa_app_connect`
  `{"app_version":2,"connect_result":0,"device_type":"Mobile App"}`.
- The "dialog is showing" push arrives on `…/data/authentication` (empty
  payload) — *not* on `authenticationcode`. Some firmware never sends it.
- **Re-triggering rotates the PIN.** A keepalive that republishes
  `vidaa_app_connect` every few seconds guarantees the code you read is stale
  by the time you submit it (`result:100, "illegal authNum!!"`). Trigger once,
  wait, submit.
- PIN submission: `ui_service/actions/authenticationcode` `{"authNum": 1234}`
  (int, not string). Reply on `…/data/authenticationcode` with `result: 1`.
- Submitting a wrong/expired PIN returns `result: 100 "illegal authNum!!"`.
- Two clients with the **same client_id** kick each other off the broker
  (classic MQTT takeover) — diagnostic scripts must not reuse the paired
  client_id while the server runs.

## 5. Firmware broker quirks

- **Wildcard subscriptions are denied.** `SUBACK` returns *Unspecified error*
  for `/remoteapp/mobile/…/#`; you must subscribe to **exact topics**. This
  silently breaks every naive client (you publish fine, hear nothing back).
- Responses are JSON; lists (applist/sourcelist) are JSON **arrays**, dicts
  (state/token) are objects — filter carefully or you drop half the traffic.
- TV state: `broadcast/ui_service/state` with `statetype` —
  `remote_launcher` = VIDAA's own home screen (the home watcher's trigger),
  `sourceswitch` on input change, etc.
- Source objects carry both `is_signal` and `has_signal`; `is_signal` is 0 for
  every non-active input, `has_signal` reflects actual presence. OR them.

## 6. Installing a web app as a native app

Three generations of installers:

1. `hisense://debug` in the TV browser — the 2021-era hidden installer.
   **Closed on this firmware** (URL does nothing).
2. `Hisense_installApp(appId, name, thumb, iconS, iconL, url, storeType, cb)`
   — the JS bridge function from the Bananamafia era. May still exist.
3. **`HiUtils_createRequest`** — the modern one, verified working on this TV:
   ```js
   const cur = HiUtils_createRequest("fileRead", {path: "websdk/Appinfo.json", mode: 6});
   const list = cur.ret ? JSON.parse(cur.msg) : {AppInfo: []};
   list.AppInfo.push({
     Id: "vidaa-home", AppName: "Home", Title: "Home",
     URL: "http://<server>:8765/", StartCommand: "http://<server>:8765/",
     IconURL: icon, Icon_96: icon, Image: icon, Thumb: icon,
     Type: "Browser", InstallTime: "2026-10-29",
     RunTimes: 0, StoreType: "custom", PreInstall: false
   });
   HiUtils_createRequest("fileWrite", {path: "websdk/Appinfo.json", mode: 6,
                                       writedata: JSON.stringify(list)});
   ```
   Restart the TV afterwards; the app appears at the end of the app list.

Both JS bridge functions are exposed to **any page the TV browser opens** —
no `hisense://debug` needed. This project's launcher page detects them and
offers a self-install tile, so the TV installs itself from a plain
`http://<server>:8765/` visit. (This is also the silent-install attack the
Bananamafia post demonstrated — one more reason to DNS-block TV telemetry and
not browse the open web on the TV.)

## 7. The VIDAA browser (Chromium 111 "odin" vs. legacy Chrome 77 notes)

- Older community guides assume Chrome 77 (`ES2018` max); on 2024+ firmware (`V0000.09.01O.P0813`), the web-app browser (`odin`) actually reports **Chromium 111** (`armv7l`), while the stock home (`bin/hisenseUI`) runs in an embedded Cobalt engine (see [03-bridge-internals.md](03-bridge-internals.md) §10.1 and [LAUNCHER_V2.md](../../../../launcher/LAUNCHER_V2.md)).
- One canvas at 960×540 (720p-class) upscaled by the TV renders predictably and keeps repaints cheap.
- Shipping ES2018-compatible JS (avoiding optional chaining / nullish coalescing) keeps pages portable across older VIDAA builds.
- **The D-pad moves an on-screen pointer** and OK emits a **click** — keyboard
  events are not the primary input. Support both: hit-test `click` on canvas
  tiles *and* `keydown` arrows/Enter.
- `Cache-Control: no-store` on everything, or firmware caching will serve
  stale pages after you fix bugs.
- Full-screen offscreen canvases render empty; pre-render shadows/sprites if
  you need effects.

### Launcher startup and action handling (code review, Oct 30)

- Cached tiles can set the initial focus before the first live server snapshot.
  Using that focus flag to identify the first snapshot prevented the optional
  HDMI auto-switch from starting. Track the first live snapshot separately and
  leave the user's focus alone if they have already navigated.
- A launch/source command could silently fail while offline, and WebSocket
  action responses were ignored. The launcher now reports offline and server
  errors and clears its busy state on a response or lost connection.
- Cancel a pending auto-switch if the user navigates or the sole active input
  changes before the countdown expires. These changes were exercised in a
  simulated browser; they have not yet been verified on the TV.
