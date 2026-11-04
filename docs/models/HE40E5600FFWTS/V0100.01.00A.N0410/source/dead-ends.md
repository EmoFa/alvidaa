# Dead Ends — short, so nobody repeats them

These paths were investigated and **rejected**. They are **not** needed for the final root/SSH/modding path. Details/history: the earlier run archive (not part of this repository; evidence).

## Factory / AM / keys
- **`Builtin Video` (Factory):** rebuilds the path from the `StoreModeDemo[Backup]` prefix; suffix injection is ignored → "can not find built-in video".
- **`Write Keys` (Factory):** fixed filenames + file API, no `system()`/`popen()` with attacker input.
- **AM `startApp`:** `:am,<app>,:<verb>=<val>` for start/stop/pause/resume/URL/backgm/foregm/shutdown/suspend/wakeup; **no** `args`/`exec`/`run`. Shell injection attempts (`startApp("id>…")`, `sh -c`) were negative.
- **FAT32 USB/factory injection:** the `factory_lite` USB callback/copy path could not be triggered; no root exec.
- **`checker.sh` / `file_upgrading` / `.pkg` / `bspatch`:** not used as a root trigger; no flash/OTA path.

## V8 / FileReader
- The engine is **Chromium 59.0.3071.115 / V8 203.0.113.38** (not 63/6.3, not 43/4.3 — those are UA presets).
- No public ARM32 exploit for this combination; a custom one would be needed. **Not needed**, because the loader shadow path yields root cleanly.
- `navigator.requestMediaKeySystemAccess` is **not available** in this build → the Widevine/EME CDM trigger as a root path is dead.

## `liblogLevel` shadow
- `/3rd_rw/loglevel/lib` is index 17 (first writable LD position), but **`liblogLevel.so` exists there** → it cannot be overwritten via the symlink trick (target exists → the `realpath` check fires).
- `libIQQILib` (RPATH `/3rd/iqqi/lib`), `libota`/`libhisensefileutils` (later LD positions) were rejected as shadow targets; only **`libtvsysinfo.so`** is a direct `NEEDED` and free at index 17.
- `liblogLevel`/`ota`/`hisensefileutils` payload variants and the `/3rd_rw/ms-screen/lib` variant (`lib` symlink) are **not** in the active loader path; not needed.

## Write/JS API
- `File.write` with binary data → `EINVAL` (22); text works, binary does not. Binary write via **`File.download`** (curl) through the symlink works.
- `HiBrowser.loadLibrary`/`jsplugins` tricks: the library is built from `${OPERA_DIR}/jsplugins/<name>`, but is not loaded into the process; dead.
- Whitelist `IsSubDentry`: no trailing slash, `realpath` + prefix; only the **dangling symlink** on the ext4 USB is the bypass.

## USB
- **Whole-disk ext4 (superfloppy, no `sdX1`)** is not mounted by the TV; MBR + partition required.
- **FAT32** cannot represent symlinks → no symlink bypass; ext4 required.
- The `pwn` symlink was only the proof of the bypass; the final path uses **`tvi`**.

## SSH
- Dropbear option **`-s`** does not exist in this build ("Invalid option -s"); password auth is **compile-time** off (`DROPBEAR_SVR_PASSWORD_AUTH=0`). Start script without `-s`.
- **PTY:** `/dev` is a static ro squashfs (no devtmpfs); `mount -t devpts` directly on `/dev/pts` fails. Only the workaround **devpts on `/dev/shm/pts` + bind `/dev/pts`** works; `/dev/ptmx` (5,2) stays static.
- The `/etc/passwd` bind mount is needed because the root home `/basic` is ro; `/etc/shadow` is not touched (key-only).
- **SFTP/SCP:** Dropbear alone has no sftp-server — that was the reason for `sh: /usr/libexec/sftp-server: No such file`. **No longer a dead end:** the final folder ships a static OpenSSH-9.9p1-sftp-server + Dropbear with `SFTPSERVER_PATH=/3rd_rw/sshd/sftp-server`; installation `root/scripts/host/install_sftp.sh` (test on 2222, then 22). After that `sftp` and modern `scp` work.

## UI experiments
- `/3rd_rw/launcher` and `/3rd_rw/VIDAAU2Launcher` are **old/alternative skins**; the active UI is `/3rd_rw/UI/index.html` (`hisenseUI`). The old launcher HTML/JS is not the active entry point.
- The `preset`/`deleted` probe URLs (data:, javascript:, 127.0.0.1;cd…) are our old experiments; not included in the final folder. The TV's `deletedPresetApp.txt` was emptied during cleanup (`[]`, as of 2026-10-26).
- `ms_service`/`swrc`/`runlog`/`Seriallog`/`HamService` are not needed for the root path; only the `HamService` wrapper is used as a boot hook for SSH/root loop.

## What applies instead
**USB ext4 + `tvi` → `libtvsysinfo` shadow → DT_INIT root → root loop → Dropbear/PTY → HamService wrapper.**  
That is the final, live-confirmed path. Everything else is optional modding (see `modding/`).
