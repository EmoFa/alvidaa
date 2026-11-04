# alvidaa findings — who runs what — the privilege map (recon §10.4, 10.6–10.8)

> Split from the original FINDINGS.md lab notebook. Canonical record; the blog and STORY.md draw from these.

### 10.4 Who runs what (privilege map)

- **Verified boot is active**: rootfs is dm-verity squashfs (ro), cmdline carries
  `androidboot.vbmeta.device_state=locked`, `verifiedbootstate=green`, and ro
  partitions are mounted via MTK `mtk_mount` with a vbmeta reference partition.
  System partitions are off-limits — the lane is rw mounts only.
- **rw + exec-flagged**: `/APPS` (p41), `/data` (p27), `/var/local` (p39),
  `/var/tvservice` (p35), `/OAD` (p42, OTA staging — and `/OAD` sits on
  `login.sh`'s PATH), plus tmpfs (`/dev/shm`, `/var/run`, `/var/log`).
  rw + `noexec`: `/cache`, `/certificate`. Everything else ro.
- Accounts of interest (`/etc/passwd`): `root` shell = `/usr/local/scripts/rootlogin.sh`
  (root-only readable); **`cli` is UID 0**, shell = `/etc/cli_login.sh` (also
  root-only) — the classic Hisense debug shell, gate contents unknown;
  `television` (uid 300, the UI) shell = `/usr/local/scripts/login.sh`;
  an `sshd` account exists (uid 999) — server presence unconfirmed;
  phoenix = `UhisPhoenix` uid 314, **no capabilities, no seccomp**, PPid 306.
- **The UART console is live**: `inittab` respawns `getty -L ttyS0 115200` —
  a USB-TTL adapter on the service port reaches a real login prompt gated only by
  the (unreadable) login scripts.
- Boot chain: `rcS` → `mount -a` → `rcS.utopia.linux` (mounts, insmods, then
  `/usr/local/scripts/start-hisense.sh`, `setenforce 0`, sources
  `/config/daemon_profile` and `/application/network`) → `rcS.ko.linux`;
  `otaflag=170` in cmdline switches the tail to `rcS.OTA`/`rc.ota` — the `/OAD` lane.

### 10.6 Lane assessment

1. **Persistent code exec as uid 314**: phoenix runs JS from our writable `/APPS`.
   If the package isn't re-extracted at boot, augmenting `phoenix.server.js` =
   arbitrary code exec at every service restart (see §10.7 below for the v5 dump).
2. **Root**: needs a root-run service that consumes attacker-controlled files from
   a rw mount (mapped in §10.7–10.8 below, leading to the `rc.local` hook in
   [05-root-primitive.md](05-root-primitive.md)), the `/OAD`/OTA lane
   (`otaflag=170` → `rcS.OTA`/`rc.ota`), a kernel route on the MTK box, or the
   UART gate (physical; scripts are root-only readable).
3. Everything alvidaa does today minus MQTT: uid-314 read/write already covers
   app install and config without the RemoteNow channel.

### 10.7 v5 results: the backend source, the boot map, and the root trigger

- **The raw API needs no auth**: `POST http://localhost:9009/service/hiutils` with
  `{"api":"fileRead","args":{...}}` works with **no identifier header at all** from
  any page. The OPTIONS handler answers `Access-Control-Allow-Origin: *` — any page
  the TV browser ever opens can use the full file bridge. (One more reason the
  TV browser should never see the open web.)
- phoenix.server.js is just a framework (Router + `ServiceManager` + WS on 9888
  with `./cert/cert.{key,pem}`); the real action table lives in service packages
  loaded by `ServiceManager.init()` from paths set by env vars (`BASIC_JS_LIB`,
  `PHOENIX_LIB`). Those env vars are readable via `/proc/self/environ` — fileRead
  runs *as* phoenix, so it can read its own process env (v6).
- No dir-listing or exec-class api exists in the guessed-name space (17 names,
  all `"Not supported api"`); the authoritative table is in the service JS, not
  the guessed list.
- **The boot map** (`start-hisense.sh`, run as root): mounts the rw partitions,
  then `/usr/local/bin/deploy` (MW-deploy), `deploy_oem_data.sh` (OEM-deploy),
  `start-security.sh`, `start-network.sh`, `superwatch` (the supervisor that
  respawns phoenix — explains the crash recovery), `secure_exec`-wrapped
  `masman`/`systemserver`/`tvmain`/`startgui.sh`, and three background watchers:
  `check_usb_key.sh`, `checkEmergentOTA.sh`, and the IPK trigger:
  ```sh
  if [ -e "/APPS/pkgs/NewUpdatedIPK.txt" ]; then
      /usr/local/scripts/set_ipk_path.sh || true
      rm -f "/APPS/pkgs/NewUpdatedIPK.txt"
  fi
  ```
  `/APPS` is the partition the bridge can write. If `set_ipk_path.sh` executes or
  sources anything from `/APPS/pkgs`, that is **root code exec at next boot,
  no hardware** (v6 reads it). Also: `/var/tvservice/reset_working` (rw for us)
  triggers a root factory-reset flow — do not create that file casually.
- `chmod 777 /var/local` at boot; `/dev/ttyS0` is `chown root:808` — the UART
  login prompt is group-accessible, still gated by the login scripts.

### 10.8 v6 results: the root-side consumers of our writable mounts

- **`set_ipk_path.sh` is a symlink flipper, not an installer**: it reads
  `/APPS/pkgs/NewUpdatedIPK.txt` (writable by us) and, as root, for each listed
  existing dir creates `<dir>/current → <basename>` (the A/B `CHA`/`CHB` scheme).
  No script exec — but any boot-time consumer that resolves a package through
  `current` can be repointed at a directory we control. `SSL_CERT_FILE` already
  resolves via `current`; whether JS-service pkgs load via `current` or fixed
  `CHA/` is what `start-kilby.sh` will answer (v7).
- **`deploy_oem_data.sh` is a root-run arbitrary file deployer**: it copies
  everything under `/var/local/oem/…` — and `start-hisense.sh` does
  `chmod 777 /var/local`, i.e. the bridge can write it directly — into
  `/hidata/factory`, `/hidata/model`, `/var/local/dataModule/current`,
  `/vendor/tvconfig/config` (remounted rw by the script itself!) and
  `/serialdata/common/{logos,EPOS}`, then runs `security-dac-oem.sh`. The guarded
  import path (`import_oem_data.sh`: encrypted `OEM*.zip` via `dectool`, MD5,
  white-name ini) only applies to USB import — irrelevant, since the bridge
  writes the staging dir directly. Open question: what *executes* from those
  destinations; `oem_files_white_name.ini` enumerates the legitimate ones (v7).
- **The UART console gate is a readable script**: `check_usb_key.sh` sources
  `/usr/local/scripts/key_check.sh` and calls `check_key_to_open_console`
  (v7 reads it — if the gate is a flag file on rw storage, the console opens
  without hardware).
- **`checkEmergentOTA.sh`** only fires `rescueOTA` when the UI fails to flag
  ready within 60s — emergency lane, not primary.
- phoenix env (`/proc/self/environ`, readable by the bridge since it runs as
  phoenix): `ROOT_SYSTEM_JS=/APPS/pkgs/tv.vidaa.jsservice.system/CHA/` (the
  second JS service pkg — where the real fileRead implementation lives),
  `PHOENIX_BIN_PKG=/opt/pkgs/tv.vidaa.app.phoenix/`,
  `SSL_CERT_FILE=/APPS/pkgs/tv.vidaa.phony.keystore/current/common/cacerts.pem`
  (a `current` consumer), WSS certs at
  `/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/cert/cert.{key,pem}` (readable text),
  `PWD` = the CHA dir, and `start-security.sh` is root-only (EACCES).

## euladpp: a candidate root lane and its later test (Oct 30)

Field report from a 2026-07 firmware (V0000.09.60V.Q0612, MTK9603, VIDAA 9.0)
says the `../` escape is **closed**. An initial hypothesis from the older
09.01 dump was that euladpp could provide a root path without traversal;
subsequent testing did not establish that path:

- `euladpp-init-check.sh` (root, every boot): if
  `/APPS/euladpp/current/versionInfo.json` is missing/broken, it **untars
  `/APPS/euladpp/eulaDpp.tar.gz` into `/opt/eulaDppTemp` as root** and moves
  it to `current/`. `/APPS/euladpp/` sits on the rw partition the file
  bridge writes (relative paths — no `../` needed if the sandbox base is
  still `/APPS`; on 2026-07 firmware, test `fileWrite("euladpp/probe.txt")`).
- `euladpp-upgrade-install.sh` (root): `rm -rf current; mv upgrade current`
  — root `mv`/`rm -rf` over attacker-influenceable paths in `/APPS/euladpp`.
- The initial tar-slip idea assumed GNU tar 1.17 would follow a symlink or
  accept `..` members. The later test below disproved both assumptions for
  the vectors tested on the 09.01 unit.
- Trigger without reboot: `euladpp-upgrade-install.sh` appears tied to the
  EULA-acceptance flow — the `Hisense_*` bridge may expose the trigger.

Other hypotheses, including app-install behavior and the raw API on newer
firmware, require model-specific confirmation. The 09.60 EU_A reporter
observed `fileWrite` denied even for in-sandbox paths, so a reachable base
alone does not establish an install or write path. See
[the patched-firmware playbook](../../../../research/10-patched-firmware-playbook.md).

**Tar-slip verdict (live-tested Oct 30):** GNU tar 1.17 on this firmware
refuses BOTH classic vectors — symlink members are created but unlinked
(not followed) when a file member writes through them, and `..` members are
detected ("Member name contains '..'") and sanitized to relative paths.
Combined with the init-check's `chown -R UhisTvm` + `chmod -R 644`
stripping any setuid bits, the euladpp untar is **file-ops-as-root only —
no code exec**. The no-traversal root lane needs a different primitive;
Chromium N-days and the installed-app context remain the open ones.

**Static-audit corrections (2026-11-04, from the pristine vendor tree):**
`euladpp-init-check.sh` decompresses into `/OAD/eulaDppTemp`, not
`/opt/eulaDppTemp` — `/opt/euladpp` is the read-only backup source the script
copies `eulaDpp.tar.gz` from when the `/APPS` copy is missing. And the
boot-time OEM deploy copies the staging tree **unfiltered**:
`oem_files_white_name.ini` gates only `import_oem_data.sh`/`export_oem_data.sh`
(the USB lane), not `deploy_oem_data.sh` — the destination set is what bounds
that lane, and it stays data-only. Method entries filed in
[EXPLOITS.md](../../../../research/EXPLOITS.md) (uart-console-gate,
oem-staging-deployer, ipk-channel-symlink-flipper).

### superwatch_server and the IPK channel (2026-11-04, static)

From the pristine vendor tree (`usr-local/bin` + `usr-local/scripts`; binaries
via strings only — no disassembly, no live test):

- **`superwatch_server` is a root UDS command server** at
  `/var/run/superwatch_socket` (source path in the binary:
  `systools/superwatch_server/src/`). Its `CommandFactory` registers:
  `RunIpkInstall`, `RunIpkUninstall`, `RunIpkBackup`, `RunIpkRestore`,
  `RunIpkClearBackup`, `RunRecreateSoftlink`, `RunCheckPkgsUsd`,
  `GetDirUsage`, `MkDirForPVR`, `DropCache`, `IrGetLog`,
  `EnterWifiTestmode`, plus a `GeneralCommand` base class. Each command logs
  the client's `pid/uid/gid` (peer credentials) and passes through a
  per-command authorization check (`command unauthorized %d acess`); the
  check's policy (which uid may run which command) is compiled in and was not
  extracted. The boot map starts it as root (`start-superwatch.sh` loop +
  `superwatch &`).
- **The install command runs `opkg` as root**: `RunIpkInstallCommand` →
  `ipk_install.sh` = `opkg ${pkg_options} --force-reinstall install ${ipk_path}`
  + `ipk-update -n ${pkg_name}`, with the path and options taken from the
  socket message. `opkg` executes post-install scripts as root. The result
  file `/tmp/ipk_install_result` is created, chmodded 640 and **chowned
  314:314** — same for `check_pkgs_used.sh`'s result. The design intent is
  that **phoenix (uid 314) is the client class** for this socket. This is the
  same architecture the 100U7Q chain drives (`pkgmgr` → root superwatch
  socket → install 82/83); on this unit it is statically confirmed end to end
  on the server side, but the client-side authorization model is unresolved
  and no client was demonstrated. The sibling scripts `ipk_backup.sh`,
  `ipk_restore_backup.sh`, `ipk_clear_backup.sh`, `ipk_recreat_softlink.sh`
  implement the other IPK commands (backup/restore mirror packages between
  `/APPS/pkgs` and `/OAD/pkgs/backup`; the `cp -a` source path is
  symlink-following).
- **The package feed is plaintext HTTP**: `opkg.conf` (in
  `apps/opt-pkgs/`) sets `dest apps /APPS/pkgs`, `dest opt /opt/pkgs`,
  `option cache_dir /OAD/pkgs/download`, and sources
  `http://d2op21qr755kpl.cloudfront.net/mtk9603/Packages{,_all,.gz}` — no
  `option signature-check` and no keyring in the conf. Vendor-encrypted IPKs
  are handled out-of-band by `ipk-decrypt` (RSA_public_decrypt + AES-CBC) and
  `app_upgrade` (libcurl downloader with Authenticate/CheckVersion/Download
  services). Whether the app-store path enforces the RSA layer is a
  binary-analysis question; the opkg conf itself imposes nothing.
- **`secure_exec`** is a small setuid/caps wrapper ("execvp process and set
  uid,gid,groups,caps by secure_exec", usage
  `secure_exec <label> <full-path> <argv...>`) — the policy is compiled in
  per label; `masman`/`systemserver`/`tvmain`/`startgui.sh`/`rescueOTA` all
  start through it.
- **`masman`** listens on `127.0.0.1:12321`, has a command interface
  ("Available commands:") and `-S`/`-s` options for startup/shutdown shell
  scripts — not used in the boot invocation. Loopback-only, root-run; noted
  for the map, not pursued.
