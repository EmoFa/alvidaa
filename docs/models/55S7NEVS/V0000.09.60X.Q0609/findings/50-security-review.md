# Security review — VIDAA U09 / MT9618

> From the contributed bundle by [possibly_matt](https://www.reddit.com/user/possibly_matt/)
> (2026-11-05), adapted for this repo 2026-11-06 with the author's permission
> for the documentation. See the [guide README](../README.md) for scope.

A short version of the offline review done on a full eMMC image. It asks the
question the backup was taken to answer: *once you can read the whole
platform, what does it give away, and what would have been the easy way in?*

Nothing here is a step-by-step exploit. The verified chain is documented
only in the author's private bundle; this page is the shape of the attack
surface and the fixes that would close it.

---

## 1. Trust model

- **Verified boot is real but narrow.** MBoot is locked (AVB 1.1 +
  dm-verity) and covers the kernel, rootfs and about ten hashed partitions
  in the dual-bank tables. Everything *below* that — all writable data:
  `APPS`, `APPS2`, `/var/local`, `/data`, `/vendor/persist`,
  `/var/tvservice`, `/OAD` — is unsigned, and a lot of vendor code executes
  out of it.
- **SELinux is cosmetic.** The policy is loaded and then `setenforce 0` is
  called in *both* branches of `init_selinux.rc`. This is a vendor choice on
  the build, not a root-strip side effect.
- **`secure_exec` is not an integrity mechanism.** It is a uid/gid/caps DAC
  launcher: `execvp` after a label match, with labels resolved from a
  manifest. No code signature.
- **Boot mode split.** If the factory info carries the OTA flag, init swaps
  entirely into the OTA path, and the flasher writes raw block devices per
  `otaPartitionConfig.ini`. Anything that survives into that state is a
  supply-chain-level write.

## 2. The main surface

### 2.1 The Phoenix JS bridge

Listens on `localhost:9009`, accepts raw socket JSON, HTTP with `Origin`
headers, and WebSockets. It is reachable from **any page the TV renders**,
because the renderer runs with
`--disable-features=BlockInsecurePrivateNetworkRequests` and has
`file://`/loopback access.

There is a gate — "writey" APIs return `503 please check appconfig` — but
several useful calls are **ungated**, including `fileRead` (seven
root-anchored mount modes), `securityEncrypt/Decrypt`, `getInstalledPkgs`,
`getDefaultCDNInfo` and `tvinfo`. `fileRead` alone is a complete exfiltration
primitive.

The sharpest one is the `fetcher` service: its permission list is **empty**,
so `fetcher.fetchFile` accepts a download with an arbitrary destination path
and no gate. That is an arbitrary write as the service uid. Its companion,
`fetcher.fetchResponse`, performs a request from the fetcher's own process,
so the gate sees `from: 'Unknown'` and gated APIs can be driven indirectly.

### 2.2 The support shells

`/etc/passwd` ships three support accounts with real shells, reachable over
the serial console (`getty` on `ttyS0` at 115200 8N1, respawned in runlevels
0–6):

| user | uid | shell | What it gives |
|---|---|---|---|
| `television` | 300 | login script | 19-item menu: `wget` into `/var/local`/`/OAD`/`/tmp`, `touch` arbitrary files, `cat`, `cp`/`rm` in `/OAD`, superwatch import/export, tcpdump |
| `loewe` | 299 | login script | same menu family |
| `cli` | **0** | `cli_login.sh` | decrypts and unpacks a `vidaa_commands.bin` pack, sha256-verifies it, then runs it |
| `root` | 0 | `rootlogin.sh` | root |

The menu shell runs as uid 300, so it cannot flip factory state — but
`wget` plus `touch` into the writable trees is one boot-hook away from
persistence. The only real barrier is the account password.

### 2.3 The package installer

The vendor's own package path — `installApplication`, superwatch import,
`pkgmgr` — runs `postinst` as **root**. There is no content signature check
anywhere in it: the package database and the ipk metadata are the only
inputs. Field values matter (`Persistent`, `SkipFirstStartVerify`,
`UpgradeMode`, `PackageType`) because they map onto vendor checks, but none
of them is a signature.

This is the "root equalizer": any write primitive plus this path equals
root. It is also the most fixable thing on the platform.

## 3. Crypto and credential posture

- **No signature on OTA content.** The updater imports OpenSSL for
  decrypt/base64/MD5/SHA-256 only — no RSA/ECDSA/X509 symbols. Integrity is
  md5+sha256 taken from the same untrusted XML. This is the finding with the
  widest blast radius.
- **Password hashes ship on the device.** The shadow files contain real
  sha512crypt entries for the support family. They are offline-crackable;
  whether they are *unit-unique* or *vendor-static* decides how bad that is.
- **A decryption key ships world-readable.** `0001-cli-login-aes.pem` feeds
  the CLI pack decryptor. It is decrypt-only — the signing side is a public
  key — so it lets you read genuine packs, not forge them. It still means
  the confidentiality of those packs rests on filesystem permissions.
- **No cloud tokens or plaintext CDN hosts** were found in the trees. Hosts
  are resolved at runtime by `libhi_cloud_openapi.so` / `getDynamicDomain`,
  and the updater's URLs are `%s` placeholders. That part is done properly.

## 4. Doors that exist but were not needed

| Door | Where | Note |
|---|---|---|
| hidden firewall/webUI config | `security-firewall-*`, `access-route-rule.ini` | present in the image, not reversed |
| `superwatch_clientExec` | vendor `usrlocal/bin` | generic "exec staged payload" tool the vendor infra itself uses |
| MQTT broker | `opt/iot/mosquitto` + `iot_service` | LAN MQTT; the launcher already rides it |
| Matter commissioner | `opt/iot/matter`, port 5552 | LAN commissioning surface, un-probed |
| vestigial inetd | `inetd.conf` | telnet/ftp/rlogind/rshd lines are uncommented but **the binaries are absent** — do not rely on it |
| Chromium debug port | `--remote-debugging-port=9226` | comes up with the renderer; firewall drops it externally in the EULA-on chain |

## 5. What would actually fix it

Ranked by effort-to-impact, from the vendor's side:

1. **Give `fetcher` a path allow-list.** One config edit; kills the arbitrary
   write.
2. **Checksum `UpgradeReport.js`** (and the other pkgmgr inputs) in the
   existing `checkAndRestoreInfoFiles` ledger. The infrastructure is already
   there.
3. **Authenticate the superwatch message channel.** A token between pkgmgr
   and the root daemon. Harder, one release.
4. **Sign OTA content**, and stop trusting md5/sha256 from the same XML.
5. **Stop shipping `setenforce 0`.** It is not load-bearing on this build.

Two of the first three together close the chain in this bundle.
