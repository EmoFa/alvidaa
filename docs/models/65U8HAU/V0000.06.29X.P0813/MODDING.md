# 65U8HAU V0000.06.29X.P0813 — modding & launcher notes

## In-Browser Fingerprint & JS Bridge Surface

Captured via read-only inspection (`POST /api/probe`) when opening `http://<server>:8765/` in `TV Browser`:

### 1. User-Agent & `WebSDK_getParam("deviceInfo")`

- **`navigator.userAgent`:**
  ```text
  Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36
  ```
- **`GET http://localhost:9009/tvapi/initialData` (`WebSDK_getParam("deviceInfo")`):**
  ```json
  {
    "4kState": true,
    "CCModeStatus": 0,
    "IPAddress": "<tv-ip>",
    "adTargetEnable": 0,
    "adsID": "<redacted>",
    "avsPlayerInfo": false,
    "blockEndTime": 0,
    "blockStartTime": 0,
    "blockTimeWeekly": "sun,mon,tue,wed,thu,fri,sat",
    "capabilityCode": "2023031403",
    "chipsetName": "MTK9900",
    "countryID": "AUS",
    "customerID": "2",
    "debugLevelForHisenseUI": 1,
    "deviceID": "<redacted>",
    "eulaAdEnable": -1,
    "featureCode": "861003009000007000000733",
    "isContrastMenu": false,
    "isHotelMode": 0,
    "languageID": "chi",
    "localeLanguage": "chi",
    "modelName": "65E83GAVT",
    "netStatus": true,
    "netType": "wireless",
    "oemManuFacture": 0,
    "osVersion": "U06.29",
    "panelResolution": "3840*2160",
    "parentalControlEnabled": 0,
    "pictureMode": 1,
    "playerFeatureInfo": "006001000.VD9900O_GL",
    "region": "EM_C",
    "resolution": "0,0,0,0",
    "roleID": "-1",
    "schemeMenu": 0,
    "serialType": "65U8H",
    "softwareVersion": "V0000.06.29X.P0813",
    "soundMute": 0,
    "soundVolume": 4,
    "supportDolbyAtmos": true,
    "supportHDR": "HDR10",
    "supportHdrAndDolbyVision": "HDR10+HLG+HDR10Plus+DolbyVision",
    "timeZone": 36000,
    "transparecyMenu": 1,
    "ttsEnable": 0,
    "ttsLanguage": "eng",
    "ttsPitch": 30,
    "ttsRate": 2,
    "ttsVolume": 50,
    "tvBrand": "Hisense",
    "tvLogo": "his",
    "uuid": "<redacted>",
    "versionStatus": "release",
    "volumeBarMode": 0,
    "volumeBarVisible": 0,
    "volumeType": 0,
    "wolEnable": 1,
    "wowEnable": 1
  }
  ```

### 2. VIDAA U6 vs. VIDAA U9 JS Bridge Architecture (`localhost:9009`)

Unlike VIDAA U7/U9 (`09.x`) where `HiUtils_createRequest(action, params)` posts `{"api": "<name>", "args": {...}}` to `http://localhost:9009/service/hiutils`, `V0000.06.29X.P0813` (`U06.29`) exposes 10 `WebSDK_*` functions backed by `r = "http://localhost:9009"` and two internal XHR helpers (`a(e, t)` synchronous, `f(e, t)` asynchronous):

```javascript
// Internal helpers captured via Function.prototype.toString + nonStrictOpen.caller:
function a(e, t) {
  var n = new XMLHttpRequest;
  return n.open("POST", e, !1),
    n.send(t),
    n.status === 200
      ? typeof n.responseText == "string" ? n.responseText : !0
      : (console.log("HTTP ERROR CODE: " + n.status), !1);
}
function f(e, t) {
  var n = new XMLHttpRequest;
  return n.open("POST", e, !0), n.send(t), !0;
}

// Exported WebSDK_* shims on window:
WebSDK_createFileRequest = function(e, t) { var n = r + "/file/" + e; return a(n, t); };
WebSDK_createLibRequest  = function(e, t) { var n = r + "/lib/" + e, i = f(n, t); return i; };
WebSDK_getParam          = function(e) {
  if (e == "deviceInfo") return o;
  if (!o.hasOwnProperty(e)) {
    var t = new XMLHttpRequest, n = r + "/tvapi/initialData";
    t.open("GET", n, !1), t.send(null);
    if (t.status !== 200) return "null";
    p(t.responseText);
  }
  return o[e];
};
WebSDK_setParam          = function(e, t) { var n = r + "/tvapi/" + e, i = f(n, t); return i; };
WebSDK_getCurrentParam   = function(e, t) { var n = r + "/tvapi/" + e, i = a(n, t); return i; };
WebSDK_writeTvRunLog     = function(e, t) { var n = r + "/logReport/" + e, i = f(n, t); return i; };
WebSDK_hiSignVerify      = function(e, t) { var n = r + "/signVerify/" + e, i = a(n, t); return i; };
WebSDK_hiSecurity        = function(e, t) { var n = r + "/hiSecurity/" + e, i = a(n, t); return i; };
```

| Capability | VIDAA U9 (`09.x`) Route | VIDAA U6 (`06.29X`) Route | Behavior on `65U8HAU` (`V0000.06.29X.P0813`) |
| --- | --- | --- | --- |
| Device info cache | `POST /service/tvinfo` | `GET /tvapi/initialData` | Returns `200 OK` JSON from any page origin |
| Dynamic TV param (`deviceCode`) | `POST /service/hiutils` (`deviceCode`) | `POST /tvapi/deviceCode` | Returns `200 OK` with the unmasked 6-digit `deviceCode` from any page origin |
| File read/write | `POST /service/hiutils` (`fileRead` / `fileWrite`) | `POST /file/fileRead`, `POST /file/fileWrite` | Requires `t` as a JSON string (`JSON.stringify(...)`); `localhost:9009/file/*` enforces a server-side `vidaahub.com` HTTP `Origin`/`Referer` check and returns `200 OK` (`content-type: text/json`) with empty body `""` when called from a raw LAN IP origin |
| Library / log / sign / security | `POST /service/hiutils` | `POST /lib/<e>`, `/logReport/<e>`, `/signVerify/<e>`, `/hiSecurity/<e>` | Present on `localhost:9009` |
| OMI platform messaging | `HiUtils_sendPlatformMessage` | `opera_omi.sendPlatformMessage` / `omi_platform.sendPlatformMessage` | Used by `Hisense_LoginWithVIDAA` (`{"type":"APPMessage","MsgType":"LoginWithVidaa"}`) |

Because `http://localhost:9009/file/fileWrite` returns `""` when the launcher is opened via a raw LAN IP (`Origin: http://<lan-ip>:8765`) — and calling `/file/fileWrite` from a raw IP or with `[object Object]` / out-of-bounds `mode: 6` wedges the U6 UI input handler and freezes the physical TV remote — [`fileBridgeCall()`](../../../../launcher/index.html) in [`launcher/index.html`](../../../../launcher/index.html) skips `WebSDK_createFileRequest` unless `location.hostname` contains `vidaahub.com` and instead uses the server-side install fallback (`{"t": "install", "url": APP_URL}` over WebSocket) in [`server/vidaa_server.py`](../../../../server/vidaa_server.py), which registers `"installed": true` and `"launcherUrl"` in `server/config.json`.

---

## MQTT `applist` and `sourcelist` Schema on `V0000.06.29X.P0813`

Unlike newer `09.x` firmware where custom apps carry string `storeType: "custom"`, stock entries in `applist` on `V0000.06.29X.P0813` use integer `storeType` values (`98`, `99`, `100`) and symbolic `url` identifiers (`"url<appId>"`):

```json
{
  "url": "url16",
  "isunInstalled": false,
  "name": "TV Browser",
  "from": "",
  "storeType": 100,
  "appId": "16",
  "move": true,
  "isFav": false,
  "httpIcon": "data:image/png;base64,iconDownloadhttps://img.vidaahub.com/vidaa/2023/11/202311210704287492.png"
}
```

### Launching the TV Browser Over MQTT

When the TV remote or home screen does not expose a direct web browser shortcut, call `GET /api/browser` on [`server/vidaa_server.py`](../../../../server/vidaa_server.py) or publish to `/remoteapp/tv/ui_service/<client_id>/actions/launchapp`:

```json
{
  "appId": "16",
  "name": "TV Browser",
  "url": "url16",
  "storeType": 100
}
```

The TV transitions to:

```json
{
  "statetype": "app",
  "name": "tv browser",
  "url": "browser"
}
```

### Input Sources (`sourcelist`)

`sourcelist` returns 7 entries (`TV`, `284` / `VIDAA tv`, `HDMI1`–`HDMI4`, `AVS`), preserving user-configured input labels in `displayname` (e.g., `NS`, `XBox`, `PS5`, `CrCast`) and string `"0"`/`"1"` flags in both `is_signal` and `has_signal`.

---

### 4. LAN TCP Port Filter & DevTools Surface

A read-only TCP `connect_ex` probe (`timeout=1.5s`) against the TV's LAN IP distinguishes between ports dropped by the TV's packet filter (`errno=11` / timeout) and ports allowed through the filter with no active listener (`errno=111` / `ECONNREFUSED`):

| TCP Port | Purpose | Observed Result | Meaning |
| --- | --- | --- | --- |
| `36669` | RemoteNow MQTT over TLS | **`OPEN` (`rc=0`)** | Active MQTT broker |
| `18400` | UPnP / DLNA `MediaRenderer` HTTP | **`OPEN` (`rc=0`)** | Active SSDP descriptor server |
| `9226` | Browser DevTools target port (`setDebugPort`) | **`closed (errno=111, ECONNREFUSED)`** | **Allowed through packet filter** (immediate TCP `RST`), no listener bound by default |
| `9222`–`9224` | Legacy / UI DevTools ports | `closed (errno=11, timeout)` | Dropped by TV packet filter |
| `2222`, `2323`, `8008` | Custom SSH / telnet ports | `closed (errno=11, timeout)` | Dropped by TV packet filter |

