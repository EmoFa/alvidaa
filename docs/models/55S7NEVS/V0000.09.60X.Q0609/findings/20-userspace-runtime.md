# Userspace, services & runtime — 55S7NEVS

> From the contributed bundle by [possibly_matt](https://www.reddit.com/user/possibly_matt/)
> (2026-11-05), adapted for this repo 2026-11-06 with the author's permission
> for the documentation. "FACTS" pointers below refer to the author's
> private working notes, which are not part of this repo. See the
> [guide README](../README.md) for scope.

Evidence: the boot scripts (`rootfs/etc/init.d/*`, `rootfs/etc/scripts/*`),
tvroot scripts (`mnt_tvroot.tar.zst` → `/usr/local/scripts/*`), the shipped
init config (`usrlocal/scripts/init.rc`), and the live process tree +
iptables/netstat captured in `meta/runtime.txt` (process list quoted below).

## Stage-by-stage startup (as shipped)

1. **sysvinit runlevel 3** (`/sbin/init`, ARM-32):
   `si::sysinit:/etc/init.d/rcS`, `getty` on `ttyS0` (115200). No runlevel
   scripts otherwise — everything below is duct-taped into rcS.
2. **rcS**: mounts /proc,/dev (tmpfs 200–300 MB per RAM), /dev/pts, /dev/shm
   per RAM, /var/crash (100 MB tmpfs); reads `ota_upgrade_flag` from
   `/dev/his_facinfo` (factory-backed raw byte — written by the OTA flow;
   deciding flag then branches OTA-boot vs normal boot); `mount -a -v`
   resolves fstab (sysfs/debugfs/pstore/pts,/run tmpfs).
3. **rcS.utopia.linux** (normal boot) — orchestrates in parallel with
   `${CHIP_TYPE}=mixed` (an MStar/MTK hybrid variant, the others being `merak`,
   `fusion` — those are used on different SoCs; module lists etc. live under
   `/etc/init.d/<type>/`):
   - `init_fsck_partition.rc &` — **fsck in background** on every rw ext4
     partition (data/cache/persist/certificate/CUST/varlfs/servicedata/usrfs/optfs/apps/oad).
     Also builds `/dev/block/by-name/<name>` symlinks here.
   - `init_early_insmod.rc &` → `init_insmod.rc &` → `init_post_insmod.rc &`
     — staged `insmod` of the vendor kernel module set (mixed/).
   - `init_selinux.rc` — loads policy, then `setenforce 0` (see boot doc).
   - `init_udevd.rc` + `init_udevd_settle.rc` — MStar `udevd` (`/basic/bin/udevd -d`).
   - `init_mount.rc` — per-slot splits (see boot doc) then mounts 10+
     partitions; vendor persist rw, tvconfig ro, cert, customer.
   - **`mount_his.sh`** — mounts the Hisense-side "hidata" family
     (`/hidata/{critical,factory,model,common}`, `/var/tvservice` rw,
     `/var/local` rw, `/serialdata` ro, `/APPS`, `/APPS2`, `/OAD`, `/oemdata`,
     `/logo`, `/mnt/tvroot` erofs via avb_mount, `/sysadapter` erofs).
     Failing ext4 e2fsck+remount gets a `/var/crash/*_crash_stack.txt` breadcrumb.
   - `init_kilby.rc` — the main kickoff: `start-kilby.sh` (below).
   - `start-deploy_tvconfig.sh` — copies model configs onto big mounts, see
     later; `mount_overlayfs.sh` (no-op unless debug_version + preinit cmdline).
   - `init_update_projectid.rc` — reconcile `/project_id` with the mboot-supplied one.
   - `init_tee_supplicant.rc` — `/application/tee-supplicant -d` (OP-TEE).
   - `init_rt_framework.rc` — real-time service framework (merak-family SoCs).
   - `init_svcmgr.rc` — `/application/gam/svcmgr` (service manager, the
     vendor's Binder-analog "servicemanager" of mi_ipc).
   - `init_midaemon.rc` — `/application/miaudproc` + `daemon_profile`,
     `/application/mi_daemon_sys.bin`.
   - `init_delay_mount.rc` — mounts `/3rd` (ro over dm-verity via avb_mount)
     + `/cache`, `mount_cusdata.sh`.
   - Optionally `mount_overlayfs.sh`, `init_voicesdk.rc`, zram init.
   `touch /tmp/vendor_all_ready` is the barrier; the *Kilby* side waits on it.
4. **rc.local** — tmp dir scaffolding (`/dev/shm/shm_tmp/<app>` with
   per-app uid/gid ownership — chrome, alexa, airplay, avahi, dplus, netflix,
   cobalt, vibra, factory_service …), then syslogaliases, kprop-driven.
5. **OEM facstart hook:** at the bottom, `source /usr/local/scripts/OEMfacstart.sh`
   → (quoting `tvroot/usrlocal/scripts/OEMfacstart.sh`) chains
   `sub_deploy_scripts/setup_system.sh` style OEM boot depending on `SYS_ODM`.
6. **customer card:** `getty` on ttyS0 → `cli_login.sh` (uses
   `/etc/{0001-cli-login-aes.pem,0002-cli-login-sign-public.pem}`,
   `cli` accepted in `usr/bin/cli`; suppors "serial check" mode).

## Kilby — the real service framework

`init_kilby.rc` waits for `/tmp/vendor_*_ready`, then (`kilbyKinit=1`)
`/usr/local/scripts/start-kilby.sh`, which:

- starts `syslogd`/`klogd` (busybox), `syslogviewer` log router;
- `kinit -p -e &` → the **kproperty daemon** (`/dev/__kproperties__`,
  `/var/run/kproperty_service`) — an Android property service: `kprop`,
  `setkprop`, `getkprop` in `/usr/local/bin` are its gawk-less CLI. It's read
  from the `init.rc` in the same dir (`usrlocal/scripts/init.rc`):
  `on property:init.boot.action.second=1 → class_start second-service`, etc.
- runs the `init.rc`-declared services — classes so started:
  - **early** (property `…none`): `syslogviewer`, `biz` (broker daemon,
    uid 341), `chassis` (startup hw skeleton), `sysmain`, `mediamain -D`;
  - **second** (`init.boot.action.second=1`, set by `start-kilby.sh` after
    `/sbin/setkprop` echo): `systemserver` (per-uid apm), `tvmain -D`,
    `avmain -D`, `sololp64` (aarch64 runner);
  - **deployed** (`init.boot.action.deployed=1`): `knode -m node -d` (Node.js
    embedder), `superwatch`, `superwatch_server`, `mdharvester -d3000`,
    `masman -a -p dvb -u 127.0.0.1:12321 …` (Multi-Audio-… DTV agent);
  - **post**: singing long service. plus `initspecialenv`, `inithitast`.
- after props: `setkprop init.boot.action.deployed 1` (the framework allows
  the class "deployed" to start), waits for `post_insmod_finish`,
  `vendor_all_ready`, starts zram etc.
- finally `/usr/local/scripts/start-deploy.sh` (deploys VIDAAs from serialdata
  into /var/local, `/opt`, `/hidata/model` copy into RAM), `/APPS/pkgs` ipk
  handling (see `40-version-facts.md`), ipked via `ipk-*` scripts.

**Property API** (`kilby.sl2.*` names are used end-to-end from vendor apps to
the ota_upgrade binary — e.g. `kilby.sl2.action.software.update.start.download/x`,
`kilby.sl2.i32.software.update.download.progress/rw`). Permission encoding is
`/r`,`/rw`,`/x` suffix. Everything is dispatched via `kcomd` (kilby com
daemon, `/usr/local/bin/kcomd`) → under the hood there's one socket per
grandname (`var/run/kproperty_service`).

## The process tree as shipped (from `meta/runtime.txt`, minus our dropbear residue)

Notable *factory* processes, all started via kinit classes:

| PID cluster | User | What |
|---|---|---|
| 704/705/706 | 341/342/340 | `biz`, `chassis`, `sysmain` — the 3 Kilby core services |
| 707 | 345 | `mediamain -D` |
| 709 | uid 351 | `syslogviewer` |
| 1188 | UhisApm | `systemserver` (main app-man hybrid) |
| 1189 | 343 | `tvmain -D` — DTV middleware main |
| 1191 | 344 | `avmain -D` — A/V pipeline |
| 1235 | — | (kernel threads) |
| 1439 | root | `rcS.utopia.linux` (asynchronous, still in-flight) |
| 1646 | loewe | `app_man -c /basic/am_config -input_fifo` (concurrent app manager) |
| 1833 | voicesdk | `voicesdk_server` |
| 2753 | UhisBrow | `browser` (odin) + zoom's Chromium `zenixservicework` renderers (Chromium 111, the render stack this project studied) |
| 2756 | 372 | `mosquitto_mosquitto` — MQTT |
| 2760 | UhisOta | `ota_upgrade` (see 30-update) |
| 2764 | UhisLog | `hi_logreport_service` — telemetry! |
| 2800 | 372 | `iot_service` (matter) |
| 2802 | UhisDial | `dialserver` (DIAL discovery) |
| 2848/22533 | UhisPhoe | `phoenix` ×2: server (`phoenix.server.js`) + faas worker — the **localhost:9009 bridge** (MQTT broker on :10377, the "no auth" bridge) |
| 2857 | 356 | `airplay_bridge` |
| 2881 | 385 | `capture` (frame-buffer capture service) |
| 2911 | 372 | `matter-tv-app` (chip KVS at `/var/local/iot/matter`) |
| 2914 | 386 | `avserver` (AV service) |
| 2917 | 384 | `karaoke` |
| 3168 | 340 | `wpa_supplicant` |
| 3278/3292 | 340 | `btmanager`, `btservice` |
| 3391 | 360 | `airplay` demo |
| 4111 | UhisHam | `HamService` (DLNA) |
| 4188 | 340 | `dhcpcd` (ip/pv6) |
| 4285 | amazon | `ignition` (Amazon VSK, `--launch-in-background`) |
| 4309 | UhisYout | `youtube` (cobalt container) preload |
| 5641/6884 | UhisAvs | `AlexaNativeAppService`, `voiceservice` |
| 6886 | UhisDlna | `dlna_service` |

`Uhis<Name>` usernames are fictional/auditable only inside `ps`, resolved by
uid via `kireg` data (`var/local/kilby/kireg-kilby0.dat`): those uids are
`313`-`386`-ish kilby subusers (UIDs are **assigned out of band**, not all in
`/etc/passwd` — passwd only carries the stable set netflix/chrome/amazon/
alexa/…).
Full passwd: `root, system(100), chrome 1000, netflix 1001, tester 1002,
sntpd 1003, log 1005, graphics 1006, bluetooth 1007, wifi 1008, net_mgr 1009,
watchdog 1010, panel 1012, dhcpcd 1013, metrics 1014, mdns 1015, audio 1016,
browser 1017, amazon 1018, vudu 1019, samba 1020, cobalt 1021, sraf 1022,
rpc 1023, dash 1025, qjy 1026, hls 1027, cmpb 1028, alexa 1029, dcc 1030,
netflix_cert 1031, qda 1032, svad 1033, airplay 1034, localking 1035,
shell 2000, inet 3003, net_bt_stack 3008, mi 3010, utopia 3011, mtal 3012,
fb 3013, cb 3014, event 3015, mali 3016, tee 3017, shm 3018,
dialserver 3019, playready 3020`.

## secure_exec

Every Kilby service runs as **`/usr/local/bin/secure_exec <label> <full-path> [argv]`**.
Per its own usage string it is *not* an integrity checker — it is a
**DAC shim**: `execvp` after setting uid/gid/groups/caps for `<label>`
(mapping resolved via `libsecure-processid.so`, `match_process()`); the
label name is how `ps` shows `UhisBrow`/`UhisPhoe`/`UhisOta` etc. That's the
whole mechanism — one root-owned launcher that demotes processes to the
kilby sub-UIDs (313–386 range) at spawn time. `libsecure-processid.so`
carries a `dynamic_permission` API so the labels can be granted/revoked
at runtime.

## The two big filesystem stores (VSM "VIDAA Software Manifest")

- **APPS (p54) + APPS2 (p46)** — ipk packages at `pkgs/<name>/{current,CHA,CHB}`
  (CHA/CHB = channel variants); `pkgs/opkgmeta/{status,info,lists,backup}` =
  opkg-like db. Upgrade-fills via "ipk-update" wrapper. Observed packages:
  `tv.vidaa.app.browser`, `tv.vidaa.app.phoenix`, `tv.vidaa.app.tvbrowser`,
  `tv.vidaa.app.youtube`, `tv.vidaa.app.operationui`, `tv.vidaa.app.osconfig`,
  `tv.vidaa.jsservice.basic`, `tv.vidaa.jsservice.system`,
  `tv.vidaa.lib.mediamain`, `tv.vidaa.lib.odin`, `tv.vidaa.phony.btrc`,
  `appconfigs`, `ipk_resource`. `pkgs/betaipk/oem` models.
- **tvroot (optfs p47, erofs, dm-verity)** — `/opt` (shared targets:
  `hisenseUI` (SystemUI binary + web), `mmlib`, `webengine`, `iot`, `netflix`,
  `alexa|avsservice`, `dial`, `airplay`, `karaoke`, `keystore`, `factory`,
  `TTS`, `flutter`, `cu...`) and `/usrlocal` (bootstrap scripts, sbin, etc) —
  this is what `/usr/local` **symlinks into** (`usr/local -> /mnt/tvroot/usrlocal`).
  ro except under OTA flows.
- **3rd (p28, avb-verified ro)** — `/3rd/Netflix` (nfxdevsplash etc.),
  `/3rd/airplay`, `/3rd/amazon`, `/3rd/dlna`, `/3rd/websocket_server`,
  `/3rd/bin/{wpa_supplicant,dhcpd,hostapd,iw…}`, `/3rd/upgrade -> /3rd_rw/upgrade`.
  `basic` (in-SYS root at `/basic`, from p3? actually from `/basic_mount_*` from
  rw copy — `basic_mount_rw` runs first, remount-ro later): `app_man`,
  `modules/` (kernel .ko loader), `bin/TSPlayer e2fsck`...

## Network posture (as shipped, before our residue)

- `init_iptables.rc` loads `etc/iptables/iptables.conf`, whose shipped filter
  skeleton is `-A INPUT -p tcp --dports 0:1023 -j DROP` (all low ports
  externally dropped) plus generated per-EULA chain rules from
  `security-firewall-*` scripts.
- Runtime capture (`meta/runtime.txt` `iptables -L`) shows:
  - INPUT policy ACCEPT, all traffic funnels into an active
    `FIREWALL_IN_EULAON` chain (150 K hit-packets; its rule contents weren't
    fully captured by the busybox `netstat`/`iptables` binaries we used);
  - the *off* chain `FIREWALL_IN_EULAON`/`FIREWALL_IN_EULAOFF` (0 refs) is
    fully visible: accept loopback, mark 0x64, icmp, :8090, :36669, then DROP
    of ~120 well-known vendor debug/audio/AirPlay ports (22, 23, 4033,
    10485, 12321, 3366/3367, 4635-4637, 6300-region, 6970-7014, 8086, 8554-
    8556, 9013, 9080, 9086, 10106-10113, 10120, 10205, 10480, 11669/11679 …);
  - OUTPUT only has two anti-collision rules around localhost :9000 and
    :8933 scoped to owner-UIDs (313=Uhis service, 317); everything else
    egress-unfiltered as shipped.
- Our own ACCEPT rules for 24242/24245/24246/24247 are **our** additions
  the author's additions, not vendor.
- Listening services (as shipped, minus our residue): mosquitto (:1883
  loopback-style per config), iot_service, matter-tv-app (5552),
  dialserver, phoenix (:9009 host-bridge area), telnet **not** in factory,
  no sshd in factory. Full listener list was to be re-derived from a live
  `netstat -tln` since the saved run used busybox netstat which rejected
  `-tlnp` (its output shows only usage text — treat saved netstat section
  as not usable).

## Crash/ANR plumbing

- `/var/crash` tmpfs; `coredump.sh`; mount-miss breadcrumbs in
  `/var/crash/core_anr_pid_*_anrmount_crash_stack.txt` — mount_his failure path.
- `monitor-appmanio.sh` watchdog (root, script under `usrlocal/scripts`),
  `superwatch(_server)` requestline. The "rebootByHUI" channel from ota bin.
- `start-resmon.sh` — resource monitor (`resmon_lite`).
