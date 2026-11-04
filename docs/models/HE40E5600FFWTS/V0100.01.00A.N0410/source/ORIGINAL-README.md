# Hisense HE40E5600FFWTS — Root & Modding — Final Documentation

> **Publication note:** this public tree does not ship the vendor binaries
> (`tvi_original.so`, `libtvsysinfo.so`) or device-specific key material
> (`authorized_keys`, host-key fingerprint). Paths in the listings below are
> kept for documentation — recreate the artefacts from your own device.

**One folder, two sections, no more searching.**
**TV:** Hisense HE40E5600FFWTS, FW `V0100.01.00A.N0410`, LAN `192.0.2.94`
**Host:** Linux, Python 3, `arm-linux-gnueabihf-*`; host IP in the example `192.0.2.150`
**Status:** 2026-10-26 — root + Dropbear SSH (key-only) + PTY confirmed live; boot persistence installed (reboot test pending). SFTP optional (static OpenSSH sftp-server + patched Dropbear).

---

## The three questions in 30 seconds

### Which Linux?
**Hisense/MediaTek Embedded Linux**, not a standard distro:
- Linux **3.18.25**, ARMv7 (Cortex-A53, NEON/VFPv4), MediaTek **MT53xx/MT5863** class (`mt53xx-emmc`, `mt5863_sa_768_linux`)
- **glibc 2.18**, **BusyBox 1.18.5**, SysV init (`inittab`/`rcS`/`rc.local`), **no systemd**
- No `/etc/os-release`; firmware `V0100.01.00A.N0410`
- **squashfs-ro**: `/` (38.8 MB, 100 %), `/3rd` (141 MB, 100 %)
- **ext4-rw**: `/3rd_rw` (1.1 GB, 56 %), `/data` (1.9 GB), `/perm` (3.9 MB); `/spdata` ro
- **No overlayfs** → modding via rw partitions + `mount --bind`

### Is there a package manager?
**No.** No `apt`, `dpkg`, `opkg`, `ipkg`, `rpm`, `apk`, `yum`, `pacman`; no `/etc/opkg`/`/var/lib/dpkg`.  
**Consequence:** build static ARM binaries/shell scripts and get them to `/3rd_rw` via `File.download`/SSH/`base64`/`tar`. No `opkg install`.

### Where is the UI and how does it run?
TV UI = web UI in the **`hisenseUI` browser** (root, GLES):

```
/basic/autorun.sh (line 168)
  → /3rd/opera4x/hisenseUI/start-UI.sh
    → ./bin/hisenseUI --hw-gles --jsplugins-dir=/3rd/UI_jsplugins \
         --disable-web-security ... -u /3rd_rw/UI/index.html
```

- **UI:** `/3rd_rw/UI/index.html` (PIXI), UI process `hisenseUI` (e.g. PID 589), DevTools **9223**
- **Launcher/apps:** `/3rd_rw/appdata/launcher/` with `preset.txt` (26 preinstalled tiles), `Appinfo.json` (user apps), `deletedPresetApp.txt` (hidden), `data/Category*.xml`, `PicInfo.xml`, `res/`
- **LauncherService:** `/3rd/launcherservice/bin/LauncherService` (via `startLS.sh` from `delayrun.sh`)
- **Native apps / AM:** `/basic/app_man -c /basic/am_config -s /basic/am_start.ini`; `dtv_svc`, `netflix`, `dialserver`, `samba`, `browser_base`, `securetime`, …; control is `:am,<app>,:<verb>=<val>`
- **Web browser (not the TV UI):** `hisense_browser` (e.g. PID 1320), `run-Browser.sh`, `--hw-dfb`, `--allow-file-access-from-files`, DevTools **9224**; the recon page runs here.

**UI ≠ browser:** `hisenseUI` (TV UI) and `hisense_browser` (web browser) are separate processes with their own start scripts, renderers, JS plugins and debug ports.

---

## Folder structure

```
<repo-root>/
├── README.md                         # this file
├── dead-ends.md                      # short list of dead ends
├── SHA256SUMS
├── root/                             # SECTION 1: Root
│   ├── ROOT-GUIDE.md                 # complete path (manual + scripts)
│   ├── README.md                     # short index
│   ├── tools/
│   │   ├── server.py                 # host: recon + /pub + /cmd + /recon + /dump
│   │   ├── recon.html                # TV page (fileXHR/listDir/HiBrowser hook)
│   │   ├── live_cmd.txt              # optional live channel (empty)
│   │   └── pub/                      # served files
│   │       ├── libtvsysinfo.so       # final root payload
│   │       ├── dropbear/dropbearkey  # static ARM Dropbear 2022.83
│   │       ├── dropbear-sftp         # Dropbear with SFTPSERVER_PATH=/3rd_rw/sshd/sftp-server
│   │       ├── sftp-server           # static OpenSSH-9.9p1-sftp-server
│   │       ├── authorized_keys       # your public key
│   │       ├── start_sshd.sh         # Dropbear + passwd/PTY bind mounts
│   │       ├── root_loop.sh          # root command channel
│   │       ├── hamservice-wrapper.sh # boot hook
│   │       ├── deploy_sshd.sh        # installation as root
│   │       ├── verify.sh / rollback.sh
│   ├── scripts/
│   │   ├── host/
│   │   │   ├── prepare_usb.sh        # ext4/MBR stick + tvi symlink
│   │   │   ├── start_http.sh         # server on :9000
│   │   │   ├── plant_payload.js      # write payload through tvi
│   │   │   ├── upload_to_appdata.js  # Dropbear/deploy to appdata
│   │   │   ├── run_root_cmd.js       # root_cmd/root_out
│   │   │   ├── build_payload.sh      # reproduce payload
│   │   │   ├── build_tvi_payload.py  # builder (deterministic)
│   │   │   ├── build_dropbear.sh     # build Dropbear from sources/
│   │   │   ├── build_sftp_server.sh  # build static sftp-server
│   │   │   ├── patch_dropbear_sftp.py # patch Dropbear SFTP path
│   │   │   └── install_sftp.sh       # install/test SFTP and swap to 22
│   │   └── tv/
│   │       ├── start_sshd.sh
│   │       ├── root_loop.sh
│   │       ├── hamservice-wrapper.sh
│   │       ├── deploy_sshd.sh
│   │       ├── verify.sh
│   │       ├── rollback.sh
│   │       ├── install_sftp_stage.sh # sftp-server + test Dropbear on 2222
│   │       ├── enable_sftp.sh        # schedule the swap to 22
│   │       └── swap_sftp.sh          # perform the swap detached
│   └── artifacts/
│       ├── tvi_original.so           # original library (33.220 B)
│       └── keys/{authorized_keys,host-key-fingerprint.txt}
├── modding/                          # SECTION 2: Modding
│   ├── README.md                     # modding index/TL;DR
│   ├── 01-system-linux.md            # Linux/SoC/userland/package manager/storage
│   ├── 02-boot.md                    # boot, autorun, developer.sh, services
│   ├── 03-ui.md                      # hisenseUI vs hisense_browser, UI data, AM
│   ├── 04-modding.md                 # recipes: custom app/UI/services/bloat
│   ├── 05-bloat.md                   # 26 preset apps, service matrix, disabling
│   ├── 06-toolchain-deploy.md        # build/deploy static ARM, SSH/PTY
│   ├── 07-evidence-unknowns.md       # evidence, status, known unknowns
│   └── templates/
│       ├── developer.sh              # earlier root boot hook
│       ├── custom-app.json           # Appinfo tile
│       ├── hide-preset.json          # deletedPresetApp.txt
│       ├── custom-ui.html            # minimal custom UI
│       ├── start-UI-custom.sh        # start-UI.sh with custom.html
│       └── README.md
└── sources/
    ├── dropbear-2022.83.tar.bz2      # offline build source
    └── openssh-9.9p1.tar.gz          # offline build source for sftp-server
```

---

## Replicate in 11 steps

```bash
# 1) Host: stick (DESTRUCTIVE)
sudo root/scripts/host/prepare_usb.sh /dev/sdX
# 2) Host: server
root/scripts/host/start_http.sh
# 3) TV: open http://<host-ip>:9000/recon.html
# 4) TV console: adjust USB dev, run plant_payload.js
#    -> /3rd_rw/loglevel/lib/libtvsysinfo.so (33500 B, SHA 37b13f…)
# 5) Reboot the TV
# 6) Verify root: /3rd_rw/root_proof.txt = ROOT_EXEC_TVI
# 7) TV console: upload_to_appdata.js
# 8) TV console: run_root_cmd.js (deploy_sshd.sh)
# 9) ssh root@192.0.2.94
#10) Rollback: /bin/sh /3rd_rw/appdata/rollback.sh
#11) SFTP optional: root/scripts/host/install_sftp.sh
#    afterwards: sftp root@192.0.2.94
```

**Complete:** [`root/ROOT-GUIDE.md`](root/ROOT-GUIDE.md)  
**Modding:** [`modding/README.md`](modding/README.md)  
**Dead ends:** [`dead-ends.md`](dead-ends.md)  
**Integrity:** `sha256sum -c SHA256SUMS`

---

## What the root path does (brief)

1. **Browser is root:** `hisense_browser` UID/GID 0, full `CapEff`, single process, no seccomp.
2. **USB write primitive:** dangling symlink `tvi` on ext4 → `IsSubDentry` bypass → new root-owned file.
3. **Loader shadow:** `libtvsysinfo.so` is a direct `NEEDED`; `LD_LIBRARY_PATH` index 17 is `/3rd_rw/loglevel/lib`; the shadow library sits there.
4. **DT_INIT payload:** appended code at the end of the file, RX `p_filesz/memsz` extended, `DT_INIT=0x81c4`; unlink self, proof, fork/exec `root_loop.sh`, original init.
5. **Root loop:** `root_cmd.sh` → `root_out.txt`.
6. **SSH:** Dropbear 2022.83 static, key-only, `/etc/passwd` bind (root home `/3rd_rw/sshd/home`), devpts on `/dev/shm/pts` → bind `/dev/pts` (PTY), `HamService` wrapper for boot persistence.
7. **SFTP (optional):** Dropbear has no sftp-server of its own; static OpenSSH-9.9p1-sftp-server + Dropbear with `SFTPSERVER_PATH=/3rd_rw/sshd/sftp-server`. Installation tests port 2222, then swaps to 22; afterwards `sftp root@…`.

---

## Security / ground rules

- **No flash, no `.pkg`, no bootloader.** Rootfs/`/3rd` are squashfs-ro; changes only in `/3rd_rw`, `/data`, `/perm`, bind mounts.
- **SSH is key-only root on the LAN.** No password; protect the private key; do not expose it to the internet.
- **SFTP is optional and root-equivalent.** Key-only like SSH; installation first tests 2222, backup `/3rd_rw/sshd/dropbear.nosftp`, rollback in the root guide.
- **The root loop is root-equivalent.** Anyone who can write `root_cmd.sh` (browser root) can run root commands.
- **Back up before UI/AM/launcher changes.** Especially `/3rd_rw/UI/index.html`, `/3rd_rw/appdata/launcher/*`, `/basic/am_config`/`am_start.ini`.
- **Keep SSH/root as a rescue path.** A broken UI means a black screen; kill and restart `hisenseUI` via SSH/root loop, restore the page from backup.
- **`developer.sh` is an early root hook** (before `ms_service`/UI/`app_man`/`delayrun`); errors there can affect boot/UI.
- **`/3rd_rw/patch/opera4x` is a full bind mount** over `/3rd/opera4x`; only with a complete copy/symlink tree; for single files prefer a file bind mount via `developer.sh`.
- **No secrets in the folder:** no root hash, no private SSH key; only the public key + host fingerprint.
- **Not everything is tested:** root/SSH/PTY live; the modding recipes are derived from static/live data; status in `modding/07-evidence-unknowns.md`.

---

## Verification status (excerpt)

| Item | Status |
|---|---|
| Browser root / full CapEff | **CONFIRMED live** |
| USB ext4 symlink bypass | **CONFIRMED live** |
| `libtvsysinfo` shadow / DT_INIT | **CONFIRMED live** (`ROOT_EXEC_TVI`, self-unlink) |
| Root loop / command channel | **CONFIRMED live** (`uid=0`, `root_out.txt`) |
| Dropbear SSH / port 22 / pubkey root | **CONFIRMED live** |
| PTY / interactive shell | **CONFIRMED live** (pts/0) |
| SFTP (optional) | static sftp-server + patched Dropbear; installer tests 2222 before 22; **TV test after install** |
| HamService boot persistence | configured; reboot test in the root guide |
| Modding recipes / custom UI / bloat | **UNVERIFIED** (derived from static/live data, not all executed yet) |

**Host key (SSH):** `<host-key-fingerprint>`  
**Your key:** `<your-public-key>` (fingerprint `<host-key-fingerprint>`)

---

## Provenance

The earlier run archive (not part of this repository; in the old project) is
kept as **evidence/history**. You do not need it for replication or modding:
the original research folder contained the final state, binaries, scripts and
docs. The old experiments/dead ends are summarised briefly in `dead-ends.md`.
