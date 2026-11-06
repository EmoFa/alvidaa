# alvidaa findings — root SSH on 55A7KAU (55U66GAVT), V0000.09.09O.P1015

> Phase-3 chain executed 2026-11-06. Adapted from the 100U7Q/75UR9S
> superwatch chain ([100U7Q guide](../../../100U7Q/V0000.09.60I.Q0813/README.md),
> [75UR9S record](../../../75UR9S/V0000.09.60W.Q0624/README.md)) with
> 09.09O-specific constants measured on this unit. Read-only recon first
> ([01-recon-ladder.md](01-recon-ladder.md)), OTA frozen in the TV settings
> menu before the first write.

## Chain that worked

```
TV browser page (fetcher FaaS, wss://localhost:9888)
  └─ vowOS.service.syncExecute("basic/fetcher", {api:"fetchFile", args:…})
       └─ downloads placed as uid 314:
            /APPS/pkgs/tv.vidaa.jsservice.basic/CHA/functions/fetch/sw2.js
            /APPS/installer.ipk
  └─ POST https://localhost:9888/function/basic/fetch/sw2
       body {"list":["<sid>:53:<sid>;/APPS/installer.ipk;re.installer;"]}
       └─ superwatch_server (root) → /usr/local/scripts/ipk_install.sh
            └─ opkg --force-reinstall install /APPS/installer.ipk
                 └─ IPK postinst: uid 0, CapEff 0000003fffffffff
                      ├─ deploys static ARMv7 dropbear 2022.83 → 0.0.0.0:8008
                      ├─ iptables -I FIREWALL_IN_EULAON 1 -p tcp --dport 8008 -j ACCEPT
                      └─ /APPS/shell whitelist, /dev/ptmx 666, host key
                           └─ key-only root SSH on 8008 (verified Uid: 0)
```

## 09.09O specifics (differences from the 09.60 records)

| Area | 09.60 (100U7Q/75UR9S) | 09.09O — measured |
| --- | --- | --- |
| superwatch command ids | install `82`, uninstall `83` | **install `53`, uninstall `54`** (from `pkgmgr/PackageInstall.js`: `IPK_INSTALL_COMMAND='53'`); `82`/`83` → reply `604` (invalid id) |
| wire format | `<sid>:<cmd>:<sid>;<ipk>;<pkg>;<options>` | identical; sid 10–99 (`generateSessionId(10,99)`); replies `<sid>:<rc>`, `0` ok / `-1` fail / `604` invalid |
| install result | socket reply / poll pidfile | result file **`/tmp/ipk_install_result`** — created EMPTY by `ipk_install.sh` (`rm -f; touch`), written **only on failure** (`{"code":414,…,"msg":"opkg install failed"}`); an empty file means "running or succeeded" — poll `/APPS/.re_sshd/installer_log.txt` instead |
| installer script | — | `/usr/local/scripts/ipk_install.sh` runs `opkg ${options} --force-reinstall install <ipk>` then `ipk-update -n <pkg>`; `#!/bin/bash` (bash exists on this build) |
| opkg | — | `/usr/local/bin/opkg`, status db `/APPS/pkgs/opkgmeta/status`; **`Architecture:` must be `mtk9602`** (vendor packages use `mtk9602`/`all`; the 100U7Q template's `mtk9655` fails opkg) |
| pkgmgr | does not install itself | `pkgmgr` (jsservice.system, `permission: {}`) exposes `debugForceInstall` but answers **"Not in debug mode"** — the direct superwatch path is the way in |
| firewall | 75UR9S: no iptables | **iptables present**: INPUT policy ACCEPT → `FIREWALL_IN_EULAON` DROP-blacklists debug ports (22, 23, 1025, 4444, 4445, 9222, 9536, 9666, 10001, 10485, 12321, 3366, 3367, 4635, … incl. 8008). Outbound (OUTPUT) unrestricted. Fix: insert ACCEPT for 8008 at position 1 of the chain |
| dropbear caps | `CapEff 000001ffffffffff` | **`CapEff 0000003fffffffff`** (different, still root) |
| session PATH | — | dropbear session PATH has no `/usr/local/bin` and **no `id`/`uname` binaries** (minimal busybox); export `PATH=/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin` |
| login shell | `/bin/bash` via `/APPS/shell` | dropbear patched to force `/bin/sh` (bash presence likely but unverified at build time; `/bin/sh` guaranteed). `/APPS/shell` whitelists `/bin/sh` + `/bin/bash` if present |
| binaries | 4.7 MB w/ debug | **strip before shipping**: static ARMv7 dropbear 4.7 MB → 657 KB, IPK 4 MB → 791 KB (smaller fetch, faster install) |

## Traps hit on the way

- **Rapid synchronous `fileRead` bursts crash/jam the hiutils bridge**
  (localhost:9009 stops answering; recovers on its own or after a reboot).
  Pace reads ≥1 s apart, one file per beat.
- **Binary reads kill the bridge transport** (large ELF read → XHR NetworkError).
  Never read binaries through `HiUtils fileRead`.
- **`fetchFile` from the wrong origin deletes the target**: a page served from
  `:8765` built the fetch URL from `location.host`, got a 404, and the failed
  fetch removed `/APPS/installer.ipk`. Serve installer pages from the same
  origin as `/pub/`, or use absolute artifact URLs.
- **`syncExecute` can hang the page indefinitely** when the target service is
  wedged (no timeout) — split fetch and trigger into separate page loads.
- **Empty `/tmp/ipk_install_result` is not an error** — see table above; the
  first two "failed" attempts were misread this way.
- **Reverse-shell transport**: this build's `bash` may lack `/dev/tcp` (the
  phonehome loop never connected; not conclusively diagnosed because the
  iptables ACCEPT rule made direct SSH possible first — try `dbclient -R`
  as the fallback if ever needed).

## Boot persistence (verified cold-boot, 2026-11-06)

After the session-root, a JS service makes root re-arm itself at every boot —
no PC, no network, fully offline. Same pattern as the 75UR9S `re_sshd`
(serviceList autostart), adapted to 09.09O:

```
boot → phoenix (uid 314) → serviceManager.init()
  → startAutoStartServices('basic', …/services/serviceList.json)
       → re_sshd (autoStart: true)
            → connect /var/run/superwatch_socket
            → "80:54:80;re.installer" + "81:53:81;/APPS/installer.ipk;re.installer;"
                 → opkg --force-reinstall → postinst uid 0
                      → dropbear on 8008 + iptables ACCEPT rule
```

Deployed files (repo copy: `source/re_sshd/`):

- `/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/services/re_sshd/index.js`
- `…/re_sshd/package.json`
- entry appended to `…/services/serviceList.json`
  (`{"id":"re_sshd","autoStart":true,"isKeepAlive":false}`);
  pristine copy at `/APPS/.re_sshd/serviceList.json.pristine`
- `/APPS/installer.ipk` stays in place — the service reinstalls from it

**Cold-boot evidence** (final test, uptime 74 s, no PC reachable):

```
re_sshd start pid=1624 uid=314
attempt 1 uninstall=[80:0] install=[TIMEOUT]
ARMED: dropbear up
```

One attempt, one install, single firewall rule.

### 09.09O traps in the persistence layer (all measured)

| Trap | Measured result |
| --- | --- |
| SDK require idiom | Stock 09.09O services use `require(globalThis.PHOENIX_LIB + '/baseService.js')`; the 09.60-era `require("@sdk/baseService.js")` **does not resolve** — the service silently fails to register (manager logs "Not supported service" into the fast-rotating logservice). Module-load logging to `/tmp/re_sshd_boot.log` is the reliable load detector. |
| `dropbear.pid` readability | postinst leaves it mode 640 root:root; a pid-file check as uid 314 gets EACCES → `dropbearRunning()` always false → the arm loop re-installs every ~24 s, killing and restarting dropbear until a race kills it (Connection refused). Fix: detect the `:1F48` LISTEN entry in `/proc/net/tcp` (uid 314-readable). |
| Duplicate firewall rules | Every postinst run inserts another `ACCEPT dpt:8008`. postinst now deletes existing 8008 rules before inserting. |
| serviceList.json | One JSON entry appended; original owner/mode preserved (314:314, 640). Pristine backup kept. Hot-reload: none — takes effect next boot. |
| Manual kick | The service can be started live via the FaaS channel: wss `phoenix://service/basic/re_sshd`, method `start` (`launcher/svcstart.html`). |

**Teardown (persistence):** restore `serviceList.json.pristine`, remove
`CHA/services/re_sshd/`, `rm /APPS/.re_sshd/boot_marker.txt /tmp/re_sshd_boot.log`.
Everything else per the root teardown above.

## What is on the TV now (and how to undo it)

1. `/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/functions/fetch/sw2.js` — delete.
2. `/APPS/installer.ipk` — delete (or leave; harmless).
3. `/APPS/pkgs/APPS/.re_sshd/` + `/APPS/.re_sshd/` — the package payload
   (`opkg remove re.installer` as root, then `rm -rf` leftovers).
4. `/APPS/shell` — delete.
5. Firewall rule — `iptables -D FIREWALL_IN_EULAON 1` (it is entry 1) or the
   exact rule `-p tcp --dport 8008 -j ACCEPT`.
6. dropbear process — `kill $(cat /APPS/.re_sshd/dropbear.pid)`.
7. A reboot clears items 5–6 automatically (iptables is volatile; dropbear
   has no persistence — **no serviceList entry was added on this unit**).

**Persistence is deliberately NOT installed.** After a reboot, root access is
gone until the installer is re-triggered (fetch + trigger pages are preserved
in `tools/u7q/web/pub/` and `launcher/`). Boot persistence via a
`jsservice.basic` `serviceList.json` autostart entry (the 75UR9S `re_sshd`
pattern) is the documented next step if wanted — not done here.

## State after this session

- dropbear on 0.0.0.0:8008, key-only, authorized key
  `server/keys/tv_root_ed25519.pub`; connect:
  `ssh -p 8008 -i server/keys/tv_root_ed25519 root@192.168.50.34`
- iptables ACCEPT for 8008 live
- opkg package `re.installer 1.0.0` registered
- OTA: disabled in the TV settings menu by the owner before first write
