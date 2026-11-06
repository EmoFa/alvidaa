# Native custom Home installed: N02 rendering and transitions confirmed

The user authorized replacing stock Home with the custom launcher and retaining
a path back to stock. This is the first user-confirmed native module replacement
on this unit; it is not the earlier browser/watcher overlay.

## Deployment

- Staged first-party tools under `/var/local/alvidaa/native-v2/`, verified
  uploads byte-for-byte, and passed pinned-hash/bridge/process preflight.
- Private originals, uid/gid/modes, hashes, recovery manifest and platform
  environment snapshot are under `/var/local/alvidaa/native-home/`.
- Replaced only `/APPS/channelA/operation-ui/apps/launcher/js/app.js` with
  `tools/launcher-host/native-launcher.js` (N02, 8389 bytes at deployment).
- Disabled the bridge Home watcher. Shared index/SDK/router stayed intact.
- Swapped only compiled/uncompiled JS caches while Cobalt was stopped.
- Used the verified SIGTERM → secure_exec/startgui lifecycle, not SIGKILL and
  assumed APM respawn. Cobalt PID changed **3268 → 5484**, with matching
  credentials and a stable identity during the startup check.
- Worker recorded `2026-11-06T11:42:07.385Z {"phase":"installed","enginePid":5484}`
  using the TV clock. Installed launcher/config hashes subsequently matched
  the manifest, and watcher.enabled was false.

## User-visible verification

The user explicitly selected **N02 and working arrows** after pressing Home,
then **Both work** after testing an app and HDMI input and returning Home
from each. The distinctive yellow `ALVIDAA — NATIVE TEST N02` heading and
disabled watcher disambiguate this result from the old browser launcher.

The custom Home is left installed; there is no automatic timer reverting it.
The original launcher code is not mounted or run behind a hidden div. Shared
platform services and other operation-ui modules still run.

## Restore option

From the repo root:

```sh
tools/launcher-host/home-control.sh restore
tools/launcher-host/home-control.sh status
```

The installed manager is `/var/local/alvidaa/native-v2/native-home.cjs`.
Restore returns the stock launcher/cache files and relaunches through the
vendor wrapper. It deliberately keeps the watcher disabled: restoring the old
watcher=true config would reintroduce the unwanted browser bounce. The exact
historical config remains backed up. Other config fields are restored.

The staged manager was updated with this restore policy after tests passed;
that update did not restart or change the running custom launcher. The host
status wrapper was exercised and reported installed/PID 5484. The full restore
of this working installation has not been exercised; earlier stock restart
was verified and file/rollback behavior has local fault-test coverage.

## Scope and remaining evidence gaps

26 local tests pass, including original vendor-loader contract checks, explicit
restart, failed startup rollback, source-ID normalization, watcher-off stock
restore, concurrent edit guards and stale operation locks. No PC setup server
was restarted. Root persistence and bridge startup were not modified.

A cold power-cycle of this installed version, standby/resume and sustained
application use remain untested. Files are persistent, but persistence is not
claimed as empirically verified until that boot test. Kids/game modes and
stock-home accessibility/personalization are not implemented.

The bridge `/api/state` returned an empty string after installation despite
working user-confirmed app/input/Home transitions. The sampled log ring had
no `alvidaa-native` markers. These are diagnostic limitations to investigate,
not evidence that the native screen was absent.

See the [control and recovery guide](../../../../../tools/launcher-host/NATIVE-LAUNCHER.md).
