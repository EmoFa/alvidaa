# 07 — Evidence, Verification, Unknowns

**Zweck:** Belegbarkeit und ehrlicher Status. Keine Behauptung ohne Pfad/Auszug; alles, was nicht live getestet ist, ist als `UNVERIFIED` markiert.

---

## 1. Was live bestätigt ist

| Fakt | Beleg | Status |
|---|---|---|
| Browser root | `/proc/self/status` → `Uid/Gid 0 0 0 0`, `CapEff=0000003fffffffff`, Single-Process | **CONFIRMED live** |
| USB-ext4-Symlink-Bypass | `pwn`/`tvi` dangling; `File.write`/`File.download` legt Root-Datei an; `SYMTEST` | **CONFIRMED live** |
| `libtvsysinfo`-Shadow | 33.500 B, SHA `37b13f…`; Boot lädt sie; `ROOT_EXEC_TVI`; self-unlink | **CONFIRMED live** |
| Root-Loop | PID/Log; `uid=0`; `root_cmd.sh` → `root_out.txt` | **CONFIRMED live** |
| Dropbear-SSH | `dropbear` static ARM; `0.0.0.0:22`; `Pubkey auth succeeded for 'root'` | **CONFIRMED live** |
| PTY | Session `pts/0`; `busybox script` → `uid=0(root)` | **CONFIRMED live** |
| `/etc/passwd`-Bind | Root-Home `/3rd_rw/sshd/home:/bin/sh`; authorized_keys 600 | **CONFIRMED live** |
| HamService-Wrapper | `/3rd_rw/hamservice/HamService` startet Loop + SSH, exec real HamService | **CONFIRMED installiert**; Reboot-Test im Root-Guide |
| Payload-Repro | `build_tvi_payload.py` → exakt `37b13f…` | **CONFIRMED** (Host) |

---

## 2. Was aus statischen/live Daten abgeleitet ist (nicht zwingend getestet)

- Die **Modding-Rezepte** (App-Tile, Custom-UI, Launcher-Daten, AM-/Service-Bloat, `developer.sh`-Bind-Mounts, `patch/opera4x`) sind aus den live gelesenen Dateien/Strukturen abgeleitet.
- **Custom-UI** (`UI/index.html` ersetzen) ist **nicht** live getestet; das Risiko (schwarzer Bildschirm) ist dokumentiert.
- **Bloat-Deaktivierungen** (`ms_service`, `swrc`, `runlog`, `Seriallog`, `securetime`, `netflix`, `browser_base`, `app_man`, `dtv_svc`) sind **nicht** alle getestet; Matrix/Rollback in `05`.
- **`Hisense_StartApp`/`TVAPI`/`guijs`-Signaturen** in der UI sind nicht vollständig belegt; im UI-DevTools (9223) prüfen.
- **`app_man`/`:am`-Semantik** je App (`start`/`URL`/`backgm`/`coexist`) ist aus Strings/Config abgeleitet; einzelne Aktionen testen.
- **`VIDAAU2Launcher`** ist als Alternativ-Skin vorhanden; ob aktiv, `UNVERIFIED`.
- **`preset.txt`/`Category*.xml`-Regeneration** durch `LauncherService`/UI ist nicht vollständig geklärt; die `deletedPresetApp.txt` ist der robuste Hide-Hebel.
- **U-Boot-Env** (Bad CRC/default NFS) ist nicht die echte Boot-Konfiguration; `/proc/cmdline` ist maßgeblich.
- **Secure Boot/Signaturprüfung**, **DRM/PlayReady/Widevine**, **OTA/`checker.sh`** sind nicht Teil des Root-Wegs und nicht vollständig untersucht.

---

## 3. Evidence-Dateien / Pfade

### 3.1 In diesem Ordner

- `root/tools/pub/libtvsysinfo.so` — finaler Payload (33500 B, SHA `37b13f…`)
- `root/artifacts/tvi_original.so` — Original-Lib (33220 B, SHA `36ddee…`)
- `root/tools/pub/dropbear`, `dropbearkey` — statische Binaries
- `root/artifacts/keys/{authorized_keys,host-key-fingerprint.txt}`
- `root/tools/{server.py,recon.html,icon.png,live_cmd.txt}`
- `root/scripts/{host,tv}/*` — Build/Deploy/Verify/Rollback
- `sources/dropbear-2022.83.tar.bz2`
- `SHA256SUMS`
- `dead-ends.md`

### 3.2 Am TV (live gelesen)

- `/proc/version`, `/proc/cmdline`, `/proc/cpuinfo`, `/proc/filesystems`, `/proc/mounts`, `/proc/partitions`
- `df -h`, `ls -l /lib`, `ls -l /bin`, `ls -l /etc`
- `/etc/inittab`, `/etc/init.d/rcS`, `/etc/rc.d/rc.local`
- `/basic/autorun.sh` (Zeilen 90/162/168/177/190), `/basic/delayrun.sh`
- `/basic/am_config`, `/basic/am_start.ini`
- `/3rd/launcherservice/startLS.sh`, `/3rd/hamservice/startHam.sh`, `/3rd/opera4x/browser/run-Browser.sh`, `/3rd/opera4x/hisenseUI/start-UI.sh`
- `/3rd_rw/UI/index.html`, `UI/pub/HisProductConfig.js`, `UI/lib/launcherDataInterface.js`
- `/3rd_rw/appdata/launcher/{preset.txt,Appinfo.json,deletedPresetApp.txt,data/*,res/*,cache/*}`
- `/3rd_rw/user_db.db` (Settings), `/3rd_rw/opera4x/opera_home_browser/{opera.json,browser.db}`
- `/3rd_rw/sshd/…`, `/3rd_rw/appdata/root_loop.sh`, `root_loop.pid`, `root_out.txt`
- `ps`, `/proc/<pid>/cmdline`, `/proc/<pid>/status`

### 3.3 Alter Run (nur Provenienz)

Der frühere Run-Ordner `the earlier run archive (not part of this repository)` (im alten Projekt) enthält die Roh-Captures/History. Er ist **nicht** nötig für die Replikation; die finalen Artefakte/Skripte/Docs liegen in diesem Ordner.

---

## 4. Verification-Status (Modding)

| Bereich | Status |
|---|---|
| System/Linux/Package Manager/Storage | **CONFIRMED** (live/static) |
| Boot-Kette/Skripte/Zeilen/Services | **CONFIRMED** (live/static) |
| UI-Start/Prozesse/Pfade/App-Daten/AM | **CONFIRMED** (live/static) |
| 26 Preset-Apps / `Appinfo` / `deleted` | **CONFIRMED** (live gelesen) |
| App-Tile (Route A) | **UNVERIFIED** (nicht live getestet; Mechanik aus `Appinfo`/Launcher) |
| Custom-UI (Route B) | **UNVERIFIED** (nicht live getestet; Risiko dokumentiert) |
| Launcher-Daten/Skin (Route C) | **UNVERIFIED** (nicht live getestet) |
| Eigener Service (Route D) | **Root/SSH-Teil live**; Dienst-Beispiele `UNVERIFIED` |
| Bind-Mount/Overlay (Route E) | **Mechanik live** (`/etc/passwd`, `/dev/pts`); AM-/UI-Bind-Mounts `UNVERIFIED` |
| Statische Tools/Deploy (Route F) | **Dropbear/SSH/PTY live**; andere Tools `UNVERIFIED` |
| SFTP (optional) | statischer OpenSSH-sftp-server + gepatchter Dropbear gebaut; Installer testet 2222 vor 22; **TV-Test nach Install** |
| Bloat-Deaktivierungen | **UNVERIFIED** (Matrix/Rollback in `05`) |

---

## 5. Bekannte Unknowns

- Exakte SoC-Bezeichnung (MT5863 vs. MT53xx-Familie), Kernanzahl, Secure-Boot/Signaturen.
- Vollständige Kernel-Config, `dm-3`-Konstruktion, `spdata`/`perm`/`facset`/`hiscfg`/`eeprom`/`channel`/`pq`/`adsp`/`logo`.
- Echter U-Boot-Flow/Env (Bad CRC), A/B-Slot-Auswahl, Recovery.
- `checker.sh`/`ota_upgrade_strategy.sh`/`file_upgrading`/`bspatch`/OTA.
- `dtv_svc`/`app_man`/`:am`-Interna, `coexist_set`/`backgm`/`keymap`.
- `LauncherService`-Datenquelle/Update (Store/Foxxum/FCGI), `preset`-/`Category`-Regeneration.
- Aktive UI-Template-/Skin-Auswahl; `VIDAAU2Launcher` aktiv? `UNVERIFIED`.
- `Hisense_StartApp`/`TVAPI`/`guijs`-Signaturen; `app_man`-Start-Sinn.
- Bloat-Folgen: `ms_service`/`swrc`/`runlog`/`Seriallog`/`HamService`/`securetime`/`browser_base`/`app_man`/`dtv_svc`.
- DRM/PlayReady/Widevine/Netflix/Cobalt/Amazon; `securetime`.
- SFTP ist über den statischen OpenSSH-sftp-server + gepatchten Dropbear nachgerüstet; der Installer testet Port 2222 und erst dann 22. Das TV-Testergebnis steht in `/3rd_rw/sshd/dropbear2222.log` und `swap.log`; `ssh`+base64/tar bleibt der Fallback.
- Ob eine eigene `UI/index.html` die `TVAPI`/`model`-Globals braucht oder `Hisense_*`/`guijs` direkt nutzbar sind.
- Ob `preset`/`Category`/`serviceUpdate` bei Store-/Netz-Updates überschrieben werden.

---

## 6. Dead Ends (Kurzfassung)

Siehe `../dead-ends.md`. Die wichtigsten:

- Factory `Builtin Video`/`Write Keys`, AM `startApp` (kein exec/args).
- V8 5.9/Chromium 59 ohne öffentlichen ARM32-Exploit; nicht nötig.
- `liblogLevel`-Shadow (Index 17 belegt), `libIQQILib`/`libota`/`hisensefileutils`-Varianten, `ms-screen`-`lib`-Symlink.
- `File.write` binär (`EINVAL`), `loadLibrary`-Tricks.
- FAT32/Superfloppy-USB, fehlende Symlink-Möglichkeit.
- Dropbear `-s` (gibt es nicht), PTY direkt auf `/dev/pts` (ro). **SFTP ist kein Dead End mehr**: statischer OpenSSH-sftp-server + gepatchter Dropbear (`install_sftp.sh`).
- UI-Alt-Skins (`launcher`/`VIDAAU2Launcher`) als aktiven Einstieg; die aktive UI ist `/3rd_rw/UI`.

---

## 7. Keine Secrets

- **Kein Root-Hash** in diesem Ordner.
- **Kein privater SSH-Key**; nur der Public Key (`authorized_keys`) + Host-Key-Fingerprint.
- **Keine Captures/ungefilterten Dumps** in diesem Ordner; die Roh-Evidence liegt (falls benötigt) im alten Run-Ordner.
- **Keine Zugangsdaten** zu Dritt-Diensten; die Preset-URLs sind nur Ziel-Daten, keine Aufforderung, sie zu kontaktieren.
