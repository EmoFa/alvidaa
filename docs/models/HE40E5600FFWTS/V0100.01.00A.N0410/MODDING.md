# Modding — HE40E5600FFWTS / V0100.01.00A.N0410

**Precondition:** the root channel from [README.md](README.md) (root loop or
SSH). **Rule:** one change, test it, then the next; take a backup first; keep
SSH/root-loop open as the rescue path. No flash, no `.pkg`.

This page separates the system facts (recorded live/static) from the recipes
(mostly **UNVERIFIED**). Do not read a recipe as a tested procedure.

> `source/...` citations point into the sanitized research notes included in
> [`source/`](source/README.md). See [EVIDENCE.md](EVIDENCE.md) for the claim
> matrix.

## System layout, storage, constraints

| Constraint | Value | Consequence for modding |
|---|---|---|
| Root FS | squashfs, read-only, 38.8 MB, 100 % full | nothing can be installed into `/` |
| `/3rd` | squashfs via `dm-3`, read-only, 141 MB, 100 % full | vendor tree is immutable |
| Writable | `/3rd_rw` (ext4, 1.1 GB), `/data` (ext4, 1.9 GB), `/perm` (ext4, 3.9 MB) | put your files in `/3rd_rw` or `/data` |
| Overlay | **none** (`/proc/filesystems` has no overlay) | use writable dirs plus `mount --bind` |
| `/dev` | part of the read-only squashfs, no devtmpfs | PTY needs the devpts-on-tmpfs workaround |
| Package manager | **none** (`apt`, `dpkg`, `opkg`, `ipkg`, `rpm`, `apk`, `yum`, `pacman` all absent) | no install step; copy files and run them |
| libc | glibc 2.18 (`/lib/libc-2.18.so`, `ld-linux.so.3`) | dynamic binaries must match; prefer `-static` |
| CPU | ARMv7 EABI5, hard-float, VFPv4/NEON, Cortex-A53 | `arm-linux-gnueabihf-gcc -static` |
| Init | SysV (`inittab` → `rcS` → `rc.local` → `autorun.sh`) | boot hooks are files in writable paths, see below |

Sources: `source/modding/01-system-linux.md`, `:56-59`, `:67-93`, `:99-114`,
`:128-169`; `source/modding/06-toolchain-deploy.md`.

Minimal static build and deploy:

```sh
arm-linux-gnueabihf-gcc -static -Os -o hello hello.c
# via SSH:
base64 -w0 hello | ssh -i <key> root@<tv-ip> \
  'base64 -d > /3rd_rw/bin/hello && chmod 755 /3rd_rw/bin/hello'
```

Deploy alternatives: `HiBrowser.File.download` (binary-safe, into the file-API
whitelist or through the USB symlink bypass), `File.write` (text only; binary
data returns `EINVAL`), the root command loop, SSH + `base64`/`tar`, USB, and —
only after the optional SFTP install — `sftp`/`scp`. Source:
`source/modding/06-toolchain-deploy.md`.

## Boot order and persistence hooks

```
U-Boot → Linux 3.18.25 → /sbin/init → /etc/inittab → /etc/init.d/rcS
  → /etc/rc.d/rc.local
      mount_main.sh, mount_data.sh, 3rd_ini env, mount_3rd*, mount_perm.sh
      fusion.ko, hisense_rc.sh
      → /basic/autorun.sh
          line ~90   /3rd_rw/developer.sh            (root, early)
          line ~162  ms_service
          line 168   hisenseUI/start-UI.sh
          line 177   app_man -c am_config -s am_start.ini
          line 190   delayrun.sh
                       swrc-server, runlogservice, LauncherService,
                       Seriallog, startHam.sh (~15 s), swap
```

Two writable hooks matter:

| Hook | When | What it can do |
|---|---|---|
| `/3rd_rw/developer.sh` | early, `autorun.sh` line 90, as root | bind-mount modified read-only files **before** they are read (`am_config`, `am_start.ini`, `delayrun.sh`, `start-UI.sh`), start early services |
| `/3rd_rw/hamservice/HamService` | late, after `delayrun.sh` + ~15 s, as root | wrapper around the real service; this is what starts the root loop and SSH on boot |

Also present: `/3rd_rw/patch/opera4x` — if this directory exists, `autorun.sh`
bind-mounts it **as a whole** over `/3rd/opera4x` before the UI starts. That is
a full-tree replacement, not a single-file patch; a partial tree breaks the
browser and UI. For one file, use a file bind mount from `developer.sh`
instead. Sources: `source/modding/02-boot.md`, `:201-214`, `:218-235`.

**Important for the root chain:** the web browser (`opera4x`,
`hisense_browser`) is **not** started at boot (`source/modding/02-boot.md`). The
shadow library from the root chain therefore runs when the browser is opened,
not during boot. Boot survival of the root loop and SSH comes from the
`HamService` wrapper.

Example early hook (pattern; the bind-mount targets are **UNVERIFIED** as
recipes):

```sh
#!/bin/sh
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin
export PATH
exec >>/3rd_rw/developer.log 2>&1
echo "developer.sh $(date)"
# mount --bind /3rd_rw/etc/am_start.ini /basic/am_start.ini
# /3rd_rw/bin/mydaemon &
```

A faulty `developer.sh` runs before `ms_service`, the UI, `app_man` and
`delayrun`, so it can prevent the TV from coming up. Keep an SSH/root-loop
fallback and a log.

## UI, launcher and app surface

Two different browser processes, both root:

| | TV UI | Web browser |
|---|---|---|
| Process | `hisenseUI` | `hisense_browser` |
| Start | `/3rd/opera4x/hisenseUI/start-UI.sh` (autorun line 168) | `/3rd/opera4x/browser/run-Browser.sh` (AM app `opera4x`) |
| Renderer | GLES (`--hw-gles`, Mali) | DirectFB (`--hw-dfb`) |
| Page | `/3rd_rw/UI/index.html` (PIXI) | any URL; the recon page during the root work |
| DevTools | 9223, only with `/3rd_rw/appdata/enable_developer_tools` | 9224, same flag |

The TV UI is **not** the "TV Browser" tile. Modifying the UI means editing
`/3rd_rw/UI/index.html`; modifying app tiles means editing the launcher data.

Launcher data (`/3rd_rw/appdata/launcher/`, read through `ldi.js`):

```
preset.txt                 cache of the preset tiles (regenerated)
Appinfo.json               user-installed web apps (the right place for your own tile)
deletedPresetApp.txt       persistent hide list (JSON array)
rememberEditApp.json       edit state
settingappinfo.txt         setting/app info
data/CategoryIndex.xml     categories (used when serviceUpdate matches the country)
data/Category*.xml         tiles
data/PicInfo.xml           images/assets
data/serviceUpdate.xml     country/timestamp of the store data
res/                       tile icons
cache/index.json           icon cache
```

`ldi.js` chooses `launcher/data/` when `serviceUpdate` matches the device
country and timestamp; otherwise it falls back to `/3rd_rw/UI/data/`
(`source/modding/03-ui.md`). `preset.txt` is a **cache** and can be
regenerated — `deletedPresetApp.txt` is the durable hide lever, `Appinfo.json`
is the durable place for user apps.

Native apps are started by `app_man` (`/basic/app_man -c /basic/am_config -s
/basic/am_start.ini`), controlled with `:am,<app>,:<verb>=<val>` verbs such as
`start`, `stop`, `pause`, `resume`, `URL`, `backgm`, `foregm`, `shutdown`,
`suspend`, `wakeup`. There is **no** `exec`/`args` injection through AM: only
the configured command line runs. From the web browser:
`HiBrowser.System.startApp(":am,opera4x,:start=opera4x")`
(`source/modding/03-ui.md`; `source/dead-ends.md`).

### Routes and risk

| Route | Goal | Risk | Reversible | Status |
|---|---|---|---|---|
| A | own app tile (opens a page in the web browser) | low | yes, file backup | **UNVERIFIED** |
| B | replace `/3rd_rw/UI/index.html` with your own page | medium (black screen) | yes, backup + UI restart | **UNVERIFIED** |
| C | launcher data/skin (tiles, categories, icons) | low–medium | yes, backup | **UNVERIFIED** |
| D | own service / early or late hook | medium | yes, scripts/wrapper | root/SSH part recorded; service examples **UNVERIFIED** |
| E | patch read-only files via bind mount / vendor overlay | medium–high | yes, unmount/reboot | mechanics recorded for `/etc/passwd` and `/dev/pts`; AM/UI binds **UNVERIFIED** |
| F | static tools / deploy / SSH | low | yes | Dropbear/SSH/PTY recorded; other tools **UNVERIFIED** |

Route A, backing up and extending `Appinfo.json`:

```sh
cp /3rd_rw/appdata/launcher/Appinfo.json /3rd_rw/backup/Appinfo.json.$(date +%s)
```

```json
{"AppInfo":[
  {"AppId":"MyApp",
   "Thumb":"file:///3rd_rw/appdata/custom/icon.png",
   "Icon_96":"file:///3rd_rw/appdata/custom/icon.png",
   "Image":"file:///3rd_rw/appdata/custom/icon.png",
   "URL":"file:///3rd_rw/appdata/custom/index.html",
   "AppName":"MyApp",
   "Title":"MyApp",
   "IconURL":"file:///3rd_rw/appdata/custom/icon.png",
   "StartCommand":"file:///3rd_rw/appdata/custom/index.html",
   "InstallTime":"2026-10-26",
   "RunTimes":0,
   "StoreType":"foxxum",
   "PreInstall":false}
]}
```

Keep the existing entries. The tile launches the **web browser**, not the UI
page. Then restart the UI or reboot: `kill $(pidof hisenseUI)` and
`nohup /3rd/opera4x/hisenseUI/start-UI.sh >/tmp/hisenseUI.log 2>&1 &`.
Status: **UNVERIFIED** — the mechanics come from the live `Appinfo.json`
structure, the recipe was not executed end-to-end
(`source/modding/07-evidence-unknowns.md`).

Route B, custom UI page: build it as `/3rd_rw/UI/custom.html` first, test it in
the web browser, then either copy it over `index.html` (after backing up
`index.html`) or point `start-UI.sh` at it through a file bind mount. Keep a
backup and expect a black screen on failure; SSH/root-loop still works.
Status: **UNVERIFIED** (`source/modding/07-evidence-unknowns.md`).

Route E, single-file bind mount (the mechanic that is proven for
`/etc/passwd` and `/dev/pts`):

```sh
cp /basic/am_start.ini /3rd_rw/etc/am_start.ini
# edit the copy, then, from developer.sh before app_man starts:
mount --bind /3rd_rw/etc/am_start.ini /basic/am_start.ini
```

Rollback: `umount /basic/am_start.ini` or reboot. The original file is never
written. Status of this specific AM bind: **UNVERIFIED**.

### Preset tiles

26 tiles were observed on the reference device, including the lab
`VidaaRecon` app (`http://<host-ip>:9000/recon.html`). That is a **modified
device snapshot, not a stock retail list**
(`source/modding/03-ui.md`; `source/modding/05-bloat.md`, `:39`). Hiding is done by
adding the tile's start command/ID to `deletedPresetApp.txt`; adding a durable
tile is done through `Appinfo.json`.

## Verified vs UNVERIFIED

| Area | Status | Basis |
|---|---|---|
| Linux/kernel/package manager/storage | recorded live/static | `source/modding/07-evidence-unknowns.md` |
| Boot chain, script lines, service order | recorded live/static | `:76` |
| UI start, processes, paths, app data, AM | recorded live/static | `:77` |
| 26 preset tiles / `Appinfo` / `deleted` | recorded live (inventory only) | `:78` |
| Route A app tile | **UNVERIFIED** | `:79` |
| Route B custom UI | **UNVERIFIED** | `:80` |
| Route C launcher data/skin | **UNVERIFIED** | `:81` |
| Route D own service | root/SSH part recorded; examples **UNVERIFIED** | `:82` |
| Route E bind mount / overlay | mechanics recorded; AM/UI binds **UNVERIFIED** | `:83` |
| Route F static tools/deploy | Dropbear/SSH/PTY recorded; other tools **UNVERIFIED** | `:84` |
| Bloat deactivation effects | **UNVERIFIED** | `:86` |
| Optional SFTP | built/staged; device result not recorded | `:85` |

## Rollback and recovery

- **Backups first.** Recommended: `/3rd_rw/backup/<date>/` for every file you
  touch — `UI/index.html`, `Appinfo.json`, `deletedPresetApp.txt`, `preset.txt`,
  `Category*.xml`, `am_config`, `am_start.ini`, `delayrun.sh`, the
  `HamService` wrapper.
- **UI broken (black screen):** restore `index.html` from the backup, kill and
  restart `hisenseUI`. SSH and the root loop do not depend on the UI.
- **Bind mounts:** `umount <target>` or reboot; the read-only originals are
  untouched.
- **`developer.sh` mistake:** remove or fix it over SSH/root-loop, reboot. It
  runs before the UI and AM, so a hang there looks like a dead TV.
- **Vendor overlay:** `rm -rf /3rd_rw/patch/opera4x` and reboot.
- **Root/SSH layers:** `/bin/sh /3rd_rw/appdata/rollback.sh`, then reboot (see
  the model README). It does not remove every file you uploaded yourself.
- **One change at a time**, and be conservative with `dtv_svc`, `app_man`,
  `LauncherService`, the UI start and the SSH wrapper while experimenting: the
  effects of disabling them are only partly documented.

## Tools

| Path | Purpose |
|---|---|
| [tools/he40/templates](../../../../tools/he40/templates) | `developer.sh`, `custom-app.json`, `hide-preset.json`, `custom-ui.html`, `start-UI-custom.sh` |
| [tools/he40/root/scripts/tv](../../../../tools/he40/root/scripts/tv) | root loop, SSH start/verify/rollback, SFTP staging |
| [tools/he40/root/scripts/host](../../../../tools/he40/root/scripts/host) | deploy helpers (`upload_to_appdata.js`, `run_root_cmd.js`) and builds |
| [tools/he40/recon](../../../../tools/he40/recon) | recon page and capture server |

The templates are patterns, not tested recipes. Read them before use and keep
the backup path outside the directories you replace.

## Evidence

See [EVIDENCE.md](EVIDENCE.md) for the claim matrix, source lines, corrections
and the full unknown list.
