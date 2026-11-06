# Boot chain — 55S7NEVS (MTK9618, `mt5879` die)

> From the contributed bundle by [possibly_matt](https://www.reddit.com/user/possibly_matt/)
> (2026-11-05), adapted for this repo 2026-11-06 with the author's permission
> for the documentation. Content is the author's; unit identifiers were
> redacted by the author before sharing. Evidence lines cite the author's
> full eMMC backup of their unit — those snapshots travel with the author's
> private bundle, not this repo. See the [guide README](../README.md) for
> what was and was not republished.

Evidence: `meta/system.txt` (cmdline, mounts, by-name, partitions),
`meta/partition-offsets.txt`, `/etc/inittab`, `/etc/init.d/{rcS,rcS.OTA,rcS.utopia.linux}`
and `common/`|`mixed/` rc scripts, `rootfs/bin/avb_mount`,
`rootfs/usr/bin/upgradeprogress/otaPartitionConfig.ini`, mboot/KL/optee
partitions carved from `raw/emmc-full.img.zst` (see carve notes at bottom).

## Startup at a glance

```
SoC boot ROM
  └→ MBoot bootloader            (p1 mboot_a / p2 mboot_b, 2 slots, obfuscated)
      ├ loads FlashEnv from eMMC boot0 ("sboot") → picks boot slot
      ├ AVB 1.1 verify: vbmeta_a/b (p22/p23) → hash-descriptors for hashed partitions
      ├ assembles the whole kernel cmdline (slot suffix, dm-verity table, factory data …)
      └→ kernel "KL" image       (p7 KL_a / p8 KL_b, 32 MB slots, Linux 5.4.302 aarch64)
          └→ rootfs (squashfs, dm-verity → dm-0, currently rootfs_b = p21)
              └→ /sbin/init (sysvinit, 32-bit ARM, runlevel 3)
                  ├ /etc/init.d/rcS  (mount /proc, /dev, /dev/shm, /var/crash)
                  │   └─ mount -a -v (fstab: sysfs, pts, /run tmpfs, debugfs, pstore)
                  ├ OAD-boot branch? (his_facinfo ota_upgrade_flag == Y) → /etc/init.d/rcS.OTA
                  ├ else /etc/init.d/rcS.utopia.linux   (see 20-userspace-runtime.md)
                  └ then execs into Kilby (`start-kilby.sh` → kinit + init.rc service classes)
```

## eMMC layout (7.3 GiB, 55 partitions `mmcblk0p1…55`)

Two mirrored pairs at the top of the flash — `boot0`/`boot1` hardware
partitions (not visible in p1–p55, called **sboot** in the BAR table) hold the
FlashEnv backing store; everything else is pN. Full sector map with offsets in
`meta/partition-offsets.txt`. Semantics by name:

| Group | Partitions | Filesystem | Live at |
|---|---|---|---|
| MBoot bootloaders | p1 mboot_a, p2 mboot_b | raw image (obfuscated MTK MBoot, build `01.01.<BUILD>` per cmdline) | — |
| u-boot env | p3 uenv | FlashEnv records (opaque binary) | — |
| uuenv | p4 uuenv | ext4 (rw) `uuenv.ini`, **raw OTA flag storage** (`ota_upgrade_flag`, `ota_reboot_flag`… written by `ota_upgrade` via `setRawEmmcFlag` at parsed offsets) | `/vendor/uuenv` |
| certs | p5 certificate | ext4 (rw!) — Netflix ESN id, CIP+ root CAs, TIAs, company QDA config, patch images (`tvconfig.img.lzo`-style blobs) | `/certificate` |
| eeprom | p6 eeprom_a | raw board data (calibration, EDID …) | — |
| kernel | p7 KL_a, p8 KL_b | raw "kernel loader" (machine code ‖ kernel header area ~26 MB into slot; string `Linux version 5.4.302` present) | — |
| TEE | p9 optee_a, p10 optee_b | OP-TEE image, ARM-64 | — |
| scratch | p11 cache, p12 data | ext4 rw (`/var/crash`, `/dev/shm` ↔ p11/p12 swap of flow) | `/cache`, `/data` |
| FRC | p13 frc | p13 is a **single** (A ≠ B) raw FRC firmware for the video board | — |
| armfw | p14 armfw_a, p15 armfw_b | 256 KB each, micro-controller-side RTOS image ("TwoWorlds") | — |
| DTB / dtbo | p16/17 DTB_a/b, p18/19 dtbo_a/b | raw / dtbo| — |
| rootfs | p20 rootfs_a, p21 rootfs_b | squashfs 128 MB per slot, dm-verity (verified live) | `/` |
| vbmeta | p22 vbmeta_a, p23 vbmeta_b | 64 KB each, AVB 1.1 descriptors covering hashed partitions | — |
| tvconfig | p24 tvconfig_a, p25 tvconfig_b | ext4 ro (`/config`, `/vendor/tvconfig`; per-UI model INI tree incl. `sys.ini`) | `/config` |
| demura | p26 demura | panel demura compensation data | — |
| CUST | p27 CUST | ext4 rw (custdata, `mwlib` content…) | `/Customer` |
| 3rd party | p28 3rd | ext4 **avb-hash-verified** (mounted via avb_mount, hash in vbmeta): Netflix, Amazon, airplay, DLNA, dial, wpa_supplicant | `/3rd` (+ rw mirror `/3rd_rw` overlay) |
| MWLIB / LIB | p29 MWLIB, p30 LIB | vendor middleware + dylibs; avb_mount verified (vendor/lib → dm-1, lib/utopia → dm-3) | `/vendor/lib(/utopia)` |
| APP | p31 APP_a, p32 APP_b | ext4, avb_mount verified (dm-2): `miaudproc`, `mi_daemon_sys.bin`, `gam/svcmgr` | `/application` |
| persist | p33 persist | ext4 rw (`/vendor/persist`): `upgrade_mode.ini`, `standby_mode.ini`, `panel_mode_cfg.ini`, `voc_env.ini`, `oemdata.bin`, calibration blobs, our marker `oct/` | `/vendor/persist` |
| bootdata | p34 bootdata | raw kernel-boot control data — dual-boot flag & bootcount go here (mboot A/B slot chooser) | — |
| project_id | p35 project_id | ext4 ro: project_id (`0x01` ⇒ model from models.ini) | `/project_id` |
| his_facinfo | p36 his_facinfo | raw: factory settings (buildmacros), incl. `ota_upgrade_flag=` (keyed by rcS each boot) | `/dev/his_facinfo` |
| his_usrinfo | p37 his_usrinfo | raw runtime usage counters | — |
| his_devinfo | p38 his_devinfo | raw device info (net MAC, panel brand …) | — |
| misc | p39 his_misc, p40 misc | raw (boot-control/misc bytes) | — |
| logo | p41 logo | ext4 ro: boot logo assets | `/logo` |
| hidata | p42 criticaldata, p43 factorydata, p44 servicedata, p45 modeldata, p51 comdata | ext4 ro (except p44 rw `/var/tvservice`) — factory presets, switching presets, per-model data | `/hidata/{critical,factory,model,common}`, `/var/tvservice` |
| logofs | p41 (partition name is `logofs`) | ext4 ro: boot-splash/logo assets | `/logo` |
| servicedata | p44 | rw (`/var/tvservice`) — service DBs (`servicelist.db`, `epgsql.db3`, FVP OTT DB), hotel-mode ini, `debug_secrets.dat` | `/var/tvservice` |
| usrfs | p46 usrfs | ext4 rw, quota-enforced — dirty app state and our root-kit tool dir | `/APPS2` |
| optfs | p47 optfs | **erofs**, avb_mount verified (dm-4): the big VIDAA layer (`/usr/local` symlink → `/mnt/tvroot/usrlocal`, plus `/opt/{hisenseUI, mmlib, webengine, iot, netflix, alexa…}`), ~1.1 GB unpacked | `/mnt/tvroot` |
| sysadapter | p48 sysadapter | erofs ro: MTK sysadapter SDK | `/sysadapter` |
| varlfs | p49 varlfs | ext4 rw — dirty app state, upgrade work dir, ROM-auto-restore of dataprj (`/etc` binds here? no: /etc is a **second ro mount on p12**) | `/var/local` |
| serialdata | p50 serialdata | ext4 ro: models.ini + version signatures + model-specific `tvconfig.img.lzo`, `modeldata.img.lzo`, `his_devinfo.img.lzo` per 5 model strings incl. **55S7NEVS**, plus `upgrade.txt` lists | `/serialdata` |
| oemdata | p52/53 oemfiledata/oemrawdata | ext4 ro: OEM id & overlay raw data | `/oemdata` |
| apps | p54 apps | ext4 rw ipk store (`tv.vidaa.*` packages see below) | `/APPS` |
| oad | p55 oad | ext4 rw: upgrade work partition (target of downloads and temporary A/B hold-over, plus an AdapTable area for **policy** files) | `/OAD` |

`/etc` is a **second, rw mount of p12 (data)** layered over the rootfs — fs
state (hosts, resolv.conf, dhcpcd bits, our own edits) lives on `data`, not in
the squashfs.

The build rule baked into every script is:

```
linuxboot.slot_suffix=_b  →  app=31 mw=29 lib=30 vbmeta=23 tvcfg=25 persist=33
everything else (slot _a) →  app=31, same except vbmeta=22, app=31|32 by slot, tvcfg=24
```

## Verified-boot details (as shipped)

- Bootloader version shipped: `androidboot.bootloader=01.01.<BUILD>` — MTK MBoot
  release 01.01 dated 2606-09 (same build root date 2026-06-09 as kernel).
- AVB: cmdline claims `vbmeta.avb_version=1.1`, `device_state=locked`,
  `verifiedbootstate=green`, `veritymode=enforcing`, sha256 of vbmeta.
- After userspace starts, `/bin/avb_mount <dev> <mnt> <fs> <name> <vbmeta_dev> vbmeta`
  validates the partition against AVB descriptors in vbmeta, **then mounts it
  ro + dm-verity.** Applied to: `/application`, `/vendor/lib`, `/vendor/lib/utopia`,
  `/3rd`, `/mnt/tvroot` (optfs erofs). /vendor/persist, /vendor/uuenv,
  /Customer, usrext4 are mounted without verity (rw, first-boot writes hit there).
- rootfs semantics differ: cmdline carries an explicit dm-setup string for
  `root=/dev/dm-0` over the *current-slot* rootfs partition, null-diff →
  29410-block sha256 chain (`restart_on_corruption, use_fec_from_device …`).
- SELinux: policy **is** loaded (`init_selinux.rc` calls `load_policy -i`), but
  the rc script then calls **`setenforce 0` in BOTH branches** (permissive and
  "else") — i.e. the vendor build ships SELinux-in-name-only. This matches the
  observed runtime `enforce=0`. (AVBCmdline owns `androidboot.selinux=`
  but no enforcer actually turns `enforce` on.)

## Partition A/B banking & the bootroot

Per `rootfs/usr/bin/upgradeprogress/otaPartitionConfig.ini`, the genuinely
dual-bank partitions are:

```
sboot  /dev/mmcblk0boot0 ; /dev/mmcblk0boot1   (FlashEnv boot0/boot1)
mboot  p1 ; p2
kernel p7 KL_a ; p8 KL_b
optee  p9 ; p10
frc    p13 ; p13        (single, global copy)
armfw  p14 ; p15
DTB    p16 ; p17
dtbo   p18 ; p19
rootfs p20 ; p21
vbmeta p22 ; p23
tvconfig p24 ; p25
application p31 ; p32
```

Everything else is single-copy (with `fuse-hooks` for updates — see 30-update).
Why: rootfs/application/vbmeta/mboot/KL add up to ~500 MB × 2 which budget
fits, while the big ext4 trees (usrfs/optfs/serialdata) are rebuilt by
the OTA's `untar` path rather than streamed as raw block images.

Slot semantics: `bootdata` p34 = the U-Boot-style bootctrl (see
`libbootctrl.so` symbols in `ota_upgrade`: `bootctrl_read_boot_slot`,
`bootctrl_ota_success`) that carries slot metadata between userspace
`(ota_upgrade)` and next-boot MBoot decisions; mboot also reads FlashEnv
"start chain" pairs (`findRunningStartchain` / `setRunningStartchain`
"dualFlag") — the two mechanisms co-operate: **FlashEnv says which chain
(sboot/boot0 vs boot1); bootdata says which A/B half to pick inside it.**

## The debug/overlay escape hatch (as shipped, unused in our build)

`/etc/scripts/mount_overlayfs.sh` exists but is inert in the factory build:
it requires (a) `/usr/local/debug_version` marker file and (b) an
`init=/sbin/preinit` token on the cmdline; then it layers overlayfs on every
erofs mount using `/OAD/overlay_fs/<layer>` as upperdir and calls
`setenforce 0`. A signed `patch_package.zip` OTA decides per-build whether
that marker is installed (see 30-update-oad.md § USB-OTA: it diff-checks
`patch_package/debug_version` against `/usr/local/debug_version` and refuses
mismatched debug/release builds).

## Carve notes (for future re-analysis)

`raw/emmc-full.img.zst` is a straight zstd of the image, so a single
`zstd -dc raw/emmc-full.img.zst | <filter>` gives a sequential stream.
`head -c N` yields byte offset N. Useful slices (0-based byte offsets =
`sector×512`, from `meta/partition-offsets.txt`):

| Slice | Start | Size |
|---|---|---|
| mboot_a/b, uenv, uuenv, eeprom, KL_a/b, optee_a/b, p12 data | 2 MiB … 150 MiB | all in first `head -c 199,991,040` |
| project_id, his_facinfo, his_usrinfo, his_devinfo, his_misc, misc | 1 547 376 640 × ∈ [1.5 GiB, 1.55 GiB] | 24 MiB window |
| vbmeta_a/b | 871 891 456 (831.8 MiB) | 131 072 B |

Boot partition contents (verified by build-string greps):
- `mboot_a` non-empty but obfuscated; the first printable run is a banner
  `*****/ …` then nothing readable — image is compressed/encrypted before ROM hands off.
- `KL_a`/`KL_b` are 12 MB-ish of loader + a 5.4.302 kernel in the upper address
  region; both slots currently hold the **same** kernel (sha256 of carved
  `mboot_a` ≠ `mboot_b` though — bootloader at least differs between slots; last
  OTA flipped rootfs from `_a` → `_b`, see 30-update-oad.md).
- `optee_a`/`optee_b` are OP-TEE mantles (no ARM ELF header, "tee" users)
