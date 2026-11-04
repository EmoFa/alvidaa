# Modding — 100U7Q / V0000.09.60I.Q0813

**Precondition:** the root channel from [README.md](README.md), or at minimum
the app-context write/exec primitives. **Rule:** own device only; no flashing,
no reflashing or raw partition writes, no vendor service calls. Back up
`/APPS/websdk/Appinfo.json` before touching the launcher.

This page separates measured facts from **UNVERIFIED** candidates. The record
states that everything in its `modding/` directory was measured on the device,
and that anything not measured is marked UNVERIFIED and is not a recipe. That
distinction is preserved here.

> `source/...` citations point into the sanitized research notes included in
> [`source/`](source/README.md). See [EVIDENCE.md](EVIDENCE.md) for the claim
> matrix.

## System layout, storage, constraints

`/proc/mounts` (recorded):

```
/dev/root        /            erofs   ro,seclabel,...
/dev/dm-1        /application erofs   ro,seclabel,...
/dev/mmcblk0p54  /APPS        ext4    rw,seclabel,nosuid,nodev
/dev/mmcblk0p56  /OAD         ext4    rw,seclabel,nosuid,nodev
/dev/mmcblk0p12  /data        ext4    rw,seclabel,nosuid,nodev
/dev/mmcblk0p5   /certificate ext4    rw,nosuid,nodev,noexec
```

Consequences:

- **`/` is read-only and integrity protected.** erofs, `dm-verity` enforcing,
  `androidboot.verifiedbootstate=green`, `root=/dev/dm-0`. `/etc/rc.d/rc.local`
  exists but cannot be edited, even as root.
- **Every writable data partition is `nosuid`.** A `chmod 4755` binary still
  runs as uid 314 (verified).
- **The app context (uid 314) can write `/APPS`, `/OAD` and `/vddt`.** It cannot
  write outside that set (for example `/data`, `/usr/local`, `/tvsapp` or
  `/basic`).
- **SELinux is enforcing.** uid 314 has only `CAP_SYS_NICE`; files owned by
  other users stay unreadable (for example `/etc/shadow` → `EACCES`).

There is an `opkg` package path, but it is **not a general-purpose package
manager**: the app context cannot invoke `opkg` directly, and the record shows
no repository configuration or dependency resolution. Installs happen only when
the root superwatch daemon runs `opkg install` on a package you placed in a
writable path.

| Constraint | Value |
|---|---|
| Kernel | `5.15.192-ge6d9f75ad2ad-dirty` |
| Userland | 32-bit ARM (`EM_ARM`), Node `arm` |
| Static builds | the safe default: static ARMv7 EABI5 binaries |
| Dynamic builds | must match the TV's libc; the record uses static Dropbear |
| Package output | `Architecture: mtk9655` in the control file |

## Boot chain and persistence

The boot chain is entirely on the read-only root:

```
/sbin/init
  /etc/inittab
  /etc/init.d/rcS
    /etc/rc.d/rc.local
      /usr/local/scripts/tvs-debug.sh      (if present)
      /tvsapp/etc/init.d/start-early-tvs.sh
      /usr/local/scripts/start-tvs.sh      (if present)
      /usr/local/scripts/start-kilby.sh
```

There is **no writable path that the boot chain executes**. Two `/OAD`
candidates exist in the scripts but are inert on this build:

- `init_kilby.rc` sets `kilbyDebug=0` as a literal before the branch, so it
  always sources `/usr/local/scripts/start-kilby.sh`, never
  `/OAD/start-kilby.sh`.
- `3rd_overlayfs.sh` exits early unless the kernel command line contains
  `init=/sbin/preinit` and `/mnt/tvroot/usrlocal/debug_version` exists. This
  build has `init=/sbin/init` and no such file; it would overlay `/3rd`
  anyway, not `/etc`.

Consequence: a daemon started by a `postinst` lives until the next reboot. Root
SSH must be re-armed after every boot (uninstall `83`, then install `82`).

### Persistence candidates — all UNVERIFIED

None of these was tested; they are recorded as open questions, not recipes.

| Candidate | What is known | What is unknown |
|---|---|---|
| `/APPS/pkgs/appinfo.json` | entries with `Main: pkgapp://<pkg>/<script>`, `Type: nativeType`, `Persistent: true`; `systemserver` contains the string `appinfo.json` | whether adding an entry makes `systemserver` start it at boot, and with which uid |
| `/APPS/pkgs/tv.vidaa.app.phoenix/CHA/run_phoenix.sh` | writable (`314:314`), 3109 bytes, vendor script that starts phoenix; a background line before its final `exec` would be additive | whether the launcher runs it as root or uid 314 |
| `systemserver` configuration | uid 301, `/mnt/tvroot/usrlocal/bin/systemserver`, parent of phoenix | its start list was not readable from uid 314; format unknown |

Do not present any of these as a working persistence method.

## UI, launcher and app surface

The launcher's tile registry is:

```
/APPS/websdk/Appinfo.json      owned 311:713, mode 0660, writable by uid 314
```

A malformed file can empty the launcher. Always copy it first:

```sh
cp /APPS/websdk/Appinfo.json /APPS/websdk/Appinfo.json.bak
```

Keep it valid JSON. The launcher may cache it until it reloads; **when** it
reloads after an edit was not measured (it kept stale tiles during the run).

Other surfaces visible from the app context:

- the FaaS function tree under `/APPS/pkgs/tv.vidaa.jsservice.<type>/current/functions/<module>/<func>.js`
  — a function written there runs in the FaaS worker (uid 314) when POSTed to
  `https://localhost:9888/function/<type>/<module>/<func>`;
- browser favourites and the tile registry (the record lists both as editable
  from root);
- `/OAD` as OTA staging — nothing in the root path needs a write there except
  the self-expiring `enable_selenium` flag.

DevTools: `devtoolSwitch` (`kilby.sl2.i32.browser.devtool.switch`) can be set
via `TvInfo_setParam` without a permission check. Setting it to `2` survived a
reboot, but **ports 9222/9223/9224 stayed closed**, including after a cold
boot. `/OAD/enable_selenium` is a 24-hour flag consumed by `getSeleniumDebug`
(content must be a parseable date younger than 24 h). It was written; whether a
browser restart opens a debug port is **not verified**.

The app-context service host is `phoenix` (uid 314), started by `systemserver`
(uid 301). The FaaS worker is a child of phoenix. That is why a JavaScript file
in the function tree runs as uid 314, and why privilege escalation still needs
the `postinst`.

## What is verified vs UNVERIFIED

| Area | Status | Basis |
|---|---|---|
| Mounts, writable set, `nosuid`, SELinux | measured | `source/modding/01-system.md:6-38`, `:83-95` |
| Boot chain, inert `/OAD` hooks, no writable boot hook | measured/documented | `source/modding/01-system.md:40-62`; `source/modding/05-limits.md:33-39` |
| `fetcher` empty permission block and the four-segment route | documented code | `source/docs/HOW-IT-WORKS.md:16-19` |
| `fetchFile` arbitrary write as uid 314 | documented code + operational reliance | `source/docs/HOW-IT-WORKS.md:33-49` |
| superwatch socket mode/group and `82` install | documented code + stated measurement (no raw transcript) | `source/docs/HOW-IT-WORKS.md:52-64` |
| `postinst` uid 0 / full capabilities | measured | `source/docs/HOW-IT-WORKS.md:71-81` |
| No signature check | documented claim, no excerpt → **UNVERIFIED/documented** | `source/docs/HOW-IT-WORKS.md:83-84` |
| Dropbear patches and offset 15162 | documented code + build recipe | `source/docs/BUILD.md:26-72` |
| Port 8008 / 22 dropped / 2222 timeout | measured | `source/docs/HOW-IT-WORKS.md:119-125`; `source/modding/01-system.md:64-81` |
| Root SSH uid 0 + PTY | measured | `source/modding/04-ssh.md:3-4`, `:54-58` |
| Re-arm with `83` then `82` | documented procedure | `source/ORIGINAL-README.md:100-111` |
| Automatic boot persistence | **none on this build** | `source/modding/05-limits.md:33-39` |
| Persistence candidates | **UNVERIFIED** | `source/modding/06-open.md:6-21`, `:40` |
| DevTools ports | **UNVERIFIED** (did not open) | `source/modding/06-open.md:23-32` |
| Full rollback | **UNVERIFIED / operator-defined** | `source/modding/03-root.md:99-102` |

## Rollback and recovery

```sh
# remove the package (command 83) through the same socket path
{list: ["70:83:70;re.installer"]}
```

`83` removes the package and its data files, but **not** everything the
`postinst` created outside the package's data list. There is no documented
single rollback.

State the run left on the device, to be undone deliberately:

| Item | What it is |
|---|---|
| `devtoolSwitch = 2` | tvinfo biz key; persists |
| `/var/local/dab_debug` | written by `setDabTool(1)` at security level 9 |
| `/OAD/enable_selenium` | 24-hour debug flag; expires by itself |
| `/APPS/.re_sshd/` | Dropbear, host key, key files, installer IPK |
| `re.installer` | installed package used by the re-trigger |
| `Appinfo.json` | test tiles removed; some system apps and a live tile remained |
| `Appinfo.json.bak` | backup taken before the tile cleanup |

Operator checklist for a fuller cleanup — verify each step yourself:

1. stop the Dropbear process (`/APPS/.re_sshd/dropbear.pid`);
2. remove `/APPS/.re_sshd/` and `/APPS/shell`;
3. restore `/dev/ptmx` and `/dev/pts/ptmx` modes (the record gives no restore
   command);
4. restore `/APPS/websdk/Appinfo.json` from your backup if you changed tiles;
5. remove `/OAD/enable_selenium`;
6. decide what to do with `devtoolSwitch` and `/var/local/dab_debug` — the
   record gives no reset recipe.

**No OTA recovery path is documented.** OTA probing found no usable image for
this model, so a bad state is not recoverable by reflash from the record.

## Tools

| Path | Purpose |
|---|---|
| [tools/u7q/scripts](../../../../tools/u7q/scripts) | `pair.sh`, `install.sh`, `trigger.sh`, `make_installer.py`, `launch_tile.py` |
| [tools/u7q/web](../../../../tools/u7q/web) | `install.html`, `trigger.html`, local HTTP server |
| [tools/u7q/faas](../../../../tools/u7q/faas) | `sw2.js`, the browser-side superwatch helper |
| [tools/u7q/bin](../../../../tools/u7q/bin) | drop point for your own static ARM32 Dropbear build |

The tool tree contains scripts and pages only. No certificate, token, session
file, key or prebuilt binary is included.

## Evidence

See [EVIDENCE.md](EVIDENCE.md) for the identity table, the claim matrix with
source lines, artifacts, sanitization, corrections and the full unknown list.
