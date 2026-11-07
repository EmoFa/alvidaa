# 03 — Launcher-lane GET + full fingerprint sweep (2026-11-06)

Served `launcher/fingerprint-full.html` from the Mac mini
(`python3 http.server`, launcher/ dir only, `<server-ip>:8770`) and opened
it in the TV's **"TV Browser"** app (app id 16, from findings/02). The TV
webview loaded the page and ran the write-free sweep.

Two things proven at once:

1. **Launcher-lane GET path works** — an alvidaa page served off the Mac
   loads in the TV webview over plain HTTP. (This is the *delivery* path,
   not the self-installing launcher tile; that remains untested.)
2. **Full `Hisense_*` fingerprint** captured on-device.

Capture method: a local drop-in server received the page's `/api/recon`
POST and wrote it to `launcher/recon-captures/` (gitignored — the raw
file contains the Device ID). Figures below are transcribed with the
identifying token redacted.

## Probe posture (write-free confirmed)

The page did a GET on `localhost:9009` and a WS open/close on
`localhost:9888` only — **no `fetcher` command, no writes**.

## Phoenix FaaS — CONFIRMED present

```
GET  http://localhost:9009/   → 200
     {"ret":false,"msg":"service register failed","session":-1,"code":503,"sdkVersion":"1.5.0"}
WS   ws://localhost:9888       → open (then closed, no bytes)
```

Both phoenix channels are live on the TV. The `503 / "service register
failed"` is the expected rejection of an unregistered passive GET — it
proves the listener is there, which is what the chain needs. **This
promotes the single biggest "confirm via browser probe" prerequisite.**

## Identity (via `Hisense_*` bridge)

| Function | Value |
|---|---|
| `Hisense_GetFirmWareVersion` | `V0000.09.60I.Q0813` |
| `Hisense_GetChipSetName` | `MTK9655` |
| `Hisense_GetModelName` | **`75U85QEVS`** (full internal model) |
| `Hisense_GetSerialType` | `75U8QE` |
| `Hisense_GetOSVersion` | `U09.60` |
| `Hisense_GetApiVersion` | `3.0.1` |
| `Hisense_GetRegion` | **`EU_A`** |
| `Hisense_GetCountryCode` | **`GBR`** |
| `Hisense_GetBrand` | `Hisense` |
| `Hisense_GetFeatureCode` | `012003039003001256000126` (feature bitmap; shared, non-identifying) |
| `Hisense_GetCapabilityCode` | `2026010402` |
| `Hisense_GetPanelResolution` | `3840*2160` |
| `Hisense_GetDeviceID` | **`012003039003001256000126` + `<redacted 32-char per-device token>`** — DEVICE-IDENTIFYING, not committed |
| `Hisense_GetSN` / `GetMacAddress` / `GetWifiMacAddress` | absent on this build |
| `Hisense_GetUuid` | no return (DeviceInfo `uuid: null`) |

`Hisense_GetDeviceInfo` JSON (non-identifying fields):
`chipset MTK9655, software_version V0000.09.60I.Q0813, os_version VIDAA
U09.60, api_version 3.0.1, runtime_version Chromium 111, brand Hisense,
uuid null, region EU_A, capability_code 2026010402, feature_code
012003039003001256000126, model_name 75U85QEVS`.

`Hisense_GetNetworkInfo`: `net_type wireless, ip_address <tv-ip>`
(LAN IP — fine per AGENTS.md).

## Browser / platform

```
UA:        Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko)
           Chrome/111.0.0.0 WebNavigator/8.3.10 Safari/537.36
platform:  Linux aarch64        languages: en-GB,en-US
screen:    1920x1080  (devicePixelRatio 1.5; panel native 3840*2160)
hardwareConcurrency: 4           secureContext: false (plain HTTP)
```

The **TV Browser app** wraps the webview as `WebNavigator/8.3.10` — a
different wrapper string from the launcher webview's `WebViewer/1.2.1`
(findings/00). Same Chromium 111 core either way.

## WebSDK

All `WebSDK_*` probes returned absent and `websdk_fn_names` is empty — this
build exposes only the legacy `Hisense_*` bridge, no WebSDK layer.

## Readings that change the plan

- **Region is `EU_A`, not a UK-specific region.** The model README treated
  UK vs EU_A as the headline delta driving a fresh pairing-cascade walk.
  This unit reports `EU_A` internally (country `GBR`), i.e. the **same
  region class as the 100U7Q reference**. The delta largely collapses —
  and pairing already succeeded on profile `modern` anyway (findings/02).
- **Phoenix present** (above) — the chain's FaaS substrate exists here.
- Still **UNVERIFIED** and gating the root chain: the `fetcher` permission
  block, the superwatch socket, package-tree writability, and 32-bit ARM
  userland. None of those were probed — this page is write-free by design.
  They belong to `launcher/recon.html` (step 4), which **does** write.

## State change

- EVIDENCE: Phoenix FaaS row → CONFIRMED live; `GetCountryCode → GBR` row →
  CONFIRMED live; `transport_protocol` row → resolved (not in SSDP
  descriptor, see findings/01). New rows added for region `EU_A` and full
  model `75U85QEVS`.
- Model README prerequisite table: Phoenix row → confirmed; region
  open-question answered.
- No inventory capability flag changes (the launcher *tile* self-install is
  still untested; only the GET delivery path was exercised).

## Next

- `04-bridge-recon.md` — load `launcher/recon.html` (**writes start here**).
  Highest-information probe: `fetcher` permission block, superwatch socket,
  package-tree writability. If the `fetcher` block is non-empty on this
  build, STOP and write it up as a dead end.
