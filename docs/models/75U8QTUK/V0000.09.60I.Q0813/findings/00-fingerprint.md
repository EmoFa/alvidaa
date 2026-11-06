# 00 — Fingerprint (2026-11-06)

First visit to a 75″ U8Q (UK SKU). The owner read the About screen, ran an
on-device browser-env page that calls `Hisense_GetFirmWareVersion()` and
`Hisense_GetChipSetName()`, and scanned the TV from the LAN with nmap.
Device-identifying fields (Device ID, Netflix ESN, serial number) are kept
out of this notebook on purpose — the measurable, non-identifying evidence
is below.

## Settings → System → About

Transcribed verbatim from the About screen (owner photo, 2026-11-06):

```
Software Version: V0000.09.60I.Q0813
Extended Version: X0001.W01.Y01.J01
Minor Version:    I.Q0813.9.06.00-a20260731p
RC Version:       ERF6H66V1.03
Serial Number:    <redacted by owner>
Device ID:        <redacted — device-identifying, not committed>
Netflix ESN:      <redacted — device-identifying, not committed>
```

**Readings:**

- `V0000.09.60I.Q0813` is the inventory-canonical firmware string; this is
  the same build id already recorded on the EU_A 100U7Q.
- The Minor Version carries a build tag `-a20260731p` → build date
  **2026-07-31** (the `p` suffix matches other U9.60-era builds in this
  repo).
- `ERF6H66V1.03` is the bundled remote firmware; it differs from the
  100U7Q (which did not record one) and from the 55A7KAU remote. Only
  relevant if IR replay ever comes up.

## On-device browser-env readout

The owner ran a small HTML page that `JSON.stringify`s a handful of
browser-globals and the two canonical Hisense_* identity functions. The
page is not committed; its output was photographed and transcribed:

```json
{
  "userAgent": "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 WebViewer/1.2.1 Safari/537.36",
  "platform": "Linux aarch64",
  "language": "en-GB",
  "secureContext": false,
  "firmware": "V0000.09.60I.Q0813",
  "chipset": "MTK9655"
}
```

**Readings:**

- `Chrome/111.0.0.0 WebViewer/1.2.1` ties the webview to the Chromium 111
  "odin" family that the 100U7Q, 75UR9S and 43Q60SEVS guides describe.
- `Linux aarch64` confirms a 64-bit kernel on an MTK9655. Userland arch
  (32-bit ARM, per 100U7Q) is **not** yet confirmed on this unit — needs a
  file-bridge read of `/system/bin/ls` or similar once the bridge primitive
  is live.
- `secureContext: false` is expected — the page loaded over plain HTTP
  (the launcher server does not serve HTTPS; the TV browser treats HTTPS
  only as a secure context).
- `en-GB` locale matches the UK SKU designation.

## Nmap, from the LAN

Owner-run against the TV's LAN address (ICMP disabled per VIDAA default,
so `-Pn` likely used):

```
Host is up (0.0078s latency).

PORT       STATE     SERVICE     VERSION
80/tcp     filtered  http
443/tcp    filtered  https
8000/tcp   filtered  http-alt
8080/tcp   filtered  http-proxy
8770/tcp   filtered  apple-iphoto
9009/tcp   filtered  pichat
36669/tcp  open      ssl/unknown
```

**Readings:**

- `36669/tcp open ssl/unknown` — the VIDAA RemoteNow MQTT-over-TLS
  endpoint, as expected on any 2024+ Hisense. Pairing path lives here.
- `9009/tcp filtered` — consistent with phoenix being localhost-only (it
  would show filtered or closed from the LAN side even though it's
  listening on the TV). Not evidence of absence.
- `80, 443, 8000, 8080, 8770` all filtered — no accidental listeners,
  clean posture. Dropbear on 8008 is not listening (expected — we haven't
  armed anything yet).

## What this unlocks and what it does not

**Unlocks:**

- Scaffolded guide + inventory row (this commit).
- Decision made: this is the same build as the 100U7Q row; the chain is
  expected to transplant. See [README](../README.md) for the four
  build-dependent prerequisites still to confirm.

**Does not unlock:**

- Nothing has been written to the TV. No pairing. No bridge probe. No
  package write. No SSH. The guide marks all of those UNVERIFIED and they
  stay that way until a later findings note records a live observation.

## Next findings entries expected

- `01-ssdp-descriptor.md` — `transport_protocol=`, device UUID, UPnP
  service list.
- `02-pairing.md` — `pair.py` CONNACK walk, chosen credential profile,
  token issuance.
- `03-launcher-lane.md` — launcher UI load, tile install, verify.
- `04-bridge-recon.md` — `recon.html` output: phoenix endpoint inventory,
  `fetcher` permission block, superwatch socket readability, package tree
  writability.
- `05-root-arm.md` — only after 01–04 are green; the actual postinst run.
