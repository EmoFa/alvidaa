# Update / OTA — 55S7NEVS

> From the contributed bundle by [possibly_matt](https://www.reddit.com/user/possibly_matt/)
> (2026-11-05), adapted for this repo 2026-11-06 with the author's permission
> for the documentation. "findings NN" pointers below refer to the author's
> private working notes, which are not part of this repo. See the
> [guide README](../README.md) for scope.

Evidence: `usrlocal/bin/ota_upgrade` (full string dump: `ota_strings.txt`
was generated from the backup and lives in the workspace temp dir — key
substrings quoted below), `rootfs/etc/init.d/rcS.OTA`,
`usrlocal/scripts/{start-ota_upgrade.sh,checkEmergentOTA.sh}` and friends,
`OAD/` partition snapshot, `var/local/upgrade/*`, the migration logs
`OAD/ota_migrate_module_log/*`, `rootfs/usr/bin/upgradeprogress/*`.

Three update paths exist: **cloud OTA** (the normal one), **USB OTA**
(the same binary pointed at a USB stick), and **rescueOTA** (fail-safe when
the UI never comes up).

## Components

| | |
|---|---|
| `ota_upgrade` (285 KB ARM ELF, runs as `UhisOta` (uid 3xx-range), one at boot) | the whole cloud-checker/downloader/flasher; links `libhi_cloud_openapi.so`, `libbspatchupdate.so`, `libbootctrl.so`, `libflashEnv.so`, `libmodel-rpc-client.so` (Kilby biz), libcurl, libwebsockets, libkiport (BspatchLinuxImageWriter) |
| `upgradeprogress` | OAD-boot-time UI (shows "Loading progress: N%", uses fusion0/framebuffer + `otaPartitionConfig.ini` for the write map) |
| `rcS.OTA` | special boot mode of rcS, executed when `ota_upgrade_flag == Y` (from `/dev/his_facinfo` raw factory-data region) |
| `/OAD` (p55) | staging area: patch packages, eulaDpp.tar.gz, hotfixVersion.ini, overlay_fs, original_file/ update_file/ patch_file/, migration logs |
| FlashEnv (boot0/boot1 "sboot") | env-key/value store on the eMMC boot partitions, accessed raw in userspace (`echo 0 >/sys/block/mmcblk0boot0/force_ro` first) |
| `bootdata` (p34) + `vbmeta` (p22/23) | A/B slot metadata (bootctrl_read_boot_slot / bootctrl_ota_success from libbootctrl) |
| `kilby.sl2.software.update.*` kproperties | the UI<->OTA RPC surface (progress, policy, new version, download/start/cancel actions) |
| `his_facinfo` (p36) | extra raw flags (`ota_upgrade_flag`, `ota_modeldata_flag`, `ota_untar_flag`, `ota_datadeploy_flag`, `ota_layer_flag`, `ota_reboot_flag`, `ota_panel_flag`, `ota_poweroutage_flag`, `ota_nstr_flag`, `ota_cloudcontrol_flag`) written via `setHisOTAFlag(i,h)` |

## Cloud check (network OTA v11)

On every boot `start-ota_upgrade.sh` (run from `autorun_root.sh`) spawns
`ota_upgrade`. Thread model: a checker thread + a downloader thread +
a mutex-check death watchdog (`mutexcheck.cpp` — dumps callstacks of stuck
`pthread_mutex_lock`).

1. **Auth** — anonymous device authentication first (no UI needed):
   `HI_GLOBAL_INIT` (cdn from `getDynamicDomain` / `HW_GetCDNInfo` →
   `vidaa-base` domain family / bridge `getDefaultCDNInfo`), then
   `HI_AUTH_AUTHENTICATE`, token written to
   `/var/local/upgrade/authentication_result_data.xml`, cached token is
   `s_pkg_authentication_token` and legality-verified via
   `check_token_legal` before reuse. Prior auth result kept in
   `authentication_result_data.xml`.
2. **Policy data** gathered per request: platform_get_software_version /
   machine_type / soft_material_num / country_name / zip_codes / tv_brand /
   gui_lang_code (also persisted into `/var/local/upgrade/am_tv_lang`,
   e.g. `eng`), HW MAC, capabilityCode (`/serialdata/common/service.ini`
   also has `[LogService] osstage = U09.60` and
   `TV_ORIGINAL_OOSTAGE_FILE`), emmc life (SLC/MLC %), hotFixVersion
   (`/OAD/hotfixVersion.ini`).
3. **Request** — JSON blob:
   `{"capabilityCode":"","osStage":"","emmcLife":"","mlcLife":"","hotfixVersion":"","currentTimestamp":…}` posted to
   `…/upgrade/check_version` with query params `&msgId=66 &msgType=256
   &msgVersion=513 &version=11.0 &format=0 &sourceType=1 &accessToken=
   &brandCode= &checkMode= &currentVersion= &deviceExtInfoStr= &dvcRsv=
   &httpmode= &languageCode= &postCode= &statCode=` — the whole device
   fingerprint goes into a signed cloud call. Result XML saved to
   `/var/local/upgrade/check_version_result_data.xml`.
4. **Rule format** (`parse_upgverchk_doc`, root element `<response>`):
   `<latestVersion>` (`Rescue.`-prefixed = refused, "Remote version starts
   with Rescue only for rota"), `<updateFlag>`, `<updateType>`,
   `<versionDesc>`, `<areaId>/<areaName>`, `<eulaUrl>/<eulaChkSum>/
   <eulaSHA256Sum>`, `<dppUrl>/<dppChkSum>/<dppSHA256Sum>`, `<fileNum>`,
   `<fileList>` → per `<fileInfo>`: `fileName/fileVersion/fileType/
   downloadUrl/checkSum (md5)/sha256Sum/fileSize` — signing material is
   md5+sha256 per file (`s_pkg_file_checksum`, `s_pkg_file_sha256sum`).
   Country provisioning gate: `/OAD/AppUpgradeSwitch.json`
   (`upgradeFlag=0` ⇒ per-country OTA kill-switch; seen current value for
   `GBR` is **0** = OTA switched off administratively, next to it a
   `signatureServer` RSA-blob).
5. **Version comparison** — region-aware (`safe_get_platform_ver` fallback
   "unknown"), per-file; local current version cached in
   `/var/local/upgrade/old_version.ini` (`Version = %s`) and reset-only
   upgrade history `/APPS/ota_history.ini` (`UPG_TIME=…,SRC_VER=…,TGT_VER=…`).
   Manual vs auto flag in `/var/local/upgrade/ota_manual_check_flag`,
   `update_info_data.ini` carries
   `update_version / update_mode / md5_check_fail_num / never_flag`
   ("never remind" support) — deleting it invalidates the cached check.
   If **appupgrade** (the packages updater) is running, the whole check is
   short-circuited (`appupgrade is running, check no version`) with a cloud
   redundancy message ("appupgrade is running abnormally, temporary policies
   are delivered on the cloud").

## Download

- Full-package or **bspatch** delta (`patch_package.zip`, tables
  `/OAD/original_file/`, `/OAD/update_file/`, `/OAD/patch_file/`) — chosen
  per file by the server via `fileType`; `libbspatchupdate.so` +
  `BspatchLinuxImageWriter` materialize `original_file + patch_file → update_file`
  per item ("Oad_VERSION_BSPATCH!" branch).
- Endpoint = `downloadUrl` (CDN resolved again with `ota_get_cdn`);
  supports cancel/suspend via `/var/run/ota_cancel`, `/var/run/ota_suspend`
  "loaded" and resume tokens; per-URL `FileLocate` streams to
  `/OAD/` with mkdir; space checks USB/data first
  (`ota_check_update_space_enough`).
- eulaDpp.tar.gz is a parallel download (EULA acceptance text + DPP privacy
  policy pack, both separately checksummed; `platform_set_eulaDpp_status`
  flips `basic.settings.eula.dpp.general`).
- Integrity: md5 and sha256 of the package(s) verified before apply —
  `md5_check_fail_num` accumulates into `update_info_data.ini` and beyond a
  threshold the TV reports "no version" (`his_ota_isNeedNotifyNewVersion`).

## Apply

1. `his_ota_start_upgrade` — UI asked for "update now" / "update later";
   HDPanel value set first, then either immediate (power keeps panel ON
   through `ota_silent_panel_flag`, AMP finalized via
   `platformFinalizeAMPBeforeReboot`, `rebootByHUI` →
   `/usr/local/bin/reboot`) or deferred (`ota_cloudcontrol_flag` written,
   seteoff STR standby, panel off, `just reboot now`).
2. `nice -n -19 <cmd> &` spawns the flasher — **per-partition writes are
   direct block device writes** (`flashWriterBlock` O_RDWR, `write()`,
   `fsync`), no LVM/no logical layer, mapping file image →
   `/dev/mmcblk0pN` straight from `otaPartitionConfig.ini`.
3. **Flash flag choreography** (this is the tricky part; the flags hand
   control between userspace and the next two boots):
   - before reboot: set `ota_upgrade_flag = Y` in `his_facinfo`
     (so rcS turns `rcS.OTA` boot ON), `ota_reboot_flag`,
     `ota_success_flag=0` (cleared; written again on success),
     `ota_panel_flag`, `ota_poweroutage_flag`, `ota_nstr_flag`
     ("no shutdown/reboot" mid-upgrade guard; set at reboot; rcS.OTA and
     upgradeprogress test it),
   - build chain writes: `ota_untar_flag`, `ota_modeldata_flag`,
     `ota_datadeploy_flag`, `ota_layer_flag` (erofs/usrext4 path layer),
   - mboot slot: `setRunningStartchain` (`Set the dualFlag`) and
     `bootctrl_ota_success` semantics decide which bank latches — the
     verified live sequence log shows `linuxboot.slot_suffix=_b` during
     `checkSHA256Sum` steps, then flips to `_a` after flashing, i.e. the
     upgrade stage flashes into the other slot, then latches it.
4. On the reboot(s) `rcS.OTA` runs (see boot doc): loads mmsdk modules,
   mounts `/vddt` (= OAD rename) and `/var/local`, runs
   `upgradeprogress` on the fusion framebuffer device; it untars/deconstructs
   each `partition.img` buffer into the mapped device inside the config:
   **`rcS.OTA` → `upgradeprogress` uses `otaPartitionConfig.ini`
   as the write map** (dual-bank lines for sboot/mboot/KL/optee/armfw/DTB/dtbo/
   rootfs/vbmeta/tvconfig/application; single-copy for frc/3rdfile/mwlib/
   libdynamic/bootdata/logo/usrfs/optfs/sysadapter/serialsdata/comdata/tvsapp).
   `verify devmsg` does the dev-node checksum before writing; per-image
   checkSHA256Sum log lines confirm each written partition (the
   "Checksums for /dev/mmcblk0pN doesn't match" lines in
   `OAD/ota_single_upgradeprocess_log.txt` are the *expected pre-write*
   comparisons of the currently-running slot, seen twice in the log: once
   with `_b` running, once with `_a`).
5. **Migration scripts** run during this stage — `OAD/ota_migrate_module_log/`
   shows the preserved list of *what user data is carried across*:
   `deviceid`, `browser db`, `emanual`, `factory_key`, `hisenseUI`,
   `iqqi_db`, `mediamain_cfg`, `package_app`, `eula_dpp` — bridging
   `/APPS`, `/APPS2` and `/var/local` content forward (that's why user
   packages/apps and databases survive the upgrade while the system
   partitions are rebuilt).
   Config backup via `usrlocal/scripts/ota_confile_backup_paste.sh` +
   `oem-basic-ota-config-backup.sh` (per-OEM model list from
   `getOemBasicModelList`).
6. On success bash, `bootctrl_ota_success` marks the slot permanently via
   `bootdata`, ota_flags cleared, normal boot.

That said: `/OAD` is single-copy and actively rewritten during upgrades —
staging and leftovers share the partition (`clearFiles`/`clearUpgradeFile`
remove the working dirs `original_file/update_file/patch_file` and the
downloaded archives once applied).

## USB OTA

`his_ota_start_bspatch` / `copyUsbOtaPackage`: reads `patch_package.zip`
from any readable USB (`platform_get_usb_path`); requirements:
`usb_compareVersionBeforeUpgrade` compares the stick's `patch_package/basic.ini`
`updateVersionParts` against the TV's `originalVersion` — must be strictly
newer; also debug-availability gating:
`patch_package/debug_version` vs `/usr/local/debug_version` — the two builds
must have the same debug flag ("The two versions are inconsistent").
Space-insufficiency errors: "usbota space is not enough". After approval a
`cp` to `/OAD` then the Cloud-OTA flash path is reused; UI shows
`Loading progress: %d`.

Note: `check_emergent OTA` docs: `checkEmergentOTA.sh` waits up to 60 s for
`/tmp/tvstatuschecker.txt` (HisenseUI "OK" marker) and runs
`rescueOTA` if the shell never sees it — that is, if the system comes up in
a non-UI state (`his_facinfo factory_mode=on` skips the check). Also
`usr/bin/upgradeprogress/WriteUpdateFlag`/`ReadUpdateFlag` filter entries.

## Reset/factory & hotel mode

- `reset-working` flag file `/var/tvservice/reset_working` — **never
  create** (flagged as a danger file in the author's notes). Its operator (`reset_process.txt`,
  and `OAd/types` logs) walks factoryOK / usr_reset / clean:
  backup log files → clean `/var/local` → do-clean `channel` (db) →
  recover `dataModule` from `/hidata/*` → re-run `eulaDpp` init → reset
  IQQI/Karaoke DB → reset pkgs (enable/ste ίδα, `pkgs-reset`) →
  restore log+log-level + wb/color_tuner → hotelmode clean-file list.
- `security-dac-*` steps re-apply partition DACs (see
  `usrlocal/scripts/security-dac-partition-*`).
- Everything is recorded into `/var/tvservice/TVResetReccord.txt`.
- The *whole thing* is independent of OTA; `upgrade_mode.ini` in
  persist just carries last-mode metadata; `resetcfg` under `usrlocal/etc`.

## Telemetry

`report_upgrade_event` is a separate call per event (search result,
download status, eula state …), posting to the same cloud session with
deviceExtInfoStr, an accessToken, currentTimestamp; results written to
`/var/local/upgrade/report_upgrade_event_result_data.xml`. The binary
masks sensitive strings with `desensitize_mac`/`mask_str` helpers — MACs
are anonymized before send.

## Consequences for the alvidaa project

- An OTA will rebuild `/opt`/`/APPS(p54)`/`/APPS2(p46)` and `var/local` —
  **our root hook `/var/local/otaTest.sh` survives because `varlfs`
  (p49) is *not* in the dual-bank/untar table at all** (durable root, per the
  author's notes).
- `/OAD` (p55) is single-copy and actively rewritten during upgrades —
  our canary/oct files there (`octcanary1.txt`, `factorykey.log`) live
  alongside OTA staging; migrations may re-create `octcanary1` but the
  content itself is nothing special.
- Firmware versions we cannot fetch locally are being held downstream:
  the **current-country rule for GBR is upgradeFlag=0** (no updates sent
  to this unit while that rule is live) — combined with the
  auto-check policies, this unit effectively cannot receive OTA even
  offline-manual check attempts report "no match upgrade rule" (see
  `var/local/upgrade/check_version_result_data.xml` errorCode 205001).
- OTA download verification depends on sha256/md5 only — **no code
  signature chain** for userspace: AVB covers boot chain + hashed ro
  partitions, but the OTA-introduced "single-copy" partitions
  (usrfs/optfs/sysadapter/3rd...) have no per-boot re-verification
  (only initial avb_mount for hashed ones). Practical focus area was
  raising this in lanes/board reviews, out of scope here.
