# Evidence — 100U7Q / V0000.09.60I.Q0813

**What this page is:** the evidence ledger behind [README.md](README.md). It
separates measured device results, quoted device code, documented procedures,
and explicit unknowns. It does not upgrade any claim.

**Basis:** the sanitized source notes included in
[`source/`](source/README.md), plus the owner's statement of 2026-11-04 where
noted. `source/...` citations are line labels in those notes. The source notes
carry no measurement dates; they were reviewed for this page on 2026-11-04.

> **Self-contained note:** the `source/` files are included in this
> repository. The guide reproduces the commands and the decisive excerpts; you
> do not need any external record to follow it.

## Target identity

| Property | Recorded value | Basis |
|---|---|---|
| Model | Hisense `100U7Q` (`100U70QEVS`, SerialType `100U7QE`), region EU_A | `source/ORIGINAL-README.md:9`; `source/modding/README.md:8` |
| Firmware | VIDAA `U09.60`, `V0000.09.60I.Q0813` | `source/ORIGINAL-README.md:11`; `source/modding/README.md:9` |
| SoC | MediaTek **MT9655** | `source/ORIGINAL-README.md:10`; `source/modding/README.md:10` |
| Userland | 32-bit ARM (`EM_ARM`), Node `arm`, static ARM32 Dropbear | `source/ORIGINAL-README.md:10`; `source/modding/README.md:11` |
| Kernel | `5.15.192-ge6d9f75ad2ad-dirty` | `source/modding/README.md:11` |
| App context | uid 314, gid 314, `CapEff=0000000000800000` (only `CAP_SYS_NICE`) | `source/modding/README.md:12`; `source/modding/05-limits.md:27` |
| SELinux | `enforce=1` | `source/modding/README.md:13`; `source/modding/05-limits.md:43` |
| Result | `ssh -p 8008 root@<tv>` — uid 0, full caps, PTY, key-only | `source/ORIGINAL-README.md:12`; `source/modding/04-ssh.md:3-4` |

Two contexts must not be conflated: the **app context** (uid 314) has only
`CAP_SYS_NICE`; the **root `postinst`** has
`CapEff=000001ffffffffff` and the resulting root SSH session has full
capabilities. `source/ORIGINAL-README.md:12` refers to the root session, `source/modding/README.md:12`
to the app context.

## Claim / status matrix

Labels: **measured (recorded)** — a device result with an output or a stated
observation; **documented code** — quoted device source/configuration;
**documented procedure** — a reproducible recipe, not itself a measurement;
**UNVERIFIED**; **DEAD END**.

| # | Claim | Status | Basis |
|---|---|---|---|
| 1 | Pairing uses MQTT/TLS on port 36669, a vendor client certificate, and an on-screen PIN; the session is per TV in `~/.sidee/session.json` | documented procedure | `source/docs/PAIRING.md:10-13`; `:64-65`; `:74` |
| 2 | The TV's identity for pairing is the Ethernet MAC with colons | documented procedure | `source/docs/PAIRING.md:49-50` — "The TV accepts only the Ethernet MAC with colons as its identity" |
| 3 | The web app reaches a local Node service at `https://localhost:9888` (fallback `http://localhost:9009`) | documented code | `source/docs/HOW-IT-WORKS.md:9-12` |
| 4 | `fetcher` has `"permission": {}` and `selfStart: false`; it is reachable at `/service/basic/fetcher`, not `/service/fetcher` | documented code | `source/docs/HOW-IT-WORKS.md:16-19` |
| 5 | `fetchFile(url, directory, permission)` writes to an absolute path with no validation, follows symlinks, does not create parents, and runs as uid 314 | documented code | `source/docs/HOW-IT-WORKS.md:36-42`; `source/modding/02-write-and-exec.md:42-49` |
| 6 | Write success on the device | documented code + operational reliance; **no standalone write log** in the record | `source/ORIGINAL-README.md:89-94` install flow; `source/ORIGINAL-README.md:14-15` claims four properties "verified on the device" |
| 7 | `pkgmgr` sends install command `82` to `/var/run/superwatch_socket`; the socket is `srw-rw---- root 616`; 616 is in uid 314's supplementary groups | documented code + stated measurement (no raw `ls`/`id` transcript) | `source/docs/HOW-IT-WORKS.md:52-60`; `source/modding/03-root.md:16-25` |
| 8 | The daemon runs `opkg install` as root; the `postinst` gets uid 0 and `CapEff=000001ffffffffff` | **measured (recorded)** | `source/docs/HOW-IT-WORKS.md:71-81` (`POSTINST_RAN`, `Uid: 0 …`, `CapEff: 000001ffffffffff`); `source/modding/03-root.md:29-33` |
| 9 | Install with empty options succeeds; a `--tmp-dir` option returns `-1` | measured (recorded) | `source/modding/03-root.md:58-59` |
| 10 | No signature check on this path | documented code claim, **no quoted source excerpt** → UNVERIFIED/documented | `source/docs/HOW-IT-WORKS.md:83-84`; `source/modding/03-root.md:61-62` |
| 11 | `opkg` extracts `data.tar.gz` relative to `/APPS/pkgs`, not `/` | documented code/procedure | `source/docs/HOW-IT-WORKS.md:86-89`; `source/modding/03-root.md:77-79` |
| 12 | Dropbear is patched in `fill_passwd()` and at binary offset 15162 (`/etc/shells` → `/APPS/shell`) | documented code + build recipe | `source/docs/HOW-IT-WORKS.md:105-112`; `source/docs/BUILD.md:30-68` |
| 13 | The deployed Dropbear is static ARM32 | documented code | `source/docs/HOW-IT-WORKS.md:114-115` |
| 14 | Dropbear listens on 8008; 22 is dropped; 2222 times out; `Connection refused` means "allowed, nothing listening" | measured (recorded) | `source/docs/HOW-IT-WORKS.md:119-125`; `source/modding/01-system.md:72-81` |
| 15 | Root SSH gives uid 0, full capabilities, PTY, key-only | **measured (recorded)** | `source/ORIGINAL-README.md:12`; `source/modding/04-ssh.md:3-4` |
| 16 | PTY fails until `/dev/ptmx` and `/dev/pts/ptmx` are `chmod 666`; then `ssh -tt` works | measured (recorded) | `source/modding/04-ssh.md:56-58` |
| 17 | The daemon does not start at boot; re-arm with `83` then `82` | measured/documented procedure | `source/ORIGINAL-README.md:100-111`; `source/modding/05-limits.md:35-39`; `source/modding/04-ssh.md:70-84` |
| 18 | The re-trigger "kills the old daemon and starts a fresh one" | UNVERIFIED detail | `source/modding/04-ssh.md:84`; no `postinst` excerpt shows the kill |
| 19 | `/` and `/etc` are read-only (erofs + dm-verity enforcing), even for root | measured (recorded) | `source/modding/05-limits.md:5-15`; `source/docs/HOW-IT-WORKS.md:129-130` |
| 20 | setuid does not work on writable partitions | measured (recorded) | `source/modding/05-limits.md:20-23` ("stayed 314") |
| 21 | `/OAD` boot hooks are inert on this build | measured/documented | `source/modding/01-system.md:53-62`; `source/docs/HOW-IT-WORKS.md:131-133` |
| 22 | OTA probing found no usable image (`errorCode 205001`, 21 requests) | self-reported measurement | `source/modding/05-limits.md:58-62` |
| 23 | DevTools ports stayed closed after `devtoolSwitch = 2`, including cold boot | measured claim, "closed" undefined | `source/modding/06-open.md:25-28` |
| 24 | Persistence candidates exist but were not tested | UNVERIFIED | `source/modding/06-open.md:6-21`, `:40` |
| 25 | The chain is not generic; a different build breaks at least one assumption | documented conclusion | `source/ORIGINAL-README.md:14-15`, `:56-57` |

## What was actually captured vs. only documented

**Measured and recorded on the device:**

- The `postinst` privilege block: `POSTINST_RAN`, `Uid: 0 0 0 0`,
  `Gid: 0 0 0 0`, `CapEff: 000001ffffffffff`.
- Root SSH login (`ssh -p 8008`) with uid 0, full capabilities, key-only, and a
  working PTY after the ptmx mode change.
- Port behaviour: 8008 answered `Connection refused` when idle; 2222 timed out;
  port 22 was dropped.
- Mounts and permissions (`/proc/mounts`, `accessSync` probes for the writable
  set), SELinux enforcing, app-context capability mask, `chmod 4755` staying at
  uid 314.
- The install with empty options returning `0`, and with a `--tmp-dir` option
  returning `-1`.

**Quoted device code / configuration (documented, not re-run here):**

- `PackageInstall.js` and `SuperwatchCtrl.js` command construction and socket
  protocol.
- `fetchfile.js` write behaviour.
- `services/fetcher/package.json` permission block.
- `/etc/passwd` root line and the absent `/etc/shells`.
- The iptables rule and the two inert `/OAD` hooks.

**Documented but not evidenced by an excerpt:**

- The `postinst` internals ("creates `/APPS/.re_sshd`", "generates the host
  key", "opens `/dev/ptmx`", "starts dropbear").
- No signature check on this path.
- The socket group membership (stated as measured, but no `id`/`ls -l` output is
  included).
- The "kills the old daemon" detail on re-trigger.

## Artifacts

The record gives build sizes and hashes; **no binary and no key material is
shipped in this repository**. Both must be rebuilt from the documented patches.

| Artifact | Size | SHA-256 (recorded) |
|---|---:|---|
| `bin/dropbear-root` (patched at offset 15162) | 478,840 B | `536b5563d8fa357bfb461b2e3559caa085c57b33c73438e06a7fb117a5a97f4d` |
| `bin/dropbearkey` (unpatched) | 347,064 B | `738949933f67b8825423cef4a3db4fb759ee3a3206a521d4256153bdc8b6d33c` |
| Dropbear source tarball 2022.83 | — | `bc5a121ffbc94b5171ad5ebe01be42746d50aa797c9549a4639894a16749443b` |

Source: `source/docs/BUILD.md:108-113`; `source/docs/BUILD.md:10-16`. The upstream tarball is signed;
the record names the release key. Neither the tarball nor a binary is included.

Also recorded on the device: the host key (generated there), the root and
uid-314 key files, `/APPS/shell` containing `/bin/bash`, and the installed
package. None of these are reproduced here.

## Sanitization and provenance

Removed from this public page, and why:

| Removed | Why |
|---|---|
| Example LAN addresses from the record's commands | Replaced with `<tv-ip>` / `<host-ip>`; public docs should not carry example LANs |
| Public-key blobs and key comments from examples | Key material is not documentation |
| `authorized_keys` contents | Only paths and modes matter |
| Runtime session/message ids in examples | Device-run-specific; replaced with `<session>`. The installer package name is kept only where the command needs it. |
| The per-device state values and tile counts from the run | Not needed to reproduce; describes one device's state |
| References to the pairing certificate/token/session files as if obtainable from the repo | They are not shipped and must not be redistributed |
| Absolute host paths from the author's environment | Replaced with repository-relative paths |

Remaining, deliberately: platform paths (`/APPS`, `/OAD`, `/var/run/...`),
socket mode/group, sizes, hashes, package layout, patch offsets and the
commands required to reproduce the chain.

Provenance note: the sanitized source notes are included in
[`source/`](source/README.md). This page is an independent English restatement,
not a copy of vendor code. Where the notes contradict themselves, the narrower
reading is used and the correction is written down below.

## Corrections and contradictions

**C1 — The write primitive is `fetcher`, not `hiutils.fileRead`.**
`source/ORIGINAL-README.md:17` names "`hiutils.fileRead` / the `fetcher` FaaS service" as the
arbitrary-write path. The detailed documents describe only `fetcher`
(`source/docs/HOW-IT-WORKS.md:14-45`; `source/modding/02-write-and-exec.md:6-49`), and `source/modding/06-open.md:36-37`
says the earlier `fileRead` path crashed the service on binary content.
*Public wording:* the arbitrary write is the `fetcher` FaaS function's
`fetchFile`. `hiutils.fileRead` is not a write primitive and is not used by
this chain.

**C2 — Port 22 is not explained by a missing capability.**
`source/modding/04-ssh.md:51-52` says port 22 "would need `CAP_NET_BIND_SERVICE`, which the
context does not have". But the daemon is started by the root `postinst` with
`CapEff: 000001ffffffffff`. The missing capability is true of uid 314, not of
the root `postinst`.
*Public wording:* 8008 was free and allowed; 22 was dropped by the filter on
this build. No capability argument is used.

**C3 — The installer IPK has no single asserted location.**
`source/ORIGINAL-README.md:93` and `source/modding/04-ssh.md:80` use an `/APPS/...` path; `source/modding/06-open.md:53`
lists an "installer IPK" inside `/APPS/.re_sshd/`. The record does not say
whether it was copied or moved.
*Public wording:* the install page serves an installer IPK and triggers the
package manager; the exact path is installer-internal.

**C4 — "Three writes and one call".**
`source/ORIGINAL-README.md:89` says the page does "exactly three writes and one call", then
lists four numbered actions (`:91-94`).
*Public wording:* the page performs four actions — start `fetcher`, fetch
`sw2.js`, fetch the IPK, POST the install command. The count is not repeated.

**C5 — "Additive" vs runtime system-state changes.**
`source/modding/03-root.md:3-4` and `source/ORIGINAL-README.md:27-28` say no vendor file is replaced and `/`
stays read-only. `source/modding/04-ssh.md:58` changes `/dev/ptmx` and `/dev/pts/ptmx` to mode
666 at runtime, and the run leaves `/APPS/.re_sshd`, `/APPS/shell`, the package
`re.installer`, and tile edits.
*Public wording:* the path is additive in the sense that it does not replace a
vendor file or write a read-only partition, but it does change runtime device-
node modes and leaves files and a package behind.

**C6 — Re-trigger kill behaviour.** `source/modding/04-ssh.md:84` says the re-run "kills the
old daemon and starts a fresh one". No quoted `postinst` code shows a kill.
*Public wording:* the re-run re-executes the `postinst`, which restarts
Dropbear; the kill detail is UNVERIFIED.

**C7 — Socket group claim without raw output.** The record asserts that 616 is
in uid 314's supplementary groups but includes no `id`/`ls -l` transcript.
*Public wording:* the socket is `root:616` and the app context can connect
according to the record; the raw group listing is not part of the evidence.

**C8 — "Closed" DevTools ports.** `source/modding/06-open.md:27-28` says 9222/9223/9224
"stayed closed" without distinguishing refused from filtered.
*Public wording:* the ports did not accept a connection; which filter layer
applies is unknown.

**C9 — OTA result is self-reported.** `source/modding/05-limits.md:60-62` gives
`errorCode 205001` and 21 requests without a log or transcript.
*Public wording:* the record reports no usable OTA image for this model; it is
not independently checkable from the files.

**C10 — App context vs root session capabilities.** Not a contradiction, but
easy to misread: `source/ORIGINAL-README.md:12` ("full caps") describes root SSH;
`source/modding/README.md:12` (`CAP_SYS_NICE` only) describes uid 314.
*Public wording:* the two contexts are always named explicitly.

**Attribution.** The generated tables previously credited an older handle for
these two models; the inventory has been corrected to
[@oOHiyoriOo](https://github.com/oOHiyoriOo). This page uses that handle.

## Unknowns

- Whether `/APPS/pkgs/appinfo.json` entries with `Main: pkgapp://<pkg>/<script>`
  and `Persistent: true` are started by `systemserver` at boot, and with which
  uid.
- Whether the writable `run_phoenix.sh` is executed as root or uid 314, and
  whether a pre-`exec` line would run.
- The `systemserver` configuration format (not readable from uid 314).
- Whether a browser restart after `/OAD/enable_selenium` opens a debug port.
- Whether an installed IPK with `ProcessId`/start metadata is started at boot.
- When the launcher reloads `Appinfo.json` after an edit.
- The identity of the second port-filter layer.
- The `sendAPMMessage` message schema.
- The installer IPK's final location and what `83` leaves behind.
- A restore recipe for `/dev/ptmx` modes, `/APPS/shell`, `devtoolSwitch` and
  `/var/local/dab_debug`.
- Whether the no-signature-check claim holds beyond the record's assertion.

## Dead ends (do not repeat)

- **The HE40 chain does not transfer:** `/3rd_rw` hooks, `developer.sh`,
  `libtvsysinfo` shadowing, ext4/USB symlink delivery. None of it is present
  here and none applies (`source/ORIGINAL-README.md:42-43`; `source/modding/README.md:38-42`).
- **`/OAD` boot hooks** are inert on this build (`source/modding/01-system.md:53-62`).
- **setuid escalation** on writable partitions fails (`source/modding/05-limits.md:20-23`).
- **Low ports 22/2222** are not usable from the app context: 22 dropped,
  2222 timed out (`source/modding/01-system.md:72-81`).
- **OTA image search** produced no usable image (`source/modding/05-limits.md:58-62`).
- **DevTools ports** did not open after `devtoolSwitch = 2` and a cold boot
  (`source/modding/06-open.md:25-28`).
- **`hiutils.fileRead` as a write primitive** — conflated in one line, refuted
  by the detailed documents and by the binary-content crash.

## Limits of this evidence

- Only documentation was available; no IPK, FaaS script, `postinst`, binary or
  device was inspected.
- The strongest measurements are the `postinst` uid/capability block, the SSH
  result and the port behaviour. The `fetcher` write, socket access and
  dropbear deployment are documented and operationally relied upon, but lack
  raw transcripts in the record.
- The record has no measurement dates. "Reviewed 2026-11-04" is not a device
  verification date.
