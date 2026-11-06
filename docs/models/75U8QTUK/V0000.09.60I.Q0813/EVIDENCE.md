# 75U8QTUK V0000.09.60I.Q0813 — evidence ledger

Label grammar is defined in [`docs/models/README.md`](../../README.md#how-to-read-the-labels).
Nothing on this page is a recipe; every row is a labelled claim with its
basis. UNVERIFIED rows are left in so future sessions can see what still
needs confirming on this specific TV.

| Claim | Label | Evidence | Source |
|---|---|---|---|
| Retail model is **75U8QTUK** (75″ U8Q, UK SKU) | owner-verified | owner states the model; back-sticker not photographed in-repo | owner, 2026-11-06 |
| Firmware id is **`V0000.09.60I.Q0813`** | CONFIRMED live (recorded) 2026-11-06 | About screen; on-device browser-env page echoing `Hisense_GetFirmWareVersion()` returns the same string | [`findings/00-fingerprint.md`](findings/00-fingerprint.md) |
| Extended Version is `X0001.W01.Y01.J01` | CONFIRMED live (recorded) 2026-11-06 | About screen | [`findings/00-fingerprint.md`](findings/00-fingerprint.md) |
| Minor Version is `I.Q0813.9.06.00-a20260731p` (build tag → 2026-07-31) | CONFIRMED live (recorded) 2026-11-06 | About screen | [`findings/00-fingerprint.md`](findings/00-fingerprint.md) |
| RC Version is `ERF6H66V1.03` | CONFIRMED live (recorded) 2026-11-06 | About screen | [`findings/00-fingerprint.md`](findings/00-fingerprint.md) |
| SoC vendor-reports as **`MTK9655`** | CONFIRMED live (recorded) 2026-11-06 | `Hisense_GetChipSetName()` return in the owner's browser-env JSON | [`findings/00-fingerprint.md`](findings/00-fingerprint.md) |
| Kernel is **aarch64** (Linux, 64-bit) | CONFIRMED live (recorded) 2026-11-06 | `navigator.platform = "Linux aarch64"`; UA `X11; Linux aarch64` | [`findings/00-fingerprint.md`](findings/00-fingerprint.md) |
| Webview is Chromium 111 "WebViewer/1.2.1" (odin class) | CONFIRMED live (recorded) 2026-11-06 | `navigator.userAgent` | [`findings/00-fingerprint.md`](findings/00-fingerprint.md) |
| Language is `en-GB` (UK locale) | CONFIRMED live (recorded) 2026-11-06 | `navigator.language` | [`findings/00-fingerprint.md`](findings/00-fingerprint.md) |
| LAN posture: TCP 36669 open (MQTT/TLS); 80, 443, 8000, 8080, 8770, 9009 filtered | CONFIRMED live (recorded) 2026-11-06 | owner-run `nmap` output | [`findings/00-fingerprint.md`](findings/00-fingerprint.md) |
| Userland is 32-bit ARM (`EM_ARM`) | UNVERIFIED (inferred) | matches 100U7Q record on the identical firmware id; needs on-device confirm (file bridge read of `/system/bin/ls` or `file`-equivalent) | inferred; [100U7Q EVIDENCE](../../100U7Q/V0000.09.60I.Q0813/EVIDENCE.md) |
| Phoenix FaaS stack present (`http://localhost:9009`, `wss://localhost:9888`) | CONFIRMED live (recorded) 2026-11-06 | on-TV browser probe: `GET localhost:9009` → 200 `{…"sdkVersion":"1.5.0","code":503,"msg":"service register failed"}` (listener present; 503 = expected rejection of an unregistered passive GET); `ws://localhost:9888` opened | [`findings/03-launcher.md`](findings/03-launcher.md) |
| `fetcher` file read/traversal primitive usable (the chain's keystone) | **DISPROVEN on this build** 2026-11-06 | on-TV `recon.html`: the fetcher returned `ret:false "invalid path:…"` for all 10 probed reads (both `../` traversal and package-tree paths), zero successes — the fetcher validates/rejects paths here | [`findings/04-bridge-recon.md`](findings/04-bridge-recon.md) |
| `/var/run/superwatch_socket` reachable from app uid 314 (group 616) | UNVERIFIED (unreachable) | could not be reached — the fetcher read of `../usr/local/scripts/start-superwatch.sh` was rejected `invalid path`; traversal is blocked | [`findings/04-bridge-recon.md`](findings/04-bridge-recon.md) |
| `/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/…` writable by the app uid | **not demonstrated** 2026-11-06 | the recon marker write to `…/CHA/.recon_marker` never established (`existed_before:false, content:null`) | [`findings/04-bridge-recon.md`](findings/04-bridge-recon.md) |
| Root SSH endpoint will be `0.0.0.0:8008` key-only on success | **N/A — chain halted** | the fetcher primitive the chain needs is unavailable (above); no `postinst`/root step attempted | [`findings/04-bridge-recon.md`](findings/04-bridge-recon.md) |
| Boot persistence: none automatic | N/A — chain halted | root not armed on this unit | — |
| `transport_protocol` SSDP value | resolved — not exposed | the TV's `dd.xml` (port 3366) is a 417-byte stub with no `transport_protocol` and an empty `serviceList`; the field is not surfaced over UPnP on this build. Pairing was handled by Sidee (profile `modern`), so the cascade it would steer is already resolved | [`findings/01-ssdp.md`](findings/01-ssdp.md) |
| `Hisense_GetCountryCode()` → `GBR` | CONFIRMED live (recorded) 2026-11-06 | on-TV `Hisense_GetCountryCode()` return | [`findings/03-launcher.md`](findings/03-launcher.md) |
| `Hisense_GetRegion()` → **`EU_A`** (not a UK-specific region) | CONFIRMED live (recorded) 2026-11-06 | on-TV `Hisense_GetRegion()`; same region class as the 100U7Q reference, so the UK region delta largely collapses | [`findings/03-launcher.md`](findings/03-launcher.md) |
| Full internal model is **`75U85QEVS`** (`GetSerialType` → `75U8QE`; sticker `75U8QTUK`) | CONFIRMED live (recorded) 2026-11-06 | on-TV `Hisense_GetModelName()` / `Hisense_GetSerialType()`; SSDP `modelName` = `75U8QE` | [`findings/03-launcher.md`](findings/03-launcher.md), [`findings/01-ssdp.md`](findings/01-ssdp.md) |
| Launcher-lane GET delivery works (served page loads in TV webview) | CONFIRMED live (recorded) 2026-11-06 | `fingerprint-full.html` served from the Mac loaded in the TV Browser app over HTTP; **tile self-install still UNVERIFIED** | [`findings/03-launcher.md`](findings/03-launcher.md) |

Images (private, not committed): the owner's About screen and browser-env
readout photos contain the Device ID, Netflix ESN and serial — identifying
fields deliberately kept out of the repo per AGENTS.md ("Keys and tokens
never leave `server/keys/`"), extended here to device-identifying material.
The redacted textual facts above are the on-record evidence.
