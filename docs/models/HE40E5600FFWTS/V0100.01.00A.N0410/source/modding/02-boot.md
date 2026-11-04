# 02 — Boot: vom U-Boot bis UI/AM/Services

**Status:** Boot-Kette, Skripte, Zeilennummern und Service-Reihenfolge **CONFIRMED** aus `/etc`, `/basic`, `/3rd` (live/static). Einzelne Bootloader-/Hardware-Details `UNVERIFIED`.

---

## 1. Boot-Reihenfolge (Überblick)

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
              → OTA-Check, Wireless, /3rd_rw/developer.sh (Zeile 90)
              → preload_opera, core-dump, ms_service (162)
              → hisenseUI/start-UI.sh (168)
              → app_man -c am_config -s am_start.ini (177)
              → delayrun.sh (190)
                → swrc-server, runlogservice, LauncherService, Seriallog,
                  HamService, swap
              → usb_console.sh, Bluetooth
```

**Wichtig:** `/3rd_rw/developer.sh` läuft **früh** (Zeile 90) — **vor** `ms_service`, `hisenseUI`, `app_man` und `delayrun`. Das ist der beste Hook für frühe Bind-Mounts/Stubs/custom Services. Der `HamService`-Wrapper läuft **spät** (nach `delayrun` + 15 s) und ist der aktuelle SSH/Root-Loop-Boot-Hook.

---

## 2. U-Boot / Kernel / Partitionen

- **Bootmedium:** eMMC, MediaTek `mt53xx-emmc`.
- **A/B-Slots:** `ubootA/B`, `kernelA/B`, `rootfsA/B`; root ist `/dev/mmcblk0p9` (rootfsA).
- **Rootfs:** squashfs **ro** (38.8 MB, 100 %); `/3rd` ist `dm-3` squashfs ro (141 MB, 100 %).
- **Kernel-Cmdline** (Auszug):
  ```
  rootwait rootfstype=squashfs ro console=ttyMT0,115200n1 vmalloc=512mb quiet
  mtdparts=mt53xx-emmc:... root=/dev/mmcblk0p9 ... adb_enable=0
  ```
- **U-Boot-Env:** `fw_printenv` → **„Bad CRC, using default environment“**; Default ist NFS (`bootcmd=bootp...`). Die **echte** Boot-Konfiguration ist die `/proc/cmdline`; das gespeicherte U-Boot-Env ist nicht verlässlich.
- **Seriell:** `ttyMT0` 115200 (getty); `rootlogin.sh` = USB-Key + doppelt-MD5-PIN (Hardware-Root). **Nicht nötig** für den Software-Root.
- **ADB:** `adb_enable=0`; kein ADB.

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

### `/etc/rc.d/rc.local` (Auszug)

```sh
echo "rc.local begin" > /proc/boottime
# /dev/shm/shm_tmp (Basis für /tmp)
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

- **`/proc/boottime`** wird an mehreren Stellen geschrieben (Boot-Timing).
- **`file_upgrading`** in `/proc/cmdline` triggert `checker.sh` + `mount_perm`/`mount_3rd`/`mount_3rd_ro`; nicht der normale Boot.
- **`/basic/3rd_ini/*/global_env_setup.ini`** setzt `LD_LIBRARY_PATH`/Env für die 3rd-Services.
- **`fusion.ko`** ist das MediaTek-AM-/App-Framework-Modul; `dtv_driver*.ko` für den Tuner/DTV.
- **`/3rd_rw/patch/opera4x`**: Vendor-Overlay — wenn das Verzeichnis existiert, wird es **als Ganzes** über `/3rd/opera4x` gebindet (`mount -o bind`). Siehe Abschnitt 7.
- **`/3rd_rw/developer.sh`**: früher Root-Hook (siehe Abschnitt 6).

---

## 4. `/basic/autorun.sh` — die Service-Zentrale

Reihenfolge (Zeilennummern aus der Datei):

| Zeile | Aktion |
|---:|---|
| 1–~60 | Header, OTA-Strategie (`ota_upgrade_strategy.sh`), Wireless-Datei, Developer-Hook |
| **90–92** | **`if [ -f /3rd_rw/developer.sh ]; then sh /3rd_rw/developer.sh; fi`** |
| ~128 | `preload_opera.sh` (Opera-Libs) |
| ~137 | Core-Dump-Setup (optional) |
| ~162 | **`ms_service`** starten (`/3rd/ms-screen/ms_service &`) |
| **168** | **`hisenseUI/start-UI.sh &`** (TV-UI, `/3rd_rw/UI/index.html`) |
| **177** | **`/basic/app_man -c /basic/am_config -s /basic/am_start.ini -input_fifo &`** |
| **190** | **`sh /basic/delayrun.sh &`** |
| danach | `usb_console.sh`, Bluetooth-Service |

**Wichtig:** Der `developer.sh`-Hook ist **vor** `ms_service`/`hisenseUI`/`app_man`/`delayrun`. Damit lassen sich ro-Dateien (z. B. `/basic/am_config`, `/basic/am_start.ini`, `/basic/delayrun.sh`, `/3rd/ms-screen/ms_service`, `/3rd/opera4x/hisenseUI/start-UI.sh`) per **Datei-Bind-Mount** oder Stub ersetzen, **bevor** sie gelesen/ausgeführt werden.

---

## 5. AM (app_man), am_start, am_config, delayrun

### 5.1 `app_man`

```sh
cd /basic
/basic/app_man -c /basic/am_config -s /basic/am_start.ini -input_fifo &
```

- **AM** = MediaTek App Manager. Startet native Apps/Services aus `am_start.ini`/`am_config`.
- Steuerung: `:am,<app>,:<verb>=<val>`; Verbs u. a. `start`, `stop`, `pause`, `resume`, `URL`, `backgm`, `foregm`, `shutdown`, `suspend`, `wakeup`; `:am,am,...` für den Manager.
- **Kein `exec`/`args` über AM** (nur die konfigurierten `exec`/`args`).

### 5.2 `am_start.ini` — Boot-App-Sektionen

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

- **`dtv_app_mtk` / `dtv_svc`**: TV-Kern (Tuner/DTV/Navigator); wird zuerst gestartet.
- **`netflix`**: Netflix-App; `coexist_set` mit `dtv_app_mtk`, `opera4x`, `factory_lite`.
- **`dialserver`**: DIAL/CAST.
- **`samba_relay_agent`**: Samba-Relay (Port 9090).
- **`browser_base`**: Hintergrund-Browser (`/3rd/internet_browser/browser -x bws_background`), `start_self=true`.
- **`securetime`**: PlayReady Secure Time (`/3rd/playready/securetime`).

### 5.3 `am_config` — App-Definitionen (Auszug)

| App | exec / args | Bemerkung |
|---|---|---|
| `opera4x` | `/3rd/opera4x/browser/run-Browser.sh` | Web-Browser (`hisense_browser`), `start_self=true`, DevTools 9224 |
| `netflix_niab` | `/3rd/netflix/nrd-app/netflix` | Netflix |
| `opera_browser` | `/3rd/internet_browser/browser -u http://www.google.com ...` | „Internet Browser“-Variante |
| `opera_tv_store` | `/3rd/internet_browser/browser -u https://demo.tvstore.opera.com ...` | TV Store |
| `youtube` | `/3rd/internet_browser/browser -u http://www.youtube.com/tv ...` | YouTube (Web) |
| `youtube_kids` / `youtube_tv` | `/3rd/cobalt/cobalt ...` | Cobalt-YouTube |
| `cobalt` | `/3rd/cobalt/cobalt ...` | Cobalt |
| `amazon_ignition` | `/3rd/amazon/bin/ignition` | Amazon |
| `factory_lite` | `/3rd/his_factory/factory_lite -qws` | Factory-Menü |
| `huluplus`, `hotlist`, `generic_osd` | Internet-Browser | Legacy/Store |
| `vudu` (referenziert) | — | Store/Region |

- `exec`/`args`; `coexist_set`; `start_self`; `backgm_support`; `keymap`; `timeout_4_stop`; `loosely_exclusive_set`.
- **Der Web-Browser** (`opera4x`) wird **nicht** beim Boot aus `am_start.ini` gestartet; er wird bei Bedarf (TV-Browser-Tile) über AM gestartet. **Die UI** (`hisenseUI`) startet separat aus `autorun.sh` (Zeile 168).

### 5.4 `delayrun.sh` — späte Services (nach 15 s)

```sh
sleep 15
export LD_LIBRARY_PATH=/3rd/loglevel/lib:$LD_LIBRARY_PATH
/3rd/swrc-server/swrc-server &
/3rd/his_runlog/runlogservice.sh &
/3rd/launcherservice/startLS.sh &      # LauncherService
/3rd/Serial_log/Seriallog &
/3rd/hamservice/startHam.sh &          # HamService (unser Wrapper)
mkswap /dev/mmcblk0p34; swapon /dev/mmcblk0p34
```

- **`swrc-server`**: Software-Remote-Control-Server.
- **`runlogservice`**: Logging/Runlog.
- **`LauncherService`**: Launcher-/App-Daten/UI-Service (`startLS.sh`).
- **`Seriallog`**: serielles Logging.
- **`HamService`**: ACR/Hisense-Service; **hier** greift unser Wrapper (`/3rd_rw/hamservice/HamService`), der Root-Loop + Dropbear startet und dann das echte `/3rd/hamservice/HamService` ausführt.
- **Swap:** `mmcblk0p34` (100M).

---

## 6. Boot-Hooks (die wichtigen)

| Hook | Zeitpunkt | Was |
|---|---|---|
| **`/3rd_rw/developer.sh`** | **früh** (autorun Zeile 90) | Root; vor `ms_service`/`hisenseUI`/`app_man`/`delayrun`. Bestens für: `mount --bind` von modifizierten `am_start.ini`/`am_config`/`delayrun.sh`, Stubs für `ms_service`/`start-UI.sh`/`app_man`, frühe eigene Services, SSH/Root-Loop. |
| **`/3rd_rw/hamservice/HamService`** | spät (delayrun + 15 s) | Root; unser Wrapper: `root_loop.sh` + `start_sshd.sh`, dann `exec /3rd/hamservice/HamService`. **Aktuelle SSH/Root-Persistenz.** |
| **`/3rd_rw/patch/opera4x`** | autorun (vor `preload_opera`/UI) | Vendor-Overlay: `mount -o bind /3rd_rw/patch/opera4x /3rd/opera4x`. **Full overlay** — nur mit vollständigem Baum/Symlinks; für einzelne Dateien lieber Datei-Bind-Mount via `developer.sh`. |
| **`/3rd_rw/UI`** | UI-Start | Die aktive UI-Seite (`/3rd_rw/UI/index.html`); rw. |
| **`/3rd_rw/appdata/launcher`** | UI/LauncherService | App-Tiles/Daten (`preset.txt`, `Appinfo.json`, `deletedPresetApp.txt`, `data/Category*.xml`, `res/`). |
| **`/3rd_rw/sshd`** | via HamService/`start_sshd.sh` | Dropbear, Host-Key, authorized_keys, Startskript. |
| **`/3rd_rw/appdata/root_loop.sh`** | via HamService/`developer.sh` | Root-Kommandokanal (`root_cmd.sh` → `root_out.txt`). |
| **`/3rd_rw/patch/opera4x`** | autorun | full `/3rd/opera4x` overlay; siehe oben. |

**Wichtig:** Die ro-Dateien `/basic/am_config`, `/basic/am_start.ini`, `/basic/delayrun.sh` werden **nach** dem `developer.sh` gelesen/ausgeführt. Ein `mount --bind` in `developer.sh` wirkt daher. Ein Stub über `/3rd/ms-screen/ms_service` oder `/3rd/opera4x/hisenseUI/start-UI.sh` wirkt ebenfalls, weil die `-x`-Checks danach kommen.

---

## 7. `/3rd_rw/patch/opera4x` (Vendor-Overlay)

In `autorun.sh`:

```sh
BROWSER_3RD_RW=/3rd_rw/patch/opera4x
if [ -d $BROWSER_3RD_RW ]; then
   mount -o bind $BROWSER_3RD_RW /3rd/opera4x
fi
```

- **Full directory bind**: `/3rd/opera4x` wird komplett durch `/3rd_rw/patch/opera4x` ersetzt.
- **Konsequenz:** Der Patch-Ordner muss die **komplette** `opera4x`-Struktur enthalten (oder ein Symlink-Baum auf `/3rd/opera4x` sein), sonst fehlen Browser/UI/Libs.
- **Für einzelne Dateien** (z. B. `hisenseUI/start-UI.sh`, `opera_env.sh`) ist ein **Datei-Bind-Mount** in `developer.sh` sicherer:
  ```sh
  mount --bind /3rd_rw/patch/start-UI-custom.sh /3rd/opera4x/hisenseUI/start-UI.sh
  ```
- Der Patch-Ordner ist **nicht** vorhanden; er ist ein optionaler Vendor-Hook. Siehe `04-modding.md` Route E.

---

## 8. Logs / Verifikation

- **`/proc/boottime`**: Timing-Marker (`rc.local begin`, `mount_main.sh`, `fusion.ko`, `ms_service` etc.).
- **`/tmp/am_*`**: AM-Infos (`am_tv_model_name`, `am_tv_version`, `am_start.ini`-Status).
- **`/tmp/fifo_am_*`, `/tmp/DmrLaunchedStatus.dat`, …**: AM/DIAL.
- **Hisense Runlog**: `/3rd/his_runlog/runlogservice.sh`, `/3rd_rw/...` (Logs).
- **`Seriallog`**: `/3rd/Serial_log`.
- **Unser SSH/Deploy**: `/3rd_rw/sshd/dropbear.log`, `/3rd_rw/sshd/mount.log`, `/3rd_rw/appdata/root_out.txt`, `/3rd_rw/appdata/root_loop.log`.
- **Prozesse:** `ps`, `/proc/<pid>/cmdline`, `/proc/<pid>/status`.
- **UI:** `hisenseUI` (PID z. B. 589), `hisense_browser` (PID z. B. 1320), `app_man`, `dtv_svc`, `LauncherService`, `HamService`.

**Health-Check auf dem TV:**

```sh
/bin/sh /3rd_rw/appdata/verify.sh
```

---

## 9. Risiken / Grenzen

- **`developer.sh`-Fehler** können `ms_service`/UI/`app_man`/`delayrun` verhindern → TV-UI schwarz, Apps starten nicht. Immer mit `set -x`/Log und Fallback (SSH/Root-Loop, Web-Browser) arbeiten.
- **`am_config`/`am_start.ini` beschädigen** → native Apps (TV, Netflix, DIAL) starten nicht. Modifizierte Kopien **vorher testen**; `developer.sh`-Bind nur mit Backup; Rollback = Bind lösen/reboot.
- **`app_man`/`dtv_svc` deaktivieren** → TV/Remote/Apps kaputt; für eine reine Custom-UI riskant. `dtv_svc`/`app_man` lieber behalten.
- **`/3rd_rw/patch/opera4x` full overlay** → fehlende Dateien = Browser/UI kaputt. Nur mit vollständiger Kopie; besser Datei-Bind.
- **`ms_service`/`swrc`/`runlog`/`Seriallog`** abschalten ist meist unkritisch, kann aber DLNA/Remote/Logs kosten.
- **`securetime`** ist PlayReady/DRM; deaktivieren kann DRM/Netflix brechen.
- **Kein Flash/Recovery:** Der TV hat kein UART angeschlossen; der Root/SSH-Weg und `developer.sh`/HamService-Wrapper sind die Rettungswege. Keine Änderungen am ro Rootfs/`/3rd` ohne vollständiges Verständnis.

---

## 10. Unknowns

- Echter U-Boot-Flow/Env (Bad CRC), Secure Boot, Signaturprüfung, A/B-Slot-Auswahl.
- Voller Inhalt von `checker.sh`, `ota_upgrade_strategy.sh`, `file_upgrading`, `bspatch`/OTA.
- `dtv_svc`/`app_man`/`am`-Interna, `:am`-Semantik im Detail, `coexist_set`/`backgm`/`keymap`.
- `LauncherService`-Datenquelle (Store/Foxxum/FCGI), `hisenseUI`-Template-Auswahl.
- Ob `VIDAAU2Launcher` auf diesem Modell je aktiv ist (die aktive UI ist `/3rd_rw/UI`).
- `ms_service`/`swrc`/`runlog`/`Seriallog`/`HamService`-Abschaltfolgen.
- Exakte Service-PIDs/Reihenfolge variieren pro Boot; die Skript-/Zeilen-Reihenfolge ist stabil.
