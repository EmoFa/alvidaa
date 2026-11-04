# tools/ — device and firmware tooling

This directory is the tooling half of the VIDAA research in this repository.
It contains static firmware parsers, device-specific root helpers, and the
publication guard used to keep secrets and device identifiers out of the tree.
It is research code, not a supported product: expect hardcoded constants,
model-specific paths, and scripts that assume you have read the matching model
guide before running anything.

The tools are deliberately split by layer. Firmware analysis does not need a
TV. The HE40 and 100U7Q helpers do need one, and they only make sense on the
exact model and firmware they were written for.

## Provenance

The tool tree is ported and adapted from the author's `vidaa` research tree at
commit `b893f1b`, by [@oOHiyoriOo](https://github.com/oOHiyoriOo). The HE40 and
100U7Q source subtrees carry MIT licenses; the published copies here are
released under this repository's MIT license, and the device-independent `fw/`
scripts are the author's own tooling. Paths were reorganized for this
repository and the documentation was rewritten; the original scripts and their
model-specific constants are preserved where they are still useful.

The `alvidaa` launcher and the original code in this tree are MIT. Third-party
components keep their own licenses. See [../LICENSE](../LICENSE) and the build
recipes linked below.

## What is deliberately absent

This tree ships no runnable device payload. That is a design rule, not an
unfinished upload.

| Category | Not in this tree | Where it comes from instead |
|---|---|---|
| Binaries | Dropbear, `sftp-server`, patched Dropbear, installer IPK, vendor `.so` files | You build them from upstream source with the recipes in the model guides. |
| Firmware | `.pkg` images, extracted partitions, OTA payloads | Your own device or a vendor download you are entitled to use. |
| Keys and identity | Private keys, certificates, `authorized_keys`, host fingerprints, tokens, serials, MAC addresses | Generated locally or supplied by you through the documented paths and environment variables. |
| Captures | `.pcap`, `.pcapng`, recon logs, raw HTML/JSON dumps | Produced locally by you, and kept out of version control. |
| Vendor code | Extracted VIDAA OS code, decompiled vendor libraries | Not redistributed. The tools describe formats and behavior. |

The HE40 and 100U7Q trees intentionally contain no Dropbear binary and no IPK.
Their READMEs name the build scripts and the directories where your own build
belongs. The `fw/ota/sign` helper contains no vendor key; it signs with a public
key you provide.

## Map

| Path | Purpose | Needs a TV? |
|---|---|---|
| [`fw/`](fw/README.md) | Device-independent static analysis: MediaTek `.pkg` structure, AQDA/UENV containers, version scanning, OTA format helpers, firmware metadata catalog, archive inventory, pcap host extraction. | No |
| [`he40/`](he40/README.md) | HE40E5600FFWTS / `V0100.01.00A.N0410` root chain: browser payload planting, shadow library build, root command loop, Dropbear, optional SFTP, recon page and UI templates. | Yes |
| [`u7q/`](u7q/README.md) | 100U7Q / `V0000.09.60I.Q0813` root chain: pairing wrapper, installer IPK builder, FaaS/superwatch trigger, install and re-arm pages. | Yes |
| [`sanitize/`](sanitize/README.md) | Offline secret/PII scanner and rule set used before publication. | No |

### Existing loose tools

These predate the `fw/`, `he40/`, and `u7q/` subtrees and are kept at the top
level because they belong to the launcher or to one-off device work.

| Path | Purpose | Notes |
|---|---|---|
| [`deploy-overlay.sh`](deploy-overlay.sh) | Build the launcher overlay locally and push it to a rooted TV in one batch. | Writes the TV's UI file, clears cache, reboots. Requires the root channel and `server/keys/`; pass `<tv-ip> <bridge-url>` or set `TV_HOST` / `BRIDGE_URL`. |
| [`tvshell.py`](tvshell.py) | Send commands to the TV's busybox `telnetd` root shell on port 2323. | Plain TCP, no authentication of its own; root-equivalent. Requires `TV_HOST=<tv-ip>`. |
| [`make_bg.py`](make_bg.py) | Generate the launcher's 960x540 PNG wallpapers. | Stdlib only; writes into `launcher/bg/`. |
| [`fbcat.c`](fbcat.c) | Read `/dev/fb0` and write the framebuffer to stdout. | Read-only framebuffer dump; build for the TV's ARM userland. |
| [`doomgeneric_fb.c`](doomgeneric_fb.c) | Doomgeneric framebuffer/input backend for the TV. | Needs the Doomgeneric sources; not a standalone game. |

## How to use this tree

1. **Read the model guide first.** The tools encode one chain on one firmware.
   The guide states which stages were measured, which are owner-verified, and
   which are still unknown. Start at
   [`../docs/models/HE40E5600FFWTS/V0100.01.00A.N0410/README.md`](../docs/models/HE40E5600FFWTS/V0100.01.00A.N0410/README.md)
   or
   [`../docs/models/100U7Q/V0000.09.60I.Q0813/README.md`](../docs/models/100U7Q/V0000.09.60I.Q0813/README.md).
2. **Read the tool README.** Each subtree documents its layout, expected input,
   network behavior, and hazards.
3. **Build your own binaries.** The model guides contain the upstream versions,
   configure flags, patches, and expected file properties. The tool READMEs name
   the build scripts.
4. **Place them in the documented directory.** HE40 expects built files in
   `he40/root/tools/pub/` and the original library in `he40/root/artifacts/`.
   The 100U7Q installer expects `u7q/bin/dropbear-root` and
   `u7q/bin/dropbearkey`. `fw/` tools take a package path at runtime.
5. **Run the offline checks before touching a device.** See below.

### Directory contract

| Subtree | You supply | Expected location |
|---|---|---|
| `he40/` | Original `tvi_original.so` from your own TV | `he40/root/artifacts/tvi_original.so` |
| `he40/` | Upstream Dropbear and OpenSSH source tarballs | `he40/sources/` (or `DROPBEAR_SRC` / `OPENSSH_SRC`) |
| `he40/` | Your own public key and built binaries | `he40/root/tools/pub/` |
| `u7q/` | Static ARM32 Dropbear 2022.83 build with the documented patches | `u7q/bin/dropbear-root`, `u7q/bin/dropbearkey` |
| `u7q/` | Your own public key, passed at install time | `--pubkey` argument |
| `u7q/` | A `sidee` checkout with your own paired session | `--sidee` / `SIDEE` |

No private key, certificate, session file, or token belongs in any of these
directories.

## Safety and legal

- **Own device only.** Every device-side tool here is written for a TV you own
  and are authorized to modify. There is no remote target support.
- **LAN only.** The install, trigger, and recon servers are plain HTTP on your
  local network, with no authentication. Never expose them to the internet.
- **No DRM, no partition writes.** The documented chains are additive: they do
  not flash firmware, do not write read-only partitions, and do not touch DRM
  or verified-boot state. A tool that needs a writable path uses the TV's
  user-writable storage.
- **Reversibility is a requirement.** Read the rollback section of the model
  guide before starting. Keep the root channel available before installing a
  boot hook or replacing a runtime file.
- **Root is root.** A root command loop, a root SSH daemon, and a page that can
  feed JavaScript to a root browser are all root-equivalent. Treat every one of
  them as a full compromise of the TV.
- **Destructive helpers are marked.** `he40/root/scripts/host/prepare_usb.sh`
  wipes the block device you pass to it. `he40/recon/server.py` binds loopback
  by default; the wrapper opts into the LAN and warns.
- **Vendor material is not redistributed.** Do not commit firmware, extracted
  libraries, keys, or captures. Public firmware metadata is not a license to
  redistribute the firmware itself.

## Verification

The repository check is offline and read-only:

```sh
./scripts/check.sh
```

It checks generated tables against their JSON sources, Python syntax, shell
syntax, and every relative Markdown link. It does not run device tools and does
not prove that a chain works.

The firmware subprojects have their own pytest suites:

| Suite | Covers | Optional dependency |
|---|---|---|
| `fw/fwmap` | Offline fixture scans, host guard, store, extraction | `pytest`; `playwright` only for render tests, if present |
| `fw/fwinv` | Archive inventory and path-safety checks | `pytest` |
| `fw/pcap` | pcap/pcapng parsing and host extraction | `pytest` |
| `fw/ota/sign` | Signing round-trip with a throwaway key | `pytest`, `cryptography` |
| `sanitize` | Scanner rules against synthetic fixtures | `pytest` |

Run each suite from its own directory. A missing optional dependency is a
`NOT_RUN`, not a pass. No hardware test is recorded by these suites, and this
tree contains no device log that would substitute for one.

The signing helper also has a self-check that generates a throwaway key in
memory:

```sh
python3 tools/fw/ota/sign/ota_sign.py --selftest
```

## Model guides

| Model | Firmware | Guide |
|---|---|---|
| HE40E5600FFWTS | `V0100.01.00A.N0410` | [`../docs/models/HE40E5600FFWTS/V0100.01.00A.N0410/README.md`](../docs/models/HE40E5600FFWTS/V0100.01.00A.N0410/README.md) |
| 100U7Q (100U70QEVS) | `V0000.09.60I.Q0813` | [`../docs/models/100U7Q/V0000.09.60I.Q0813/README.md`](../docs/models/100U7Q/V0000.09.60I.Q0813/README.md) |

Project policies: [../SECURITY.md](../SECURITY.md) for disclosure and
publication hygiene, [../AGENTS.md](../AGENTS.md) for the rules an AI session
must follow when working in this repository.
