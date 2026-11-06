# 75U8QTUK (UK) — V0000.09.60I.Q0813 — VIDAA U9 on MTK9655

**Status:** fingerprint captured (2026-11-06); the firmware string, SoC, kernel
architecture and browser class match the **100U7Q** record byte-for-byte, so
the 100U7Q root chain is expected to apply here. **Nothing on this unit has
been exercised yet beyond the fingerprint readout — launcher, pairing, bridge
and root are all UNVERIFIED until on-device probes land.** Do not treat this
page as a recipe; it's the lab notebook's cover sheet.

**Contributor:** [@kingpandacc](https://github.com/kingpandacc) (issue thread TBD).
**Region:** UK (`GBR`, language `en-GB`). The existing `V0000.09.60I.Q0813`
record is from an EU_A unit; the region delta is the first thing to re-check
on the MQTT pairing profile.

> **The chain this guide expects to apply is written up in full on the
> 100U7Q:** [`../../100U7Q/V0000.09.60I.Q0813/README.md`](../../100U7Q/V0000.09.60I.Q0813/README.md).
> Read that first. This page tracks only the deltas this specific unit shows,
> and which of the chain's four build-dependent prerequisites still need
> to be confirmed on this TV.

## Device fingerprint

| Field | Value | Source |
|---|---|---|
| Retail model | 75U8QTUK (75″ U8Q, UK SKU) | sticker + owner |
| Series / generation tag | U8Q | on-device `U8Q Browser Environment` page header |
| Firmware | **`V0000.09.60I.Q0813`** | About → *Software Version* (also returned by `Hisense_GetFirmWareVersion()` via the user's browser-env page) |
| Extended version | `X0001.W01.Y01.J01` | About |
| Minor version | `I.Q0813.9.06.00-a20260731p` | About — build tag `a2026-07-31p` |
| RC version | `ERF6H66V1.03` | About |
| SoC (vendor-reported) | **`MTK9655`** | `Hisense_GetChipSetName()` |
| Kernel | **aarch64** (Linux, 64-bit) | `navigator.platform = "Linux aarch64"` |
| Userland arch | expected **32-bit ARM** (`EM_ARM`) — matches 100U7Q build | inferred from identical firmware id; **unverified on this unit** |
| VIDAA OS | `U09.60` | firmware id class + `Q0813` tag |
| Browser | Chromium 111 "WebViewer/1.2.1" (odin class) | `navigator.userAgent` |
| UA string | `Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 WebViewer/1.2.1 Safari/537.36` | on-device readout |
| Language | `en-GB` | `navigator.language` |
| `secureContext` | `false` on the loaded page | expected — TV browser served the page over plain HTTP |
| `transport_protocol` (SSDP) | **pending** | SSDP descriptor XML not yet captured |
| Serial number / internal board code | owner-redacted / pending `Hisense_GetSerialType()` | |
| Netflix ESN, Device ID | owner-redacted (not committed) | PII; kept in private notes |

Nmap of the TV from the LAN (owner-run, 2026-11-06):

```
PORT       STATE     SERVICE     VERSION
80/tcp     filtered  http
443/tcp    filtered  https
8000/tcp   filtered  http-alt
8080/tcp   filtered  http-proxy
8770/tcp   filtered  apple-iphoto
9009/tcp   filtered  pichat
36669/tcp  open      ssl/unknown
```

Consistent with the expected VIDAA LAN posture (MQTT-over-TLS on **36669**
only; phoenix on `9009` is localhost-only). Dropbear on 8008 would appear here
*after* the root chain is armed and would be visible only until the next
reboot — not currently present, as expected before any work.

## Why we think the 100U7Q chain transplants

| Chain prerequisite | 100U7Q record | 75U8QTUK observation | State |
|---|---|---|---|
| **Same firmware build** (not just the same version string) | `V0000.09.60I.Q0813` on MT9655 | `V0000.09.60I.Q0813` on `MTK9655` | matches — strong |
| **aarch64 kernel + 32-bit ARM userland** | kernel `5.15.192`, ELF `EM_ARM` | aarch64 kernel confirmed (UA + `platform`); userland arch unverified | matches kernel; **confirm userland on-device** |
| **Chromium 111 webview** | Chromium 111 (odin) | Chrome/111 WebViewer/1.2.1 | matches |
| **Phoenix FaaS stack present** (`http://localhost:9009`, `wss://localhost:9888`) | yes | unverified; `9009` LAN-filtered as expected | **confirm via browser probe** |
| **`fetcher` FaaS at `/service/basic/fetcher` with empty permission block** | yes | unverified | **the whole chain hinges on this; probe first** |
| **`/var/run/superwatch_socket` reachable from app uid 314 (group 616)** | yes | unverified | **confirm with a `ls -l` via bridge if read works** |
| **`/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/functions/fetch/` writable by uid 314** | yes (write primitive) | unverified | **confirm before pushing** |

Three of the four build-dependent properties sit inside the firmware image and
are therefore inherited from the same build; the fourth (group membership of
the app uid) is governed by the same init boot path on the same SoC class.
Odds strongly favour drop-in applicability, but every one of them has to be
checked before the install step runs. That's the next session's work (see
[Next up](#next-up)).

## Deltas from 100U7Q that this unit will show

- **Region:** UK (`GBR`) vs EU_A. The `pair.py` credential profile cascade
  needs the same walk as a fresh TV; `remotenow` / `standard` / `modern` may
  fall differently. Language locale `en-GB` affects the on-screen pairing
  dialog text only.
- **Panel / SKU:** 75″ U8Q vs 100″ U7Q. HDMI count, panel driver, input list
  and the launcher tile layout differ. None of that touches the root chain.
- **Build-tag suffix:** the About screen shows the build id
  `I.Q0813.9.06.00-a20260731p`; the 100U7Q record did not note a Minor
  Version string explicitly, so this is new context, not a conflict.
- **Remote hardware:** `ERF6H66V1.03`. Different silicon can mean different
  `irkey` tables in RemoteNow — only relevant if we ever wire up IR replay.

## Safety / ground rules (restated)

Per [AGENTS.md](../../../../AGENTS.md):

- LAN-only, on the owner's own TV. No DRM circumvention. No OTA writes.
- Reversibility is the design law: the 100U7Q chain writes to `/APPS/pkgs`
  and installs a package; the uninstall path (`pkgmgr` opcode `83`) is in the
  parent guide. Nothing on `/` is touched (erofs, dm-verity enforcing).
- **One MQTT server per TV.** If the owner has another pairing session
  active, kill it before re-pairing from `server/pair.py`.
- Keys stay in `server/keys/`. The Device ID, Netflix ESN and serial seen in
  the owner's About screen are deliberately **not** committed; they're
  device-identifying.

## Next up

In order, per the AGENTS.md onboarding ladder:

1. **Capture the SSDP descriptor.** `curl http://<tv-ip>:49152/description.xml`
   (port may vary; discover via SSDP M-SEARCH or UPnP tools). Record the
   `transport_protocol=` field into this guide + `inventory.json`.
2. **Launcher lane.** `server/pair.py <tv-ip>`; confirm 4-digit PIN; verify
   actions (`state`, `sourcelist`, `applist`, `launchapp`) respond. If the
   `standard` credential profile fails CONNACK, walk the cascade like the
   65U7H work.
3. **Bridge recon.** Load `launcher/recon.html` via `/api/open?url=…`;
   capture Phoenix endpoint inventory (`9009`/`9888`) and the `fetcher`
   permission block — a non-empty block here stops the chain cold and needs
   its own writeup.
4. **Only then, root lane.** Apply the 100U7Q `postinst` path verbatim.
   Expected endpoint: key-only Dropbear on `0.0.0.0:8008`, no automatic
   boot persistence. Consider the 75UR9S `re_sshd`-via-serviceList
   boot-persistence adapter later; its payload is in-tree at
   `docs/models/75UR9S/V0000.09.60W.Q0624/source/re_sshd/`.

Each discovery, bug, trap, errno gets a dated note in
[`findings/`](findings/) the same hour it happens — AGENTS.md discipline rule.

## Open questions

- Does the UK SKU ship the same `fetcher` FaaS permission block the EU_A
  100U7Q had, or did a region-specific patch change it? (**the whole chain
  hangs on this answer**)
- Is the `/data` partition writable by the app uid on this unit? (Was not
  on the 100U7Q — if that changed on the UK build, it widens options.)
- `Hisense_GetCountryCode()` output — `GBR`? That decides the SSDP region
  digit used by the pairing cascade.

## References

- Parent chain: [100U7Q / V0000.09.60I.Q0813](../../100U7Q/V0000.09.60I.Q0813/README.md)
  (same build, verified root chain)
- Boot-persistence adapter idea: [75UR9S / V0000.09.60W.Q0624](../../75UR9S/V0000.09.60W.Q0624/README.md)
  (`re_sshd` serviceList autostart; different build letter, same SoC family)
- Method catalogue: [docs/research/EXPLOITS.md](../../../research/EXPLOITS.md)
- Project ground rules: [AGENTS.md](../../../../AGENTS.md)
