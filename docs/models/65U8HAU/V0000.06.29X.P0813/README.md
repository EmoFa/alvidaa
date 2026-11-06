# 65U8HAU — V0000.06.29X.P0813 (extension X.P0813)

- **Model:** `65U8HAU` (Australian U8H series; internal board/model `65E83GAVT` via `Hisense_GetModelName()`)
- **Firmware:** `V0000.06.29X.P0813` (extension `X.P0813` via `Hisense_GetFirmWareVersion()`)
- **SoC:** `MTK9900` (MediaTek MT9900, 64-bit ARM `aarch64` via `Hisense_GetChipSetName()` and UA)
- **Region:** `AU` (`Hisense_GetRegion()` = `EM_C`, `Hisense_GetCountryCode()` = `AUS`, SSDP `region=0`)
- **VIDAA OS:** `U06.29` (via `Hisense_GetOSVersion()`)
- **Transport Protocol:** `3160`
- **Browser:** `Chrome/88.0.4324.182` (`Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36`), launched as `TV Browser` (`appId: "16"`, `storeType: 100`, `url: "url16"`)
- **Reported by:** [@MewX](https://github.com/MewX)

> **Applies to the `65U8HAU` (`65E83GAVT`) running `V0000.06.29X.P0813` (`transport_protocol=3160`).**
> See [EVIDENCE.md](EVIDENCE.md) for the measured claim ledger and [MODDING.md](MODDING.md) for the in-browser `WebSDK_*` / `Hisense_Get*` JS bridge surface and launcher details.

---

## Summary of Status & Outcomes

1. **Phase 0 — SSDP & Network Fingerprint (`CONFIRMED live`):**
   - UPnP/DLNA `MediaRenderer` descriptor responds on `:18400/MediaServer/rendererdevicedesc.xml`.
   - `modelDescription` reports `transport_protocol=3160`, `region=0`, `platform=1`, `voice=2`, `brand=his`, `vidaa_support=1`, plus `mac`, `macWifi`, and `macEthernet` (12 lowercase hex chars without colons).
   - RemoteNow MQTT over TLS is open on TCP `36669`.
2. **Phase 1 — RemoteNow MQTT Pairing & Control (`CONFIRMED live`):**
   - Client certificate extracted from `res/El.p12` (2565 bytes) inside `com.universal.remote.multi` v1.09.05.001.0 (`CN=VidaaAppAndroidV01`, valid 2024–2034). No APK modification, re-signing, or phone installation is needed — `res/El.p12` is read directly from the APK ZIP archive.
   - **MAC format requirement:** Passing the unformatted 12-hex-character `macWifi` from SSDP is rejected at MQTT `CONNECT` with **`rc=133` (Client Identifier not valid)**. Formatting `TV_MAC` as uppercase colon-separated (`XX:XX:XX:XX:XX:XX`) is required.
   - **Profile selection:** With `TV_MAC="XX:XX:XX:XX:XX:XX"`, `modern` and `middle` profiles fail with `rc=135` (*Not authorized*), whereas the **`standard`** profile (`his$<ts>` + `STANDARD_SALT`) connects cleanly with **`rc=0`**.
   - **Token issuance & post-pairing actions:** Submitting the 4-digit PIN to `ui_service/actions/authenticationcode` returns `{"result": 1, "info": ""}`, and `platform_service/data/tokenissuance` issues a 2-day `accesstoken` and 30-day `refreshtoken`.
   - **Why prior `V0000.06.29X.P0813` reports saw "silent actions":** Actions (`gettvstate`, `sourcelist`, `applist`, `launchapp`) are ignored on the initial pairing connection (which logged in with the temporary dynamic pairing password). Reconnecting a fresh MQTT session with `username=_username` and `password=accesstoken` (as [`server/vidaa_server.py`](../../../../server/vidaa_server.py) does) unlocks full two-way MQTT responses:
     - `state`: live input/app state (`sourceswitch`, `app`)
     - `sourcelist`: 7 sources (`TV`, `VIDAA tv`, `HDMI1`–`HDMI4` with custom display names and `is_signal`/`has_signal` flags, `AV`)
     - `applist`: 45 installed apps (`storeType` integer `98`/`99`/`100`, including `appId: "16"` `TV Browser`)
     - `launchapp`: verified launching `TV Browser` remotely over MQTT without a physical browser shortcut on the remote.
3. **Phase 2 — In-Browser Hardware Identity & JS Bridge Surface (`CONFIRMED live`):**
   - Opening `http://<server>:8765/` in `TV Browser` renders the 1080p HiDPI canvas launcher and connects to `/ws`.
   - In-browser `Hisense_Get*` calls confirm:
     - `Hisense_GetFirmWareVersion()`: `"V0000.06.29X.P0813"`
     - `Hisense_GetChipSetName()`: `"MTK9900"`
     - `Hisense_GetOSVersion()`: `"U06.29"`
     - `Hisense_GetModelName()`: `"65E83GAVT"`
     - `Hisense_GetRegion()`: `"EM_C"`
     - `Hisense_GetCountryCode()`: `"AUS"`
     - `Hisense_GetBrand()`: `"Hisense"`
   - **VIDAA U6 `WebSDK_*` bridge support added to `launcher/`:** [`launcher/index.html`](../../../../launcher/index.html), [`launcher/index-dom.html`](../../../../launcher/index-dom.html), [`launcher/recon.html`](../../../../launcher/recon.html), [`launcher/hookcheck.html`](../../../../launcher/hookcheck.html), and [`launcher/hookinstall.html`](../../../../launcher/hookinstall.html) now detect `WebSDK_createFileRequest` (`BRIDGE.websdk`) alongside `HiUtils_createRequest` (VIDAA U7/U9) and `Hisense_installApp` (legacy). On `V0000.06.29X.P0813` (`U06.29`), the browser exposes the **VIDAA U6 `WebSDK_*` + Opera OMI bridge** (`WebSDK_createFileRequest`, `WebSDK_createLibRequest`, `WebSDK_hiSecurity`, `WebSDK_hiSignVerify`, `WebSDK_getParam`, `WebSDK_setParam`, `opera_omi`, `omi_platform`, `Hisense_LoginWithVIDAA`, and 66 `Hisense_Get*` / `Hisense_Set*` functions — full list in [MODDING.md](MODDING.md)).

---

## Step-by-Step Walkthrough

### Step 1: Extract the 2024 Client Certificate from the APK

You do **not** need to decompile, recompile, re-sign, or install the APK on a phone. Android `.apk` files are standard ZIP archives, and `res/El.p12` (2565 bytes) inside `com.universal.remote.multi_1.09.05.001.0` can be extracted directly on Linux/WSL:

```sh
mkdir -p server/keys
unzip -p com.universal.remote.multi_1.09.05.001.0.apk res/El.p12 > server/keys/El.p12

# OpenSSL 3.x requires -legacy; OpenSSL 1.1.1 (e.g. Ubuntu 20.04) rejects -legacy and runs without it:
openssl pkcs12 -in server/keys/El.p12 \
  -passin pass:186e990688070325a1c4b0ce275d2388 \
  -clcerts -nokeys -out server/keys/vidaa_cert.pem
openssl pkcs12 -in server/keys/El.p12 \
  -passin pass:186e990688070325a1c4b0ce275d2388 \
  -nocerts -nodes -out server/keys/vidaa_key.pem

rm -f server/keys/El.p12
chmod 600 server/keys/vidaa_key.pem
```

Verify the subject matches `CN = VidaaAppAndroidV01`:

```sh
openssl x509 -in server/keys/vidaa_cert.pem -noout -subject -issuer -dates
```

### Step 2: Discover the TV via SSDP (`Phase 0`)

Send an SSDP `M-SEARCH` (`ST: ssdp:all`) to `239.255.255.250:1900` and fetch `http://<tv-ip>:18400/MediaServer/rendererdevicedesc.xml`:

```xml
<modelDescription>#CAP#
mac=<redacted>
macWifi=<redacted>
macEthernet=<redacted>
ip=<tv-ip>
region=0
transport_protocol=3160
platform=1
voice=2
brand=his
vidaa_support=1
</modelDescription>
```

### Step 3: Pair Over MQTT (`36669`) Using Colon-Formatted `TV_MAC` & `standard` Profile

[`server/pair.py`](../../../../server/pair.py) now automatically normalizes a 12-character SSDP `macWifi` into uppercase colon-separated format (`XX:XX:XX:XX:XX:XX`) when the broker returns `rc=133` (*Client Identifier not valid*):

```sh
TV_MAC="<macWifi>" ./server/venv/bin/python server/pair.py <tv-ip>
```

| `TV_MAC` Format | Profile | MQTT `CONNACK` (`paho-mqtt` v2) | Meaning |
| --- | --- | --- | --- |
| `xxxxxxxxxxxx` (no colons) | `modern` / `middle` / `standard` / `legacy` | `rc=133` | Client Identifier not valid (`pair.py` auto-retries with `XX:XX:XX:XX:XX:XX`) |
| `XX:XX:XX:XX:XX:XX` (uppercase + colons) | `modern` / `middle` / `legacy` | `rc=135` | Not authorized |
| `XX:XX:XX:XX:XX:XX` (uppercase + colons) | **`standard`** | **`rc=0`** | **Session established** |

### Step 4: Run `vidaa_server.py` and Open the TV Browser

Once `server/keys/tokens.json` is written:

```sh
./server/venv/bin/python server/vidaa_server.py <tv-ip> 8765
```

To open the built-in browser on the TV over MQTT (useful when no browser icon is pinned on the home screen), call the `/api/browser` endpoint added to [`server/vidaa_server.py`](../../../../server/vidaa_server.py):

```sh
curl "http://localhost:8765/api/browser"
```

Under the hood, `/api/browser` publishes `launchapp` with the `TV Browser` entry from `applist`:

```json
{
  "appId": "16",
  "name": "TV Browser",
  "url": "url16",
  "storeType": 100
}
```

---

## Practical Tips & Traps Learned During This Process

1. **The 30-second PIN dialog timeout vs. AI chat latency:**
   - On `V0000.06.29X.P0813`, the TV closes the 4-digit PIN popup after ~30 seconds and pushes `ui_service/data/authenticationcodeclose`. Any PIN submitted after that push fails with `{"result": 100, "info": "illegal authNum!!"}`.
   - Relaying the PIN through a multi-turn AI chat interface (~25–35 seconds round-trip) consistently loses the race against `authenticationcodeclose`.
   - **Solution:** Serve a minimal local HTML page on `http://localhost:8799/` with a **"1. Trigger PIN on TV"** button and a **"2. Submit PIN"** input box. Triggering and submitting directly from the browser completes in <5 seconds and succeeds on the first try.
2. **Repeated PIN code screen loop ("switching between code screen and browser continuously"):**
   - **Root cause 1 (uncompleted `vidaa_app_connect`):** If `vidaa_app_connect` (`{"connect_result": 0}`) is published a second time for an already-paired `client_id` without completing the new PIN, the TV's `ui_service` resets that `client_id` into an unauthenticated state even though MQTT `CONNECT` with `accesstoken` still succeeds (`rc=0`). Every subsequent `ui_service/actions/gettvstate` call then triggers `ui_service/data/authentication` and pops a new 4-digit code overlay on the TV.
   - **Root cause 2 (`watcher_loop` polling when disabled):** In [`server/vidaa_server.py`](../../../../server/vidaa_server.py), `watcher_loop()` previously polled `gettvstate` every 3 seconds and `sourcelist` every 9 seconds even when `"watcher": {"enabled": false}` in `server/config.json`. Combined with Root Cause 1, this popped a fresh PIN screen every 3 seconds and stole focus from `TV Browser`.
   - **Fix applied in [`server/vidaa_server.py`](../../../../server/vidaa_server.py):**
     Gated `watcher_loop()` polling behind `if w.get("enabled", True) and self.connected.is_set():` so no background `gettvstate` / `sourcelist` MQTT actions are sent while `watcher.enabled` is `false`.
   - **TRAP — Never send `authenticationcodeclose` without a validated PIN (`result: 1`), and never call `WebSDK_createFileRequest("fileWrite", ...)` from a non-`vidaahub.com` origin or with `mode: 6`:**
     - Publishing `ui_service/actions/authenticationcodeclose` to forcibly dismiss an unverified PIN popup hides the visual dialog on `V0000.06.29X.P0813` **without releasing the modal input grab in `hisenseUI`**, leaving the physical TV remote (D-pad / OK / Back) unresponsive until a power-cycle or dedicated system/app button press. Always let an unwanted PIN dialog time out naturally (~30s) or complete the 4-digit PIN.
     - Similarly, on `V0000.06.29X.P0813`, `http://localhost:9009/file/*` (`WebSDK_createFileRequest`) is served by the U6 UI service (`content-type: text/json\r\n`), enforces a server-side `vidaahub.com` `Origin` check, and only defines 4 mode bases (`0..3`, not `0..7`). Calling `WebSDK_createFileRequest("fileWrite", ...)` from a raw LAN IP origin or passing an unstringified object (`[object Object]`) / out-of-bounds `mode: 6` wedges the U6 UI/input handler after a few seconds and freezes the TV remote controller. [`fileBridgeCall()`](../../../../launcher/index.html) in [`launcher/index.html`](../../../../launcher/index.html) now skips `WebSDK_createFileRequest` whenever `location.hostname` does not contain `vidaahub.com`.
3. **Reference-TV `server/config.json` defaults (`DOOM` shortcut & `only` filter):**
   - The repository's default [`server/config.json`](../../../../server/config.json) ships with an `"only"` filter for the reference TV and a `"DOOM"` shortcut pointing to `http://127.0.0.1:8770/doom` (which only exists on a rooted TV running the on-TV Go bridge).
   - Further, `launcher/index.html` caches the first `hello` payload in `localStorage` (`alvidaa_cache_v1`). After removing the `DOOM` shortcut and `"only"` filter in `server/config.json`, refresh the page in `TV Browser` so the live WebSocket `hello` overwrites `localStorage`.
4. **Always reconnect with `accesstoken` after `tokenissuance`:**
   - Do not reuse the pairing MQTT connection to test `gettvstate`, `sourcelist`, or `applist`. Disconnect after receiving `tokenissuance` and reconnect using `username=_username` and `password=accesstoken`.
5. **Topic subscription quirk on `transport_protocol=3160`:**
   - Subscribing to `/remoteapp/mobile/<client_id>/platform_service/data/gettoken` returns `ReasonCode(Suback, 'Unspecified error')`, whereas `/remoteapp/mobile/<client_id>/platform_service/data/tokenissuance` returns `Granted QoS 0` and delivers the tokens when `platform_service/<client_id>/data/gettoken` is published.
6. **WSL2 + Windows Host Networking Traps:**
   - **PowerShell `stdin` hang:** Invoking `powershell.exe` from WSL2 without `-NonInteractive` and `< /dev/null` can hang indefinitely waiting for `stdin` EOF.
   - **SSDP multicast routing:** WSL2 NAT (`172.24.x.x/20`) does not bridge multicast UDP (`239.255.255.250:1900`) to the physical Wi-Fi LAN. Bind `System.Net.Sockets.UdpClient` explicitly to the Windows host's LAN IP (`192.168.x.x`) via `powershell.exe -NoProfile -NonInteractive -Command '...' < /dev/null`, then fetch the resulting HTTP `Location` URL directly from WSL2.
   - **Exposing `vidaa_server.py` (`8765`) from WSL2 to the TV:** Forward port `8765` from Windows to the WSL2 IP and allow it in Windows Firewall:
     ```powershell
     netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8765 connectaddress=<wsl-ip> connectport=8765
     New-NetFirewallRule -DisplayName "alvidaa WSL 8765" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765
     ```
7. **Python 3.8 Compatibility:**
   - `pathlib.Path.is_relative_to()` requires Python 3.9+. On Ubuntu 20.04 (Python 3.8), use `DOCS.resolve() in path.parents` (fixed in [`scripts/gen-exploits.py`](../../../../scripts/gen-exploits.py)), and avoid backslashes inside `{...}` expressions in f-strings (`SyntaxError` prior to Python 3.12).
