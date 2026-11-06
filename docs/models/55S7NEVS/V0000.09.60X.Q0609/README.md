# 55S7NEVS / V0000.09.60X.Q0609 — root over the vendor package path (MT9618)

**Status:** root SSH (uid 0) was achieved on this model/firmware, **with boot
persistence** — a cold-boot re-fire was verified on the contributor's unit
(postinst at uptime ~11 s, uid-0 SSH reachable shortly after). The chain is
the same family as the [100U7Q guide](../../100U7Q/V0000.09.60I.Q0813/README.md)
(`fetcher` write → vendor package path → root `postinst`) but on a different
SoC generation (MTK9618 / `mt5879`, aarch64 Cortex-A72) and a 2026-06 U09.60
build.

> **Applies to the `55S7NEVS` EU build `V0000.09.60X.Q0609` (VIDAA `U09.60`,
> branch `all-VIDAA_U96_MT9618_EUAU_hotfix_20260531`).** The same board build
> also carries `55U75LEVS`, `65S7NAVS` and `75S7NAVS` (per `serialdata`), so
> the guide is relevant to that family — untested on those units. Firmware
> families drift; the chain rests on the properties listed under
> [What it rests on](#what-the-chain-rests-on).

> **Contributed by [possibly_matt](https://www.reddit.com/user/possibly_matt/).**
> The material arrived as a private bundle (2026-11-05) and was adapted for
> this repo — docs only, with the author's permission for the documentation.
> The operational payload was deliberately **not** republished; see
> [What this guide includes and leaves out](#what-this-guide-includes-and-leaves-out).

## What the chain rests on

Four properties of this build, in dependency order (architecture level —
the same shape the 100U7Q guide documents in full):

1. **Page-to-bridge access.** A page rendered on the TV (the MQTT
   `launchapp` lane, as in [findings 01](../../50A51HUV/09.01O.P0813/findings/01-mqtt-bridge.md))
   can talk to the vendor's Phoenix JS bridge on `localhost:9009`.
2. **Arbitrary write.** The `fetcher` service ships with an **empty
   permission list**, so `fetcher.fetchFile` writes an arbitrary path with
   no gate — including the pkgmgr package tree.
3. **Unverified package-manager input.** A hooked `UpgradeReport.js` in the
   pkgmgr package is loaded at boot; it can reach the vendor's own root
   daemon (superwatch) and make it run `opkg` on an attacker-supplied IPK.
   The package path runs no content-signature check.
4. **Root `postinst`.** The IPK's `postinst` executes as `uid 0`, installs a
   kit, and starts a self-healing daemon. The boot hook re-fires the install
   on every cold boot (verified), and a deep mirror under `/vendor/persist`
   survives wipes of the app area.

Nothing here touches verified boot: all writes land in `APPS`/`APPS2`,
`/var/local`, `/data`, `/OAD` or `/vendor/persist` — every one of them
unsigned. AVB stays green, Widevine L1 stays intact
([findings/10](findings/10-boot-chain.md) maps the whole verified/unverified
split).

## What this is

- A **documented, live-verified root** for this exact build, contributed by
  a community researcher who ran it on their own unit.
- An **offline firmware analysis** of the MT9618 generation — boot chain,
  userspace runtime, OTA/update path, version facts, a security review, and
  a telemetry/privacy deep-dive — published as
  [findings files](findings/).

## What this is not

- **Not a step-by-step procedure.** The exact phase-by-phase chain, the
  payload scripts and the static binaries are **not republished here** —
  that is a deliberate, author-endorsed boundary (see below). The
  architecture documentation stands on its own.
- **Not tested on this repo's reference unit.** Our lab TV is the
  [50A51HUV / MTK9602](../../50A51HUV/09.01O.P0813/README.md); this chain
  comes from the contributor's 55S7NEVS. Capability rows in the
  [inventory](../../../research/inventory.json) that our own lanes did not
  exercise are marked `untested`.
- **Not a launcher-lane result.** Pairing/launcher capability on this
  generation is expected to work (the contributor used this repo's pairing
  server during the work) but is not separately verified here.

## What this guide includes and leaves out

The bundle's own disclosure policy — quoted from the author's notes —
draws the line precisely: *"The docs in this bundle are publishable on
their own. The payload and the exact chain are what shorten the window."*
The chain rests on three vendor properties that are cheap to fix (an empty
`fetcher` permission list, an unverified `UpgradeReport.js`, an
unauthenticated superwatch message); a public repost of the working payload
turns that into a patch request with a countdown. This adaptation follows
that line:

| Included (adapted, with credit) | Left in the private bundle |
|---|---|
| the six offline analysis docs → [findings/](findings/) | the phase-by-phase root procedure |
| the chain at the architecture level (above) | the payload scripts (`postinst`, poison hook, daemon, guard stubs) |
| safety-shape summary (below) | the static `kit/` binaries (busybox, iptables, patched dropbear) |
| facts the inventory needs (below) | key generation specifics tied to the kit |

No key material of any kind was included: the bundle ships none (its
`MAKE-KEYS.md` is instructions-only, verified before adaptation), and the
repo ships no vendor binaries by policy.

## Facts this guide adds to the inventory

| | Value | Source in findings |
|---|---|---|
| Model | `55S7NEVS` (EU; board family covers `55U75LEVS`/`65S7NAVS`/`75S7NAVS`) | [findings/40](findings/40-version-facts.md) |
| SoC | MTK9618 (`mt5879` die), 4× Cortex-A72, aarch64 | [findings/40](findings/40-version-facts.md) |
| Kernel | 5.4.302 aarch64 (SMP PREEMPT, built 2026-06-09) | [findings/40](findings/40-version-facts.md) |
| Firmware | `V0000.09.60X.Q0609`, OS `U09.60`, built 2026-06-09 | [findings/40](findings/40-version-facts.md) |
| Browser | Chromium 111.0.0.0 (`zenixservicework` shim), V8 11.1 | [findings/40](findings/40-version-facts.md) |
| Verified boot | AVB 1.1 + dm-verity on kernel/rootfs + ~10 hashed partitions; everything writable is unsigned | [findings/10](findings/10-boot-chain.md) |
| SELinux | policy loaded, then `setenforce 0` in both rc branches (vendor build choice) | [findings/10](findings/10-boot-chain.md) |
| OTA content auth | md5+sha256 only, from the same untrusted XML — no signature chain | [findings/30](findings/30-update-oad.md) |
| ACR / Enhanced Viewing | full Alphonso→Tremor→Nexxen stack shipped; **opted out** on the contributor's unit | [findings/80](findings/80-telemetry.md) |

## Safety shape (summary)

The full operational safety/teardown pages travel with the author's private
bundle. The shape, for anyone evaluating the risk:

- **Four ways to brick or lock out**, all avoided by the chain as designed:
  writing to an AVB-verified partition (never needed — see the write map
  above); a known `postinst` regression that can delete the live `/etc`
  mirror (fixed in the author's v19 payload, documented in the bundle); the
  vendor factory-reset trigger file (never create it); and a fetch helper
  that deletes its destination on download failure (always serve-then-verify).
- **Teardown exists** without touching verified partitions: restore the
  hooked file from the clean copy, remove the package records, kill the
  daemons, undo the freeze mounts, reboot.
- **LAN-only discipline** applies as everywhere in this repo: the exposed
  surfaces after root are scoped to the local subnet by design, and nothing
  here is for a network you do not control.

## Provenance

- Chain verified live on one 55S7NEVS unit 2026-11-02; cold-boot re-fire
  verified 2026-11-03 (postinst at uptime ~11 s → daemon → first uid-0 SSH
  ~87 s). Architecture docs derived from a full eMMC backup of that unit.
- Steps that were derived from firmware rather than executed on a fresh
  unit are marked `[derived]` in the author's procedure (not reproduced
  here).
- Adapted for this repo 2026-11-06: unit identifiers were already redacted
  by the author (`<TV_LAN_IP>`, `<UNIT_SERIAL>`, … placeholders retained);
  internal references to the author's private notes were rewritten as
  provenance pointers. The author reviewed what the bundle contains via its
  own MANIFEST, which this adaptation trusts.
