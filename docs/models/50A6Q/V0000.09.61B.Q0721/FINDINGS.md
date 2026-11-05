# Findings 12 — Hisense 50A6Q (NT72690 / 09.61B): first probe of the Novatek lane

> First entry for a **Novatek** SoC and a 09.61B build; neither is in the
> inventory yet. Community model: 50A6Q (EU/intl naming; TV self-reports
> 50A60QXVT / 50A6QX). Probe: `launcher/recon-a6q.html` (read-only v1),
> 2026-11-04, TV on LAN <TV_IP>, server on <LAN_BOX>:8770.

## Fingerprint

| Field | Value | Source |
| --- | --- | --- |
| Model | 50A6Q (50A60QXVT per UA) | UA string |
| Firmware | V0000.09.61B.Q0721 (build 2026-07-20) | user + UA |
| VIDAA OS | U09.61 | `Hisense_GetOSVersion()` |
| SoC | **NT72690 (Novatek)** | `Hisense_GetChipSetName()` |
| Arch | **aarch64** | UA (`X11; Linux aarch64`) |
| Browser | Odin Chromium 111.5563.5.1 | UA |
| `transport_protocol` | 3290 | SSDP `modelDescription` |
| region | 4 | SSDP |
| MACs | eth `<MAC_ETH_NOCOLON>`, wifi `<MAC_WIFI_NOCOLON>` | SSDP |

Modern MQTT pairing (cert + dynamic creds, "modern" profile) already worked
on this set 2026-11-03 — `transport_protocol=3290` as predicted.

## Bridge probes (read-only)

- `HiUtils_createRequest` present; `HiUtils_sendPlatformMessage` absent
  (differs from the 09.60V freeze-bug context); no `WebSDK_*` shims.
- **errno leak works**: absolute read of `/etc/passwd` returns
  `open("/APPS//etc/passwd") -> ENOENT` — same `/APPS/` chroot shape as 09.01.
- **Traversal is closed, and the rejection is a validator string**:
  every `../…` read returns `invalid path:../etc/passwd` — not an errno.
  That is the same class as the 09.60V EU_A "literal `../` substring test":
  the path is rejected before the chroot prefix is ever applied. The
  base-prefix bug is known; the input filter is the wall.

## What this means

1. **Classic otaTest chain: dead on arrival** (traversal closed → no write
   outside `/APPS` bases regardless of write permissions).
2. **Novatek is a new lane.** Every root in the inventory is MTK or
   MT53xx-class; the NT72690 firmware is a different build lineage. The
   09.60V gate findings (identity gate on fileWrite) may or may not carry
   over — **fileWrite is untested on this set**.
3. **aarch64, not armv7** — toolchain retarget: `aarch64-linux-musl` via
   `zig cc`. V8 pointer compression (and possibly the V8 sandbox) is likely
   ON here, unlike the armv7 units — the "favorable N-day target" note in
   the playbook weakens for this arch.
4. Next probes (recon v2): fileRead of `websdk/Appinfo.json` (in-base read),
   a button-gated fileWrite marker into an allowed base (write-gate test),
   and the `deviceCode` action (security-code forge precondition).

## Operational notes

- The box server initially ran with the reference TV's `config.json`
  (Doom shortcut, watcher enabled) — it attempted `ssh root@…:2222` (doom
  watchdog) and logged MQTT publish failures. Reset to a minimal config;
  do not copy reference-TV config to a new set.
- TV friendly name: "<friendly-name>" (SSDP). Recon page flashes on screen for
  the probe duration (~1 s of probes, stays until closed).

## Recon v2–v6 (Nov 4, evening): the array-path bypass and the factory lane

### The validator, from its own source (in-base reads of `/APPS/pkgs/.../services/hiutils/`)

`fileOperation.js` — `fullPath = pathList[mode] + path`, then
`if (params.path.includes('../')) return cb(false, ...)` — **`.includes()` on an
attacker-controlled non-string**. `path: ["../etc/passwd"]` (JSON array) fails the
substring check (array element equality) and string-concats to `/APPS/../etc/passwd`.
**Proven live (recon v4): arbitrary fileRead as phoenix (uid 314, CapEff 000…80 a.a.).**
`writeFile` has the same flaw. Raw API on `localhost:9009/service/hiutils` is
unauthenticated (no `identifier` needed); validator runs server-side (shim bypass N/A).
`/etc/shadow` → EACCES (boundary real). No `/etc/rc.local`; busybox init,
`::sysinit:/etc/init.d/rcS` → `S??*` loop. Kernel 5.4.283 aarch64, **armhf (ELF32) userland**.

### The factory lane (recon v6) — root exec candidate, no traversal needed

- `models.ini`: `SERIALS = NOVATEK_72690_EU_4K_1080P` → the `OEMfacstart.sh` loop runs
  (30 × 1 s): on `/tmp/cvtefac` it `secure_exec`s `/opt/cvte/start-cvtefactory.sh` **as root**
  (`secure_exec` = match_process + execvp + set uid/gid/caps, ships with the factory flow).
- `start-cvtefactory.sh` iterates `/tmp/lo_*/` and **executes `cvte_autorun.sh`
  directly from the root shell** (`$usb_path_home/$usbpath/$exec_usb_cmd`) — no
  signature check on the payload script itself. `/tmp/lo_*` is also where the UART
  gate looks for `securecode.key`, so `lo_*` dirs are a normal artifact.
- phoenix can write `/tmp/lo_x/cvte_autorun.sh` + `/tmp/cvtefac` via mode 0 — plain paths.

### Open questions (next session)

1. Who invokes `OEMfacstart.sh` (which S??* script) and does its 30 s window overlap
   phoenix's start? `/etc/init.d/` can't be listed (EISDIR oracle only) — no dir-read API.
2. Does `/tmp` persist across a real reboot (fstab has no /tmp entry; root is `ext2 rw,noauto`!)?
   Persistence test: write marker → power-cycle → read back.
3. `secure_exec`'s `match_process` config (dynamic_permission / libsecure-processid.so /
   cJSON) — does the `cvtefac` label pass? The flow is shipped, so presumably yes.
4. fileWrite bypass untested (recon v2 button was never pressed). Root is `rw` per fstab —
   test whether `/etc/...` takes a write (EROFS oracle) before assuming squashfs-ro.
5. Write-test → stage payload+trigger → real power-cycle → check root exec. 42-partition
   dump + OTA freeze should happen before the first reboot that matters.

Server note: a stale second vidaa_server (port 8767, `~/firm/firm`) squatted the MQTT
session for ~20 h and caused intermittent /api/open failures — killed; one server per TV.

## Write primitive and the root-door hunt (Nov 4, late evening)

### Capabilities gained (all as phoenix uid 314)
- **Arbitrary file READ**: array-path bypass (`path: ["../…"]`), v4-proven.
- **Arbitrary file WRITE**: the `fetcher` service (`permission: {}` → "No auth apis
  configured, check passed") exposes `fetchFile {url, directory:<full path>}` via
  `/service/basic/fetcher`, ungated. `fetchResponse` likewise (SSRF/GET oracle).
  `fetchFile` **replaces existing files** in phoenix-writable dirs (proven — a failed
  download truncated `services/hiutils/package.json`; restored from captured bytes).
  No mkdir.hotel dirs/tmp `.tmp` missing → dir-creation blocked.
- The sensitive-API gate (`serviceManager.checkRequestPermission`) decrypts
  `identifier` = AES-256-CBC(identifierKey, iv='0'*16) over `<uptime>+<appid>+<perms>`,
  freshness `seconds - timenow > 3` (future timestamps pass). identifierKey =
  `get_security('IDENTIFIER_KEY')` — native, non-printable, lossy-read destroys it.
  `securityEncrypt` (ungated!) is a deterministic AES oracle but with a different key.
  `tv_secret_keys.json` = cloud img_key, not the identifier key.

### Root-exec doors examined (all blocked so far)
- No `/etc/rc.local`; rcS → `S??*` (names unlistable — no readdir anywhere).
- `start-kilby.sh` (root, boot): **`hotelmodeProcess()` evals content of
  `/var/tvservice/hotel/hotelmode.ini`** — perfect injection — but the file is
  root-owned (EACCES) and `hotel/` is not phoenix-writable. OEM deployData
  (`cp $dir/$file /$file -af` as root, driven by our ini) blocked: `/var/local/.tmp`
  missing, no mkdir. `set_ipk_path.sh` flips only CHA/CHB symlinks. `loadbtwifi.sh`
  case-statement is clean. euladpp tar: `/APPS/euladpp/eulaDpp.tar.gz` root-owned
  unwritable, consumer unknown. `/proc` environ/maps of other uids: EACCES.

### Next step (staged, pending go): sandboxed code exec via tilesService
`fetchFile` can replace `services/tilesService/index.js` (system jsservice — NOT the
bridge process). Patch = original + 137-byte delta: `try { require('./a6q_boot.js') } catch {}`
inside `start()`. `a6q_boot.js` (syntax-validated, on the box) = recon only: uid/groups,
readdir of /etc/init.d, /usr/local/*, /proc walk (all root processes + cmdlines), SUID
scan; reports via HTTP POST to the box. Broken payload = caught = service continues.
Original JS kept on the box for instant restore. Then one power-cycle.

## Main-hook deployed; tvinfo regression; deadlock (Nov 4, night)

### What works
- **Persistent boot-time code exec as uid 314, every boot** (2/2 cold boots): the
  `hiutils/package.json` main-hook (`main: hiutils_boot.js` → try/catch
  `require('./a6q_boot.js')` → re-export original) survives and runs; payload reports
  via HTTP POST to the box (12.5 KB recon: uid/groups, /etc/init.d listing, /proc walk,
  SUID scan — **zero SUID binaries**).
- Full boot architecture mapped: kinit (root) → init_kilby/start-kilby{,1,2}.sh;
  8 phoenix processes (basic + system + package hosts), no crash loop; root procs =
  init, kinit, superwatch_server, com.nvt.appmgr, start-security.sh (root sh),
  checkEmergentOTA.sh, syslogviewer, getty.
- `restorephoenix.sh` (root): opkg --force-reinstall of phoenix/basic/system from
  /opt/pkgs/backup/*.ipk — a stock-recovery path that exists independently of us.

### The regression
- **tvinfo does not register in the basic phoenix on both post-hook boots**
  (`service register failed`; was up pre-hook — fetchFile worked all evening).
  Consequence: `fetcher.checkRequestCondition` (getTVAPI('netStatus')) fails →
  **no new file deployments** (fetcher is the only ungated writer). TV itself works
  (YouTube OK). Root cause unproven; prime suspect: the v1 payload's synchronous
  boot-time fs work racing tvinfo's init (15 s delay may overlap the init window),
  or the extra files we created in the tvinfo dir. Deterministic 2/2 — reboot alone
  won't clear it if it's the overlap.
- v2 payload (mass script reader + full proc map + 60 s delayed start) is written,
  syntax-validated, sitting on the box — undeployable until any writer path returns.
- Deadlock: no remote revert (revert needs a writer; writer needs tvinfo).
- Dead ends closed: identifierKey (native, lossy-read-proof; securityEncrypt oracle
  uses a different key), euladpp tar (root-owned archive), OEM deployData (needs
  /var/local/.tmp mkdir), pfm-manager eval lane (needs /var/local/pfmParse mkdir),
  hotelmode.ini eval (root-owned file), SUID scan (none), GET-dispatch (args-as-string),
  no-Origin bypass (browser always sends Origin; GET can't carry object args).

### Exit ladders
1. Factory reset wipes /APPS + /data + /var/local + /tmp → guaranteed stock (hook lives
   only there); verified boot untouched throughout.
2. restorephoenix.sh would reinstall jsservice pkgs from backup IPKs if its trigger
   fires (caller not yet identified).

## THE CASCADE (Nov 5, ~00:30): full gated-API breach via in-process ISC

**The unlock: the boot payload runs INSIDE phoenix — `serviceCallAPI` (ISC) hits
`checkRequestPermission` with `origintype='service'` → `return true` — NO PERMISSION CHECK.**
The HTTP identifier gate is irrelevant for in-process callers.

Chain (all from the boot payload, `a6q_boot.js` v3.2d):
1. `getTVAPI('deviceCode')` → `<MAC_WIFI>` (wifi MAC! — key names are swapped vs intuition)
2. `getTVAPI('macAddress')` → `<MAC_ETH>` (ethernet MAC)
3. `device_code = md5(deviceCode)[:6]` = `<dc6>` (the MD5 step is mandatory — first attempt used the raw MAC → 30004)
4. security code = `"0" + "9999" + auth8 + "9" + "0" + "00"` where auth8 = HMAC-SHA1(key=base64(dc6), msg=mac+"2015-01-01"+"9") weird-hex-arithmetic % 1e8 — ACCEPTED by checkAccessCode → **security_level = 9** in the live hiutils instance
5. `setDebugPort(1)` → **`devtoolSwitch = 2` — develop DevTools enabled on the TV browser** (port binds on browser restart; the EULA firewall blocks it externally — needs an ACCEPT rule or localhost access)
6. ISC `fileWrite`: success — in-process writes need no identifier at all

Notes:
- The identifier/HTTP gate became moot: ISC is the cleaner bypass for everything in-process.
- The security code is STABLE for this device (deviceCode/mac are static; valid 9999 days).
- Gotchas: service state 2 ("wrong state") after listeners drop — OOM-reload via huge fileRead
  (the 100MB node binary into a 9MB heap) restores state 1 reliably; the fetcher's 30MB
  fetchResponse does NOT kill the process (faa streams); payload markers must be renamed per run
  (they self-write even on error paths); TV clock skews after cold boots (cosmetic).
- Keys extracted in-process (v3 report): IDENTIFIER_KEY (32b), SERVER_PRIVATE_KEY (RSA 1676b),
  IPK_KEY (32-char value redacted).

## The IPK lane (Nov 5, 02:00–03:00): pkgmgr.debugInstall → superwatch (root) — install succeeds, extraction unresolved

### The chain, verified from source + live
- `pkgmgr.debugInstall` (AppUpgrade.js:1479): **NO signature check, NO integrity check** — parses the IPK
  control (opkg info), registers it, calls `opkgInstall(ipk, '--force-downgrade')`.
- `opkgInstall` → **superwatch_server (root)** via unix socket `/var/run/superwatch_socket`:
  message `<sessionId>:82:<sessionId>;<ipk_path>;<Package>;<options>` (4-byte LE length prefix).
  commandId 82 = install, 83 = uninstall. MAX_PARAMS 256. Result → `/tmp/ipk_install_result` (JSON)
  + `/tmp/ipk_install_status` (step lines). Socket response: `<sessionId>:<code>`.
- The payload reaches pkgmgr via **ISC (service origin → permission check skipped)** — no HTTP gate.
- `getDownloadBaseDir()` = `/OAD` (APPSEXPAND env) → `/OAD/pkgs/download/` (exists, writable).
- RSA signature wall: keys at `/opt/pkgs/rsa_public_{2048,4096}.key` — **read-only rootfs** → forgery dead;
  salt = `59ae11c25af312e97846f1cffc7c2ccd81aab9aa`; verification = RSA-SHA256 over md5(SHA256sum-field)+salt.

### Live results
- Direct socket install (bypassing pkgmgr's own cleanup): **`resp: 42:0` / `77:0` / `88:0` — code 0 SUCCESS**;
  status file progressed to `[tv.vidaa.app.debug]step:finish`; the opkg DB registers
  `tv.vidaa.app.debug 1.0.0 "install user installed"` (path field empty) — **installed by the root daemon**.
- **BUT**: the data.tar contents (`./var/local/.a6q_root/proof.txt`) and the postinst script left **no trace**
  on any writable partition (swept /, /APPS, /OAD, /vddt, /var/local, /hidata, /usr/local, /tmp, pkg-dirs).
  The result file was captured EMPTY mid-run and deleted after (racing pkgmgr's cleanup loses; in the direct
  socket path pkgmgr isn't involved but the file still ends up empty/gone).

### Open questions (next session)
1. Where does this opkg extract data? (dest config not at /etc/opkg.conf, /usr/local/etc/opkg.conf,
   /APPS/pkgs/opkgmeta/opkg.conf; status DB not at /usr/lib/opkg/status; the opkg binary uses **libarchive**)
2. Does this opkg build run maintainer scripts (postinst) at all?
3. Capture the result file content: a 200 ms poller during the install, or make superwatch write it and read
   before pkgmgr's rm (direct socket path has no rm by pkgmgr — check again after a run).
4. Full opkg binary dump (the 8 KB/60 KB slices truncated — read in chunks via the payload) for the dest/conf
   strings and the maintainer-script logic.
5. `--force-reinstall` may be dropped by superwatch's arg handling → same-version reinstall may no-op
   (explains code 0 with nothing extracted on the second+ runs; the FIRST run's extraction still unexplained).

## 🔴 ROOT CONFIRMED (Nov 5, ~02:15): the PFM/eval chain

The complete chain, every step verified live:
1. `fetchFile` (ISC, ungated) delivers `/var/local/pfmParse/PFMCheck` (eval payload) +
   `Data/platform.txt` (control vars) + `/var/local/DebugPowerup` (the gate flag)
2. Cold boot → start-kilby (root) → `[ -f DebugPowerup ] && pfmDebug` → PFMCheck exists →
   `bash pfm-manager.sh &` (root, background)
3. pfmAutorun → `getPFMCheck` → **`eval "$line"` per line of PFMCheck → uid=0 execution**
4. Proof: `/var/local/.a6q_root/proof.txt` = `uid=0(root) gid=0(root)` on Linux NT72690 aarch64

**The three files persist across reboots** — this is boot-persistent root code execution.

The self-cleanup: PFMCheck sets `runCount=99`, platform.txt sets `runMaxCount=1` → pfmAutorun
hits the `runCount >= runMaxCount` branch → `rm -rf pfmParse + DebugPowerup` → self-cleaning.
Re-plant all three via fetchFile for the next boot.

The debug framework: Hisense's own PFM (Performance Monitoring) boot-time debug hook, gated by
DebugPowerup, driven by eval'd config files — a root exec primitive left in production firmware.

### Gotchas (all hit live)
- `DebugPowerup` must exist (the gate nobody mentions)
- `platform.txt` is MANDATORY for pfmAutorun (missing = silent exit before getPFMCheck)
- The PFMCheck eval lines run in order — variable assignments + commands can be mixed
- The TV clock resets to epoch on cold boot (NTP syncs later) — dates in proofs show 1970
- The eval runs very early in boot — files needed at that point must be delivered in a prior session

## The dropbear war (Nov 5, evening–night): four boots, four distinct walls

Root exec is stable; the fight was getting SSH listening on 2222. Each boot exposed one wall.

### Wall 1 — the `-r` flag bug (v9/v10 era, fixed)
The eval line used `-r /var/local/.a6q_authorized_keys`. In dropbear, **`-r` = host key file**,
not authorized_keys. Feeding it a pubkey file → dropbear exits silently (stderr was `2>/dev/null`).
Fix: `-r /var/local/.a6q_host_ed25519` + `-R` (auto-generates host keys into a writable path —
the rootfs is ro, so `-R` alone targeting /etc/dropbear_* would fail). authorized_keys belongs in
`/root/.ssh/authorized_keys` (the eval already copies it there).

### Wall 2 — the vendor firewall (mapped at boot #4)
- iptables exists (`/usr/local/bin/iptables`) and works. Early boot, the xtables lock is
  sometimes held ("Another app is currently holding the xtables lock") → retry loops required.
- INPUT's only rule: `-A INPUT -j FIREWALL_IN_EULAON` — the "EULA firewall" chain, created by a
  vendor daemon AFTER our boot eval runs. Contents (boot #4 dump): allowlist accepts (loopback,
  mark 0x64, ports 36669/9226/8086/9080/…/13452/19500/…/36669, DHCP/SSDP/MDNS/UDP set,
  ESTABLISHED, icmp) → `FIREWALL_IN_EULAON_DYNAMIC` → **final `DROP all`**. 2222 not on the list.
- 9226 works externally because it is explicitly allowlisted — explains the earlier
  "firewall blocks DevTools" observation resolving after `setDebugPort(1)`.
- **Neutralization that works** (boot #4, verified by dump): insert
  `iptables -I INPUT 1 -p tcp --dport 2222 -j ACCEPT` **and** `iptables -D INPUT -j FIREWALL_IN_EULAON`
  — INPUT policy is ACCEPT, so deleting the jump opens inbound. An eternal root loop re-applies
  both every 15 s (survives daemon rebuilds) and dumps `iptables -S INPUT` +
  `-L FIREWALL_IN_EULAON -n` to `/var/local/.a6q_root/fw_now.txt` each cycle.
- IPv6 is not a side door: dropbear binds `::` fine but the TV has no v6 address (lo ::1 only).

### Wall 3 — dropbear ENOENT/Permission-denied at boot (partially explained)
- The binary (`dropbear_aarch64`, static-PIE, md5 `b13ccc408b80a73c57c0992ac31f5c47`, 560592 B)
  sometimes **vanishes from /var/local across a power cycle** (absent at boot #4 eval, present
  boot #3; cause unidentified — vendor cleanup suspect; `/usr/local/bin/cleanfiles` exists).
- v9's boot payload re-delivers it via fetchFile at boot+45 s; that copy is **md5-clean** (verified
  twice). But fetchFile writes it as uid 314 mode 644 → **must `chmod 755` immediately before
  every exec attempt** (boot #4's retry failed with "Permission denied" for exactly this reason).
- busybox here is minimal: **no `nc`, no `telnetd`** applets — the telnetd fallback door is dead.
- Boot #2's exec ENOENT with the file present (diag `ls` showed it, exec failed microseconds
  later, same md5 later) remains unexplained — possible mount/page-cache race right after power
  loss. The self-healing loop sidesteps it either way.

### The v15 state (deployed + verified Nov 5 ~00:40)
PFMCheck v15 (live + `.a6q_PFMCheck_backup`) = v12 boot block (md5 check, keys, iptables retry
×40, dropbear attempts, full logging to `.a6q_root/v12.log`) + three eternal root loops:
1. every 15 s: ensure ACCEPT for 2222 at INPUT 1 + delete the FIREWALL_IN_EULAON jump + dump
   firewall state (fw_now.txt) + **if port 2222 not bound and `/var/local/dropbear` exists:
   chmod 755 + start it** (`fw_loop.log` records every start)
2. every 30 s: `touch /var/local/DebugPowerup` (a periodic watchdog DELETES this flag during
   runtime — verified twice live; gate only needs existence at boot)
3. tail at boot+5 s: restore PFMCheck + platform.txt from backups + touch DebugPowerup

**Expected boot timeline:** +0 eval fires (root) → +45 s v9 redelivers clean dropbear →
+~60 s the 15 s loop starts it → firewall already neutralized → **2222 open**.
Validation: `nc <TV_IP> 2222` → expect `SSH-2.0-dropbear` banner; then
`ssh -p 2222 root@<TV_IP>` (keys: `/var/local/.a6q_authorized_keys`, both Mac + box pubkeys).

### Tooling notes
- Bridge `fileWrite` via localhost:9009 is HTTP-gated (503) — **fetcher `fetchFile` is the writer**
  (creates files fine; EACCES overwriting root-owned ones).
- DebugPowerup deletion culprit: something removes it within minutes during runtime, twice
  verified. The eternal toucher defeats it.
- The eval runs at pfm-manager.sh line ~93; CDP target IDs rotate per boot — re-read
  `/json/list` after every reboot.

## 🔴 ROOT SSH ACHIEVED (Nov 6, ~01:50): the dropbear gauntlet — five locks, all mapped

`ssh -p 2222 root@<TV_IP>` → **uid=0(root) root shell** on NT72690 aarch64.
The same five-lock gauntlet the upstream author documented for MTK applies to Novatek, lock for lock:

| # | Lock | Evidence | Fix (all deployed + persistent) |
|---|---|---|---|
| 1 | `FIREWALL_IN_EULAON` netfilter chain (allowlist + final DROP all; created by a vendor daemon AFTER early-boot) | boot #2/#4 dumps | eternal root loop: `-I INPUT 1 ACCEPT 2222` + `-D INPUT -j FIREWALL_IN_EULAON` every 15 s (proven: chain → 0 references) |
| 2 | root's home is `/` (RO rootfs) → `mkdir /root/.ssh` silently EROFS, authorized_keys never existed | boot #9 ENOENT | wrapper v4 (root): `mkdir /var/local/roothome` + `cp` keys + `dropbear -D /var/local/roothome` |
| 3 | `/etc/shells` check: root's shell `/etc/rootlogin.sh` not listed → "invalid shell, rejected" | boot #8 db.log | patched out (`goto goodshell`) in svr-auth.c; string dead-code-eliminated from binary |
| 4 | `checkpubkeyperms`: /var/local is world-writable by vendor design → keys dir under it rejected | boot #11 db.log | patched out (`return DROPBEAR_SUCCESS`) in svr-authpubkey.c |
| 5 | root shell = factory USB-gate script (`/etc/rootlogin.sh`) | /etc/passwd | `get_user_shell()` forced to return `/bin/sh` in common-session.c |

### Additional findings (all hit live)
- **dropbear `-r` = HOSTKEY, not authorized_keys** (the original silent-fail bug).
- This build (`DROPBEAR_SVR_MULTIUSER=0`, 2026.94): every connection child dies
  **"Early exit: String too long"** — proven a MULTIUSER=0 build bug by rebuilding with
  MULTIUSER=1 on the box (kex immediately worked). Rebuilt aarch64 with
  `MULTIUSER=1` + `SVR_DROP_PRIVS=1`.
- Hostkey files must be **dropbear-native binary format** (dropbearkey output); ssh-keygen's
  OpenSSH-armor PEM → `Early exit: String too long` at startup (buf_getstring reads 4-byte binary
  length from "----"). Native ed25519 key generated on the box with a natively-built dropbearkey.
- `-E` (stderr logging) exists in the aarch64 build but NOT in a fresh native x86 configure —
  config differs per configure run; without it dropbear logs to syslog (invisible on TV).
- **A runtime watchdog deletes `/var/local/DebugPowerup`** (the PFM gate!) periodically —
  countermeasure: payload re-plants gate + PFMCheck + platform.txt + dropbear artifacts every 10 s
  (v18 a6q_boot.js), plus the root toucher loop.
- The old v9 payload's **IPK reinstall clobbered PFMCheck** every boot (opkg data.tar `../`
  traversal extracted the old 655-byte version over the new one) — v18 dropped the IPK lane.
- The wrapper pattern: `/var/local/dropbear` = root-owned-at-boot sh wrapper (chmod real binary,
  prepare keys, exec real binary with -E, log to `.a6q_root/db.log`) — makes every boot's dropbear
  fully observable and configurable without touching the loop machinery.

### Current persistent state (all self-healing, survives reboots)
- PFMCheck v15 (firewall strip + dropbear start + full logging) live + backup + DebugPowerup
  (re-planted every 10 s by v18 payload + root toucher loop)
- v18 boot payload: no IPK; re-plants ALL artifacts (patched binary, wrapper, native hostkey,
  keys, gate, PFMCheck, platform.txt) every 10 s
- Eternal root loops: firewall strip (15 s) + gate touch (30 s)
- `/var/local/dropbear` = wrapper v4 → `.a6q_dropbear_real` = patched binary (MU=1, three source
  patches) → logs to `/var/local/.a6q_root/db.log`

**Teardown:** delete `/var/local/{.a6q_*,dropbear,pfmParse,DebugPowerup,roothome}`, restore
`services/hiutils/package.json` (original in pkg_current.json), remove `a6q_boot.js` — factory
reset is the nuclear option.
