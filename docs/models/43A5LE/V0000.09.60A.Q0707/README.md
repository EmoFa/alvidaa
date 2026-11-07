# 43A5LE (internal 43A60LEVS_0002) — V0000.09.60A.Q0707

- **Model:** `43A5LE` (`Hisense_GetSerialType()`); internal
  `Hisense_GetModelName()` = `43A60LEVS_0002`
- **Firmware:** `V0000.09.60A.Q0707` (build 2026-07-07; AirPlay `fv`
  `p20.09.6010.260707`)
- **SoC:** `MTK9603` (`Hisense_GetChipSetName()`)
- **Region:** `EU_A` (`Hisense_GetRegion()`), country `ITA`
  (`Hisense_GetCountryCode()`)
- **VIDAA OS:** `U09.60`
- **Browser:** Chromium 111, `armv7l`, UA
  `Mozilla/5.0 (X11; Linux armv7l) AppleWebKit/537.36 (KHTML, like Gecko)
  Chrome/111.0.0.0 SurfMaster/3.0.1 Safari/537.36`; 1920×1080 @ DPR 1.5
- **`transport_protocol`:** not measured — SSDP multicast did not reach this
  host on the test LAN; only TCP 36669 (MQTT) and 7000 (AirPlay) answered
- **Reported by:** owner (this session), 2026-11-06

**Status:** launcher lane verified end-to-end on an external server
(pairing → page → WebSocket → home-watcher bounce). Native `Appinfo.json`
self-install is **closed** by the per-app permission gate. Root was **not
attempted**.

> This guide is for the exact model **and** firmware above. The MTK9603 /
> 09.60 family is shared with the
> [43Q60SEVS guide](../../43Q60SEVS/V0000.09.60W.Q0612/README.md), but the
> firmware strings differ and its root chain was not tested here.

## Pairing — working

The 2024 client certificate is required. It is inside the official
`com.universal.remote.multi` APK as `res/El.p12` (2565 bytes,
`CN=VidaaAppAndroidV01`, valid 2024–2034), keystore password
`186e990688070325a1c4b0ce275d2388`:

```sh
unzip -p com.universal.remote.multi_1.09.05.001.0.apk res/El.p12 > El.p12
openssl pkcs12 -legacy -in El.p12 -passin pass:186e990688070325a1c4b0ce275d2388 \
  -clcerts -nokeys -out server/keys/vidaa_cert.pem
openssl pkcs12 -legacy -in El.p12 -passin pass:186e990688070325a1c4b0ce275d2388 \
  -nocerts -nodes -out server/keys/vidaa_key.pem
```

Measured on this unit:

| `TV_MAC` form | Profile | MQTT result |
| --- | --- | --- |
| `XX:XX:XX:XX:XX:XX` (uppercase, colons) | `modern` | **rc 0** |
| 12 lowercase hex chars, no colons | `modern` | rc 135 (not authorized) |
| `XX:XX:XX:XX:XX:XX` | `middle` / `standard` | rc 135 |

The PIN dialog appears once `vidaa_app_connect` is published. Submit the PIN
once; re-triggering rotates it. On success the TV returns
`authenticationcode {"result": 1}` and issues `tokenissuance` with a 2-day
access token and 30-day refresh token. Reconnecting with the issued token
enables two-way actions: `state`, `gettvstate`, `applist`, `sourcelist`, and
`launchapp` all answered on this build.

**Certificate sourcing trap:** the older `1.08.02.007.0` APK ships
`res/raw/remoteclientmobile.p12` / `res/raw/remoteclientoem.p12` instead;
the documented keystore passphrase did not open either (MAC verify error).
Use a build that ships `res/El.p12` (confirmed with `1.09.05.001.0`).

## Launcher — working, but not installable

The [server](../../../launcher/DEPLOY.md) serves the page, `/ws`, and the icon
proxy. On the TV the page renders, connects, and receives live state.

### The install gate

`HiUtils_createRequest` is present; `Hisense_installApp` and
`WebSDK_createFileRequest` are **absent**. Writing the TV's app registry is
rejected:

```
fileWrite websdk/Appinfo.json mode 6
-> {"ret":false, "code":503,
    "msg":"client request permission check error, please check appconfig",
    "sdkVersion":"1.5.0"}
```

`fileRead` on the same path works and returned the 4314-byte registry with
four entries, unchanged after the failed write. This is the same per-app
identity gate reported on [43Q60SEVS / 09.60W](../../43Q60SEVS/V0000.09.60W.Q0612/README.md)
and on the 09.60V 55A60LEVS report. **Do not expect INSTALL AS APP to
persist a tile on this firmware without root.** The launcher's file-bridge
fallback and the server-side registration keep working; the tile itself is
never created.

### The launch shape that works

A custom `appId` (`vidaa-recon`, `vidaa-home`) is silently ignored on this
build. The built-in Browser entry launches and honours an overridden URL:

```json
{"appId":"16","name":"Browser","url":"http://<server>:8770/",
 "urlType":"1","storeType":100}
```

Published to
`/remoteapp/tv/ui_service/<client_id>/actions/launchapp`.

The home watcher then works as in Lane 1: when VIDAA reports
`statetype == remote_launcher`, the server relaunches the Browser at the
launcher URL. The ~1–2 s stock-home flash is inherent to this lane. The
watcher needs the server to stay up and the TV to reach it — on this host
`firewalld` blocked TCP 8770 until it was opened explicitly.

## Reversibility

Nothing was written to the TV: the registry write returned 503 and the file
was unchanged on read-back. The only local state is the server's
`server/keys/launcher.json` plus the paired tokens.

Teardown:

1. Stop the server (and any second instance — one MQTT session per identity).
2. `sudo firewall-cmd --remove-port=8770/tcp` if the port was opened only for
   this test.
3. `rm -rf server/keys server/venv` (keys and tokens are device credentials).
4. Press **HOME** on the TV. No TV file or app entry needs restoring.

The paired credential is ephemeral (2-day access / 30-day refresh). If the
TV exposes a paired-mobile-device list, remove the entry there for a
zero-trace cleanup.

## Not tested

- `file_bridge_traversal` (`../` beyond the mode base)
- `euladpp_untar` and `devtools_forge`
- root — the sibling 09.60 MTK9603 guides use the FaaS fetcher /
  superwatch-install surface, **not** the browser `fileWrite` that is gated
  here. That is a hypothesis for another session, not a result on this unit.

Field definitions: [TESTED-MODELS.md](../../../research/TESTED-MODELS.md).
Inventory row: [`V0000.09.60A.Q0707`](../../../research/inventory.json).
