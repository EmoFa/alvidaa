# Model and firmware guides

This directory holds **model- and firmware-specific** root and modding guides.
A guide is published only for the exact model *and* firmware string it was
recorded on. The general chains live elsewhere:

- [docs/ROOT.md](../ROOT.md) — the 2024+ MTK9602 / 09.01 chain
- [docs/EXPLOITS.md](../EXPLOITS.md) — method inventory across tested devices
- [docs/FINDINGS.md](../FINDINGS.md) — the lab notebook
- [docs/inventory.json](../inventory.json) — machine-readable model rows

## Which guide applies to my TV?

Only the one whose **model and firmware both match**. Check the firmware string
in the TV's system information and compare it character by character.

| Model | Firmware | SoC class | Result | Persistence | Guides |
|---|---|---|---|---|---|
| `HE40E5600FFWTS` | `V0100.01.00A.N0410` | MediaTek MT53xx / MT5863 class, ARMv7 Cortex-A53 | root via browser + loader shadow; key-only Dropbear SSH on 22; PTY | `HamService` wrapper; owner-verified across reboots (2026-11-04) | [README](HE40E5600FFWTS/V0100.01.00A.N0410/README.md) · [EVIDENCE](HE40E5600FFWTS/V0100.01.00A.N0410/EVIDENCE.md) · [MODDING](HE40E5600FFWTS/V0100.01.00A.N0410/MODDING.md) |
| `100U7Q` (`100U70QEVS`) | `V0000.09.60I.Q0813` (VIDAA `U09.60`, EU_A) | MediaTek MT9655, 32-bit ARM userland | root via `fetcher` write + package `postinst`; key-only root SSH on 8008; PTY | **none automatic**; re-arm with uninstall `83` + install `82` after each reboot | [README](100U7Q/V0000.09.60I.Q0813/README.md) · [EVIDENCE](100U7Q/V0000.09.60I.Q0813/EVIDENCE.md) · [MODDING](100U7Q/V0000.09.60I.Q0813/MODDING.md) |

These two chains are **different and not interchangeable**:

| | HE40 | 100U7Q |
|---|---|---|
| Entry point | browser runs as root; file-API whitelist bypass | app-context FaaS write + privileged package socket |
| Root execution | shadow library `DT_INIT` in the browser | IPK `postinst` via the root package daemon |
| Boot persistence | `HamService` wrapper (owner-verified) | none; manual re-arm |
| Recovery | `rollback.sh` + reboot | uninstall `83` + operator cleanup |

A third chain, [docs/ROOT.md](../ROOT.md), targets a different generation
(MTK9602 / 09.01O.P0813) and shares no steps with either guide. Do not apply
one model's paths to another.

## How to read the labels

Every guide uses the same vocabulary:

| Label | Meaning |
|---|---|
| **CONFIRMED live (recorded)** | the author's record reports a device observation, usually with output or an artifact. A record claim, not an independent re-test. |
| **CONFIRMED host/build** | reproduced on a build host, not on the TV. |
| **owner-verified** | stated by the device owner after the record; no file in the record set contains the observation. |
| **documented code** | quoted device source/configuration or a build recipe. |
| **UNVERIFIED** | not tested, or explicitly open. Never a recipe. |
| **DEAD END** | tried and rejected; listed so nobody repeats it. |

The EVIDENCE page of each model carries a claim matrix with a `file:line`
basis and short quotes. The README page carries the procedure. The MODDING page
carries the system layout and the modding surface, with its own
verified/unverified table.

## Ground rules

These guides are for **hardware you own**, on your own LAN.

- **No flashing, no `.pkg`, no UART, no case opening** is the design property of
  both chains. Read-only partitions stay untouched; verified boot stays green.
- **No vendor binaries and no keys are shipped.** Payloads and SSH binaries are
  rebuilt from your own device and the documented patches. Private keys never
  leave your machine.
- **Keep a recovery path.** A root shell or command loop is the way back from a
  broken UI or boot hook. Do not close it until you are done.
- **One change at a time.** Back up every file you replace. Reboot to test.
- **Do not expose debug interfaces to the internet.** The HE40 recon server is
  unauthenticated and drives a root browser; the SSH daemons are key-only root
  access on your LAN.
- **A failed observation applies to one route and one device.** It is not proof
  that a firmware is safe in general.

See [SECURITY.md](../../SECURITY.md) for the disclosure stance and
[AGENTS.md](../../AGENTS.md) if an AI session is doing the work.

## Tools

The scripts referenced by the guides live under [tools/](../../tools/):

| Tree | Contents |
|---|---|
| [tools/he40/](../../tools/he40/) | USB prep, recon server/page, payload and Dropbear builds, TV-side deploy/verify/rollback, templates |
| [tools/u7q/](../../tools/u7q/) | pairing, installer and trigger scripts, install/trigger pages, FaaS helper |
| [tools/fw/](../../tools/fw/) | firmware inventory/map/OTA tooling (not used by these two chains) |
| [tools/tvshell.py](../../tools/tvshell.py) | generic SSH wrapper |
| [tools/deploy-overlay.sh](../../tools/deploy-overlay.sh) | launcher deployment helper |

`tools/*/bin` and `tools/*/tools/pub` are **drop points**, not binary
distributions. Build or supply your own.

## Contributing a model

Add the model to [docs/inventory.json](../inventory.json) first, then report
the method result in [docs/exploits.json](../exploits.json) — the generated
tables in the repository README and [docs/EXPLOITS.md](../EXPLOITS.md) come
from those files. A model guide is worth writing only when the firmware string
is exact and the observations are separable from the inferences. Follow the
status vocabulary above; keep unknowns unknown.

Field definitions for a device report:
[docs/TESTED-MODELS.md](../TESTED-MODELS.md).

## Attribution

The HE40 and 100U7Q research is by
[@oOHiyoriOo](https://github.com/oOHiyoriOo); the source is the author's vidaa
research repository, commit `b893f1b` (a private record, cited in the guides,
not linked). The guides themselves are original English text under the
repository's MIT license — see [LICENSE](../../LICENSE).
