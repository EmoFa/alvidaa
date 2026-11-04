# 07 — Evidence, Verification, Unknowns

**Purpose:** verifiability and honest status. No claim without a path/excerpt; everything that has not been tested live is marked `UNVERIFIED`.

---

## 1. What is confirmed live

| Fact | Evidence | Status |
|---|---|---|
| Browser root | `/proc/self/status` → `Uid/Gid 0 0 0 0`, `CapEff=0000003fffffffff`, single process | **CONFIRMED live** |
| USB ext4 symlink bypass | `pwn`/`tvi` dangling; `File.write`/`File.download` creates a root file; `SYMTEST` | **CONFIRMED live** |
| `libtvsysinfo` shadow | 33,500 B, SHA `37b13f…`; boot loads it; `ROOT_EXEC_TVI`; self-unlink | **CONFIRMED live** |
| Root loop | PID/log; `uid=0`; `root_cmd.sh` → `root_out.txt` | **CONFIRMED live** |
| Dropbear SSH | `dropbear` static ARM; `0.0.0.0:22`; `Pubkey auth succeeded for 'root'` | **CONFIRMED live** |
| PTY | session `pts/0`; `busybox script` → `uid=0(root)` | **CONFIRMED live** |
| `/etc/passwd` bind | root home `/3rd_rw/sshd/home:/bin/sh`; authorized_keys 600 | **CONFIRMED live** |
| HamService wrapper | `/3rd_rw/hamservice/HamService` starts loop + SSH, execs real HamService | **CONFIRMED installed**; reboot test in the root guide |
| Payload repro | `build_tvi_payload.py` → exactly `37b13f…` | **CONFIRMED** (host) |

---

## 2. What is derived from static/live data (not necessarily tested)

- The **modding recipes** (app tile, custom UI, launcher data, AM/service bloat, `developer.sh` bind mounts, `patch/opera4x`) are derived from the files/structures read live.
- **Custom UI** (replacing `UI/index.html`) is **not** tested live; the risk (black screen) is documented.
- **Bloat deactivations** (`ms_service`, `swrc`, `runlog`, `Seriallog`, `securetime`, `netflix`, `browser_base`, `app_man`, `dtv_svc`) are **not** all tested; matrix/rollback in `05`.
- **`Hisense_StartApp`/`TVAPI`/`guijs` signatures** in the UI are not fully evidenced; check in the UI DevTools (9223).
- **`app_man`/`:am` semantics** per app (`start`/`URL`/`backgm`/`coexist`) is derived from strings/config; test individual actions.
- **`VIDAAU2Launcher`** is present as an alternative skin; whether it is active, `UNVERIFIED`.
- **`preset.txt`/`Category*.xml` regeneration** by `LauncherService`/UI is not fully clarified; the `deletedPresetApp.txt` is the robust hide lever.
- **U-Boot env** (bad CRC/default NFS) is not the real boot configuration; `/proc/cmdline` is authoritative.
- **Secure Boot/signature verification**, **DRM/PlayReady/Widevine**, **OTA/`checker.sh`** are not part of the root path and not fully investigated.

---

## 3. Evidence files / paths

### 3.1 In this folder

- `root/tools/pub/libtvsysinfo.so` — final payload (33500 B, SHA `37b13f…`)
- `root/artifacts/tvi_original.so` — original lib (33220 B, SHA `36ddee…`)
- `root/tools/pub/dropbear`, `dropbearkey` — static binaries
- `root/artifacts/keys/{authorized_keys,host-key-fingerprint.txt}`
- `root/tools/{server.py,recon.html,icon.png,live_cmd.txt}`
- `root/scripts/{host,tv}/*` — build/deploy/verify/rollback
- `sources/dropbear-2022.83.tar.bz2`
- `SHA256SUMS`
- `dead-ends.md`

### 3.2 On the TV (read live)

- `/proc/version`, `/proc/cmdline`, `/proc/cpuinfo`, `/proc/filesystems`, `/proc/mounts`, `/proc/partitions`
- `df -h`, `ls -l /lib`, `ls -l /bin`, `ls -l /etc`
- `/etc/inittab`, `/etc/init.d/rcS`, `/etc/rc.d/rc.local`
- `/basic/autorun.sh` (lines 90/162/168/177/190), `/basic/delayrun.sh`
- `/basic/am_config`, `/basic/am_start.ini`
- `/3rd/launcherservice/startLS.sh`, `/3rd/hamservice/startHam.sh`, `/3rd/opera4x/browser/run-Browser.sh`, `/3rd/opera4x/hisenseUI/start-UI.sh`
- `/3rd_rw/UI/index.html`, `UI/pub/HisProductConfig.js`, `UI/lib/launcherDataInterface.js`
- `/3rd_rw/appdata/launcher/{preset.txt,Appinfo.json,deletedPresetApp.txt,data/*,res/*,cache/*}`
- `/3rd_rw/user_db.db` (settings), `/3rd_rw/opera4x/opera_home_browser/{opera.json,browser.db}`
- `/3rd_rw/sshd/…`, `/3rd_rw/appdata/root_loop.sh`, `root_loop.pid`, `root_out.txt`
- `ps`, `/proc/<pid>/cmdline`, `/proc/<pid>/status`

### 3.3 Previous run (provenance only)

The earlier run archive (not part of this repository; in the old project) contains the raw captures/history. It is **not** needed for replication; the final artifacts/scripts/docs are in this folder.

---

## 4. Verification status (modding)

| Area | Status |
|---|---|
| System/Linux/package manager/storage | **CONFIRMED** (live/static) |
| Boot chain/scripts/lines/services | **CONFIRMED** (live/static) |
| UI start/processes/paths/app data/AM | **CONFIRMED** (live/static) |
| 26 preset apps / `Appinfo` / `deleted` | **CONFIRMED** (read live) |
| App tile (route A) | **UNVERIFIED** (not tested live; mechanics from `Appinfo`/launcher) |
| Custom UI (route B) | **UNVERIFIED** (not tested live; risk documented) |
| Launcher data/skin (route C) | **UNVERIFIED** (not tested live) |
| Own service (route D) | **root/SSH part live**; service examples `UNVERIFIED` |
| Bind mount/overlay (route E) | **mechanics live** (`/etc/passwd`, `/dev/pts`); AM/UI bind mounts `UNVERIFIED` |
| Static tools/deploy (route F) | **Dropbear/SSH/PTY live**; other tools `UNVERIFIED` |
| SFTP (optional) | static OpenSSH-sftp-server + patched Dropbear built; installer tests 2222 before 22; **TV test after install** |
| Bloat deactivations | **UNVERIFIED** (matrix/rollback in `05`) |

---

## 5. Known unknowns

- Exact SoC designation (MT5863 vs. MT53xx family), core count, Secure Boot/signatures.
- Full kernel config, `dm-3` construction, `spdata`/`perm`/`facset`/`hiscfg`/`eeprom`/`channel`/`pq`/`adsp`/`logo`.
- Real U-Boot flow/env (bad CRC), A/B slot selection, recovery.
- `checker.sh`/`ota_upgrade_strategy.sh`/`file_upgrading`/`bspatch`/OTA.
- `dtv_svc`/`app_man`/`:am` internals, `coexist_set`/`backgm`/`keymap`.
- `LauncherService` data source/update (store/Foxxum/FCGI), `preset`/`Category` regeneration.
- Active UI template/skin selection; `VIDAAU2Launcher` active? `UNVERIFIED`.
- `Hisense_StartApp`/`TVAPI`/`guijs` signatures; `app_man` start meaning.
- Bloat consequences: `ms_service`/`swrc`/`runlog`/`Seriallog`/`HamService`/`securetime`/`browser_base`/`app_man`/`dtv_svc`.
- DRM/PlayReady/Widevine/Netflix/Cobalt/Amazon; `securetime`.
- SFTP is retrofitted via the static OpenSSH-sftp-server + patched Dropbear; the installer tests port 2222 and only then 22. The TV test result is in `/3rd_rw/sshd/dropbear2222.log` and `swap.log`; `ssh`+base64/tar remains the fallback.
- Whether a custom `UI/index.html` needs the `TVAPI`/`model` globals or whether `Hisense_*`/`guijs` can be used directly.
- Whether `preset`/`Category`/`serviceUpdate` is overwritten on store/network updates.

---

## 6. Dead ends (short version)

See `../dead-ends.md`. The most important:

- Factory `Builtin Video`/`Write Keys`, AM `startApp` (no exec/args).
- V8 5.9/Chromium 59 without a public ARM32 exploit; not needed.
- `liblogLevel` shadow (index 17 occupied), `libIQQILib`/`libota`/`hisensefileutils` variants, `ms-screen` `lib` symlink.
- `File.write` binary (`EINVAL`), `loadLibrary` tricks.
- FAT32/Superfloppy USB, missing symlink capability.
- Dropbear `-s` (does not exist), PTY directly on `/dev/pts` (ro). **SFTP is no longer a dead end**: static OpenSSH-sftp-server + patched Dropbear (`install_sftp.sh`).
- UI legacy skins (`launcher`/`VIDAAU2Launcher`) as an active entry point; the active UI is `/3rd_rw/UI`.

---

## 7. No secrets

- **No root hash** in this folder.
- **No private SSH key**; only the public key (`authorized_keys`) + host key fingerprint.
- **No captures/unfiltered dumps** in this folder; the raw evidence is (if needed) in the old run folder.
- **No credentials** for third-party services; the preset URLs are target data only, not an invitation to contact them.
