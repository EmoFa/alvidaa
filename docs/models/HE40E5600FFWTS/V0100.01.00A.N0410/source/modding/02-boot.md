# 02 — Boot: from U-Boot to UI/AM/Services

**Status:** boot chain, scripts, line numbers and service order **CONFIRMED** from `/etc`, `/basic`, `/3rd` (live/static). Individual bootloader/hardware details `UNVERIFIED`.

---

## 1. Boot order (overview)

```text
U-Boot (eMMC)
  → Linux 3.18.25 (cmdline: root=/dev/mmcblk0p9, rootfstype=squashfs, console=ttyMT0)
    → /sbin/init
      → /etc/inittab (getty ttyMT0, sysinit)
        → /etc/init.d/rcS
          → mount -a
          → /etc/rc.d/rc.local
            → rc.local.partial, mount_main.sh, mount_data.sh, 3rd_ini env
            → mount_3rd_ro.sh, mount_3rd.sh, mount_perm.sh
            → insmod /basic/fusion.ko
            → /etc/scripts/hisense_rc.sh (mount_userdata.sh async)
            → /basic/autorun.sh
              → OTA check, wireless, /3rd_rw/developer.sh (line 90)
              → preload_opera, core-dump, ms_service (162)
              → hisenseUI/start-UI.sh (168)
              → app_man -c am_config -s am_start.ini (177)
              → delayrun.sh (190)
                → swrc-server, runlogservice, LauncherService, Seriallog,
                  HamService, swap
              → usb_console.sh, Bluetooth
```

**Important:** `/3rd_rw/developer.sh` runs **early** (line 90) — **before** `ms_service`, `hisenseUI`, `app_man` and `delayrun`. That is the best hook for early bind mounts/stubs/custom services. The `HamService` wrapper runs **late** (after `delayrun` + 15 s) and is the current SSH/root loop boot hook.

---

## 2. U-Boot / Kernel / Partitions

- **Boot medium:** eMMC, MediaTek `mt53xx-emmc`.
- **A/B slots:** `ubootA/B`, `kernelA/B`, `rootfsA/B`; root is `/dev/mmcblk0p9` (rootfsA).
- **Rootfs:** squashfs **ro** (38.8 MB, 100 %); `/3rd` is `dm-3` squashfs ro (141 MB, 100 %).
- **Kernel cmdline** (excerpt):
  ```
  rootwait rootfstype=squashfs ro console=ttyMT0,115200n1 vmalloc=512mb quiet
  mtdparts=mt53xx-emmc:... root=/dev/mmcblk0p9 ... adb_enable=0
  ```
- **U-Boot env:** `fw_printenv` → **"Bad CRC, using default environment"**; the default is NFS (`bootcmd=bootp...`). The **real** boot configuration is `/proc/cmdline`; the stored U-Boot env is not reliable.
- **Serial:** `ttyMT0` 115200 (getty); `rootlogin.sh` = USB key + double-MD5 PIN (hardware root). **Not needed** for the software root.
- **ADB:** `adb_enable=0`; no ADB.

---

## 3. init / rcS / rc.local

### `/etc/inittab`

```text
id:3:initdefault:
1:012345:respawn:/sbin/getty -L ttyMT0 115200 vt100
si::sysinit:/etc/init.d/rcS
```

### `/etc/init.d/rcS`

```sh
#! /bin/sh
source /etc/profile
# Don't use scripts. Just use mount -a for fast boot.
/bin/mount -avt nonfs,nosmbfs
[ -x /etc/rc.d/rc.local ] && /etc/rc.d/rc.local
```

### `/etc/rc.d/rc.local` (excerpt)

```sh
echo "rc.local begin" > /proc/boottime
# /dev/shm/shm_tmp (basis for /tmp)
sh /etc/rc.d/rc.local.partial &
sh /etc/scripts/mount_main.sh
sh /etc/scripts/mount_data.sh
for INI_3RD in `ls /basic/3rd_ini`; do source /basic/3rd_ini/$INI_3RD/global_env_setup.ini; done
# mount_3rd_ro.sh / mount_3rd.sh / mount_perm.sh
insmod /basic/fusion.ko
sh /etc/scripts/hisense_rc.sh          # mount_userdata.sh async
# dtv_driver_adpt.ko / dtv_dolby_vision.ko / dtv_driver.ko
# BROWSER_3RD_RW=/3rd_rw/patch/opera4x; mount -o bind ... /3rd/opera4x
# preload_opera.sh, core-dump, ut_drv, aud_cpudec
# ms_service, hisenseUI/start-UI.sh, app_man, delayrun
```

- **`/proc/boottime`** is written from several places (boot timing).
- **`file_upgrading`** in `/proc/cmdline` triggers `checker.sh` + `mount_perm`/`mount_3rd`/`mount_3rd_ro`; not the normal boot.
- **`/basic/3rd_ini/*/global_env_setup.ini`** sets `LD_LIBRARY_PATH`/env for the 3rd-party services.
- **`fusion.ko`** is the MediaTek AM/app framework module; `dtv_driver*.ko` for the tuner/DTV.
- **`/3rd_rw/patch/opera4x`**: vendor overlay — if the directory exists, it is bind-mounted **as a whole** over `/3rd/opera4x` (`mount -o bind`). See section 7.
- **`/3rd_rw/developer.sh`**: early root hook (see section 6).

---

## 4. `/basic/autorun.sh` — the service hub

Order (line numbers from the file):

| Line | Action |
|---:|---|
| 1–~60 | Header, OTA strategy (`ota_upgrade_strategy.sh`), wireless file, developer hook |
| **90–92** | **`if [ -f /3rd_rw/developer.sh ]; then sh /3rd_rw/developer.sh; fi`** |
| ~128 | `preload_opera.sh` (Opera libs) |
| ~137 | Core dump setup (optional) |
| ~162 | Start **`ms_service`** (`/3rd/ms-screen/ms_service &`) |
| **168** | **`hisenseUI/start-UI.sh &`** (TV UI, `/3rd_rw/UI/index.html`) |
| **177** | **`/basic/app_man -c /basic/am_config -s /basic/am_start.ini -input_fifo &`** |
| **190** | **`sh /basic/delayrun.sh &`** |
| after that | `usb_console.sh`, Bluetooth service |

**Important:** the `developer.sh` hook is **before** `ms_service`/`hisenseUI`/`app_man`/`delayrun`. This allows ro files (e.g. `/basic/am_config`, `/basic/am_start.ini`, `/basic/delayrun.sh`, `/3rd/ms-screen/ms_service`, `/3rd/opera4x/hisenseUI/start-UI.sh`) to be replaced via **file bind mount** or stub **before** they are read/executed.

---

## 5. AM (app_man), am_start, am_config, delayrun

### 5.1 `app_man`

```sh
cd /basic
/basic/app_man -c /basic/am_config -s /basic/am_start.ini -input_fifo &
```

- **AM** = MediaTek App Manager. Starts native apps/services from `am_start.ini`/`am_config`.
- Control: `:am,<app>,:<verb>=<val>`; verbs include `start`, `stop`, `pause`, `resume`, `URL`, `backgm`, `foregm`, `shutdown`, `suspend`, `wakeup`; `:am,am,...` for the manager.
- **No `exec`/`args` via AM** (only the configured `exec`/`args`).

### 5.2 `am_start.ini` — boot app sections

```ini
[ application_context ]
app_sect = securetime
app_sect = dialserver
app_sect = netflix
app_sect = samba_relay_agent
app_sect = browser_base
app_sect = dtv_app_mtk   # first started

[ dtv_app_mtk ]
exec = /basic/dtv_svc
args = --am -input_fifo
coexist_set = [opera4x,factory_lite,diskcache,netflix]

[ netflix ]
exec = /3rd/netflix/nrd-app/netflix
...
```

- **`dtv_app_mtk` / `dtv_svc`**: TV core (tuner/DTV/navigator); started first.
- **`netflix`**: Netflix app; `coexist_set` with `dtv_app_mtk`, `opera4x`, `factory_lite`.
- **`dialserver`**: DIAL/CAST.
- **`samba_relay_agent`**: Samba relay (port 9090).
- **`browser_base`**: background browser (`/3rd/internet_browser/browser -x bws_background`), `start_self=true`.
- **`securetime`**: PlayReady Secure Time (`/3rd/playready/securetime`).

### 5.3 `am_config` — app definitions (excerpt)

| App | exec / args | Note |
|---|---|---|
| `opera4x` | `/3rd/opera4x/browser/run-Browser.sh` | Web browser (`hisense_browser`), `start_self=true`, DevTools 9224 |
| `netflix_niab` | `/3rd/netflix/nrd-app/netflix` | Netflix |
| `opera_browser` | `/3rd/internet_browser/browser -u http://www.google.com ...` | "Internet Browser" variant |
| `opera_tv_store` | `/3rd/internet_browser/browser -u https://demo.tvstore.opera.com ...` | TV Store |
| `youtube` | `/3rd/internet_browser/browser -u http://www.youtube.com/tv ...` | YouTube (web) |
| `youtube_kids` / `youtube_tv` | `/3rd/cobalt/cobalt ...` | Cobalt YouTube |
| `cobalt` | `/3rd/cobalt/cobalt ...` | Cobalt |
| `amazon_ignition` | `/3rd/amazon/bin/ignition` | Amazon |
| `factory_lite` | `/3rd/his_factory/factory_lite -qws` | Factory menu |
| `huluplus`, `hotlist`, `generic_osd` | Internet browser | Legacy/store |
| `vudu` (referenced) | — | Store/region |

- `exec`/`args`; `coexist_set`; `start_self`; `backgm_support`; `keymap`; `timeout_4_stop`; `loosely_exclusive_set`.
- **The web browser** (`opera4x`) is **not** started at boot from `am_start.ini`; it is started on demand (TV browser tile) via AM. **The UI** (`hisenseUI`) starts separately from `autorun.sh` (line 168).

### 5.4 `delayrun.sh` — late services (after 15 s)

```sh
sleep 15
export LD_LIBRARY_PATH=/3rd/loglevel/lib:$LD_LIBRARY_PATH
/3rd/swrc-server/swrc-server &
/3rd/his_runlog/runlogservice.sh &
/3rd/launcherservice/startLS.sh &      # LauncherService
/3rd/Serial_log/Seriallog &
/3rd/hamservice/startHam.sh &          # HamService (our wrapper)
mkswap /dev/mmcblk0p34; swapon /dev/mmcblk0p34
```

- **`swrc-server`**: software remote control server.
- **`runlogservice`**: logging/runlog.
- **`LauncherService`**: launcher/app data/UI service (`startLS.sh`).
- **`Seriallog`**: serial logging.
- **`HamService`**: ACR/Hisense service; **this** is where our wrapper (`/3rd_rw/hamservice/HamService`) hooks in, starting the root loop + Dropbear and then executing the real `/3rd/hamservice/HamService`.
- **Swap:** `mmcblk0p34` (100M).

---

## 6. Boot hooks (the important ones)

| Hook | Timing | What |
|---|---|---|
| **`/3rd_rw/developer.sh`** | **early** (autorun line 90) | Root; before `ms_service`/`hisenseUI`/`app_man`/`delayrun`. Best suited for: `mount --bind` of modified `am_start.ini`/`am_config`/`delayrun.sh`, stubs for `ms_service`/`start-UI.sh`/`app_man`, early custom services, SSH/root loop. |
| **`/3rd_rw/hamservice/HamService`** | late (delayrun + 15 s) | Root; our wrapper: `root_loop.sh` + `start_sshd.sh`, then `exec /3rd/hamservice/HamService`. **Current SSH/root persistence.** |
| **`/3rd_rw/patch/opera4x`** | autorun (before `preload_opera`/UI) | Vendor overlay: `mount -o bind /3rd_rw/patch/opera4x /3rd/opera4x`. **Full overlay** — only with a complete tree/symlinks; for individual files prefer a file bind mount via `developer.sh`. |
| **`/3rd_rw/UI`** | UI start | The active UI page (`/3rd_rw/UI/index.html`); rw. |
| **`/3rd_rw/appdata/launcher`** | UI/LauncherService | App tiles/data (`preset.txt`, `Appinfo.json`, `deletedPresetApp.txt`, `data/Category*.xml`, `res/`). |
| **`/3rd_rw/sshd`** | via HamService/`start_sshd.sh` | Dropbear, host key, authorized_keys, start script. |
| **`/3rd_rw/appdata/root_loop.sh`** | via HamService/`developer.sh` | Root command channel (`root_cmd.sh` → `root_out.txt`). |
| **`/3rd_rw/patch/opera4x`** | autorun | full `/3rd/opera4x` overlay; see above. |

**Important:** the ro files `/basic/am_config`, `/basic/am_start.ini`, `/basic/delayrun.sh` are read/executed **after** `developer.sh`. A `mount --bind` in `developer.sh` therefore takes effect. A stub via `/3rd/ms-screen/ms_service` or `/3rd/opera4x/hisenseUI/start-UI.sh` also works, because the `-x` checks come afterwards.

---

## 7. `/3rd_rw/patch/opera4x` (vendor overlay)

In `autorun.sh`:

```sh
BROWSER_3RD_RW=/3rd_rw/patch/opera4x
if [ -d $BROWSER_3RD_RW ]; then
   mount -o bind $BROWSER_3RD_RW /3rd/opera4x
fi
```

- **Full directory bind**: `/3rd/opera4x` is completely replaced by `/3rd_rw/patch/opera4x`.
- **Consequence:** the patch folder must contain the **complete** `opera4x` structure (or be a symlink tree to `/3rd/opera4x`), otherwise browser/UI/libs are missing.
- **For individual files** (e.g. `hisenseUI/start-UI.sh`, `opera_env.sh`) a **file bind mount** in `developer.sh` is safer:
  ```sh
  mount --bind /3rd_rw/patch/start-UI-custom.sh /3rd/opera4x/hisenseUI/start-UI.sh
  ```
- The patch folder is **not** present; it is an optional vendor hook. See `04-modding.md` route E.

---

## 8. Logs / Verification

- **`/proc/boottime`**: timing markers (`rc.local begin`, `mount_main.sh`, `fusion.ko`, `ms_service` etc.).
- **`/tmp/am_*`**: AM info (`am_tv_model_name`, `am_tv_version`, `am_start.ini` status).
- **`/tmp/fifo_am_*`, `/tmp/DmrLaunchedStatus.dat`, …**: AM/DIAL.
- **Hisense runlog**: `/3rd/his_runlog/runlogservice.sh`, `/3rd_rw/...` (logs).
- **`Seriallog`**: `/3rd/Serial_log`.
- **Our SSH/deploy**: `/3rd_rw/sshd/dropbear.log`, `/3rd_rw/sshd/mount.log`, `/3rd_rw/appdata/root_out.txt`, `/3rd_rw/appdata/root_loop.log`.
- **Processes:** `ps`, `/proc/<pid>/cmdline`, `/proc/<pid>/status`.
- **UI:** `hisenseUI` (PID e.g. 589), `hisense_browser` (PID e.g. 1320), `app_man`, `dtv_svc`, `LauncherService`, `HamService`.

**Health check on the TV:**

```sh
/bin/sh /3rd_rw/appdata/verify.sh
```

---

## 9. Risks / limits

- **`developer.sh` errors** can prevent `ms_service`/UI/`app_man`/`delayrun` → TV UI goes black, apps do not start. Always work with `set -x`/log and a fallback (SSH/root loop, web browser).
- **Damaging `am_config`/`am_start.ini`** → native apps (TV, Netflix, DIAL) do not start. **Test** modified copies **beforehand**; `developer.sh` bind only with a backup; rollback = release the bind/reboot.
- **Disabling `app_man`/`dtv_svc`** → TV/remote/apps broken; risky for a pure custom UI. Prefer keeping `dtv_svc`/`app_man`.
- **`/3rd_rw/patch/opera4x` full overlay** → missing files = broken browser/UI. Only with a complete copy; a file bind is better.
- **Turning off `ms_service`/`swrc`/`runlog`/`Seriallog`** is mostly uncritical but can cost DLNA/remote/logs.
- **`securetime`** is PlayReady/DRM; disabling it can break DRM/Netflix.
- **No flash/recovery:** the TV has no UART connected; the root/SSH route and the `developer.sh`/HamService wrapper are the rescue paths. No changes to the ro rootfs/`/3rd` without full understanding.

---

## 10. Unknowns

- Real U-Boot flow/env (Bad CRC), secure boot, signature verification, A/B slot selection.
- Full content of `checker.sh`, `ota_upgrade_strategy.sh`, `file_upgrading`, `bspatch`/OTA.
- `dtv_svc`/`app_man`/`am` internals, `:am` semantics in detail, `coexist_set`/`backgm`/`keymap`.
- `LauncherService` data source (store/Foxxum/FCGI), `hisenseUI` template selection.
- Whether `VIDAAU2Launcher` is ever active on this model (the active UI is `/3rd_rw/UI`).
- Consequences of disabling `ms_service`/`swrc`/`runlog`/`Seriallog`/`HamService`.
- Exact service PIDs/order vary per boot; the script/line order is stable.
