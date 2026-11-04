# 100U7Q / V0000.09.60I.Q0813 — root SSH over the package manager

**Status:** root SSH (uid 0, full capabilities, PTY, key-only) was recorded on
this exact model and firmware. There is **no automatic boot persistence** on
this build: re-arm after every reboot. This chain is unrelated to the HE40
chain and to [the 50A51HUV / MTK9602 guide](../../50A51HUV/09.01O.P0813/README.md); do not mix them.

> **Applies only to `100U7Q` (`100U70QEVS`, SerialType `100U7QE`) running
> `V0000.09.60I.Q0813` (VIDAA `U09.60`, region EU_A).**
> The chain rests on four properties of this build. A different firmware
> almost certainly breaks at least one of them.

> `source/...` citations point into the sanitized research notes included in
> [`source/`](source/README.md). This page is the reviewed English guide; see
> [EVIDENCE.md](EVIDENCE.md) for the claim matrix.

## What this is

A LAN-only root path that abuses the TV's own local service stack:

1. **Pairing.** The TV exposes an MQTT/TLS control interface on port 36669. A
   client authenticates with the vendor app's certificate and a PIN shown on
   screen; the resulting session is per TV.
2. **Local service host.** The TV's web app talks to a local Node service
   ("phoenix") at `https://localhost:9888` (fallback `http://localhost:9009`).
3. **Arbitrary write.** The `fetcher` FaaS service has an **empty permission
   block** and is reachable at `/service/basic/fetcher`. Its `fetchFile` writes
   a downloaded file to an absolute path as **uid 314**, so you can place an
   installer IPK in the writable app area.
4. **Privileged package helper.** `pkgmgr` does not install anything itself; it
   sends an install command (`82`) to `/var/run/superwatch_socket`
   (`srw-rw---- root 616`). Group 616 is in uid 314's group set, so the app
   context can talk to the root daemon. The daemon runs `opkg install` as root,
   which executes the IPK's `postinst` with **uid 0** and
   `CapEff: 000001ffffffffff`.
5. **Root SSH.** The `postinst` deploys a patched static Dropbear 2022.83 that
   rewrites the root home/shell via `fill_passwd()`, listens on **port 8008**
   and is key-only. PTY needs `/dev/ptmx` opened up at runtime.

Recorded result: `ssh -p 8008 root@<tv-ip>` gives uid 0 with full capabilities
and a PTY.

## What this is not

- **Not a flash, firmware image or bootloader change.** `/` is erofs,
  read-only, dm-verity enforcing; nothing here writes it.
- **Not a persistent root.** No writable path is executed at boot. A daemon
  started by the `postinst` lives until the next reboot; you re-arm it
  manually.
- **Not generic VIDAA.** It does not transfer to the HE40 (`/3rd_rw` hooks,
  `developer.sh`, `libtvsysinfo` shadowing, ext4/USB symlink delivery) or to
  other firmware.
- **Not "nothing is changed".** It does not replace a vendor file, but it does
  change runtime modes on `/dev/ptmx` and `/dev/pts/ptmx`, and it leaves
  `/APPS/.re_sshd`, `/APPS/shell`, the package `re.installer`, and any tile
  edits behind.
- **Not a credential bundle.** No certificate, token, session, key or device
  identifier is shipped. Pairing is yours to perform.
- **Not proven to be cleaned up by one command.** Full rollback is operator-
  defined; see [Rollback](#rollback).

## At a glance

| | |
|---|---|
| Model | `100U7Q` (`100U70QEVS`, SerialType `100U7QE`), region EU_A |
| Firmware | VIDAA `U09.60`, `V0000.09.60I.Q0813` |
| SoC | MediaTek **MT9655** |
| OS / userland | kernel **5.15.192**, **32-bit ARM** userland (`EM_ARM`), SELinux **enforcing**, app context uid 314 with `CapEff=0x800000` (`CAP_SYS_NICE` only) |
| Result | root SSH on TCP **8008**: uid 0, full capabilities, PTY, key-only |
| Persistence | **none automatic**; re-arm with uninstall `83` + install `82` after each reboot |
| Last verified | device measurements are undated in the record; record reviewed 2026-11-04 |

Storage and permission constraints:

| Path | Mode | Notes |
|---|---|---|
| `/` | erofs, **ro**, dm-verity enforcing | `/etc` cannot be edited, even as root |
| `/application` | erofs, **ro** | |
| `/APPS` | ext4, **rw**, `nosuid,nodev` | writable by uid 314 |
| `/OAD` | ext4, **rw**, `nosuid,nodev` | OTA staging; writable by uid 314 |
| `/data` | ext4, **rw**, `nosuid,nodev` | **not** writable by uid 314 |
| `/certificate` | ext4, **rw**, `nosuid,nodev,noexec` | |

A setuid binary on any writable partition is ignored (`nosuid`; verified:
`chmod 4755` still executed as uid 314).

## Prerequisites

- The **exact** model and firmware. The record is explicit that this is not a
  generic chain.
- A TV **you own**, on your LAN.
- The [sidee](https://github.com/alvidaa/sidee) pairing tool. It carries its own
  client certificate; **neither sidee nor your session is shipped here**, and
  the certificate/session must not be redistributed.
- A host in the same LAN that the TV can reach over HTTP (for the installer
  page and the IPK).
- Your own SSH key pair. Only the public key is passed to the installer.
- A backup of `/APPS/websdk/Appinfo.json` before any tile work — it is the
  launcher's tile registry (`311:713`, `0660`) and malformed JSON can empty the
  launcher.

> Pairing is a LAN operation against your own TV. Do not retrigger the PIN
> request: each retrigger rotates the PIN, and repeated wrong PINs lock the
> client out temporarily (`rc=5 NOT AUTHORIZED`).

## Chain at a glance

```
sidee + vendor cert + on-screen PIN
  └─ authorised MQTT session for your TV (session file, mode 600)
       └─ TV web app → phoenix (https://localhost:9888)
            └─ FaaS route /service/basic/fetcher  ("permission": {})
                 └─ fetchFile(url, directory, permission)   → write as uid 314
                      └─ installer IPK into a writable path under /APPS
                           └─ pkgmgr → /var/run/superwatch_socket  (82 = install)
                                └─ root daemon: opkg install <ipk>
                                     └─ IPK postinst: uid 0, CapEff 000001ffffffffff
                                          └─ patched Dropbear 2022.83 static ARM32
                                               fill_passwd(): root home/shell override
                                               /APPS/shell (replaces /etc/shells, offset 15162)
                                               chmod 666 /dev/ptmx /dev/pts/ptmx
                                               listen on 0.0.0.0:8008
                                                    └─ key-only root SSH + PTY
```

## Step by step

Paths use the published tool tree (`tools/u7q/`). Placeholders: `<tv-ip>`,
`<host-ip>`, `<pubkey>`, `<session>`, `<pkg>`.

### 0. Pair with the TV

```sh
tools/u7q/scripts/pair.sh --tv <tv-ip> --sidee <sidee-checkout>
```

or directly with sidee:

```sh
python3 sidee.py pair <tv-ip>
```

The TV shows a four-digit PIN. Enter it once. On success the session lands in
`~/.sidee/session.json` with mode `600`; you never need to read it.

The TV's identity for pairing is its **Ethernet MAC with colons** — the record
states that a retail model number or a random UUID does not work. Use your own
device's value; nothing is hardcoded in this repository.

### 1. Build the installer and serve it

```sh
tools/u7q/scripts/install.sh \
    --pubkey "<pubkey>" \
    --host <host-ip> \
    --port 9000 \
    --tv <tv-ip> \
    --launch
```

`--launch` uses the paired session to open the install tile. Without it, open
`http://<host-ip>:9000/install.html` on the TV yourself (for example through a
tile you already control).

The installer builds a per-device IPK containing the patched Dropbear and your
public key, and serves it. It ships no binary: `tools/u7q/bin/` is a drop point
for **your own** static ARM32 build (see [Build](#build-the-patched-dropbear)).

### 2. What the install page does

The page performs four actions, in order:

1. start the `fetcher` service over WebSocket (`method: "start"`);
2. `fetchFile` the superwatch helper (`sw2.js`) into the FaaS function tree;
3. `fetchFile` the installer IPK into a writable path under `/APPS`;
4. `POST /function/system/fetch/sw2` with the install command.

The page **serves an installer IPK from your host and triggers the package
manager**. The record does not establish a single final path for that IPK (it
appears both as an `/APPS/...` path and inside `/APPS/.re_sshd/` in different
lines); treat the path as installer-internal.

The install message the helper sends is:

```
<session>:82:<session>;<absolute ipk path>;<pkg>;<options>
```

**Options must be empty.** With a `--tmp-dir` option the daemon answered `-1`;
with an empty option field it answered `0`. Command ids: `80/81` backup,
`82` install, `83` uninstall, `84` rollback, `85` directory size. Replies are
`<session>:<code>`; `0` = OK, `604` = invalid id, `-1` = failure.

### 3. Root `postinst`

`opkg install` runs as root, so the package's `postinst` runs with:

```
Uid:    0   0   0   0
Gid:    0   0   0   0
CapEff: 000001ffffffffff
```

That is full capability, including `CAP_SYS_ADMIN`, `CAP_MKNOD`, `CAP_NET_ADMIN`
and `CAP_SETUID`.

**Packaging trap:** `opkg` extracts `data.tar.gz` relative to `/APPS/pkgs`, not
to `/`. A member `APPS/.re_sshd/x` lands at `/APPS/pkgs/APPS/.re_sshd/x`; the
`postinst` must move it. `control` needs at least `Package`, `Version`,
`Architecture: mtk9655`, `AppId`, `AppName`; `postinst` is `0755`.

The record states there is no signature check on this path
(`checkIpkSignature` only in the store-update flow). That is a **documented code
claim without a quoted source line** in the record; treat it as
**UNVERIFIED/documented**, not as proven here.

### 4. Deploy and start Dropbear

The `postinst` is documented as creating `/APPS/.re_sshd`, deploying the
binaries, writing the key files, generating the Ed25519 host key, opening
`/dev/ptmx`, and starting Dropbear on 8008. The `postinst` script itself is not
quoted in the record, so these are **documented actions**, not separately
evidenced steps.

Deployed layout:

```
/APPS/.re_sshd/
  dropbear-root                   0755
  dropbearkey                     0755
  hostkey_ed25519                 0600   (generated on device)
  root_home/.ssh/authorized_keys  0600   root:root, home 0700
  home/.ssh/authorized_keys       0600   314:314 (the uid-314 login "re")
/APPS/shell                       contains "/bin/bash"
```

Manual start (the same command the installer uses):

```sh
cd /APPS/.re_sshd
./dropbear-root -s -r /APPS/.re_sshd/hostkey_ed25519 -p 8008 -P dropbear.pid
```

`-s` disables password logins. **Why 8008:** the packet filter drops TCP
`0:1023` and at least one further layer filters more. The signal is the error:
`Connection refused` means "allowed, nothing listening"; a timeout means
"dropped". 8008 was free and allowed. Port 22 was dropped on this build; 2222
timed out. The port choice is an operational result of that filter, not a
statement about the root `postinst`'s capabilities.

### Build the patched dropbear

Do this before step 1 if you have not built the binary yet.

The installer does not ship or download a binary; it packages **your** build
from the drop point. Put the result at `tools/u7q/bin/dropbear-root` and
`tools/u7q/bin/dropbearkey` before running `install.sh`.

Upstream is Dropbear SSH 2022.83 (GPLv2). Two patches are required:

1. `common-session.c`, `fill_passwd()`: for an unknown user, fall back to
   `re` / uid 314 / gid 314 / `/APPS/.re_sshd/home` / `/bin/bash`; for a
   resolved uid 0, force `pw_dir=/APPS/.re_sshd/root_home` and
   `pw_shell=/bin/bash`.
2. Binary field patch: replace the 11-byte literal `/etc/shells` at file offset
   **15162** with `/APPS/shell` (same length), and make `/APPS/shell` contain
   `/bin/bash`.

Why: `/etc/passwd` has `root:x:0:0:root:/basic:/etc/rootlogin.sh`; `/basic` is
on the read-only, dm-verity protected root, and `/etc/shells` does not exist, so
musl's `getusershell()` returns NULL and Dropbear rejects every login
(`User 'x' has invalid shell, rejected`).

Build with any toolchain that produces a static ARMv7 EABI5 binary (the record
used zig's musl cross compiler; `arm-linux-gnueabihf-gcc -static` also works):

```sh
./configure --host=arm-linux-musleabihf \
  --disable-zlib --disable-syslog --disable-lastlog \
  --disable-utmp --disable-wtmp --disable-utmpx --disable-wtmpx \
  CFLAGS="-Os -static" LDFLAGS="-static -no-pie"
make -j"$(nproc)"
strip dropbear dropbearkey
python3 apply_patch2.py
```

Result: `ELF 32-bit LSB executable, ARM, EABI5, statically linked, stripped`.
Recorded artifact: 478,840 bytes after patching, SHA-256
`536b5563d8fa357bfb461b2e3559caa085c57b33c73438e06a7fb117a5a97f4d`.

### 5. Connect

```sh
ssh -p 8008 -i <key> root@<tv-ip>
```

Expect uid 0 with full capabilities. Key-only: password auth is disabled.

**PTY:** `/dev/ptmx` is `root:tty 0620` and uid 314 is not in group `tty`, so
PTY allocation fails with `openpty: Permission denied` until the `postinst`
sets `chmod 666 /dev/ptmx /dev/pts/ptmx`. After that, `ssh -tt` works.

Dropbear also refuses key files whose home/`.ssh` ownership or modes are wrong.
For root: home `0700`, `authorized_keys` `0600`, root-owned. The uid-314 login
uses `/APPS/.re_sshd/home/.ssh/authorized_keys`.

### 6. Re-arm after a reboot

Nothing starts the daemon automatically, and the package stays installed, so
`postinst` does not run again by itself. Send uninstall then install:

```sh
tools/u7q/scripts/trigger.sh --host <host-ip> --tv <tv-ip> --launch
```

The page sends:

```js
{list: [
  "70:83:70;re.installer",
  "71:82:71;<ipk>;re.installer;"
]}
```

The record says the re-run kills the old daemon and starts a fresh one; the
`postinst` code that would do the kill is not quoted, so treat that detail as
**UNVERIFIED**.

## Verification: what proves success

| Check | Proves | Evidence class |
|---|---|---|
| `POSTINST_RAN`, `Uid: 0`, `CapEff: 000001ffffffffff` from a test package | the `postinst` executes as root with full capabilities | **measured and recorded** (the strongest evidence in this chain) |
| `ssh -p 8008 root@<tv-ip>` → uid 0, full caps, key-only | root SSH works | measured and recorded |
| `ssh -tt` works after the ptmx chmod | PTY works | measured and recorded |
| 8008 answers `Connection refused` while idle; 2222 times out; 22 is dropped | port choice is correct for this build | measured and recorded |
| Install page start → fetch → fetch → POST returns `0` | the package manager accepted the install | documented procedure, operationally relied on |
| `fetcher` write succeeded | file placed for the installer | documented code plus operational use; no standalone write log in the record |
| A reboot brings SSH back by itself | nothing; this is not how the build behaves | **not applicable — no autostart**; uninstall `83` + install `82` is required |
| Full cleanup removes everything | — | **UNVERIFIED**; `83` does not remove `postinst` side effects |

## Rollback

```sh
# uninstall the package through the same socket path (command 83)
{list: ["70:83:70;re.installer"]}
```

or use the trigger page's uninstall-only variant. `83` removes the package and
its data files, but **not** everything the `postinst` created outside the
package's data list.

Operator checklist for a fuller cleanup (each item must be verified by you):

- stop the Dropbear process (`/APPS/.re_sshd/dropbear.pid`) before removing the
  directory;
- remove `/APPS/.re_sshd/` and `/APPS/shell`;
- restore `/dev/ptmx` and `/dev/pts/ptmx` modes if you care about the exact
  pre-run state (the record gives no restore command);
- restore `/APPS/websdk/Appinfo.json` from your backup if you edited tiles;
- remove `/OAD/enable_selenium` (it also expires after 24 h);
- `devtoolSwitch = 2` and `/var/local/dab_debug` were also left set during the
  research; the record does not give a reset recipe.

There is **no documented single rollback** that restores all of this; the
record says only "track what you create". Full rollback is **UNVERIFIED**.

## Limits / not proven

Root does **not** unlock:

- **Writes to `/` or `/etc`.** erofs + dm-verity enforcing; `/etc/rc.d/rc.local`
  is immutable even for root.
- **A boot hook.** No writable path is executed by the boot chain; the two
  `/OAD` candidates are inert on this build (`init_kilby.rc` hardcodes
  `kilbyDebug=0`; `3rd_overlayfs.sh` requires `init=/sbin/preinit` plus a
  marker file and would overlay `/3rd`, not `/etc`).
- **setuid.** All writable partitions are `nosuid`.
- **An automatic daemon restart.** Re-arm manually after every reboot.
- **Low ports from the app context.** The filter drops `0:1023`, and a second
  layer filters more. (This statement is about the app context; the root
  `postinst` has full capabilities.)
- **Root-only files from the app context.** uid 314 has only `CAP_SYS_NICE`,
  SELinux enforcing, no `CAP_DAC_OVERRIDE`; `/etc/shadow` gives `EACCES`.
- **Firmware/OTA recovery.** OTA probing found no usable image for this model
  (`errorCode 205001`, 21 requests); there is no known public channel.

Also unproven or open:

- Boot persistence candidates (`/APPS/pkgs/appinfo.json` with
  `Main: pkgapp://…`, `Persistent: true`; a line in the writable
  `run_phoenix.sh`; the `systemserver` start list) were **not tested**, and the
  run uid of those paths is unknown.
- DevTools: `devtoolSwitch = 2` survived a reboot but ports 9222/9223/9224
  stayed closed, including after a cold boot. `/OAD/enable_selenium` was
  written; whether a browser restart opens a port is not verified.
- Reading vendor binaries from the FaaS context was not attempted; the earlier
  `fileRead` path crashed the service on binary content.
- `tvinfo.sendAPMMessage(...)` is not permission-gated, but its schema is
  unknown and it was not exercised.
- Whether an installed IPK with `ProcessId`/start metadata is started at boot.
- When the launcher reloads `Appinfo.json` after an edit.
- No signature check on this path: documented claim, no quoted source.
- The exact second port-filter layer is unidentified.

## Tools

| Path | Purpose |
|---|---|
| [tools/u7q/](../../../../tools/u7q/) | entry point for the 100U7Q tree |
| [scripts](../../../../tools/u7q/scripts) | `pair.sh`, `install.sh`, `trigger.sh`, `make_installer.py`, `launch_tile.py` |
| [web](../../../../tools/u7q/web) | `install.html`, `trigger.html`, local server |
| [faas](../../../../tools/u7q/faas) | `sw2.js`, the browser-side superwatch helper |
| [bin](../../../../tools/u7q/bin) | drop point for **your own** static ARM32 Dropbear builds |

`tools/u7q/bin/` ships no binaries by design: the upstream is GPLv2 and the
build patches are documented above; supply your own build.

## Evidence and modding

- [EVIDENCE.md](EVIDENCE.md) — identity, claim matrix, captured vs documented,
  artifacts, sanitization and the corrections (including the `fetcher` vs
  `hiutils.fileRead` conflation).
- [MODDING.md](MODDING.md) — mounts, boot constraints, launcher/UI surface,
  persistence candidates and the verified/unverified split.
- [method inventory](../../../research/EXPLOITS.md) and
  [50A51HUV findings](../../50A51HUV/09.01O.P0813/FINDINGS.md) — method inventory and lab notebook.
- [inventory](../../../research/inventory.json) — the machine-readable row.

## Attribution

Research and the original 100U7Q record: [@oOHiyoriOo](https://github.com/oOHiyoriOo).
Source: the sanitized research notes in [`source/`](source/README.md). The
bundled Dropbear is GPLv2; this page is original English text under the
repository's MIT license — see [LICENSE](../../../../LICENSE) and
[SECURITY.md](../../../../SECURITY.md).
