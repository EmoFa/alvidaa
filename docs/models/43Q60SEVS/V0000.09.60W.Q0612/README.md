# 43Q60SEVS / V0000.09.60W.Q0612 — root over the package manager + binary-less boot persistence (MTK9603, EU_A)

**Status:** root verified (13 `postinst` runs as uid 0 across probe IPKs
v1.0.0–v1.15.0); boot persistence through the vendor's own service manager
proven across a real power-cycle. No binaries shipped.

> **Applies to `43Q60SEVS` (MTK9603, VIDAA `U09.60`, region EU_A) running
> `V0000.09.60W.Q0612` (build 2026-06-12).** Same three primitives as the
> 100U7Q / 75UR9S chain — fetcher write, `/function` exec, superwatch install —
> but a different persistence layer: this build ships no Dropbear, so the
> vendor service manager carries the boot hook instead.

Everything in this file was measured on the device by the
unit's owner, in the standard research frame: verified boot untouched, no
writes to read-only mounts, no `/OAD`, every state change reversible, and the
teardown plan written before the first command.

**Independence note.** This work was discovered and verified in parallel to the
concurrent `75UR9S / Q0624` report but with no shared input — the convergence
on the same ipk-post-install root chain is therefore an independent
replication across two units of the same firmware family, not a follow-up of
another study. Later alignment is documented here.

## The verified chain

1. **Write primitive** — the vendor fetcher microservice (`basic/fetcher`,
   `fetchFile`) writes arbitrary bytes anywhere uid 314 can reach
   (including the FaaS function directory). The argument is `directory`
   (not `path`); the module allows a `permission` argument that maps to
   `chmodSync`. No file-extension whitelist, no `mkdir` (helper modules do
   that).
2. **Execution primitive** — `POST /function/basic/fetch/<name>` runs
   whatever module file sits at
   `/APPS/pkgs/tv.vidaa.jsservice.basic/current/functions/fetch/<name>.js`.
   No allow-list, no signature gate. Worker identity on this unit:
   uid 314, node 20.19.4, arm, cwd `/APPS/pkgs/tv.vidaa.jsservice.basic/CHA`.
   The require-cache makes each run need a fresh module name (nonce).
3. **Root channel** — the worker's supplementary groups include the
   superwatch socket's group (616); the socket is `mode 660 uid 0 gid 616`,
   connectable as uid 314. Protocol is length-prefixed
   (`<sessionId>:<commandId>:<message>`), install command is `82` with
   `<session>;<ipkPath>;<package>;<options>` (options left empty),
   uninstall is `83` with `<session>;<package>`.
4. **Root execution** — opkg runs the IPK's `postinst` as uid 0. Verifiably
   minimal IPK (794 bytes, one data placeholder) whose postinst writes only
   `/APPS/.re_root/PROOF`: `Uid: 0 0 0 0` from `/proc/self/status`, read
   with pure shell builtins (every external command in the postinst PATH is
   a discovery hazard — `id` and `uname` are missing there, `mount` and
   `date` exist).
5. **Persistence (no shipped binaries)** — a two-file service
   (`CHA/services/resvc/`: `index.js` extending `@sdk/baseService.js`
   plus a tiny `package.json`) appended to an already-rw vendor package,
   with one line in the package's `serviceList.json`
   (`{id, autoStart:true, isKeepAlive:false}`), made the vendor's own
   service manager run owner code on **every boot** as uid 314. Proven
   across a real power-cycle: marker file contains
   `resvc boot-run <timestamp> pid=2524 uid=314`. Root itself stays
   click-gated; the persistent layer writes one marker and nothing else.

Rollback paths, all measured: `83` uninstall, `serviceList.json` full
overwrite, unarm-overwrite disarm of every module (the FaaS directory has no
delete primitive, so cleanup is overwrite-with-zero by convention).

## System map (read-only findings)

- Mount plan: `/` `/application` `/vendor/lib` `/usr/local` `/opt` `/3rd`
  are device-mapper read-only (`kverityd` kernel threads active — dm-verity
  at runtime). rw: `/certificate` (noexec), `/data`, `/Customer`,
  `/var/local`, `/var/tvservice` (noexec), `/vendor/persist`,
  `/vendor/uuenv`, `/cache`, `/APPS`, and `/OAD` (rw — never touched).
- `inetd.conf` ships live-looking `telnet/ftp/rsh` entries, but **inetd is
  not running** (`pidof inetd` empty) — config presence is not service
  presence. Listener list came from `/proc/net/tcp` + `tcp6` instead.
- Listening surface: dual-stack on 1883 (MQTT!), 7000, 9001, 3366, 3367,
  10001, 11669, 16669, 36669; single-interface 18400; IPv6-only extras 4445
  (SystemUI) and 9888 (HTTP bridge). localhost-only: 2121–2125, 1969,
  12321/12322, 3822–3827, 11600/11601. No ssh/telnet/ftp listeners.
- iptables: INPUT policy ACCEPT with SYN/ICMP/CC flood guards only —
  unlike some builds, **iptables exists on this firmware** (an EU_A delta).
- Boot chain: `init [3]` → `/etc/init.d/rcS` → `rcS.utopia.linux` →
  `rc.local`; the vendor homepage start is `/opt/hisenseUI/startgui.sh`
  (`pidof SystemUI` guard, `HI_UI_HOME=$(GET_PKG_DEST tv.vidaa.app.ui)`
  with an rw-package preferred lookup into `/APPS/pkgs`, fallback
  `/opt/pkgs/...`).
- Root console is USB-dongle gated (`rootlogin.sh` → `check_usb_key`,
  built from `md5(VID+PID+Model)`); `cli` account is a signed-package
  console that sets SELinux permissive for its own menu (`setenforce 0`
  while logged in).
- `busybox` v1.34.1 exists at `/usr/local/bin/busybox` but ships **no**
  server applets: no `telnetd`, `httpd`, `tftp`, `ftp`, `nc`, `crond`.
  Full applet list captured.
- `/usr/local/bin/superwatch_server` runs as root (pid visible in `ps`).
  OP-TEE `tee-supplicant` active. UI runs as uid 311 with
  `--url=file:///hisenseUI/index.html` where `/hisenseUI` is `ui-engine`'s
  internal namespace, not a filesystem path (resolution attempt: ENOENT
  from the worker namespace).
- opkg status DB actually lives at `/APPS/pkgs/opkgmeta/status` and updates
  after `postinst` completes (the running postinst still sees the previous
  version row). Architecture on this SoC is `mtk9603` — surfaced by reading
  the device's own `opkg.conf`, not inherited from model docs.

## Open follow-ups

- Launcher replacement: the vendor gateway is `GET_PKG_DEST
  tv.vidaa.app.ui` (rw-preferred lookup into `/APPS/pkgs`); the RO original
  payload is 63.8 MB with SafeStart-registered `packageinfo.json`. Shadow
  copy feasibility measured, not enforced on this unit.
- `appinfo.json` app registration (`pkgapp://<pkg>/<script>` nativeType
  entries) makes apps *launchable* but the visible home tile list is not
  built from it — verified negative: registering an entry did not add a
  home-screen tile.

## Sibling-software relevance

Everything load-bearing here is volume-generic rather than board-specific:
the fetcher/service-manager/superwatch chain, the `serviceList.json`
persistence surface, the `pkgapp://` registration scheme, the
`startgui.sh`/`GET_PKG_DEST` launcher gateway and the opkg layout are all
VIDAA-framework constructs, not MTK board bindings. The genuinely
per-unit variables are few and cheap to re-derive per device: the opkg
`Architecture` string (read it from the device's own `opkg.conf`), the
socket group membership (one `/proc/self/status` read), the exact
browser-shell UA matrix, and partition numbering. Owner research on
**sibling VIDAA models of the same firmware generation (09.60X/W family,
MTK9655/9603/9618 and later 09.x builds) is therefore expected to find
the same three primitives within minor deltas** — the matrix rows and
this document are written to make that a fast, checklist-driven test
rather than an open-ended search.

## Cross-reference

Root chain convergence with the concurrent `75UR9S / 09.60W Q0624 (MT9655)`
study: same three primitives (fetch write, /function exec, superwatch
install). Deltas measured: FaaS fetch, moved to the basic package on
09.60W (matches this unit), `Architecture` resolution differs per SoC
(`mtk9603` here), iptables present here, dropbear not present here
(`/usr/sbin` empty), which is why this unit's persistence is delivered by
the vendor service manager instead of a shipped shell binary.

All payloads and probe pages stayed local; only this sanitized document
enters the repo.
