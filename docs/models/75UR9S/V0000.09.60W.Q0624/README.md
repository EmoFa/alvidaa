# 75UR9S / V0000.09.60W.Q0624 — root SSH over the package manager (MT9655, W build)

**Status:** root SSH (uid 0, `CapEff 000001ffffffffff`, key-only) verified on
2026-11-04. No automatic boot persistence on this build: re-arm after every
reboot (uninstall `83` + install `82` of the installer IPK).

> **Applies to `75UR9S` (MTK9655, VIDAA `U09.0`, region US) running
> `V0000.09.60W.Q0624` (kernel build 2026-06-24).** This is the 100U7Q chain
> ([guide](../../100U7Q/V0000.09.60I.Q0813/README.md)) adapted to the newer
> `09.60W` build. The differences below are measured, not assumed.

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
| Dropbear start flag | `-s` (disable password auth) | `-s` is `Invalid option` when the build has no password auth compiled in; this build uses `DROPBEAR_SVR_PASSWORD_AUTH 0` (key-only by compile), start without `-s` |
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
   redirect, per-step logging, env dump, no `-s`).
4. Result: superwatch reply `90:0` (OK); postinst log shows `pid=5012`,
   `0.0.0.0:8008` LISTEN in `/proc/net/tcp`; `ssh -p 8008 root@<tv>` gives
   `Uid: 0`, `CapEff: 000001ffffffffff`.

## Connect

```sh
ssh -p 8008 -i server/keys/tv_root_ed25519 root@192.168.1.20
# minimal PATH in the session: export PATH=/bin:/sbin:/usr/bin:/usr/sbin
```

Key-only; no password auth compiled in. PTY: the postinst `chmod 666`'d
`/dev/ptmx` (verify with `ssh -tt` if a PTY is needed).

## Re-arm after reboot

No boot hook (same as 100U7Q). Re-open the install page (it now sends
uninstall + install), or send both commands to the superwatch socket.

## Rollback

- Uninstall: `{"list":["70:83:70;re.installer"]}` via the same socket path.
- Then remove: `/APPS/.re_sshd/`, `/APPS/shell`, `/APPS/installer.ipk`,
  `sw2.js` from the basic package's `functions/fetch/`, and the
  `/dev/ptmx` mode change if exact pre-run state matters.
- Verified boot untouched (erofs + dm-verity, nothing written to `/`).

## Open items

- OTA freeze: **owner disabled OTA in the TV settings menu** (2026-11-04) —
  no in-kernel freeze needed. No iptables on this build; no OTA daemon
  observed running; `/OAD` logs contain no endpoint data. (Fallback if ever
  needed: router-side block, or point `/var/local/etc/resolv.conf` at a
  sinkhole DNS — the symlink target is writable.)
- Boot persistence candidates (appinfo.json `Main: pkgapp://`, `run_phoenix.sh`,
  systemserver start list) untested here.
- `gettvstate`/launcher lane untested on this unit.