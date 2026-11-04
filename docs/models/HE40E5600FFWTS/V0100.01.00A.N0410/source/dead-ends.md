# Dead Ends — kurz, damit sie niemand wiederholt

Diese Wege wurden untersucht und **verworfen**. Sie sind **nicht** nötig für den finalen Root-/SSH-/Modding-Weg. Details/History: alter Run-Ordner `the earlier run archive (not part of this repository)` (Evidence).

## Factory / AM / Keys
- **`Builtin Video` (Factory):** baut den Pfad aus dem `StoreModeDemo[Backup]`-Präfix neu; Suffix-Injection wird ignoriert → „can not find built-in video“.
- **`Write Keys` (Factory):** feste Dateinamen + File-API, kein `system()`/`popen()` mit Angreifer-Input.
- **AM `startApp`:** `:am,<app>,:<verb>=<val>` für start/stop/pause/resume/URL/backgm/foregm/shutdown/suspend/wakeup; **kein** `args`/`exec`/`run`. Shell-Injection-Versuche (`startApp("id>…")`, `sh -c`) negativ.
- **FAT32-USB-/Factory-Injection:** `factory_lite`-USB-Callback/Copy-Pfad nicht auslösbar; kein Root-Exec.
- **`checker.sh` / `file_upgrading` / `.pkg` / `bspatch`:** nicht als Root-Trigger genutzt; kein Flash/OTA-Weg.

## V8 / FileReader
- Engine ist **Chromium 59.0.3071.115 / V8 203.0.113.38** (nicht 63/6.3, nicht 43/4.3 — das sind UA-Presets).
- Kein öffentlicher ARM32-Exploit für diese Kombination; Eigenbau wäre nötig. **Nicht benötigt**, weil der Loader-Shadow-Weg sauber root liefert.
- `navigator.requestMediaKeySystemAccess` ist in diesem Build **nicht verfügbar** → Widevine-/EME-CDM-Trigger als Root-Pfad tot.

## `liblogLevel`-Shadow
- `/3rd_rw/loglevel/lib` ist Index 17 (erste schreibbare LD-Position), aber **`liblogLevel.so` existiert dort** → kann per Symlink-Trick nicht überschrieben werden (Ziel existiert → `realpath`-Prüfung schlägt zu).
- `libIQQILib` (RPATH `/3rd/iqqi/lib`), `libota`/`libhisensefileutils` (spätere LD-Positionen) als Shadow-Ziele verworfen; nur **`libtvsysinfo.so`** ist ein direktes `NEEDED` und an Index 17 frei.
- `liblogLevel`-/`ota`-/`hisensefileutils`-Payload-Varianten und die `/3rd_rw/ms-screen/lib`-Variante (`lib`-Symlink) sind **nicht** im aktiven Loader-Pfad; nicht nötig.

## Schreib-/JS-API
- `File.write` mit Binärdaten → `EINVAL` (22); Text geht, Binary nicht. Binary-Write über **`File.download`** (curl) durch den Symlink funktioniert.
- `HiBrowser.loadLibrary`/`jsplugins`-Tricks: Lib wird aus `${OPERA_DIR}/jsplugins/<name>` gebaut, aber nicht in den Prozess geladen; tot.
- Whitelist `IsSubDentry`: kein Trailing-Slash, `realpath` + Präfix; nur der **dangling Symlink** auf ext4-USB ist der Bypass.

## USB
- **Whole-Disk-ext4 (Superfloppy, kein `sdX1`)** wird vom TV nicht gemountet; MBR + Partition nötig.
- **FAT32** kann keine Symlinks → kein Symlink-Bypass; ext4 nötig.
- Der `pwn`-Symlink war nur der Proof des Bypasses; der finale Weg nutzt **`tvi`**.

## SSH
- Dropbear-Option **`-s`** existiert in diesem Build nicht („Invalid option -s“); Passwort-Auth ist **compile-time** aus (`DROPBEAR_SVR_PASSWORD_AUTH=0`). Startskript ohne `-s`.
- **PTY:** `/dev` ist statisches ro squashfs (kein devtmpfs); `mount -t devpts` direkt auf `/dev/pts` scheitert. Nur der Umweg **devpts auf `/dev/shm/pts` + bind `/dev/pts`** funktioniert; `/dev/ptmx` (5,2) bleibt statisch.
- `/etc/passwd`-Bindmount ist nötig, weil Root-Home `/basic` ro ist; `/etc/shadow` wird nicht angefasst (key-only).
- **SFTP/SCP:** Dropbear allein hat keinen sftp-server — das war der Grund für `sh: /usr/libexec/sftp-server: No such file`. **Kein Dead End mehr:** der finale Ordner liefert einen statischen OpenSSH-9.9p1-sftp-server + Dropbear mit `SFTPSERVER_PATH=/3rd_rw/sshd/sftp-server`; Installation `root/scripts/host/install_sftp.sh` (Test auf 2222, dann 22). Danach funktionieren `sftp` und modernes `scp`.

## UI-Experimente
- `/3rd_rw/launcher` und `/3rd_rw/VIDAAU2Launcher` sind **Alt-/Alternativ-Skins**; die aktive UI ist `/3rd_rw/UI/index.html` (`hisenseUI`). Die alten Launcher-HTML/JS sind nicht der aktive Einstieg.
- Die `preset`-/`deleted`-Probe-URLs (data:, javascript:, 127.0.0.1;cd…) sind unsere alten Experimente; im finalen Ordner nicht enthalten. Der TV-`deletedPresetApp.txt` wurde beim Cleanup geleert (`[]`, Stand 2026-10-26).
- `ms_service`/`swrc`/`runlog`/`Seriallog`/`HamService` sind für den Root-Weg nicht nötig; nur der `HamService`-Wrapper wird als Boot-Hook für SSH/Root-Loop genutzt.

## Was stattdessen gilt
**USB-ext4 + `tvi` → `libtvsysinfo`-Shadow → DT_INIT-Root → Root-Loop → Dropbear/PTY → HamService-Wrapper.**  
Das ist der finale, live bestätigte Weg. Alles andere ist optionales Modding (siehe `modding/`).
