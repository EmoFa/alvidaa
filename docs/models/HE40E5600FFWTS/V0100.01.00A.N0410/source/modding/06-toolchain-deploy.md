# 06 — Toolchain & Deploy (kein Package Manager)

**Status:** System-/Toolchain-Constraints **CONFIRMED**; Dropbear-Build + Deploy live bestätigt; die Skripte in `../root/` sind der finale Weg.

---

## 1. Kein Package Manager

Live-Check (root):

```sh
for c in apt apt-get dpkg rpm opkg ipkg apk yum pacman; do command -v $c; done   # leer
ls -la /etc/opkg /etc/opkg.conf /var/lib/opkg /var/lib/dpkg /usr/lib/opkg        # fehlt
/bin/busybox --list | grep -E '^(opkg|dpkg|rpm|apk|ipkg)$'                      # leer
cat /etc/os-release                                                             # fehlt
```

**Es gibt keinen Package Manager.** Kein `opkg install`, kein `apt`, kein Paket-Repo.  
**Deploy = Dateien kopieren + ausführbar machen + starten.** Keine „Installation“ im Distro-Sinn.

---

## 2. Bauen für den TV

| Constraint | Wert |
|---|---|
| Architektur | ARMv7, EABI5, hard-float, VFPv4/NEON |
| Kernel | 3.18.25; kein overlayfs, kein devtmpfs, devpts ja |
| TV-libc | glibc 2.18 (`/lib/libc-2.18.so`, `ld-linux.so.3`) |
| Host-Cross | `arm-linux-gnueabihf-gcc`, `-as`, `-ld`, `-objcopy` |
| Static | **empfohlen**; `-static`; der mitgelieferte Dropbear ist statisch und läuft |
| Dynamic | nur mit TV-glibc 2.18/Sysroot; sonst `GLIBC_2.xx not found` |
| Package Manager | keiner |

### 2.1 Einfaches statisches Tool

```bash
cat > hello.c <<'EOF'
#include <stdio.h>
int main(){ printf("hello tv\n"); return 0; }
EOF
arm-linux-gnueabihf-gcc -static -Os -o hello hello.c
file hello
# ELF 32-bit LSB executable, ARM, EABI5, statically linked
```

Deploy:

```bash
# per SSH (funktioniert immer, auch ohne SFTP)
base64 -w0 hello | ssh root@192.0.2.94 'base64 -d > /3rd_rw/bin/hello && chmod 755 /3rd_rw/bin/hello'
# oder per File.download (HTTP -> /3rd_rw/appdata) + root_loop cp/chmod
# oder nach optionalem SFTP-Install direkt: scp hello root@TV:/3rd_rw/bin/
```

**Hinweis:** Dropbear allein hat keinen sftp-server. Der finale Ordner enthält einen statischen OpenSSH-9.9p1-sftp-server + gepatchten Dropbear; nach `../root/scripts/host/install_sftp.sh` funktionieren `sftp` und modernes `scp` (SFTP). Vorher: `ssh` + `base64`/`cat`/`tar` oder `File.download`. `tar` ist auf dem TV (BusyBox) vorhanden.

### 2.2 Dynamisches Tool (nur wenn nötig)

- Gegen die **TV-glibc 2.18** linken (Sysroot/Headers aus dem TV oder ein passendes älteres Sysroot); sonst scheitert der Loader.
- Der mitgelieferte Dropbear ist **statisch** (glibc 2.39) und läuft auf dem 3.18-Kernel; das ist der pragmatische Weg.
- `LD_LIBRARY_PATH`/`RPATH` beachten; die TV-Libs liegen in `/lib`, `/basic/lib`, `/3rd/lib`, `/3rd/opera4xLib`, `/3rd_rw/...`.

---

## 3. Dropbear (SSH) — Build + Deploy

Die finalen Binaries liegen in `../root/tools/pub/`:

```
dropbear       882204 B  SHA256 976ec57e401765d5fc9c0a201d19c997c004dcf91a8d4bdb039bbb8419071eae
dropbear-sftp  882204 B  SHA256 a21b0d3e53dd1d124105350319df45a2b44e7cef70dd29b418644b11fdcfed57
dropbearkey    755452 B  SHA256 3fbfa60891b3a9f3e971a24071ed4d14c93ee3e773dd6f4969646cc811b0dbbf
sftp-server    635680 B  SHA256 d0f7700e84e582aef3948c29e4317fb0119e13393374a7455922ffa8d01202f3
```

### 3.1 Repro-Build

```bash
cd <repo-root>
root/scripts/host/build_dropbear.sh
```

Das Skript nutzt `sources/dropbear-2022.83.tar.bz2` (SHA unten), configured mit:

```
--host=arm-linux-gnueabihf
--disable-zlib --disable-pam --disable-shadow
--disable-lastlog --disable-utmp --disable-wtmp
--disable-utmpx --disable-wtmpx
--disable-pututline --disable-pututxline
CC=arm-linux-gnueabihf-gcc CFLAGS="-Os -static" LDFLAGS="-static"
```

und `localoptions.h`:

```c
#define DROPBEAR_SVR_PASSWORD_AUTH 0
#define DROPBEAR_SVR_PUBKEY_AUTH 1
#define DROPBEAR_CLIENT 0
```

- **Key-only:** Passwort-Auth ist compile-time aus; kein `-s`-Flag nötig (dieser Build kennt `-s` nicht).
- **`--disable-shadow`:** kein `/etc/shadow`-Zugriff; Pubkey-Auth.
- **Static:** keine TV-Lib-Abhängigkeit.
- **`dropbearkey`:** Host-Key erzeugen (`-t ed25519 -f /3rd_rw/sshd/host_key`).
- **`dropbear-sftp`:** `build_dropbear.sh` ruft am Ende `patch_dropbear_sftp.py`; das patcht `SFTPSERVER_PATH` auf `/3rd_rw/sshd/sftp-server` (gleiche String-Länge, keine ELF-Offsets). Der statische `sftp-server` kommt aus `build_sftp_server.sh`.

### 3.2 Deploy auf dem TV

1. `../root/scripts/host/upload_to_appdata.js` (TV-Konsole): lädt `dropbear`, `dropbear-sftp`, `dropbearkey`, `sftp-server`, `authorized_keys`, `start_sshd.sh`, `root_loop.sh`, `hamservice-wrapper.sh`, `deploy_sshd.sh`, `verify.sh`, `rollback.sh` nach `/3rd_rw/appdata`.
2. `../root/scripts/host/run_root_cmd.js` mit `/bin/sh /3rd_rw/appdata/deploy_sshd.sh`.
3. `deploy_sshd.sh`:
   - kopiert die Binaries nach `/3rd_rw/sshd` (nutzt `dropbear-sftp` und installiert `sftp-server`, falls vorhanden);
   - erzeugt Host-Key (Ed25519);
   - kopiert `/etc/passwd` → `/3rd_rw/sshd/etc_passwd` mit Root-Home `/3rd_rw/sshd/home` und **bindet** sie über `/etc/passwd`;
   - mountet devpts auf `/dev/shm/pts` und bindet es über `/dev/pts`;
   - setzt `authorized_keys` (600), `.ssh`/Home 700;
   - startet Dropbear auf `0.0.0.0:22`, key-only;
   - installiert den `HamService`-Wrapper;
   - prüft Prozesse/Port/Log/Host-Key.

### 3.3 PTY-Workaround

`/dev` ist Teil des **ro Squashfs** (kein devtmpfs); `/dev/pts` enthält statische Nodes 136,0–4; `/dev/ptmx` ist c 5,2. `mount -t devpts` direkt auf `/dev/pts` scheitert (ro Target).

```sh
mkdir -p /dev/shm/pts
mount -t devpts -o mode=620,ptmxmode=666,gid=5 devpts /dev/shm/pts
mount --bind /dev/shm/pts /dev/pts
```

- `/dev/ptmx` bleibt der statische Node; `openpty` funktioniert damit.
- `start_sshd.sh` macht das bei jedem Start; der `HamService`-Wrapper ruft es beim Boot.
- Fallback ohne PTY: `ssh -T root@192.0.2.94 'id'`.

### 3.4 Root-Home / authorized_keys

- Root-Home `/basic` ist **ro**; Dropbear braucht `~/.ssh/authorized_keys`.
- Lösung: `/etc/passwd`-Kopie mit `root:x:0:0:root:/3rd_rw/sshd/home:/bin/sh` und **Bind-Mount** über `/etc/passwd`; die ro Originaldatei bleibt unverändert.
- `authorized_keys`: dein Public Key (600, root); `.ssh`/Home 700.
- **Kein `/etc/shadow`-Eingriff**, kein Passwort.

### 3.5 Host-Key / Verbindung

```
Host-Key: <host-key-fingerprint>
Login:    ssh root@192.0.2.94
```

Beim ersten Mal Fingerprint bestätigen. Der Host-Key bleibt in `/3rd_rw/sshd/host_key` (rw, reboot-fest).

### 3.6 SFTP (optional, key-only)

Dropbear hat keinen eigenen sftp-server; der Server exec't den compile-time
`SFTPSERVER_PATH` (Default `/usr/libexec/sftp-server`). Der ro Rootfs erlaubt
dort keine Datei. Der finale Ordner liefert deshalb:

- `../root/tools/pub/sftp-server` — **statischer** OpenSSH-9.9p1-sftp-server
  (ARM, 635.680 B; kein glibc-2.18-Problem)
- `../root/tools/pub/dropbear-sftp` — Dropbear mit
  `SFTPSERVER_PATH=/3rd_rw/sshd/sftp-server`
- `../root/sources/openssh-9.9p1.tar.gz` + `build_sftp_server.sh` — Repro-Build
- `../root/scripts/host/install_sftp.sh` — Installation/Test/Tausch
- `../root/scripts/tv/{install_sftp_stage.sh,enable_sftp.sh,swap_sftp.sh}`

**Build:**

```bash
cd <repo-root>
root/scripts/host/build_sftp_server.sh     # OpenSSH sftp-server, static ARM
root/scripts/host/build_dropbear.sh        # dropbear + dropbear-sftp
```

**Install (einfachster Weg, vom Host mit deinem SSH-Key):**

```bash
cd <repo-root>
root/scripts/host/install_sftp.sh
# optional: TV=root@192.0.2.94 SSH_KEY=~/.ssh/id_ed25519 ...
```

Ablauf:

1. lädt `sftp-server` + `dropbear-sftp` per `ssh` (nicht scp!) nach
   `/3rd_rw/appdata`;
2. startet einen **Test-Dropbear auf Port 2222**; Port 22 bleibt unangetastet;
3. testet `sftp -P 2222` (echte SFTP-Session);
4. nur bei Erfolg: Backup `dropbear.nosftp`, Tausch auf Port 22, Neustart;
5. testet `sftp` auf Port 22.

**Danach:**

```bash
sftp root@192.0.2.94
# pwd, ls /3rd_rw/UI, put lokale-datei /3rd_rw/UI/, get /3rd_rw/UI/index.html, bye
```

Modernes `scp` (OpenSSH 9+) nutzt ebenfalls SFTP und funktioniert dann:

```bash
scp /local/file root@192.0.2.94:/3rd_rw/UI/
```

**Rollback:**

```bash
ssh root@192.0.2.94 \
  'cp -f /3rd_rw/sshd/dropbear.nosftp /3rd_rw/sshd/dropbear; \
   kill $(cat /3rd_rw/sshd/dropbear.pid) 2>/dev/null; \
   /bin/sh /3rd_rw/sshd/start_sshd.sh'
```

**Sicherheit:** SFTP läuft als root, key-only, im LAN; derselbe Zugang wie SSH.
Nicht ins Internet exponieren. Der sftp-server ist statisch und hat keine
TV-glibc-Abhängigkeit.

---

## 4. Deploy-Wege (ohne Package Manager)

| Weg | Wann | Beispiel |
|---|---|---|
| **`File.download`** (Browser root) | HTTP-Datei → `/3rd_rw/appdata` | `HiBrowser.File.download("http://<host>:9000/pub/x","x",1)` |
| **`File.write`** (Browser root) | Text (Skripte/JSON) → appdata | `HiBrowser.File.write("root_cmd.sh","id\n",1)` |
| **Root-Loop** | Kommandos/Deploy als root | `root_cmd.sh` → `root_out.txt` |
| **SSH + base64** | Binärdateien nach `/3rd_rw` | `base64 -w0 x \| ssh root@TV 'base64 -d > /3rd_rw/bin/x'` |
| **SSH + tar** | mehrere Dateien | `tar czf - dir \| ssh root@TV 'tar xzf - -C /3rd_rw'` |
| **USB** | Dateien auf ext4-Stick | Symlink/Datei; der TV mountet `/mnt/usb/<dev>` |
| **`scp`/`sftp`** | **nach optionalem SFTP-Install** | `../root/scripts/host/install_sftp.sh`; dann `sftp root@TV` / `scp datei root@TV:/3rd_rw/...` |

- **`File.download`** schreibt Binärdateien byte-exakt; Zielpfad muss in der Whitelist (`/3rd_rw/appdata`, `/dev/shm/shm_tmp`, `/3rd/launcher/data`) oder über den USB-Symlink-Bypass erreichbar sein.
- **`File.write`** schreibt Text; Binärdaten → `EINVAL`; für Binär `File.download`.
- **SSH** ist key-only; `root`; `/3rd_rw`/`/data`/`/perm` rw.

---

## 5. Checks / Verifikation

### 5.1 Host

```bash
cd <repo-root>
sha256sum -c SHA256SUMS
root/scripts/host/build_payload.sh          # reproduziert 37b13f…
file root/tools/pub/dropbear                # statisch ARM
```

### 5.2 TV

```sh
/bin/sh /3rd_rw/appdata/verify.sh
# oder:
cat /3rd_rw/root_proof.txt
ps | grep -E 'dropbear|root_loop'
cat /proc/net/tcp | grep :0016
grep '^root:' /etc/passwd
ls -l /3rd_rw/sshd/home/.ssh/authorized_keys
```

### 5.3 SSH

```bash
ssh root@192.0.2.94 'id; cat /proc/self/status | grep -E "^(Uid|Gid|CapEff):"'
ssh -T root@192.0.2.94 'uname -a' 2>/dev/null || true
```

- `uid=0(root)`; `CapEff=0000003fffffffff`.
- PTY: interaktive Shell; `ssh -T` als Fallback.

### 5.4 SFTP (nach Install)

```bash
printf 'pwd\nls /3rd_rw/UI\nbye\n' | sftp root@192.0.2.94
# auf dem TV:
grep -a 'sftp-server' /3rd_rw/sshd/dropbear
# -> /3rd_rw/sshd/sftp-server
```

- Wenn `sh: /usr/libexec/sftp-server: No such file` erscheint, ist noch der
  ungepatchte Dropbear aktiv: `root/scripts/host/install_sftp.sh`.
- Test-Dropbear/Logs: `/3rd_rw/sshd/dropbear2222.log`, `swap.log`,
  `dropbear.log`; Backup `/3rd_rw/sshd/dropbear.nosftp`.

---

## 6. Grenzen / Unknowns

- **Statisch** ist der sichere Weg; dynamische Binaries brauchen die TV-glibc 2.18.
- **Kein Package Manager** → kein automatisches Dependency-/Update-Handling.
- **`/dev` ro/kein devtmpfs** → PTY-Workaround nötig; andere Device-Nodes statisch.
- **Kein overlayfs** → Bind-Mounts; ro-Dateien per `developer.sh` ersetzen.
- **SFTP** ist optional: Dropbear allein hat keinen sftp-server; der statische OpenSSH-sftp-server + gepatchter Dropbear werden per `install_sftp.sh` installiert. Vorher `ssh`+`base64`/`tar`/`File.download`.
- **`/3rd`/Rootfs 100 % voll**; neue Daten nach `/3rd_rw`/`/data`; kein Flash.
- **UI-/AM-Interna** (`Hisense_*`, `guijs`/`TVAPI`, `app_man`, `LauncherService`) sind nicht vollständig dokumentiert; im DevTools/auf dem TV testen.
- **DRM/`securetime`**, Netflix/Cobalt/Amazon, OTA/`checker.sh` sind nicht Teil des Root-/Deploy-Wegs; Deaktivierung testen.
- **Keine Secrets**: kein Root-Hash, kein privater Key in diesem Ordner.
