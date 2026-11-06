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
| Phoenix FaaS stack present (`http://localhost:9009`, `wss://localhost:9888`) | UNVERIFIED | inferred from same-build equivalence; `9009` is localhost-only so the LAN `filtered` state does not prove presence on-TV | — |
| `fetcher` FaaS has empty permission block at `/service/basic/fetcher` | UNVERIFIED (hypothesis) | the whole chain hinges on this; probe via browser recon before any write attempt | — |
| `/var/run/superwatch_socket` reachable from app uid 314 (group 616) | UNVERIFIED (inferred) | same kernel + same init = expected; confirm by bridge-read of `/proc/self/status` groups | — |
| `/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/functions/fetch/` writable by uid 314 | UNVERIFIED | expected from same-build equivalence; confirm by a harmless write + delete probe | — |
| Root SSH endpoint will be `0.0.0.0:8008` key-only on success | UNVERIFIED (hypothesis) | 100U7Q `postinst` deploys Dropbear on 8008; identical postinst expected | — |
| Boot persistence: none automatic | UNVERIFIED (hypothesis) | matches 100U7Q record; could be lifted later via the 75UR9S `re_sshd` adapter if applicable | — |
| `transport_protocol` SSDP value | UNVERIFIED (not captured) | SSDP descriptor XML not yet fetched | — |
| `Hisense_GetCountryCode()` → `GBR` (UK) | UNVERIFIED (not captured) | needed to decide the pairing credential profile | — |

Images (private, not committed): the owner's About screen and browser-env
readout photos contain the Device ID, Netflix ESN and serial — identifying
fields deliberately kept out of the repo per AGENTS.md ("Keys and tokens
never leave `server/keys/`"), extended here to device-identifying material.
The redacted textual facts above are the on-record evidence.
