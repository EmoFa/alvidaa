# 01 — System: Linux, SoC, Userland, Package Manager, Storage

**Ziel:** Hisense HE40E5600FFWTS, FW `V0100.01.00A.N0410`, LAN `192.0.2.94`.
**Quelle:** Live-Root-Reads am TV (`/proc`, `/lib`, `/bin`, `/etc`, Mounts) + statische Dumps.
**Status:** Systemfakten **CONFIRMED** (live/static); einzelne Hardware-/Bootloader-Details `UNVERIFIED`.

---

## 1. Linux / Kernel

```text
Linux version 3.18.25 (REDACTED-BUILDHOST)
(gcc version 4.8.2 20131014 (prerelease) (Linaro GCC 4.8-2013.10) )
#1 SMP PREEMPT Mon Apr 10 17:40:02 CST 2023
```

- **Kernel 3.18.25**, ARM (32-bit), SMP, PREEMPT.
- Gebaut mit **Linaro GCC 4.8.2** (2013.10), Build 2023-04-10.
- **Kein** Standard-Distro-Userland, **kein** `/etc/os-release`, **kein** `/etc/issue`, **kein** `/etc/version`.
- Firmware-Kennung: `V0100.01.00A.N0410`.

### Kernel-Cmdline (Auszug, `/proc/cmdline`)

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

- **Bootmedium:** eMMC (`mmcblk0`), MediaTek **`mt53xx-emmc`**-Partitionierung.
- **Rootfs:** `/dev/mmcblk0p9` (rootfsA), **squashfs ro**; A/B-Slots für U-Boot/Kernel/Rootfs.
- **`/3rd`:** Device-Mapper **`dm-3`**, squashfs ro (~141 MB).
- **`console=ttyMT0,115200n1`**: serielle Konsole existiert, ist aber nicht angeschlossen (kein Öffnen des TVs nötig).
- **`adb_enable=0`**: kein ADB.
- **U-Boot-Env:** `fw_printenv` meldet **„Bad CRC, using default environment“** und zeigt nur einen NFS-Default (`bootcmd=bootp...`). Die **echte** Boot-Konfiguration ist die `/proc/cmdline`; das U-Boot-Env ist **nicht** verlässlich (UNVERIFIED im Detail).

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
- **SoC-Klasse:** MediaTek **MT53xx/MT5863** (Belege: `mt53xx-emmc` in cmdline; Browser-Build `mt5863_sa_768_linux` in `run-Browser.sh`; `mt5863` im Build).
- **Exakte Kernanzahl** aus dem Dump: `processor 0..2` sichtbar; `mt5863` ist 4×A53. Als **4 Kerne** dokumentiert, exakter Count `UNVERIFIED` (der Dump war auf 28 Zeilen begrenzt).
- **GPU:** ARM Mali (`/3rd/Arm_Mali`, `/basic/lib/libMali.so`, `ins_arm_mali_mod.sh`); die UI nutzt GLES (`--hw-gles`).

---

## 2. Userland

### libc / Laufzeit

- **glibc 2.18**:
  - `/lib/ld-linux.so.3`, `/lib/ld-2.18.so`
  - `/lib/libc-2.18.so`, `libm-2.18.so`, `libdl-2.18.so`, `libpthread-2.18.so`
  - `/lib/libstdc++.so.6.0.18`, `libgcc_s.so.1`
- **ABI:** ARM EABI5, hard-float (VFPv4), `Tag_ABI_align_needed: 8-byte`.
- **Zusätzliche Libs:** `/basic/lib` (libcrypto/ssl/curl/nss/…), `/3rd/lib` (libxml2/mxml/iconv/…), `/3rd_rw/opera4xLib` (Browser-Libs), `/lib` (glibc).
- **Dynamische Binaries** brauchen die TV-glibc 2.18. **Statisch** ist der sichere Weg (siehe `06`).

### BusyBox / Shell

- **BusyBox 1.18.5** (Build 2017-12-05), multi-call.
- **Viele Applets sind nicht als Symlink vorhanden** (`uname`, `tr`, `tail`, `id` fehlen z. B. als `/bin/<name>`); nutze:
  ```sh
  /bin/busybox uname -a
  /bin/busybox tail -n 10 /pfad
  /bin/busybox tr '\0' '\n' < /proc/.../environ
  ```
- `/bin/sh` existiert (Shell), `/bin/bash` ebenfalls; `/bin`, `/sbin`, `/usr/bin`, `/basic/bin` gemischt.
- Nützliche vorhandene Tools: `mount`, `umount`, `insmod`, `mknod`, `mkfs.ext4`, `tar`, `sed`, `grep`, `awk`, `find`, `ping`, `nc`? (nicht geprüft), `ps`, `kill`, `reboot`, `fw_printenv`, `busybox`.
- **Nicht vorhanden / nicht gebaut:** `uname` (Applet), `tr` (Applet), `id` (Applet), `ssh`, `sshd`, `scp`, `sftp`, `opkg`, `apt`, `dpkg`, `rpm`, `curl` (BusyBox), `wget`? (nicht geprüft), `python`, `perl`.

### Init / Services

- **SysV-artig**, **kein systemd**:
  - `/etc/inittab`: `id:3:initdefault:`; `1:012345:respawn:/sbin/getty -L ttyMT0 115200 vt100`; `si::sysinit:/etc/init.d/rcS`.
  - `/etc/init.d/rcS`: `source /etc/profile`; `mount -avt nonfs,nosmbfs`; `/etc/rc.d/rc.local`.
  - `/etc/rc.d/rc.local`: `/proc/boottime`, `/dev/shm/shm_tmp`, `rc.local.partial`, `mount_main.sh`, `mount_data.sh`, `/basic/3rd_ini/*/global_env_setup.ini`, `mount_3rd*`, `mount_perm.sh`, `fusion.ko`, `hisense_rc.sh`, `dtv_driver*.ko`, `autorun.sh`, `patch/opera4x`, `preload_opera`, `ms_service`, `hisenseUI`, `app_man`, `delayrun`.
- **Seriell:** `ttyMT0` 115200; `rootlogin.sh` (USB-Key + doppelt-MD5-PIN) ist der Hardware-Root-Login. **Nicht nötig** für den Software-Root.
- **USB-Console:** `usb_console.sh` nur wenn `ttyUSB` in `/proc/cmdline`; hier nicht.

---

## 3. Package Manager: **keiner**

Live-Root-Check:

```sh
for c in apt apt-get dpkg rpm opkg ipkg apk yum pacman; do command -v $c; done
# -> keine Ausgabe / nicht gefunden
ls -la /etc/opkg /etc/opkg.conf /var/lib/opkg /var/lib/dpkg /usr/lib/opkg
# -> No such file or directory
/bin/busybox --list | grep -E '^(opkg|dpkg|rpm|apk|ipkg)$'
# -> keine Treffer
cat /etc/os-release
# -> No such file or directory
```

**Fazit:** Es gibt **keinen Package Manager**, kein Paket-Repo, kein `opkg install`, kein `apt`.  
**Modding-Konsequenz:**

- Eigene Tools als **statische ARM-Binaries** bauen (`arm-linux-gnueabihf-gcc -static`) oder Shell-Skripte verwenden.
- Deployment per **`File.download`** (Browser root) nach `/3rd_rw/appdata`, per **SSH** (`cat`/`base64`/`tar`) oder USB.
- Nichts „installieren“ im Sinne einer Distro; Dateien nach `/3rd_rw`/`/data`/`/perm` legen und per `developer.sh`/`HamService`-Wrapper starten.
- Siehe `06-toolchain-deploy.md`.

---

## 4. Storage / Mounts / Partitionen

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
/dev/mmcblk0p30 /vddt ext4 rw   # gleiche Partition
/dev/mapper/dm-3 /3rd squashfs ro
/dev/mmcblk0p33 /spdata ext4 ro
/dev/mmcblk0p14 /3rd_rw ext4 rw # 1.1G
/dev/mmcblk0p12 /perm ext4 rw   # 3.9M
/dev/sda1 /dev/shm/shm_tmp/mnt/usb/sda1 ext4 rw
/dev/mmcblk0p14 /etc/passwd ext4 rw   # unser Bindmount (Root-Home)
devpts /dev/shm/pts devpts rw
devpts /dev/pts devpts rw             # Bind für PTY
```

### Größen (`df -h`)

| Mount | Größe | Belegt | Frei | FS |
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

- **Kein OverlayFS** (`/proc/filesystems`: sysfs, rootfs, ramfs, bdev, proc, tmpfs, debugfs, sockfs, pipefs, **devpts**, ext2/3/4, **squashfs**, vfat, iso9660, udf, mqueue, ntfs; **kein overlay**).
- **Modding-Mechanik:** rw-Partitionen + **`mount --bind`** (Datei oder Verzeichnis), kein Overlay.
- **`/dev` ist Teil des ro Squashfs** (kein devtmpfs); `/dev/pts` enthält statische Nodes 136,0–4; **PTY-Workaround** nötig (siehe `06`/Root-Guide).
- **`/tmp` ist ein Symlink auf `/dev/shm/shm_tmp`** (tmpfs).
- **eMMC-Partitionen** (Auszug): p9 rootfsA (40M), p10 rootfsB, p12 perm, p13 3rd_ro (205M), p14 rw_area/3rd_rw (1152M), p30 data (2040M), p33 spdata (40M), p34 swap (100M); `dm-3` = 141M `/3rd`; `zram0` 200M.
- **Swap:** `delayrun.sh` macht `mkswap /dev/mmcblk0p34` + `swapon`; `zram0` 200M.
- **Rootfs/3rd 100 % voll**; neue Daten gehören nach `/3rd_rw` (489M frei) oder `/data` (1.9G frei), nicht in `/`/`/3rd`.

---

## 5. Toolchain-Constraints (Kurz)

| Constraint | Wert |
|---|---|
| Architektur | ARMv7, EABI5, hard-float, VFPv4/NEON |
| Kernel | 3.18.25 (kein overlayfs, kein devtmpfs, devpts ja) |
| libc | glibc 2.18 (TV) |
| Compiler | `arm-linux-gnueabihf-gcc` (Host) |
| Static | empfohlen; `-static`; der mitglieferte Dropbear ist statisch (glibc 2.39) und läuft |
| Dynamic | nur mit TV-glibc 2.18 / passendem Sysroot; sonst GLIBC_2.xx-Fehler |
| Package Manager | **keiner** |
| Deploy | `File.download` (Browser root), SSH (`cat`/`base64`/`tar`), USB |
| PTY | devpts auf `/dev/shm/pts` → bind `/dev/pts`; `/dev` ro |
| Overlay | **nein** → `mount --bind` + `developer.sh` |

Details, Dropbear-Build und Deploy: `06-toolchain-deploy.md`.

---

## 6. Evidence

- `/proc/version`, `/proc/cmdline`, `/proc/cpuinfo`, `/proc/filesystems`, `/proc/mounts`, `/proc/partitions`
- `df -h`, `ls -l /lib`, `ls -l /bin`, `ls -l /etc`, `/etc/inittab`, `/etc/init.d/rcS`, `/etc/rc.d/rc.local`
- `command -v apt/dpkg/opkg/...` leer; `/etc/opkg`/`/var/lib/dpkg` fehlen; `/bin/busybox --list`
- Der alte Run-Ordner (`the earlier run archive (not part of this repository)`) enthält die Roh-Captures; für die Replikation nicht nötig.

---

## 7. Bekannte Unknowns

- Exakte SoC-Bezeichnung (MT5863 vs. MT53xx-Familie), exakte Kernanzahl, Secure-Boot-/Signaturstatus.
- Vollständige Kernel-Config, `dm-3`-Konstruktion, `spdata`/`perm`/`facset`/`hiscfg`/`eeprom`-Inhalte.
- U-Boot-Env (Bad CRC; default NFS) und echter Bootloader-Flow im Detail.
- DRM/`securetime`/PlayReady/Widevine, Netflix/Cobalt/Amazon, OTA/`checker.sh`/`file_upgrading`.
- `dtv_svc`/`app_man`-Interna, `LauncherService`-Datenquelle, `Hisense_*`-API-Signaturen.
- Ob `VIDAAU2Launcher` auf diesem Modell je aktiv ist (die aktive UI ist `/3rd_rw/UI`; `launcher`/`VIDAAU2` sind Alt-/Alternativ-Skins).
- Ob der `preset.txt`-Cache vom `LauncherService`/der UI bei jedem Start neu geschrieben wird (die `deletedPresetApp.txt` ist die persistente Hide-Liste).
