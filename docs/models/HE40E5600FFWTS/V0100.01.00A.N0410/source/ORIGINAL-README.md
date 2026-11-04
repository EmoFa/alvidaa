# Hisense HE40E5600FFWTS — Root & Modding — Final Documentation

> **Publication note:** this public tree does not ship the vendor binaries
> (`tvi_original.so`, `libtvsysinfo.so`) or device-specific key material
> (`authorized_keys`, host-key fingerprint). Paths in the listings below are
> kept for documentation — recreate the artefacts from your own device.

**Ein Ordner, zwei Abteilungen, kein Suchen mehr.**
**TV:** Hisense HE40E5600FFWTS, FW `V0100.01.00A.N0410`, LAN `192.0.2.94`
**Host:** Linux, Python 3, `arm-linux-gnueabihf-*`; Host-IP im Beispiel `192.0.2.150`
**Stand:** 2026-10-26 — Root + Dropbear-SSH (key-only) + PTY live bestätigt; Boot-Persistenz installiert (Reboot-Test offen). SFTP optional (statischer OpenSSH-sftp-server + gepatchter Dropbear).

---

## Die drei Fragen in 30 Sekunden

### Welches Linux?
**Hisense/MediaTek Embedded Linux**, kein Standard-Distro:
- Linux **3.18.25**, ARMv7 (Cortex-A53, NEON/VFPv4), MediaTek **MT53xx/MT5863**-Klasse (`mt53xx-emmc`, `mt5863_sa_768_linux`)
- **glibc 2.18**, **BusyBox 1.18.5**, SysV-Init (`inittab`/`rcS`/`rc.local`), **kein systemd**
- Kein `/etc/os-release`; Firmware `V0100.01.00A.N0410`
- **squashfs-ro**: `/` (38.8 MB, 100 %), `/3rd` (141 MB, 100 %)
- **ext4-rw**: `/3rd_rw` (1.1 GB, 56 %), `/data` (1.9 GB), `/perm` (3.9 MB); `/spdata` ro
- **Kein overlayfs** → Modding über rw-Partitionen + `mount --bind`

### Gibt es einen Package Manager?
**Nein.** Kein `apt`, `dpkg`, `opkg`, `ipkg`, `rpm`, `apk`, `yum`, `pacman`; keine `/etc/opkg`/`/var/lib/dpkg`.  
**Konsequenz:** statische ARM-Binaries/Shell-Skripte bauen, per `File.download`/SSH/`base64`/`tar` nach `/3rd_rw` bringen. Kein `opkg install`.

### Wo ist das UI und wie läuft es?
TV-UI = Web-UI im **`hisenseUI`-Browser** (root, GLES):

```
/basic/autorun.sh (Zeile 168)
  → /3rd/opera4x/hisenseUI/start-UI.sh
    → ./bin/hisenseUI --hw-gles --jsplugins-dir=/3rd/UI_jsplugins \
         --disable-web-security ... -u /3rd_rw/UI/index.html
```

- **UI:** `/3rd_rw/UI/index.html` (PIXI), UI-Prozess `hisenseUI` (z. B. PID 589), DevTools **9223**
- **Launcher/Apps:** `/3rd_rw/appdata/launcher/` mit `preset.txt` (26 vorinstallierte Tiles), `Appinfo.json` (User-Apps), `deletedPresetApp.txt` (ausgeblendet), `data/Category*.xml`, `PicInfo.xml`, `res/`
- **LauncherService:** `/3rd/launcherservice/bin/LauncherService` (via `startLS.sh` aus `delayrun.sh`)
- **Native Apps / AM:** `/basic/app_man -c /basic/am_config -s /basic/am_start.ini`; `dtv_svc`, `netflix`, `dialserver`, `samba`, `browser_base`, `securetime`, …; Steuerung `:am,<app>,:<verb>=<val>`
- **Web-Browser (nicht das TV-UI):** `hisense_browser` (z. B. PID 1320), `run-Browser.sh`, `--hw-dfb`, `--allow-file-access-from-files`, DevTools **9224**; hier läuft die Recon-Seite.

**UI ≠ Browser:** `hisenseUI` (TV-UI) und `hisense_browser` (Web-Browser) sind getrennte Prozesse mit eigenen Startskripten, Renderern, JS-Plugins und Debug-Ports.

---

## Ordnerstruktur

```
<repo-root>/
├── README.md                         # diese Datei
├── dead-ends.md                      # kurze Liste der Sackgassen
├── SHA256SUMS
├── root/                             # ABTEILUNG 1: Root
│   ├── ROOT-GUIDE.md                 # kompletter Weg (manuell + Skripte)
│   ├── README.md                     # kurzer Index
│   ├── tools/
│   │   ├── server.py                 # Host: Recon + /pub + /cmd + /recon + /dump
│   │   ├── recon.html                # TV-Seite (fileXHR/listDir/HiBrowser-Hook)
│   │   ├── live_cmd.txt              # optionaler Live-Kanal (leer)
│   │   └── pub/                      # ausgelieferte Dateien
│   │       ├── libtvsysinfo.so       # finaler Root-Payload
│   │       ├── dropbear/dropbearkey  # statischer ARM-Dropbear 2022.83
│   │       ├── dropbear-sftp         # Dropbear mit SFTPSERVER_PATH=/3rd_rw/sshd/sftp-server
│   │       ├── sftp-server           # statischer OpenSSH-9.9p1-sftp-server
│   │       ├── authorized_keys       # dein Public Key
│   │       ├── start_sshd.sh         # Dropbear + passwd/PTY-Bindmounts
│   │       ├── root_loop.sh          # Root-Kommandokanal
│   │       ├── hamservice-wrapper.sh # Boot-Hook
│   │       ├── deploy_sshd.sh        # Installation als root
│   │       ├── verify.sh / rollback.sh
│   ├── scripts/
│   │   ├── host/
│   │   │   ├── prepare_usb.sh        # ext4/MBR-Stick + tvi-Symlink
│   │   │   ├── start_http.sh         # Server auf :9000
│   │   │   ├── plant_payload.js      # Payload durch tvi schreiben
│   │   │   ├── upload_to_appdata.js  # Dropbear/Deploy nach appdata
│   │   │   ├── run_root_cmd.js       # root_cmd/root_out
│   │   │   ├── build_payload.sh      # Payload reproduzieren
│   │   │   ├── build_tvi_payload.py  # Builder (deterministisch)
│   │   │   ├── build_dropbear.sh     # Dropbear aus sources/ bauen
│   │   │   ├── build_sftp_server.sh  # statischen sftp-server bauen
│   │   │   ├── patch_dropbear_sftp.py # Dropbear-SFTP-Pfad patchen
│   │   │   └── install_sftp.sh       # SFTP installieren/testen/auf 22 tauschen
│   │   └── tv/
│   │       ├── start_sshd.sh
│   │       ├── root_loop.sh
│   │       ├── hamservice-wrapper.sh
│   │       ├── deploy_sshd.sh
│   │       ├── verify.sh
│   │       ├── rollback.sh
│   │       ├── install_sftp_stage.sh # sftp-server + Test-Dropbear auf 2222
│   │       ├── enable_sftp.sh        # Tausch auf 22 planen
│   │       └── swap_sftp.sh          # Tausch detached ausführen
│   └── artifacts/
│       ├── tvi_original.so           # Original-Lib (33.220 B)
│       └── keys/{authorized_keys,host-key-fingerprint.txt}
├── modding/                          # ABTEILUNG 2: Modding
│   ├── README.md                     # Modding-Index/TL;DR
│   ├── 01-system-linux.md            # Linux/SoC/Userland/PackageManager/Storage
│   ├── 02-boot.md                    # Boot, autorun, developer.sh, Services
│   ├── 03-ui.md                      # hisenseUI vs hisense_browser, UI-Daten, AM
│   ├── 04-modding.md                 # Rezepte: eigene App/UI/Services/Bloat
│   ├── 05-bloat.md                   # 26 Preset-Apps, Service-Matrix, Deaktivieren
│   ├── 06-toolchain-deploy.md        # statisch ARM bauen/deployen, SSH/PTY
│   ├── 07-evidence-unknowns.md       # Belege, Status, bekannte Unknowns
│   └── templates/
│       ├── developer.sh              # früher Root-Boot-Hook
│       ├── custom-app.json           # Appinfo-Tile
│       ├── hide-preset.json          # deletedPresetApp.txt
│       ├── custom-ui.html            # minimale Custom-UI
│       ├── start-UI-custom.sh        # start-UI.sh mit custom.html
│       └── README.md
└── sources/
    ├── dropbear-2022.83.tar.bz2      # Offline-Buildquelle
    └── openssh-9.9p1.tar.gz          # Offline-Buildquelle für sftp-server
```

---

## In 11 Schritten replizieren

```bash
# 1) Host: Stick (DESTRUKTIV)
sudo root/scripts/host/prepare_usb.sh /dev/sdX
# 2) Host: Server
root/scripts/host/start_http.sh
# 3) TV: http://<host-ip>:9000/recon.html öffnen
# 4) TV-Konsole: USB-Dev anpassen, plant_payload.js ausführen
#    -> /3rd_rw/loglevel/lib/libtvsysinfo.so (33500 B, SHA 37b13f…)
# 5) TV rebooten
# 6) Root prüfen: /3rd_rw/root_proof.txt = ROOT_EXEC_TVI
# 7) TV-Konsole: upload_to_appdata.js
# 8) TV-Konsole: run_root_cmd.js (deploy_sshd.sh)
# 9) ssh root@192.0.2.94
#10) Rollback: /bin/sh /3rd_rw/appdata/rollback.sh
#11) SFTP optional: root/scripts/host/install_sftp.sh
#    danach: sftp root@192.0.2.94
```

**Vollständig:** [`root/ROOT-GUIDE.md`](root/ROOT-GUIDE.md)  
**Modding:** [`modding/README.md`](modding/README.md)  
**Sackgassen:** [`dead-ends.md`](dead-ends.md)  
**Integrität:** `sha256sum -c SHA256SUMS`

---

## Was der Root-Weg macht (Kurz)

1. **Browser ist root:** `hisense_browser` UID/GID 0, `CapEff` voll, Single-Process, kein Seccomp.
2. **USB-Schreibprimitive:** dangling Symlink `tvi` auf ext4 → `IsSubDentry`-Bypass → neue Root-Datei.
3. **Loader-Shadow:** `libtvsysinfo.so` ist direktes `NEEDED`; `LD_LIBRARY_PATH`-Index 17 ist `/3rd_rw/loglevel/lib`; dort liegt die Shadow-Lib.
4. **DT_INIT-Payload:** appended Code am Dateiende, RX `p_filesz/memsz` erweitert, `DT_INIT=0x81c4`; unlink self, Proof, fork/exec `root_loop.sh`, Original-Init.
5. **Root-Loop:** `root_cmd.sh` → `root_out.txt`.
6. **SSH:** Dropbear 2022.83 statisch, key-only, `/etc/passwd`-Bind (Root-Home `/3rd_rw/sshd/home`), devpts auf `/dev/shm/pts` → bind `/dev/pts` (PTY), `HamService`-Wrapper für Boot-Persistenz.
7. **SFTP (optional):** Dropbear hat keinen eigenen sftp-server; statischer OpenSSH-9.9p1-sftp-server + Dropbear mit `SFTPSERVER_PATH=/3rd_rw/sshd/sftp-server`. Installation testet Port 2222, dann Tausch auf 22; danach `sftp root@…`.

---

## Sicherheit / Spielregeln

- **Kein Flash, kein `.pkg`, kein Bootloader.** Rootfs/`/3rd` sind squashfs-ro; Änderungen nur in `/3rd_rw`, `/data`, `/perm`, Bind-Mounts.
- **SSH ist key-only root im LAN.** Kein Passwort; privaten Key schützen; nicht ins Internet exponieren.
- **SFTP ist optional und root-equivalent.** Key-only wie SSH; Installation testet zuerst 2222, Backup `/3rd_rw/sshd/dropbear.nosftp`, Rollback im Root-Guide.
- **Der Root-Loop ist root-equivalent.** Wer `root_cmd.sh` schreiben kann (Browser root), kann Root-Befehle ausführen.
- **Backup vor UI-/AM-/Launcher-Eingriffen.** Besonders `/3rd_rw/UI/index.html`, `/3rd_rw/appdata/launcher/*`, `/basic/am_config`/`am_start.ini`.
- **SSH/Root als Rettungsweg behalten.** Kaputte UI = schwarzer Bildschirm; `hisenseUI` per SSH/root-Loop killen/neu starten, Seite aus Backup zurückholen.
- **`developer.sh` ist ein früher Root-Hook** (vor `ms_service`/UI/`app_man`/`delayrun`); Fehler dort können den Boot/UI beeinflussen.
- **`/3rd_rw/patch/opera4x` ist ein full bind mount** über `/3rd/opera4x`; nur mit vollständiger Kopie/Symlink-Baum; für einzelne Dateien lieber Datei-Bind-Mount via `developer.sh`.
- **Keine Secrets im Ordner:** kein Root-Hash, kein privater SSH-Key; nur Public Key + Host-Fingerprint.
- **Nicht alles ist getestet:** Root/SSH/PTY live; die Modding-Rezepte sind aus statischen/live Daten abgeleitet; Status in `modding/07-evidence-unknowns.md`.

---

## Verifikationsstatus (Auszug)

| Punkt | Status |
|---|---|
| Browser root / CapEff voll | **CONFIRMED live** |
| USB-ext4-Symlink-Bypass | **CONFIRMED live** |
| `libtvsysinfo`-Shadow / DT_INIT | **CONFIRMED live** (`ROOT_EXEC_TVI`, Self-Unlink) |
| Root-Loop / Kommandokanal | **CONFIRMED live** (`uid=0`, `root_out.txt`) |
| Dropbear-SSH / Port 22 / Pubkey root | **CONFIRMED live** |
| PTY / interaktive Shell | **CONFIRMED live** (pts/0) |
| SFTP (optional) | statischer sftp-server + gepatchter Dropbear; Installer testet 2222 vor 22; **TV-Test nach Install** |
| HamService-Boot-Persistenz | eingerichtet; Reboot-Test im Root-Guide |
| Modding-Rezepte / Custom UI / Bloat | **UNVERIFIED** (static/live abgeleitet, noch nicht alle ausgeführt) |

**Host-Key (SSH):** `<host-key-fingerprint>`  
**Dein Key:** `<your-public-key>` (Fingerprint `<host-key-fingerprint>`)

---

## Provenienz

Der frühere Run-Ordner `the earlier run archive (not part of this repository)` (im alten Projekt) bleibt als **Evidence/History** erhalten. Für die Replikation und das Modding brauchst du ihn nicht: dieser Ordner enthält den finalen Stand, die Binaries, die Skripte und die Doku. Die alten Experimente/Dead Ends sind in `dead-ends.md` kurz zusammengefasst.
