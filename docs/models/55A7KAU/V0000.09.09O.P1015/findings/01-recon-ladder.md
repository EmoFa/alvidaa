# alvidaa findings — the recon ladder on 55A7KAU (55U66GAVT), V0000.09.09O.P1015

> Phase-2 ladder (`HACK-YOUR-OWN.md`) run on the 55A7KAU (sticker model; the
> firmware reports the internal name `55U66GAVT` — see EVIDENCE.md).
> Pages: `launcher/recon-55.html` (v1–v4 staged), `launcher/recon-55b.html`
> (raw errno capture). Read-only; nothing written to the TV. Run 2026-11-06.

## v1 — bridge enumeration, UA, sandbox

- The TV browser exposes **75 `Hisense_*` bridge functions** plus
  `HiUtils_createRequest` to any page. The `Hisense_*` list is nearly
  identical to the reference unit's (identity, settings, TTS, network,
  ad flags — see `recon-report` `hisense_fns`).
- UA: `Mozilla/5.0 (X11; Linux armv7l) AppleWebKit/537.36 (KHTML, like Gecko)
  Chrome/111.0.5563.146 Odin/111.5563.5.1 Safari/537.36
  Model/VIDAA-MT9602 VIDAA/9.0(Hisense;SmartTV;55U66GAVT;MTK9602/V0000.09.09O.P1015;UHD;55U6GA;)`
  — same Chromium 111 "odin" web-app browser as the reference.
- The file bridge answers to **`HiUtils_createRequest(action, args)` →
  `{ret: bool, msg: string|object}`** (`ret:true` boolean here, not the
  reference's truthy-string shape). `fileRead` args: `{path, mode: 6}`.

## v2 — the errno leak and the sandbox base

- **A failed read leaks the resolved absolute path in its error object.**
  `fileRead("/etc/passwd")` returns
  `{"errno":-2,"code":"ENOENT","syscall":"open","path":"/APPS//etc/passwd"}`
  → **the sandbox base is `/APPS/`** (note the naive join double-slash).
  This matches the 75UR9S behavior (`hiutils.fileRead` errno objects,
  base `/APPS/`) and is cleaner than the reference's errno leak — here the
  full resolved path is in `path`, not inferred.
- **`../` traversal escapes the base.** `../etc/passwd` (single `../`)
  reads `/etc/passwd` (`ret:true`). Extra `../` are harmless (`/APPS/../..`
  clamps at `/`). Absolute paths do **not** work (they join as
  `/APPS/` + path).
- **Directory reads return no listing**: `errno:-21, code:"EISDIR",
  syscall:"read"`. Enumerating requires reading known paths (same as every
  prior model).

## v3 — dumps (full texts in the session recon-report; excerpts here)

- **/proc/mounts** — root is **squashfs ro** (`/dev/root`); dm-mapped ro
  mounts `/3rd`, `/vendor/lib`, `/application`, **`/usr/local` (dm-4, ro)**,
  `/vendor/lib/utopia`, `/opt`. RW: `/proc`, `/sys`, `/dev/shm`,
  **`/certificate` (p17, ext4 rw)**, `/var/run`, `/var/log`, `/var/crash`,
  `/cache` (p28), **`/OAD` (p42, rw!)**, **`/var/local` (p39, rw)**,
  **`/APPS` (p41, rw)**, `/data` (p27), `/var/tvservice` (p35).
  Unlike the reference unit, `/usr/local` is **read-only** here (dm-4) —
  the openssh/telnetd starter scripts under `/usr/local/bin` cannot be
  edited from the file bridge.
- **/etc/inittab** — busybox init, runlevel 3,
  `respawn:/sbin/getty -L ttyS0 115200 vt100` (UART console), sysinit
  `/etc/init.d/rcS`.
- **/etc/passwd** — `root` shell = `/usr/local/scripts/rootlogin.sh` and a
  `cli` user with `/etc/cli_login.sh` (the same factory-gate login-shell
  pattern as the reference); `television:x:300` runs
  `/usr/local/scripts/login.sh`; `cobalt` gets `/bin/false`. Shadow not
  dumped (read-only recon).
- **/etc/init.d/rcS + /etc/profile** — standard MTK/utopia boot: mounts,
  modules, umask 0026. **No `/etc/rc.local` on this unit** (read fails
  ENOENT) — the reference's root primitive
  (`rc.local → /var/local/otaTest.sh`) **does not exist here**. The root
  lane on this set must go through a different door.

## v4 — wire format and the phoenix process

- `XMLHttpRequest.prototype` patch captured the file bridge's transport:
  every bridge call is **`POST http://localhost:9009/service/hiutils`**
  with JSON body `{"api":"fileRead","args":{"path":"…","mode":6}}`.
  Localhost-only listener, no CORS origin observed in captured requests.
- `/proc/self/cmdline` (via `../proc/self/cmdline`): the page's host process is
  **`/opt/pkgs/tv.vidaa.app.phoenix//bin/phoenix`** (a Node-based JS host)
  running `--jitless … /APPS/pkgs/tv.vidaa.jsservice.basic/CHA//phoenix.server.js`
  — the **`jsservice.basic` package** (the 75UR9S chain's package, not
  `system`).
- `/proc/self/status`: **phoenix runs uid 314, gid 314, groups
  `211 233 312 616 702 711 713 902 1018`** — group **616** is the
  superwatch-socket group from the 100U7Q/75UR9S chain, and 713 is
  `UhisPhoenix` (Appinfo.json ownership). The phoenix FaaS lane
  (`/function/basic/fetch/sw2` + superwatch trigger) is the most promising
  root primitive to test next on this set; `/usr/local`-editing tricks from
  the reference unit do not apply.

## What differs from the reference unit (50A51HUV, 09.01O)

| Area | 50A51HUV (09.01O) | 55A7KAU (09.09O) — measured |
| --- | --- | --- |
| fileRead success shape | truthy-string `ret` | boolean `ret:true/false` |
| Failed read | errno leaks sandbox base indirectly | Node error object with **full resolved path** (`/APPS/…`) |
| Root primitive | `rc.local` executes `/var/local/otaTest.sh` | **no `/etc/rc.local`** — lane absent |
| `/usr/local` | (bridge-writable scripts) | **dm-4, read-only** |
| phoenix groups | uid 314 | uid 314 **incl. 616 (superwatch)** — 100U7Q-style chain likely |
| `/certificate` | ro | **rw** (p17) |
| `/OAD` | staging, freeze before UI edits | **mounted rw (p42)** — freeze OTA before any write experiments |

## Next steps (not done yet)

1. Read `/etc/shadow`, `serviceList.json` of `jsservice.basic`, and the
   superwatch config pointer (v8 recon targets) with the traversal prefix.
2. Test `fileWrite` gates (mode list) on `/APPS` — the 55A60LEVS report
   says fileWrite was blocked on 09.60V; unknown on 09.09O.
3. If write works: the 75UR9S `re_sshd` serviceList autostart chain is the
   persistence candidate; verify package ids 82/83 on this unit first.
