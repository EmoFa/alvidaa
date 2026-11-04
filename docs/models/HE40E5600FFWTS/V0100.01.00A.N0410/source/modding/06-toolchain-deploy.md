# 06 — Toolchain & Deploy (No Package Manager)

**Status:** system/toolchain constraints **CONFIRMED**; Dropbear build + deploy confirmed live; the scripts in `../root/` are the final path.

---

## 1. No package manager

Live check (root):

```sh
for c in apt apt-get dpkg rpm opkg ipkg apk yum pacman; do command -v $c; done   # empty
ls -la /etc/opkg /etc/opkg.conf /var/lib/opkg /var/lib/dpkg /usr/lib/opkg        # missing
/bin/busybox --list | grep -E '^(opkg|dpkg|rpm|apk|ipkg)$'                      # empty
cat /etc/os-release                                                             # missing
```

**There is no package manager.** No `opkg install`, no `apt`, no package repo.  
**Deploy = copy files + make executable + start.** No "installation" in the distro sense.

---

## 2. Building for the TV

| Constraint | Value |
|---|---|
| Architecture | ARMv7, EABI5, hard-float, VFPv4/NEON |
| Kernel | 3.18.25; no overlayfs, no devtmpfs, devpts yes |
| TV libc | glibc 2.18 (`/lib/libc-2.18.so`, `ld-linux.so.3`) |
| Host cross | `arm-linux-gnueabihf-gcc`, `-as`, `-ld`, `-objcopy` |
| Static | **recommended**; `-static`; the bundled Dropbear is static and runs |
| Dynamic | only with TV glibc 2.18/sysroot; otherwise `GLIBC_2.xx not found` |
| Package manager | none |

### 2.1 Simple static tool

```bash
cat > hello.c <<'EOF'
#include <stdio.h>
int main(){ printf("hello tv\n"); return 0; }
EOF
arm-linux-gnueabihf-gcc -static -Os -o hello hello.c
file hello
# ELF 32-bit LSB executable, ARM, EABI5, statically linked
```

Deploy:

```bash
# via SSH (always works, even without SFTP)
base64 -w0 hello | ssh root@192.0.2.94 'base64 -d > /3rd_rw/bin/hello && chmod 755 /3rd_rw/bin/hello'
# or via File.download (HTTP -> /3rd_rw/appdata) + root_loop cp/chmod
# or directly after optional SFTP install: scp hello root@TV:/3rd_rw/bin/
```

**Note:** Dropbear alone has no sftp-server. The final folder contains a static OpenSSH-9.9p1-sftp-server + patched Dropbear; after `../root/scripts/host/install_sftp.sh`, `sftp` and modern `scp` (SFTP) work. Before that: `ssh` + `base64`/`cat`/`tar` or `File.download`. `tar` is present on the TV (BusyBox).

### 2.2 Dynamic tool (only if needed)

- Link against **TV glibc 2.18** (sysroot/headers from the TV or a matching older sysroot); otherwise the loader fails.
- The bundled Dropbear is **static** (glibc 2.39) and runs on the 3.18 kernel; that is the pragmatic path.
- Mind `LD_LIBRARY_PATH`/`RPATH`; the TV libs are in `/lib`, `/basic/lib`, `/3rd/lib`, `/3rd/opera4xLib`, `/3rd_rw/...`.

---

## 3. Dropbear (SSH) — build + deploy

The final binaries are in `../root/tools/pub/`:

```
dropbear       882204 B  SHA256 976ec57e401765d5fc9c0a201d19c997c004dcf91a8d4bdb039bbb8419071eae
dropbear-sftp  882204 B  SHA256 a21b0d3e53dd1d124105350319df45a2b44e7cef70dd29b418644b11fdcfed57
dropbearkey    755452 B  SHA256 3fbfa60891b3a9f3e971a24071ed4d14c93ee3e773dd6f4969646cc811b0dbbf
sftp-server    635680 B  SHA256 d0f7700e84e582aef3948c29e4317fb0119e13393374a7455922ffa8d01202f3
```

### 3.1 Repro build

```bash
cd <repo-root>
root/scripts/host/build_dropbear.sh
```

The script uses `sources/dropbear-2022.83.tar.bz2` (SHA below), configured with:

```
--host=arm-linux-gnueabihf
--disable-zlib --disable-pam --disable-shadow
--disable-lastlog --disable-utmp --disable-wtmp
--disable-utmpx --disable-wtmpx
--disable-pututline --disable-pututxline
CC=arm-linux-gnueabihf-gcc CFLAGS="-Os -static" LDFLAGS="-static"
```

and `localoptions.h`:

```c
#define DROPBEAR_SVR_PASSWORD_AUTH 0
#define DROPBEAR_SVR_PUBKEY_AUTH 1
#define DROPBEAR_CLIENT 0
```

- **Key-only:** password auth is off at compile time; no `-s` flag needed (this build does not know `-s`).
- **`--disable-shadow`:** no `/etc/shadow` access; pubkey auth.
- **Static:** no TV lib dependency.
- **`dropbearkey`:** generate the host key (`-t ed25519 -f /3rd_rw/sshd/host_key`).
- **`dropbear-sftp`:** `build_dropbear.sh` calls `patch_dropbear_sftp.py` at the end; this patches `SFTPSERVER_PATH` to `/3rd_rw/sshd/sftp-server` (same string length, no ELF offsets). The static `sftp-server` comes from `build_sftp_server.sh`.

### 3.2 Deploy on the TV

1. `../root/scripts/host/upload_to_appdata.js` (TV console): uploads `dropbear`, `dropbear-sftp`, `dropbearkey`, `sftp-server`, `authorized_keys`, `start_sshd.sh`, `root_loop.sh`, `hamservice-wrapper.sh`, `deploy_sshd.sh`, `verify.sh`, `rollback.sh` to `/3rd_rw/appdata`.
2. `../root/scripts/host/run_root_cmd.js` with `/bin/sh /3rd_rw/appdata/deploy_sshd.sh`.
3. `deploy_sshd.sh`:
   - copies the binaries to `/3rd_rw/sshd` (uses `dropbear-sftp` and installs `sftp-server` if present);
   - generates the host key (Ed25519);
   - copies `/etc/passwd` → `/3rd_rw/sshd/etc_passwd` with root home `/3rd_rw/sshd/home` and **bind-mounts** it over `/etc/passwd`;
   - mounts devpts on `/dev/shm/pts` and bind-mounts it over `/dev/pts`;
   - sets `authorized_keys` (600), `.ssh`/home 700;
   - starts Dropbear on `0.0.0.0:22`, key-only;
   - installs the `HamService` wrapper;
   - checks processes/port/log/host key.

### 3.3 PTY workaround

`/dev` is part of the **ro squashfs** (no devtmpfs); `/dev/pts` contains static nodes 136,0–4; `/dev/ptmx` is c 5,2. `mount -t devpts` directly on `/dev/pts` fails (ro target).

```sh
mkdir -p /dev/shm/pts
mount -t devpts -o mode=620,ptmxmode=666,gid=5 devpts /dev/shm/pts
mount --bind /dev/shm/pts /dev/pts
```

- `/dev/ptmx` remains the static node; `openpty` works with it.
- `start_sshd.sh` does this on every start; the `HamService` wrapper calls it at boot.
- Fallback without PTY: `ssh -T root@192.0.2.94 'id'`.

### 3.4 Root home / authorized_keys

- Root home `/basic` is **ro**; Dropbear needs `~/.ssh/authorized_keys`.
- Solution: `/etc/passwd` copy with `root:x:0:0:root:/3rd_rw/sshd/home:/bin/sh` and a **bind mount** over `/etc/passwd`; the ro original file stays unchanged.
- `authorized_keys`: your public key (600, root); `.ssh`/home 700.
- **No `/etc/shadow` modification**, no password.

### 3.5 Host key / connection

```
Host-Key: <host-key-fingerprint>
Login:    ssh root@192.0.2.94
```

Confirm the fingerprint on first connect. The host key stays in `/3rd_rw/sshd/host_key` (rw, survives reboot).

### 3.6 SFTP (optional, key-only)

Dropbear has no sftp-server of its own; the server execs the compile-time
`SFTPSERVER_PATH` (default `/usr/libexec/sftp-server`). The ro rootfs does not allow a file there. The final folder therefore ships:

- `../root/tools/pub/sftp-server` — **static** OpenSSH-9.9p1-sftp-server
  (ARM, 635,680 B; no glibc 2.18 problem)
- `../root/tools/pub/dropbear-sftp` — Dropbear with
  `SFTPSERVER_PATH=/3rd_rw/sshd/sftp-server`
- `../root/sources/openssh-9.9p1.tar.gz` + `build_sftp_server.sh` — repro build
- `../root/scripts/host/install_sftp.sh` — install/test/swap
- `../root/scripts/tv/{install_sftp_stage.sh,enable_sftp.sh,swap_sftp.sh}`

**Build:**

```bash
cd <repo-root>
root/scripts/host/build_sftp_server.sh     # OpenSSH sftp-server, static ARM
root/scripts/host/build_dropbear.sh        # dropbear + dropbear-sftp
```

**Install (simplest path, from the host with your SSH key):**

```bash
cd <repo-root>
root/scripts/host/install_sftp.sh
# optional: TV=root@192.0.2.94 SSH_KEY=~/.ssh/id_ed25519 ...
```

Sequence:

1. uploads `sftp-server` + `dropbear-sftp` via `ssh` (not scp!) to
   `/3rd_rw/appdata`;
2. starts a **test Dropbear on port 2222**; port 22 stays untouched;
3. tests `sftp -P 2222` (real SFTP session);
4. only on success: backup `dropbear.nosftp`, swap on port 22, restart;
5. tests `sftp` on port 22.

**After that:**

```bash
sftp root@192.0.2.94
# pwd, ls /3rd_rw/UI, put local-file /3rd_rw/UI/, get /3rd_rw/UI/index.html, bye
```

Modern `scp` (OpenSSH 9+) also uses SFTP and then works:

```bash
scp /local/file root@192.0.2.94:/3rd_rw/UI/
```

**Rollback:**

```bash
ssh root@192.0.2.94 \
  'cp -f /3rd_rw/sshd/dropbear.nosftp /3rd_rw/sshd/dropbear; \
   kill $(cat /3rd_rw/sshd/dropbear.pid) 2>/dev/null; \
   /bin/sh /3rd_rw/sshd/start_sshd.sh'
```

**Security:** SFTP runs as root, key-only, on the LAN; the same access as SSH.
Do not expose it to the internet. The sftp-server is static and has no
TV glibc dependency.

---

## 4. Deploy paths (without a package manager)

| Path | When | Example |
|---|---|---|
| **`File.download`** (browser root) | HTTP file → `/3rd_rw/appdata` | `HiBrowser.File.download("http://<host>:9000/pub/x","x",1)` |
| **`File.write`** (browser root) | text (scripts/JSON) → appdata | `HiBrowser.File.write("root_cmd.sh","id\n",1)` |
| **Root loop** | commands/deploy as root | `root_cmd.sh` → `root_out.txt` |
| **SSH + base64** | binary files to `/3rd_rw` | `base64 -w0 x \| ssh root@TV 'base64 -d > /3rd_rw/bin/x'` |
| **SSH + tar** | multiple files | `tar czf - dir \| ssh root@TV 'tar xzf - -C /3rd_rw'` |
| **USB** | files on an ext4 stick | symlink/file; the TV mounts `/mnt/usb/<dev>` |
| **`scp`/`sftp`** | **after optional SFTP install** | `../root/scripts/host/install_sftp.sh`; then `sftp root@TV` / `scp file root@TV:/3rd_rw/...` |

- **`File.download`** writes binary files byte-exact; the target path must be in the whitelist (`/3rd_rw/appdata`, `/dev/shm/shm_tmp`, `/3rd/launcher/data`) or reachable via the USB symlink bypass.
- **`File.write`** writes text; binary data → `EINVAL`; for binary use `File.download`.
- **SSH** is key-only; `root`; `/3rd_rw`/`/data`/`/perm` rw.

---

## 5. Checks / verification

### 5.1 Host

```bash
cd <repo-root>
sha256sum -c SHA256SUMS
root/scripts/host/build_payload.sh          # reproduces 37b13f…
file root/tools/pub/dropbear                # static ARM
```

### 5.2 TV

```sh
/bin/sh /3rd_rw/appdata/verify.sh
# or:
cat /3rd_rw/root_proof.txt
ps | grep -E 'dropbear|root_loop'
cat /proc/net/tcp | grep :0016
grep '^root:' /etc/passwd
ls -l /3rd_rw/sshd/home/.ssh/authorized_keys
```

### 5.3 SSH

```bash
ssh root@192.0.2.94 'id; cat /proc/self/status | grep -E "^(Uid|Gid|CapEff):"'
ssh -T root@192.0.2.94 'uname -a' 2>/dev/null || true
```

- `uid=0(root)`; `CapEff=0000003fffffffff`.
- PTY: interactive shell; `ssh -T` as fallback.

### 5.4 SFTP (after install)

```bash
printf 'pwd\nls /3rd_rw/UI\nbye\n' | sftp root@192.0.2.94
# on the TV:
grep -a 'sftp-server' /3rd_rw/sshd/dropbear
# -> /3rd_rw/sshd/sftp-server
```

- If `sh: /usr/libexec/sftp-server: No such file` appears, the unpatched
  Dropbear is still active: `root/scripts/host/install_sftp.sh`.
- Test Dropbear/logs: `/3rd_rw/sshd/dropbear2222.log`, `swap.log`,
  `dropbear.log`; backup `/3rd_rw/sshd/dropbear.nosftp`.

---

## 6. Limits / unknowns

- **Static** is the safe path; dynamic binaries need TV glibc 2.18.
- **No package manager** → no automatic dependency/update handling.
- **`/dev` ro/no devtmpfs** → PTY workaround needed; other device nodes are static.
- **No overlayfs** → bind mounts; replace ro files via `developer.sh`.
- **SFTP** is optional: Dropbear alone has no sftp-server; the static OpenSSH-sftp-server + patched Dropbear are installed via `install_sftp.sh`. Before that `ssh`+`base64`/`tar`/`File.download`.
- **`/3rd`/rootfs 100% full**; new data goes to `/3rd_rw`/`/data`; no flashing.
- **UI/AM internals** (`Hisense_*`, `guijs`/`TVAPI`, `app_man`, `LauncherService`) are not fully documented; test in DevTools/on the TV.
- **DRM/`securetime`**, Netflix/Cobalt/Amazon, OTA/`checker.sh` are not part of the root/deploy path; test deactivation.
- **No secrets**: no root hash, no private key in this folder.
