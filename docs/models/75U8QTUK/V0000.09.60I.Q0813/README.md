# 75U8QTUK (UK) — V0000.09.60I.Q0813 — VIDAA U9 on MTK9655

**Status (2026-11-06):** fingerprint captured; pairing confirmed (Sidee,
profile `modern`); launcher GET-delivery confirmed; Phoenix FaaS confirmed
present. **Root chain is a DEAD END on this build** — bridge recon
(findings/04) showed the `fetcher` rejects every file read with
`invalid path`, so the 100U7Q traversal/write primitive the chain hinges on
does **not** transplant. The chain was halted at step 4 per the stop
condition; no `postinst`/root step was attempted and nothing persisted on
the TV. Same firmware *version string* as the 100U7Q, but a path-validating
fetcher, so the "byte-for-byte identical build" assumption does not hold for
the fetcher surface here. Do not treat this page as a recipe; it's the lab
notebook's cover sheet.

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
| `transport_protocol` (SSDP) | **not exposed** | TV `dd.xml` on :3366 is a 417-byte stub, no such field (findings/01) |
| Region (`Hisense_GetRegion`) | **`EU_A`** | on-TV probe — same region class as 100U7Q, not UK-specific (findings/03) |
| Country (`Hisense_GetCountryCode`) | **`GBR`** | on-TV probe (findings/03) |
| Full model (`Hisense_GetModelName`) | **`75U85QEVS`** | on-TV probe; `GetSerialType`=`75U8QE`, sticker `75U8QTUK` (findings/03) |
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
| **Phoenix FaaS stack present** (`http://localhost:9009`, `wss://localhost:9888`) | yes | **confirmed** — `9009` GET→200 (`sdkVersion 1.5.0`), `9888` WS opens (findings/03) | **CONFIRMED live** |
| **`fetcher` file read/traversal primitive** (the whole chain hinges on this) | yes | **BLOCKED** — fetcher returns `invalid path` for all reads incl. `../` (findings/04) | **FAILED — chain dead-ends here** |
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

In order, per the AGENTS.md onboarding ladder. Two helpers landed on the
same branch to make step 1 one command each:

1. **Capture the SSDP descriptor.** Pi-side:
   `tools/ssdp-descriptor.sh` (auto-discover) or
   `tools/ssdp-descriptor.sh <tv-ip>` (direct). Read-only — UDP M-SEARCH
   + HTTP GET. Record `transport_protocol=`, `UDN`, `modelName` into the
   inventory row and [`findings/01-ssdp.md`](findings/). Expect
   `transport_protocol ≥ 3290` on this U09.60 build (3290+ selects the
   2024 app-style pairing path in `pair.py`).
2. **Load the full fingerprint page on the TV.** From the TV browser app,
   open `http://<pi>:8770/fingerprint-full.html` (also reachable via
   `/api/open?url=…` once the server is up). Read-only — every probe is
   a passive connection test: sweeps every `Hisense_*` and `WebSDK_*`
   function on `window`, dumps `navigator`/`screen`/`location`, and
   checks `http://localhost:9009/` + `wss://localhost:9888` *without*
   sending any fetcher command. Screenshot the JSON and the page
   auto-POSTs to `/api/recon` if the server is running.
3. **Launcher lane.** `server/pair.py <tv-ip>` (set `HISENSE_HOST` or
   pass the IP); confirm the 4-digit PIN; verify actions (`state`,
   `sourcelist`, `applist`, `launchapp`) respond. If the `standard`
   credential profile fails CONNACK, walk the cascade like the 65U7H
   work. Country code from step 2 decides which profile to try first.
4. **Bridge recon with writes.** ✅ Done 2026-11-06 (findings/04) —
   `recon.html` loaded in the TV Browser app. **Result: the fetcher
   rejects every file read with `invalid path`; the traversal/write
   primitive is unavailable on this build.** Chain halted here per the
   stop condition. Nothing persisted.
5. **Root lane.** ❌ **Not attempted — chain dead-ended at step 4.** The
   100U7Q `postinst` path presupposes the fetcher file bridge, which this
   build does not provide. Root here would require a *different* primitive
   (new research, not a transplant). If revisited, first explicitly
   register a phoenix session before re-probing the fetcher (findings/04
   caveat) to rule out a registration issue before declaring the primitive
   permanently patched.

Each discovery, bug, trap, errno gets a dated note in
[`findings/`](findings/) the same hour it happens — AGENTS.md discipline rule.

## Open questions

- Does the UK SKU ship the same `fetcher` FaaS permission block the EU_A
  100U7Q had, or did a region-specific patch change it? (**the whole chain
  hangs on this answer**)
- Is the `/data` partition writable by the app uid on this unit? (Was not
  on the 100U7Q — if that changed on the UK build, it widens options.)
- ~~`Hisense_GetCountryCode()` output — `GBR`?~~ **Resolved (findings/03):**
  `GBR`, region `EU_A`. The SSDP descriptor carries no `transport_protocol`
  digit on this build (findings/01), and Sidee already paired on profile
  `modern`, so the cascade this would have steered is moot.

## References

- Parent chain: [100U7Q / V0000.09.60I.Q0813](../../100U7Q/V0000.09.60I.Q0813/README.md)
  (same build, verified root chain)
- Boot-persistence adapter idea: [75UR9S / V0000.09.60W.Q0624](../../75UR9S/V0000.09.60W.Q0624/README.md)
  (`re_sshd` serviceList autostart; different build letter, same SoC family)
- Method catalogue: [docs/research/EXPLOITS.md](../../../research/EXPLOITS.md)
- Project ground rules: [AGENTS.md](../../../../AGENTS.md)
