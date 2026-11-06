# Native Home replacement installed (operationui Launcher component)

**2026-11-06, owner-authorized, LAN-local.** The alvidaa "Free My TV" DOM
launcher now replaces the stock Home on the 75U8QTUK. This is a component
swap inside the writable operation-ui module, not a SystemUI/root-page
replacement. Stock UI lifecycle, other routes, key dispatch, toasts and
vendor services are retained. Every change has a tested teardown path.

## Preconditions checked before overwriting anything

- `git log`: branch `u8qtuk-75`, three unpushed commits at the time, no PR opened.
- `/var/local`: **no** `/var/local/alvidaa` and **no** `/var/local/otaTest*`
  backups — no other agent session had state on this TV. `/var/local/alvidaa`
  was created by this session only.
- OTA already frozen on this unit: `/OAD/AppUpgradeSwitch.json` has
  `upgradeFlag: "0"`, `nightupdate.ini` has `dcm_update=0` and
  `dcm_standby_update=0`, and `/OAD/pkgs/{download,backup}` hold no staged
  update package. No OTA endpoints were poked.
- Stock baseline pinned and verified on both sides:
  - `/APPS/pkgs/tv.vidaa.app.operationui/CHA/apps/launcher/js/app.js`
  - size `318127`, owner `305:909`, mode `0640`
  - md5 `46bdee5a72955cda19fd361bf2954f80`
  - sha256 `380d337ecbfa08487768b18cb8342630db1c2880c6e6c14811e6f7d1c72f2c8f`
  - private copy: `firmware/75u8qtuk/operationui/apps/launcher/js/app.js`
- Root lane armed and uptime continuous (~460 s at start); root SSH on
  `10.0.0.173:8008` with `server/keys/vidaa_75u8qtuk_ed25519`. **No reboot
  was performed during this test** because root SSH has no boot persistence
  ([08](08-reboot-rearm.md)).

## Architecture

`SystemUI` (`/opt/hisenseUI/bin/SystemUI`, uid 311, group 909) is launched by
`/opt/hisenseUI/startgui.sh` with `--url=file:///hisenseUI/index.html`. The
shell lives on the read-only rootfs at `/opt/pkgs/tv.vidaa.app.ui/`; the
writable UI module is `/APPS/pkgs/tv.vidaa.app.operationui/CHA/` (symlinked
as `current`, exported as `HI_UI_OPERATIONUI`). The launcher bundle is
`/APPS/pkgs/tv.vidaa.app.operationui/CHA/apps/launcher/js/app.js`.

`app.js` ends with `(self._V_M_=self._V_M_||{}).launcher=()=>i("740m").Z`.
The appended wrapper replaces **only** `route[0].component` for `/Launcher`
with our Vue component. `beforeEnter` guards, `meta.sourceInfo`, the other
routes (`/Launcher/myApps`, `/Launcher/secondaryPage`, `/KidsLauncher`, …),
vendor key dispatch and toast/bui services are untouched. This follows the
proven 55A7KAU module-vs-root lesson; the 55A7KAU files remain unmodified.

### SDK contracts on this build (source-verified, differ from 55A7KAU)

| Concern | 55A7KAU adapter | **75U8QTUK (this build)** |
|---|---|---|
| App list | `getCurrentShowApps("Launcher")` | `me.req("app-service").getData("getAppList",{sceneCode:"launcher"}).result` |
| Availability | `getAppInfoByAppId` | `getData("getAppInfo",{appId,url:"",checkRange:1}).result` (`checkRange:1` → visible `allApps`; returns an app object or `null`) |
| Inputs | `getAllInputsData` | same |
| Input switch | `changeSourceTo` | `me.req("all-inputs").invoke("changeSourceTo",sourceId,"launcher")` |
| Settings | `open("settings",{vk:"T"})` | `me.req("setting").open("settings")` — **no `vk`** |
| App launch | `sdk.apc.start` | `sdk.apc.start` (=== stock `MP`; `DSbq.MP` is the SDK instance's `apc`) with `{name,appId,url,storeType,startMethod,typeCode:"600002",rateInfo:""}` |
| `startMethod` | `CMDMETHOD.REMOTECONTROL` | `CMDMETHOD.LAUNCHER_RECOMMEND` = **`"52"`** (home-tile equivalent); `KEY_INPUT_START` = `"207"` |
| `storeType` | separate field | app records carry `storeType`; feed tiles call the same value `openMode` (`storeType: e.openMode` in `tileOpenAction`). Adapter accepts either. |
| Icons | local `var/local/storeAppIcon/…` | `https://img.vidaahub.com/…` (feed tiles) and app-service `img` / `httpIcon` / `icon_web_url` / `icon_local_url`. Shared `localIcon()` rejects them → model override accepts the vidaahub host. |

Other measured facts:

- Exact events (present in the vendor bundles): `o2n://sdk/init-finished`,
  `o2n://app-service/all-apps-changed`, `o2n://all-inputs/inputs-data-changed`,
  `o2n://sdk/str-resuming`, `o2n://sdk/str-suspending`. `sdk.message` is an
  EventBus with `on/off/once/emit`.
- `sdk.key.KEYMAP`: `BACK:8`, `BACKSPACE:8`, `ENTER:13`, `HOME:36`, `EXIT:27`,
  `LAUNCHER:547`, `SOURCE:505`, `KEYPAD_INPUT:610`, `ALLAPP:615`.
  **`KEYMAP.RETURN` does not exist** — the shared `handleKey` comparison
  against `undefined` is harmless.
- `sdk.tts` = `{t,speak,cancel,isEnable,setState}`; `sdk.storage` is a
  `window.localStorage` wrapper with a prefix. SDK instances are cached by
  name (`Tt[e]`), so `new SDK("launcher",{storagePrefix:"Alvidaa"})` returns
  the stock instance (prefix `Launcher`) — prefs are stored under that prefix.
- `sdk.router.isCurrentPathEqualTo("/Launcher")` resolves correctly:
  `MODULE_ROUTE_MAP` maps module names to **numeric** route prefixes, and
  `getRealPath()` prepends that prefix. `getCurrentPage().path` matches.
- `_V_SDK_.vre.SDK` is the correct SDK class; `M2O5` = `_V_SDK_.vre`.

## Files added (all committed; shared 55A7KAU files untouched)

| File | Purpose |
|---|---|
| `tools/launcher-host/native-platform-75u8qtuk.js` | model-specific data adapter (apps, inputs, settings, launch) with the 55A7KAU retry/event logic |
| `tools/launcher-host/free-my-tv-native-75u8qtuk.js` | wraps `AlvidaaFreeMyTV`: vidaahub/local icon override, guarded `announce` and `routeFocus` |
| `tools/launcher-host/build-native-75u8qtuk.cjs` | asserts stock sha256, appends adapter + shared frontend + override + `native-entry.js`, `vm.Script` parse-check, private-only output |
| `tools/launcher-host/native-platform-75u8qtuk.test.cjs` | offline adapter contract test (5 groups) |
| `tools/launcher-host/native-home-75u8qtuk.test.cjs` | load-time bundle smoke test (route replaced, icons, idempotent wrapper) |
| `tools/launcher-host/switch-home-75u8qtuk.sh` | on-TV supervised restart: `dry` / `install` / `rollback` |

Candidate bundle (private, gitignored `firmware/75u8qtuk/`):
`344249` bytes, sha256
`226ac863ea26842fed0bb9872d74c00303d80131456cf53deb119c73bb793da0`,
md5 `1f465e9bd834cd98dfcdbe5c904bd02f`. Built from the unmodified vendor
bundle plus the four appended parts, with the MIT license header from
`third-party/free-my-tv/LICENSE`.

## Discoveries / traps (recorded same hour)

1. **`/var/local` is `ext4 rw,seclabel,nosuid,nodev`.** A script placed there
   cannot be executed via its shebang: `sh: …/switch-home.sh: /bin/sh: bad
   interpreter: Permission denied` (exit `126`). Invoking it as
   `/bin/sh <script>` works. The first detached dry-run attempt produced no
   log and changed nothing on the TV for exactly this reason; SystemUI stayed
   at PID 1524 and `app.js` stayed stock. Fixed by always invoking through
   `/bin/sh` explicitly.
2. **SSH sessions carry no `PATH` / `LD_LIBRARY_PATH`.** The relaunch must
   reuse the *vendor* environment. We capture `/proc/<pid>/environ` before
   the kill and re-export it in the detached launcher. Without it,
   `secure_exec` could fail to resolve its shared libraries.
3. **`secure_exec` is safely testable.** `/usr/local/bin/secure_exec SystemUI
   /opt/hisenseUI/startgui.sh` while SystemUI is live prints
   `SystemUI is running, exit!!!` and returns 1 — a no-op proof that
   `execvp` + uid/gid/groups/caps work from an SSH-spawned context.
   `secure_exec` is a small ELF using `execvp` and `libsecure-processid.so`.
4. **Restart mechanics.** `startgui.sh` refuses to start when
   `pidof SystemUI` succeeds → kill first. Its last line is
   `exec "/opt/hisenseUI/bin/$PROCESS_NAME" …`, so the new engine is
   reparented to PID 1. There is **no APM/superwatch respawn** on this build;
   the launcher must be started explicitly. `/bin/sh` is bash
   (`//openbox/bin/bash`), so `read -r -d ''` and `export "KEY=VALUE"` work.
5. **Cache scoping.** Only `compiled_js` and `uncompiled_js` were reset
   (moved aside, recreated empty as `311:311` / `0751`). All other Cobalt
   cache dirs (`image`, `css`, `font`, `html`, `splash`, `service_worker_js`,
   `cache_api`, `other`) were left intact — the 55A7KAU black-screen lesson.
   A **new** compiled entry `3005616565` (24804 bytes) appeared after the
   restart, proving the new bundle was compiled rather than served from a
   stale cache.

## Dry run (stock-only, gate)

`/bin/sh -c 'trap "" HUP; exec /bin/sh /var/local/alvidaa/switch-home.sh dry'`
run detached. No file or cache changes.

- SystemUI `1524` → `19933`; `PPid: 1`; `Uid/Gid 311:311`;
  `CapEff 0000000000a05000` and supplementary groups identical.
- Uptime continuous (no reboot); `app.js` md5 still
  `46bdee5a…`, `305:909` / `0640`.
- A **second, independent SSH session** confirmed PID 19933 alive with
  `PPid 1` after the launching session closed — the relaunch survives SSH
  teardown (the detached subshell sets `trap "" HUP` and redirects all stdio
  to `/dev/null`).
- **Owner confirmed stock VIDAA Home returned.**

## Install

Same script, `MODE=install`. Order: verify hashes → capture env → kill
SystemUI → mutate files while the engine is down → relaunch → verify.

- SystemUI `19933` → `32471`; `PPid: 1`; credentials identical.
- `app.js`: `344249` bytes, md5 `1f465e9b…`, still `305:909` / `0640`
  (staged to `<app>.alvidaa-tmp`, `chown`/`chmod`, then `mv -f`).
- `compiled_js` / `uncompiled_js` moved to
  `/var/local/alvidaa/backup/`; fresh empty dirs created `311:311` / `0751`.
- Log: `OK mode=install old=19933 new=32471 ppid=32382 wait=1s`.

### Backups (both sides, private)

- TV: `/var/local/alvidaa/backup/app.js.stock` (md5 `46bdee5a…`),
  `compiled_js/`, `uncompiled_js/`, `js-cache.tar` (md5 `11217a0b…`).
- Mac: `firmware/75u8qtuk/backup/app.js.stock`, `js-cache.tar` (gitignored).
- Screenshots: `firmware/75u8qtuk/screenshots/native-home*.png` (PNG despite
  the HAL's `.jpg` filename; 1920×1080).

## Verification (owner-confirmed + objective)

The owner reported the new Home, then confirmed **app launch**, the
**Inputs** tab and the **TV Settings** button all work. Two HAL screenshots
(`/usr/local/bin/screenshot` → `/tmp` → pulled over SSH, zero persistent TV
writes) show:

- "For You", top nav (Home / All apps / Inputs / TV Settings / Preferences),
  dark auto theme, clock `22:54`, `Fri Nov 06 2026`,
  "Your apps. Your TV. No feeds, no ads.", and the favorites shelf.
- Real vendor icons from `https://img.vidaahub.com/…` (YouTube, TV Channels+,
  Kids, Ads Privacy, APP STORE, Art Gallery, browser, media, E-MANUAL, VOD).
- Status line `Native · 10 apps · 10 inputs` (later `11 apps` after an
  `all-apps-changed` refresh), proving both services and the event logic.
- A vendor toast "Optimised for Game settings" overlaying the launcher —
  proof the stock UI lifecycle still runs underneath.
- Favorites persisted through the edit view (`sdk.storage` works), and
  arrow/OK/Back key handling works.

## Teardown / rollback

One command restores stock and restarts the engine:

```
ssh -p 8008 -i server/keys/vidaa_75u8qtuk_ed25519 root@10.0.0.173 'sh -s' <<'EOF'
PATH=/basic/bin:/bin:/usr/bin:/sbin:/usr/sbin; export PATH
D=/var/local/alvidaa
/bin/rm -f "$D/switch.done" "$D/switch.log"
/bin/sh -c 'trap "" HUP; exec /bin/sh /var/local/alvidaa/switch-home.sh rollback' \
  >/dev/null 2>&1 </dev/null &
i=0; while [ ! -f "$D/switch.done" ] && [ $i -lt 45 ]; do /bin/sleep 2; i=$((i+1)); done
/bin/cat "$D/switch.done"; /bin/cat "$D/switch.log"
EOF
```

`MODE=rollback` restores `app.js.stock` with `305:909` / `0640`, restores both
original JS-cache directories, and restarts SystemUI with captured vendor
credentials. Manual equivalent: `cp -p` the stock file back, restore the two
cache dirs from `/var/local/alvidaa/backup/`, then
`secure_exec SystemUI /opt/hisenseUI/startgui.sh` from a detached,
HUP-immune subshell using the saved `/var/local/alvidaa/systemui.env`.

If SSH itself is gone (after a reboot), re-arm root first with the `83` + `82`
sequence from [08](08-reboot-rearm.md); the launcher file lives on writable
`/APPS` and is expected to survive a reboot, but rollback then needs the SSH
lane back. **The launcher was deliberately not reboot-tested in this session.**

## Ground rules honoured

- Owner's own TV, LAN-local, no DRM circumvention, no OTA writes.
- `/` stays `erofs` with dm-verity green; only `/APPS` (writable module) and
  `/var/local` were written. Verified boot untouched.
- One MQTT server per TV: Sidee holds the pairing/control session;
  `server/pair.py` was **not** run.
- Device ID, Netflix ESN and serial are not committed; root key stays in
  `server/keys/` (gitignored). Private vendor bundles and screenshots stay in
  gitignored `firmware/75u8qtuk/`.
- No push, no PR.
