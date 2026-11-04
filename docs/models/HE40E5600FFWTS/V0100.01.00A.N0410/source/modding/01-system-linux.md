# 01 — System: Linux, SoC, Userland, Package Manager, Storage

**Target:** Hisense HE40E5600FFWTS, FW `V0100.01.00A.N0410`, LAN `192.0.2.94`.
**Source:** live root reads on the TV (`/proc`, `/lib`, `/bin`, `/etc`, mounts) + static dumps.
**Status:** system facts **CONFIRMED** (live/static); individual hardware/bootloader details `UNVERIFIED`.

---

## 1. Linux / Kernel

```text
Linux version 3.18.25 (REDACTED-BUILDHOST)
(gcc version 4.8.2 20131014 (prerelease) (Linaro GCC 4.8-2013.10) )
#1 SMP PREEMPT Mon Apr 10 17:40:02 CST 2023
```

- **Kernel 3.18.25**, ARM (32-bit), SMP, PREEMPT.
- Built with **Linaro GCC 4.8.2** (2013.10), build 2023-04-10.
- **No** standard distro userland, **no** `/etc/os-release`, **no** `/etc/issue`, **no** `/etc/version`.
- Firmware identifier: `V0100.01.00A.N0410`.

### Kernel cmdline (excerpt, `/proc/cmdline`)

```text
rootwait rootfstype=squashfs ro console=ttyMT0,115200n1 vmalloc=512mb quiet
mtdparts=mt53xx-emmc:2M(ubootA),2M(ubootB),256k(bt_flag),256k(ra_data),
2M(uboot_envA),2M(uboot_envB),5M(kernelA),5M(kernelB),40M(rootfsA),40M(rootfsB),
256k(basic),8M(perm),205M(3rd_ro),1152M(rw_area),256k(reserved),1M(channelA),
1M(channelB),4M(pq),4M(aq),48M(logo),1M(acfg_descr),256k(part_21),4M(adsp),
256k(part_23),256k(part_24),1M(eeprom_A),1M(eeprom_B),8M(facset),1M(hiscfg),
2040M(data),1M(cidata),1M(dbdata),40M(spdata),100M(swapdt)
root=/dev/mmcblk0p9 usbportusing=1,1,1,0 ... adb_enable=0
androidboot.serialno=<device-serial> ...
```

- **Boot medium:** eMMC (`mmcblk0`), MediaTek **`mt53xx-emmc`** partitioning.
- **Rootfs:** `/dev/mmcblk0p9` (rootfsA), **squashfs ro**; A/B slots for U-Boot/kernel/rootfs.
- **`/3rd`:** device mapper **`dm-3`**, squashfs ro (~141 MB).
- **`console=ttyMT0,115200n1`**: a serial console exists but is not connected (no need to open the TV).
- **`adb_enable=0`**: no ADB.
- **U-Boot env:** `fw_printenv` reports **"Bad CRC, using default environment"** and shows only an NFS default (`bootcmd=bootp...`). The **real** boot configuration is `/proc/cmdline`; the U-Boot env is **not** reliable (UNVERIFIED in detail).

### CPU / SoC

`/proc/cpuinfo`:

```text
model name : ARMv7 Processor rev 4 (v7l)
Features   : half thumb fastmult vfp edsp neon vfpv3 tls vfpv4 idiva idivt vfpd32 lpae evtstrm
CPU implementer : 0x41
CPU architecture: 7
CPU part        : 0xd03
CPU revision    : 4
```

- **ARMv7**, Cortex-A53 (`part 0xd03`), NEON/VFPv4, Thumb-2.
- **SoC class:** MediaTek **MT53xx/MT5863** (evidence: `mt53xx-emmc` in the cmdline; browser build `mt5863_sa_768_linux` in `run-Browser.sh`; `mt5863` in the build).
- **Exact core count** from the dump: `processor 0..2` visible; `mt5863` is 4×A53. Documented as **4 cores**, exact count `UNVERIFIED` (the dump was limited to 28 lines).
- **GPU:** ARM Mali (`/3rd/Arm_Mali`, `/basic/lib/libMali.so`, `ins_arm_mali_mod.sh`); the UI uses GLES (`--hw-gles`).

---

## 2. Userland

### libc / runtime

- **glibc 2.18**:
  - `/lib/ld-linux.so.3`, `/lib/ld-2.18.so`
  - `/lib/libc-2.18.so`, `libm-2.18.so`, `libdl-2.18.so`, `libpthread-2.18.so`
  - `/lib/libstdc++.so.6.0.18`, `libgcc_s.so.1`
- **ABI:** ARM EABI5, hard-float (VFPv4), `Tag_ABI_align_needed: 8-byte`.
- **Additional libs:** `/basic/lib` (libcrypto/ssl/curl/nss/…), `/3rd/lib` (libxml2/mxml/iconv/…), `/3rd_rw/opera4xLib` (browser libs), `/lib` (glibc).
- **Dynamic binaries** need the TV glibc 2.18. **Static** is the safe route (see `06`).

### BusyBox / shell

- **BusyBox 1.18.5** (build 2017-12-05), multi-call.
- **Many applets are not present as symlinks** (`uname`, `tr`, `tail`, `id` are missing e.g. as `/bin/<name>`); use:
  ```sh
  /bin/busybox uname -a
  /bin/busybox tail -n 10 /path
  /bin/busybox tr '\0' '\n' < /proc/.../environ
  ```
- `/bin/sh` exists (shell), `/bin/bash` too; `/bin`, `/sbin`, `/usr/bin`, `/basic/bin` are mixed.
- Useful tools present: `mount`, `umount`, `insmod`, `mknod`, `mkfs.ext4`, `tar`, `sed`, `grep`, `awk`, `find`, `ping`, `nc`? (not verified), `ps`, `kill`, `reboot`, `fw_printenv`, `busybox`.
- **Not present / not built:** `uname` (applet), `tr` (applet), `id` (applet), `ssh`, `sshd`, `scp`, `sftp`, `opkg`, `apt`, `dpkg`, `rpm`, `curl` (BusyBox), `wget`? (not verified), `python`, `perl`.

### Init / services

- **SysV-like**, **no systemd**:
  - `/etc/inittab`: `id:3:initdefault:`; `1:012345:respawn:/sbin/getty -L ttyMT0 115200 vt100`; `si::sysinit:/etc/init.d/rcS`.
  - `/etc/init.d/rcS`: `source /etc/profile`; `mount -avt nonfs,nosmbfs`; `/etc/rc.d/rc.local`.
  - `/etc/rc.d/rc.local`: `/proc/boottime`, `/dev/shm/shm_tmp`, `rc.local.partial`, `mount_main.sh`, `mount_data.sh`, `/basic/3rd_ini/*/global_env_setup.ini`, `mount_3rd*`, `mount_perm.sh`, `fusion.ko`, `hisense_rc.sh`, `dtv_driver*.ko`, `autorun.sh`, `patch/opera4x`, `preload_opera`, `ms_service`, `hisenseUI`, `app_man`, `delayrun`.
- **Serial:** `ttyMT0` 115200; `rootlogin.sh` (USB key + double-MD5 PIN) is the hardware root login. **Not needed** for the software root.
- **USB console:** `usb_console.sh` only if `ttyUSB` is in `/proc/cmdline`; not the case here.

---

## 3. Package Manager: **none**

Live root check:

```sh
for c in apt apt-get dpkg rpm opkg ipkg apk yum pacman; do command -v $c; done
# -> no output / not found
ls -la /etc/opkg /etc/opkg.conf /var/lib/opkg /var/lib/dpkg /usr/lib/opkg
# -> No such file or directory
/bin/busybox --list | grep -E '^(opkg|dpkg|rpm|apk|ipkg)$'
# -> no matches
cat /etc/os-release
# -> No such file or directory
```

**Conclusion:** there is **no package manager**, no package repo, no `opkg install`, no `apt`.  
**Modding consequence:**

- Build your own tools as **static ARM binaries** (`arm-linux-gnueabihf-gcc -static`) or use shell scripts.
- Deployment via **`File.download`** (browser root) to `/3rd_rw/appdata`, via **SSH** (`cat`/`base64`/`tar`) or USB.
- Do not "install" anything in the distro sense; place files in `/3rd_rw`/`/data`/`/perm` and start them via the `developer.sh`/`HamService` wrapper.
- See `06-toolchain-deploy.md`.

---

## 4. Storage / Mounts / Partitions

### Mounts (live)

```text
rootfs / rootfs rw 0 0
/dev/root / squashfs ro,relatime 0 0
none /proc proc rw
none /sys sysfs rw
none /opt tmpfs rw              # 304.6M
none /dev/shm tmpfs rw          # 304.6M; /tmp -> /dev/shm/shm_tmp
none /var/run tmpfs rw          # 304.6M
/dev/mmcblk0p30 /data ext4 rw   # 1.9G
/dev/mmcblk0p30 /vddt ext4 rw   # same partition
/dev/mapper/dm-3 /3rd squashfs ro
/dev/mmcblk0p33 /spdata ext4 ro
/dev/mmcblk0p14 /3rd_rw ext4 rw # 1.1G
/dev/mmcblk0p12 /perm ext4 rw   # 3.9M
/dev/sda1 /dev/shm/shm_tmp/mnt/usb/sda1 ext4 rw
/dev/mmcblk0p14 /etc/passwd ext4 rw   # our bind mount (root home)
devpts /dev/shm/pts devpts rw
devpts /dev/pts devpts rw             # bind for PTY
```

### Sizes (`df -h`)

| Mount | Size | Used | Free | FS |
|---|---:|---:|---:|---|
| `/` | 38.8M | 38.8M | 0 | squashfs ro (100 %) |
| `/3rd` | 141.0M | 141.0M | 0 | squashfs ro (100 %) |
| `/3rd_rw` | 1.1G | 610.6M | 489.3M | ext4 rw (56 %) |
| `/data` | 1.9G | 3.0M | 1.9G | ext4 rw |
| `/perm` | 3.9M | 172K | 3.5M | ext4 rw |
| `/spdata` | 35.4M | 1.3M | 33.3M | ext4 ro |
| `/opt` | 304.6M | 0 | 304.6M | tmpfs |
| `/dev/shm` | 304.6M | 58.8M | 245.8M | tmpfs |
| `/var/run` | 304.6M | 0 | 304.6M | tmpfs |
| USB | 927.7M | 264K | 863.5M | ext4 rw |

- **No OverlayFS** (`/proc/filesystems`: sysfs, rootfs, ramfs, bdev, proc, tmpfs, debugfs, sockfs, pipefs, **devpts**, ext2/3/4, **squashfs**, vfat, iso9660, udf, mqueue, ntfs; **no overlay**).
- **Modding mechanics:** rw partitions + **`mount --bind`** (file or directory), no overlay.
- **`/dev` is part of the ro squashfs** (no devtmpfs); `/dev/pts` contains static nodes 136,0–4; a **PTY workaround** is needed (see `06`/root guide).
- **`/tmp` is a symlink to `/dev/shm/shm_tmp`** (tmpfs).
- **eMMC partitions** (excerpt): p9 rootfsA (40M), p10 rootfsB, p12 perm, p13 3rd_ro (205M), p14 rw_area/3rd_rw (1152M), p30 data (2040M), p33 spdata (40M), p34 swap (100M); `dm-3` = 141M `/3rd`; `zram0` 200M.
- **Swap:** `delayrun.sh` runs `mkswap /dev/mmcblk0p34` + `swapon`; `zram0` 200M.
- **Rootfs/3rd are 100 % full**; new data belongs in `/3rd_rw` (489M free) or `/data` (1.9G free), not in `/`/`/3rd`.

---

## 5. Toolchain constraints (brief)

| Constraint | Value |
|---|---|
| Architecture | ARMv7, EABI5, hard-float, VFPv4/NEON |
| Kernel | 3.18.25 (no overlayfs, no devtmpfs, devpts yes) |
| libc | glibc 2.18 (TV) |
| Compiler | `arm-linux-gnueabihf-gcc` (host) |
| Static | recommended; `-static`; the bundled Dropbear is static (glibc 2.39) and runs |
| Dynamic | only with TV glibc 2.18 / matching sysroot; otherwise GLIBC_2.xx errors |
| Package Manager | **none** |
| Deploy | `File.download` (browser root), SSH (`cat`/`base64`/`tar`), USB |
| PTY | devpts on `/dev/shm/pts` → bind `/dev/pts`; `/dev` ro |
| Overlay | **no** → `mount --bind` + `developer.sh` |

Details, Dropbear build and deploy: `06-toolchain-deploy.md`.

---

## 6. Evidence

- `/proc/version`, `/proc/cmdline`, `/proc/cpuinfo`, `/proc/filesystems`, `/proc/mounts`, `/proc/partitions`
- `df -h`, `ls -l /lib`, `ls -l /bin`, `ls -l /etc`, `/etc/inittab`, `/etc/init.d/rcS`, `/etc/rc.d/rc.local`
- `command -v apt/dpkg/opkg/...` empty; `/etc/opkg`/`/var/lib/dpkg` missing; `/bin/busybox --list`
- The earlier run archive (not part of this repository) contains the raw captures; it is not needed for replication.

---

## 7. Known unknowns

- Exact SoC designation (MT5863 vs. MT53xx family), exact core count, secure boot/signature status.
- Full kernel config, `dm-3` construction, `spdata`/`perm`/`facset`/`hiscfg`/`eeprom` contents.
- U-Boot env (Bad CRC; default NFS) and real bootloader flow in detail.
- DRM/`securetime`/PlayReady/Widevine, Netflix/Cobalt/Amazon, OTA/`checker.sh`/`file_upgrading`.
- `dtv_svc`/`app_man` internals, `LauncherService` data source, `Hisense_*` API signatures.
- Whether `VIDAAU2Launcher` is ever active on this model (the active UI is `/3rd_rw/UI`; `launcher`/`VIDAAU2` are legacy/alternative skins).
- Whether the `preset.txt` cache is rewritten by the `LauncherService`/the UI on every start (the `deletedPresetApp.txt` is the persistent hide list).
