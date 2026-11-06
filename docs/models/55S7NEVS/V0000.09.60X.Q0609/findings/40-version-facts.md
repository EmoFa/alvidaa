# Version & identity facts — 55S7NEVS

> From the contributed bundle by [possibly_matt](https://www.reddit.com/user/possibly_matt/)
> (2026-11-05), adapted for this repo 2026-11-06 with the author's permission
> for the documentation. "FACTS" below is the author's private working notes
> file, which is not part of this repo. See the [guide README](../README.md)
> for scope.

Everything in this doc is quoted straight from the backup — constants
re-derivable from the evidence sources quoted alongside. Highest-value
facts first.

## Identity matrix

| | Value | Source |
|---|---|---|
| Model | 55S7NEVS (Hisense EU VIDEO-ON-DEMAND serial `MTK_9618_EU_4K_1080P_FRAMETV` family) | `serialdata/common/serials.ini`, `models.ini` — `152 = 55S7NEVS` |
| SoC | MTK 9618 (`mt5879`), 4× Cortex-A72 (CPU part 0xd09), aarch64 | `/proc/cmdline` (`DTO_CHIP=mt5879`) + `/etc/profile` (CHIP_TYPE=`mixed`), cpuinfo |
| Kernel | `Linux version 5.4.302 (user1@d02f7d5d49b0) (aarch64-linux-gnu-gcc (Linaro GCC 5.5-2017.10) …) #1 SMP PREEMPT Tue Jun 9 21:19:47 CST 2026` | `meta/system.txt ### version` |
| Bootloader | `androidboot.bootloader=01.01.<BUILD>` (MTK MBoot) | cmdline |
| Product version | `V0000.09.60X.<BUILD>` (built 2026-06-09), OS `U09.60` | `serialdata/common/basic.ini` (`[Software] Version`), service.ini `osstage` |
| Software ID | `01-9618-0000-X-<BUILD>` | basic.ini |
| Build branch | `all-VIDAA_U96_MT9618_EUAU_hotfix_20260531` | basic.ini `[Branch] Name` |
| Security RTC string | `X0003.W01.Y01.J01` (X=chipset 0003 ⇒ 9618) | basic.ini `[Security] VER` |
| Vendor tag | `t-apollo-dev-2102-linux-83-001-630-IR-U96-mtk16587-11` | basic.ini `[Tag] Vendor` |
| ODM brand tokens | `SYS_BRAND=mtk SYS_ODM=mtk SYS_MODEL_NAME=hisense_mt5879_4k_eu_linuxDB SYS_VERSION=Debug` | `/etc/profile` (MStar-built tool variables in the shipped rootfs) |
| Serial | `<UNIT_SERIAL>` | cmdline `androidboot.serialno` |
| eMMC | 7.3 GiB (7 634 944 × 1024-block), 55 partitions | `/proc/partitions` |

## Browser / render stack (attack-target constants)

- Chromium **111.0.0.0** binary `/APPS/pkgs/tv.vidaa.app.browser/current/bin/browser`
  (`zenixservicework` is its renamed chromium process shim in `CHA/bin/`;
  renderer exposes `--remote-debugging-port=9226`).
- Renderer flags (full cmdline in `meta/runtime.txt` line for PID 2753/26129)
  include `--no-sandbox`, `--disable-gpu-sandbox`, `--in-process-gpu`,
  `--disable-features=BlockInsecurePrivateNetworkRequests,MediaCapabilities…`,
  `--js-flags=--expose-gc --always_compact`.
- V8 = 11.1, no pointer compression, no sandbox (author's notes; still live
  on this build).

## Partition families (names side, all in `meta/partition-offsets.txt`)

Dual-banks: mboot, KL(kernel), optee, armfw, DTB, dtbo, rootfs, vbmeta,
tvconfig, APP.
Single-image items flashable by OTA: frc, 3rd(file), MWLIB, LIB
(dynamic), bootdata, logo, usrfs, optfs, sysadapter, serialsdata, comdata,
tvsapp (= p54 `apps`).

## Model-types covered by this board build (serialdata)

| id | model |
|---|---|
| 001 | 65ADEVTOOL |
| 132 | 55U75LEVS |
| 152 | 55S7NEVS |
| 154 | 65S7NAVS |
| 157 | 75S7NAVS |

Each model dir defines `tvconfig.img.lzo`, `modeldata.img.lzo`,
`his_devinfo.img.lzo` and `upgrade.txt` (what the serial loader re-flashes
for that model).

## Users worth quoting

`cli:x:0:0` (uid 0, shell `/etc/cli_login.sh`),
`television:x:300:300 … /usr/local/scripts/login.sh`,
`loewe:x:299:299 … loewelogin.sh`,
`root` shell `/usr/local/scripts/rootlogin.sh`.
Full passwd/group lists in `20-userspace-runtime.md`.

## Hotel/factory metadata

- `factory_mode` is a text flag inside `/dev/his_facinfo` (`factory_mode=on`); used to skip rescueOTA etc.
- Hotel mode DB: `/var/tvservice/hotel/hotelmode.ini` (HotelMode=0 in our backup).
- USB OTA package name expected: `patch_package.zip` on any FAT (`/tmp/lo_*` or `/dev/sd*`).

## What our root kit currently adds on this unit (not vendor!)

- Files in `/APPS2/pkgs/download/`: `octdropbear5`, `octrootdaemon3.sh`,
  `telnetd`, `netstat`, `iptables`, `ps`, host key `dbhostkey` — plus
  `octprobe/`, `octroot.marker`, `octcanary1.txt` markers.
- ipkg records: `tv.vidaa.app.octroot{,2,X,Y}` … with `Userid: 0:0`,
  `Persistent: true`, generated postinst scripts (author's notes).
- iptables ACCEPT additions on 24242/24245/24246/24247 (both INPUT and
  FIREWALL_IN_EULAON).
- `/etc` bind changes (`/etc/shells` added with `/bin/sh` and our paths,
  root shell sed'd in `data/etc2` copy from the dropbear saga; bind no
  longer load-bearing but still in place).
- `/etc/hosts.bak-20261102-preblock` (backup made while net-blocking
  experiments; only remnant).
- `/var/local/otaTest.sh` boot-hook file still present but its rc.local
  invocation is commented ⇒ **not part of the live chain** (see
  50-security-review §2.4).
