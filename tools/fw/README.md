# fw/ — static firmware analysis

Device-independent tooling for taking apart Hisense/MediaTek firmware packages
and reconstructing the OTA request format. Everything here is static by design:
the parsers open files read-only, none of them flashes a device, writes to a
partition, or contacts a remote service at import time.

The tools were written against specific images. They are research-grade:
hardcoded offsets, package names, and function addresses are normal. Treat every
constant as a property of the sample it was derived from, not as a format
guarantee.

## Layout

| Path | Purpose |
|---|---|
| [`pkg/`](pkg/) | MediaTek `.pkg` structure: `MtK8` header/container probes, AQDA mapping, ext4 payload scan, hash-region experiments, signature search. |
| [`pkg/AQDA-FORGE/`](pkg/AQDA-FORGE/) | Repack experiments: header inspection, hash coverage, a forged-package test build, and verification against the original. |
| [`pkg/USIG-UENV/`](pkg/USIG-UENV/) | UENV/USIG header mapping, ELF extraction from the UENV window, and hash tests. |
| [`pkg/VERSION/`](pkg/VERSION/) | Version-string scanning and A/B comparison between two packages; SPDT map/recovery helpers and report generation. |
| [`ota/he40/`](ota/he40/) | HE40-generation OTA research: request-field experiments, signature verification, and Capstone disassembly helpers for the vendor libraries. |
| [`ota/u7q/`](ota/u7q/) | 100U7Q-generation diagnostics, the rate-limited `check_version` hunt, and a legacy Playwright page renderer. |
| [`ota/sign/`](ota/sign/README.md) | The supported OTA signing primitive, its tests, and its optional dependency file. |
| [`fwmap/`](fwmap/README.md) | Metadata catalog for publicly linked firmware files: SQLite store, offline fixtures, explicit network opt-in, coverage report. |
| [`fwinv/`](fwinv/README.md) | Read-only inventory for a local firmware archive (zip/tar/raw), with path-safety checks. |
| [`pcap/`](pcap/README.md) | Host-name extractor for pcap/pcapng captures: DNS, TLS SNI, HTTP `Host`. |

## Common entry points

| Task | Start with | Notes |
|---|---|---|
| Inspect a `.pkg` | [`pkg/analyze_pkg.py`](pkg/analyze_pkg.py) | Takes a package path; prints magic offsets, header, trailer, and hash regions. |
| Map the AQDA container | [`pkg/aqda_map.py`](pkg/aqda_map.py), [`pkg/AQDA-FORGE/inspect_aqda.py`](pkg/AQDA-FORGE/inspect_aqda.py) | Read-only. The forge scripts write a separate test package, never the input. |
| Map a UENV window | [`pkg/USIG-UENV/uenv_map.py`](pkg/USIG-UENV/uenv_map.py) | Extracts the ELF at the recorded UENV offset into the working directory. |
| Compare versions / A-B | [`pkg/VERSION/scan_versions.py`](pkg/VERSION/scan_versions.py), [`pkg/VERSION/ab_compare.py`](pkg/VERSION/ab_compare.py) | Package names are constants at the top of the script. |
| Sign an OTA field | [`ota/sign/ota_sign.py`](ota/sign/ota_sign.py) | Needs your public key; no key is bundled. |
| Catalog public firmware metadata | [`fwmap/README.md`](fwmap/README.md) | Offline by default; live runs require `--allow-network`. |
| Inventory an archive | [`fwinv/fwinv.py`](fwinv/fwinv.py) | Extraction is confined to the output directory. |
| Summarize a capture | [`pcap/parse_pcap.py`](pcap/parse_pcap.py) | Prints host names only; see the privacy note in its README. |

Most older scripts default to `usb_EE5600FF.pkg` in the current directory and
adjust the path through a constant at the top of the file. Where a script
accepts a path argument, prefer it. Do not point any parser at a block device or
a device node.

## Dependencies

The default is the Python standard library. Optional packages unlock specific
helpers and tests; a missing optional package should be reported as `NOT_RUN`,
not worked around with a guess.

| Dependency | Needed by | Required? |
|---|---|---|
| Python 3.11+ | `fwmap`; the rest is older stdlib Python | Recommended |
| `cryptography` (`>=42` in [`ota/sign/requirements-ota.txt`](ota/sign/requirements-ota.txt)) | `ota/sign/ota_sign.py`, `ota/he40/ota_sign.py` | Optional; signing exits with an install hint if absent |
| `capstone` | `ota/he40/dis_*.py`, `emit_disasm.py` | Optional; disassembly helpers only |
| `playwright` | `fwmap --render`; `ota/u7q/render_hisense.py` | Optional; live rendering only |
| `pytest` | all shipped test suites | Development only |

Install the signing extra with:

```sh
python3 -m pip install -r tools/fw/ota/sign/requirements-ota.txt
```

## Network behavior

No module opens a socket at import time. Network access is explicit, with two
legacy exceptions that are called out below.

| Tool | Default | How to opt in | Guardrails |
|---|---|---|---|
| `fwmap` | Offline; `--offline DIR` performs zero requests | `--allow-network` on `probe`, `scan`, `sync`, `download` | Host allowlist, per-hop redirect checks, `robots.txt`, 1 request / 2 s, bounded retries, byte caps. Without the flag it exits before opening a socket. |
| `ota/u7q/hunt_versions.py` | `--dry-run` | `--allow-network` | Fixed host and path, no redirects, small request budget, 5 s minimum delay, token from `HISENSE_ACCESS_TOKEN`, token redacted from all output. |
| `ota/u7q/render_hisense.py` | Live on start | None | Legacy one-shot Playwright script for one public vendor page. It has no dry-run switch and is not part of the offline workflow. Do not run it unless you intend a live fetch. |
| `ota/he40/ota_sign.py` | Signing only | An explicit call to its `post()` helper | Reconstruction that reads `HISENSE_PUBKEY` at import and contains a request builder for a fixed vendor endpoint. Importing it does not send anything; using the builder does. Prefer `ota/sign/ota_sign.py` for the clean primitive. |

`fwmap` is the only catalog tool. It never logs in, never sends cookies or auth
headers, and stores metadata only. A "full map" means "all publicly linked
files observed at crawl time", not "all firmware that exists".

## Keys, credentials, and identifiers

No vendor public key, certificate, token, or firmware image is bundled. The
scripts that need per-device values read them from the environment at runtime;
none of them writes those values to disk.

| Variable | Used by | Meaning |
|---|---|---|
| `HISENSE_PUBKEY` | `ota/he40/ota_sign.py` | Path to the vendor public key extracted from your firmware. |
| `HISENSE_OTA_PUBKEY` | `ota/sign/ota_sign.py` | Path to the RSA public key used by the signing primitive. |
| `HISENSE_APP_KEY`, `HISENSE_APP_SECRET` | `ota/he40/try_signin.py` | Your own app credentials, if you are testing the sign-in path. |
| `HISENSE_DEV_SERIAL`, `HISENSE_DEVICE_ID` | `ota/he40/try_signin.py` | Your own device values. |
| `HISENSE_FEATURE_CODE` | `ota/he40/try_devserial.py` | Your own device value. |
| `HISENSE_TOKEN` | `ota/he40/try_checkver.py`, `try_devserial.py` | A token for your own device. |
| `HISENSE_MAC`, `HISENSE_DVC_RSV` | `ota/he40/try_checkver.py` | Your own device values. |
| `HISENSE_ACCESS_TOKEN` | `ota/u7q/hunt_versions.py` | Your own token; redacted as `***` in output. |
| `HISENSE_CONTENT`, `HISENSE_EXPECTED` | `ota/he40/verify_my_signer.py` | Content and recorded signature, instead of passing them as arguments. |

The signing primitive is not a request builder and not a login tool:
`ota/sign/ota_sign.py` computes
`URLEncode(base64(RSA_public_encrypt(MD5(content), pubkey, PKCS1v15)))` for a
string you provide. The vendor public key must be supplied by you; there is no
default key and no fallback path.

## Research-grade caveats

- **Hardcoded offsets are expected.** `pkg/AQDA-FORGE/build_forge.py` contains a
  full offset table for one package; `pkg/USIG-UENV/uenv_map.py` uses a fixed
  UENV offset; `pkg/VERSION/scan_versions.py` hardcodes sample names; the
  `ota/he40` disassembly scripts hardcode function addresses and library names.
  Re-derive them for your sample rather than assuming they transfer.
- **The forge scripts write derived files.** They open the original read-only
  and create a separate test package or extracted ELF. Check the output path
  before running them in a directory that contains an original.
- **The parsers are not a flashing tool.** Do not point them at a block device,
  and do not treat a successful parse as proof that an image is safe to install.
- **OTA is per-device authenticated.** The signing primitive reproduces one
  cryptographic step. It does not obtain firmware, bypass access control, or
  authenticate as another device.

## Tests

Each self-contained subproject has an offline pytest suite:

| Directory | Command | Network |
|---|---|---|
| `fw/fwmap` | `python3 -m pytest` | None; fixtures only. `--render` tests need Playwright. |
| `fw/fwinv` | `python3 -m pytest` | None. |
| `fw/pcap` | `python3 -m pytest` | None. |
| `fw/ota/sign` | `python3 -m pytest` | None; uses a throwaway in-memory key. |
| `../sanitize` | `python3 -m pytest` | None; synthetic fixtures. |

The signing helper also has a direct self-check:

```sh
python3 tools/fw/ota/sign/ota_sign.py --selftest
```

The repository-level check covers Python syntax, shell syntax, generated tables,
and relative Markdown links:

```sh
./scripts/check.sh
```

A missing `cryptography`, `capstone`, `playwright`, or `pytest` means the
corresponding check is `NOT_RUN`. Do not describe it as passed.

## Model guides

These tools are generation-specific in places. Read the matching guide before
using the OTA helpers on a device:

- [`../../docs/models/HE40E5600FFWTS/V0100.01.00A.N0410/README.md`](../../docs/models/HE40E5600FFWTS/V0100.01.00A.N0410/README.md)
- [`../../docs/models/100U7Q/V0000.09.60I.Q0813/README.md`](../../docs/models/100U7Q/V0000.09.60I.Q0813/README.md)

Publication rules and disclosure stance: [`../../SECURITY.md`](../../SECURITY.md).
The scanner that guards this tree: [`../sanitize/README.md`](../sanitize/README.md).
