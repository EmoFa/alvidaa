# 50A6Q / V0000.09.61B.Q0721 — boot-persistent root via the PFM eval chain + five-lock Dropbear SSH (NT72690, aarch64)

**Status:** root SSH (uid 0, `ssh -p 2222 root@<tv>`, key-only) verified on
2026-11-06. **Boot-persistent and self-healing**: the eval chain re-fires every
boot and a 10 s re-plant loop restores every artifact that vendor cleanup
processes delete. First **Novatek** entry and first **aarch64** unit in the
project — no public root existed for this generation before this work.

> **Applies to `50A6Q` (NT72690, VIDAA `U09.61`, region UAE / intl 50A60QXVT)
> running `V0000.09.61B.Q0721` (kernel build 2026-07-20).** Kernel is aarch64
> 5.4.283 with an **armhf (ELF32) userland**; aarch64 static-PIE binaries run
> natively. Browser: Odin Chromium 111.5563.5.1 (`--no-sandbox`), uid 313;
> jsservice/phoenix: Node 20.19.4 with `--max-old-space-size=9`, uid 314.

## Chain

```
TV browser page (recon page via /api/open, or DevTools on 9226)
  └─ bridge fileRead/fileWrite  — traversal CLOSED (validator string, not errno)
  └─ fetcher service (empty permission block, ungated)
       └─ fetchFile {url, directory}: arbitrary write as uid 314
            ├─ a6q_boot.js  -> hiutils service dir (boot hook via package.json main)
            ├─ PFMCheck + Data/platform.txt -> /var/local/pfmParse/
            └─ DebugPowerup -> /var/local/  (the gate flag)
  └─ in-process ISC: anything running INSIDE phoenix calls gated services with
     origintype='service' — checkRequestPermission returns true, no identifier
       └─ checkAccessCode forge (md5(deviceCode)[:6] + HMAC-SHA1) -> security
          level 9 -> setDebugPort(1) -> DevTools on 9226 (binds on the LAN IP)

cold boot (root):
  start-kilby -> [ -f /var/local/DebugPowerup ] && pfmDebug
       └─ bash pfm-manager.sh &  (root)
            └─ pfmAutorun: eval "$line" per line of PFMCheck  →  uid=0
                 ├─ iptables ACCEPT 2222 + delete FIREWALL_IN_EULAON jump
                 ├─ mkdir /var/local/roothome; install authorized_keys
                 ├─ wrapper -> patched Dropbear (aarch64, key-only, port 2222)
                 └─ eternal loops: firewall strip (15 s), gate touch (30 s)
```

## The five-lock Dropbear gauntlet (same walls as the MTK lane)

| # | Lock | Measured on this build | Fix (deployed, persistent) |
|---|---|---|---|
| 1 | `FIREWALL_IN_EULAON` netfilter chain | allowlist + final `DROP all`; created by a vendor daemon **after** early boot; sometimes holds the xtables lock for the first seconds | eternal root loop: `-I INPUT 1 ACCEPT 2222` + `-D INPUT -j FIREWALL_IN_EULAON` every 15 s; verified `0 references` |
| 2 | root's home is `/` on the **read-only** rootfs — `mkdir /root/.ssh` silently EROFS | `authorized_keys` never existed at the default path | wrapper (root, boot): `mkdir /var/local/roothome` + install keys + `dropbear -D /var/local/roothome` |
| 3 | `/etc/shells` check: root's shell is `/etc/rootlogin.sh`, not listed | `User 'root' has invalid shell, rejected` | source patch: shells check in `checkusername()` bypassed |
| 4 | `checkpubkeyperms()`: `/var/local` is world-writable by vendor design | `/var/local must be owned by user or root...` | source patch: `return DROPBEAR_SUCCESS` |
| 5 | root's shell = the factory USB-gate script | `/etc/passwd`: `root:x:0:0:root:/:/etc/rootlogin.sh` | source patch: `get_user_shell()` returns `/bin/sh` |

## Measured gotchas (each cost a boot)

| Gotcha | Detail |
|---|---|
| dropbear `-r` = **host key**, not authorized_keys | `-r <pubkey file>` → silent exit with stderr suppressed; authorized_keys belongs in the `-D` dir |
| `DROPBEAR_SVR_MULTIUSER=0` builds | every connection child dies `Early exit: String too long`; proven by rebuilding with `MULTIUSER=1` (kex immediately worked). Ship `MULTIUSER=1` + `SVR_DROP_PRIVS=1` |
| Hostkey file format | must be **dropbear-native** (dropbearkey output); an ssh-keygen OpenSSH-armor PEM → `String too long` at startup (`buf_getstring` reads a 4-byte binary length from `----`) |
| A runtime watchdog deletes `DebugPowerup` | the PFM gate flag is removed within minutes during runtime; countered by a 10 s re-plant loop from the payload + a root toucher loop |
| The IPK lane clobbers PFMCheck | opkg data.tar `../` traversal works as root, but reinstalling an old installer IPK re-extracts its stale PFMCheck over the live one — don't mix the two lanes |
| pfmAutorun self-cleans | `runCount=99` + `runMaxCount=1` → deletes `pfmParse` + `DebugPowerup` after the run; the eval's last line restores both from backups 5 s later |
| IPv6 is not a side door | dropbear binds `::` fine but the TV has no v6 address (`lo` only) |

## What was done

1. Recon pages (browser bridge probes) → array-path `fileRead` bypass is
   closed here; `fetcher`/`fetchFile` is the writer; full permission map.
2. `checkAccessCode` forge (device-code HMAC) → security level 9 →
   `setDebugPort(1)` → DevTools on 9226 → full CDP from a laptop.
3. Root: planted `DebugPowerup` + `PFMCheck` + `platform.txt` via `fetchFile`;
   one cold boot → `uid=0` proof (see [FINDINGS.md](FINDINGS.md)).
4. Dropbear: static aarch64 2026.94 built with `aarch64-linux-musl-gcc`,
   MULTIUSER=1 + three source patches
   ([patch](../../../../tools/a6q/dropbear-aarch64/dropbear-tv.patch),
   [recipe](../../../../tools/a6q/dropbear-aarch64/README.md)); native ed25519
   hostkey generated with a natively built `dropbearkey` (not ssh-keygen);
   delivered via `fetchFile`; wrapper as `/var/local/dropbear` makes every
   boot's dropbear fully logged (`.a6q_root/db.log`).
5. Result: `ssh -p 2222 root@<tv>` → uid 0 shell; survives reboots with zero
   manual re-arming.

## Connect

```sh
ssh -p 2222 root@<tv>          # key-only; put your pubkey in the planted set
```

The planted `authorized_keys` lives at `/var/local/.a6q_authorized_keys` and is
copied to `/var/local/roothome/authorized_keys` at boot. Edit the former (via
SSH once inside, or via the fetcher lane) and re-boot — or just `chmod`/edit in
session.

## Persistence and self-healing

| Loop | Interval | Purpose |
|---|---|---|
| v18 boot payload (inside phoenix) | 10 s | re-plants gate flag, PFMCheck, platform.txt, patched dropbear, wrapper, hostkey, keys |
| root firewall loop | 15 s | ACCEPT 2222 + delete the EULA chain jump; dumps state to `.a6q_root/fw_now.txt` |
| root gate toucher | 30 s | re-touches `DebugPowerup` (watchdog countermeasure) |

The TV clock resets to epoch on cold boot and NTP-syncs later — don't trust TV
timestamps for forensics.

## Teardown

```sh
rm -rf /var/local/{.a6q_*,dropbear,pfmParse,DebugPowerup,roothome,tv.vidaa.app.debug.ipk}
# restore services/hiutils/package.json from pkg_current.json (tools/a6q/)
rm -f <hiutils dir>/a6q_boot.js <hiutils dir>/hiutils_boot.js
```

Factory reset is the nuclear option (wipes `/APPS` + `/var/local`; the hook
lives only there). Verified boot was never touched: no read-only partition was
written, no OTA staging was modified, and the OTA endpoint was frozen at the
router before any UI-adjacent work.
