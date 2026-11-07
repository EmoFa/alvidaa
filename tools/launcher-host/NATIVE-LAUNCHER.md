# Free My TV — native Home on the 55A7KAU

The installed Home is the Free My TV offline clock-and-shelf design, adapted
to native Cobalt/Vue. It lists apps and inputs through the vendor SDK and
opens the **full stock TV Settings**. It does not redirect to a browser or
use our Go HTTP/WebSocket/MQTT server. The bridge, fallback server and their
boot-start section have been retired reversibly. Root SSH remains intact.

The original launcher factory is retained, but only its `/Launcher` component
is replaced. Original guards, other routes, kids/game entry points, initialization
and remote handlers remain. The old Home component is not rendered/hidden.
Vendor services/background behavior are still present: this is not a complete
removal of vendor code or telemetry.

## Controls and features

- **Home**: custom Home; **Input**: native input view.
- **Up** from the shelf: top navigation. **Down**: inputs.
- **Left/Right/OK**: select/activate. All-apps and inputs are paged grids.
- **Back**: close launcher subviews; Back from main Home passes to the vendor.
- **TV Settings**: original Settings, not a reduced replacement.
- **Preferences**: automatic/light/dark theme, manage/reorder shelf, refresh,
  attribution. In Reorder shelf, OK picks up/drops an app; Left/Right moves it.
- Local cached/preset icons have text/brand-colour fallbacks. No runtime CDN,
  canvas processing or external recommendation/weather/market requests.
- Home focus announcements use the native screen-reader setting; it is not
  enabled automatically. Other stock remote keys are not swallowed by Home.

## Restore stock / return to native

From the host repository:

```sh
tools/launcher-host/home-control.sh status
tools/launcher-host/home-control.sh restore
tools/launcher-host/home-control.sh native
```

`restore` and `native` request a detached TV-side worker. Wait for status
`restored` or `installed`, then press Home. Status is not proof of rendering;
the recorded engine PID belongs to the last controller restart, not necessarily
the current boot. Actual stock restore and native reapplication were both
visually verified on this TV.

The wrapper defaults to `<tv-ip>:8008`, using
`server/keys/tv_root_ed25519`. Override `TV_HOST`, `TV_PORT` or
`TV_KNOWN_HOSTS` as necessary. No PC-side server needs starting.

Current TV tools: `/var/local/alvidaa/native-free-my-tv-v2/`.
Original backups/journals: `/var/local/alvidaa/native-home/`.
**Do not delete these.** `context.json` is a private platform environment
snapshot for recovery; never publish it.

Stock restore keeps the old browser watcher disabled. It does not undo server
retirement, because stock Home does not need our server. A separate, hash-guarded
retirement reversal is documented in
[findings 13](../../docs/models/55A7KAU/V0000.09.09O.P1015/findings/13-native-boot-and-retirement.md).

## Source and build

- `free-my-tv-native.js`: Vue frontend, based on upstream's offline web design.
- `native-platform.js`: direct SDK data, readiness/events, APC launch, inputs,
  Settings and lifecycle cleanup.
- `native-entry.js`: replaces only the original main Home component.
- `third-party/free-my-tv/`: MIT license and precise upstream attribution.
- `build-native.cjs`: combines these with a pinned private stock launcher bundle.
- `native-home.cjs` / `native-update.cjs`: install, safe update, stock restore.
- `patch-native-bootstrap.py` / `retire-native-bridge.cjs`: exact, reversible
  extra-server boot-block removal and runtime archival.

Build locally (never commit the vendor-containing output):

```sh
node tools/launcher-host/build-native.cjs \
  firmware/55a7kau-09.09o/native-analysis/launcher-app.js \
  firmware/55a7kau-09.09o/native-candidate.js
```

The original bundle must match the pinned SHA256. It is not included in Git.
Stage a complete candidate privately on the TV, verify its hash, then invoke:

```sh
LD_LIBRARY_PATH=/lib:/usr/local/lib:/basic/lib \
  /opt/pkgs/tv.vidaa.app.phoenix/bin/phoenix \
  /var/local/alvidaa/native-free-my-tv-v2/native-home.cjs update /path/to/candidate.js
```

Do not rerun the original fresh-install path over an existing backup directory.
Updates journal previous bytes/cache directories and preserve the original
stock backups. They require checked hashes and a stopped engine for mutation,
then use `secure_exec hisenseUI /opt/hisenseUI/startgui.sh` with the captured
platform environment. Failed startup attempts recovery to the prior candidate.

Only compiled/uncompiled JS caches are swapped. Origin storage, read-only
partitions and `/OAD` are untouched. These tools are pinned to this TV/build,
not a generic VIDAA installer.

`native-launcher.js` is the historical N02 prototype, not the current frontend.
`native-trial.cjs` supplies backup primitives, but its old trial CLI remains
**disabled**: APM did not restart the killed UI in that experiment. Never
re-enable it unchanged. Phoenix requires explicit `process.exit(1)` for reliable
failure status; `process.exitCode` alone was ignored on this firmware.

## Verification

```sh
NATIVE_VENDOR_537=firmware/55a7kau-09.09o/537.js.orig \
  node --test tools/launcher-host/native*.test.cjs \
  tools/launcher-host/stock-ui-restart.test.cjs
sh -n tools/launcher-host/home-control.sh
./scripts/check.sh
```

54 tests pass with the private loader fixture. Without it, that loader test
skips. No vendor code is redistributed by the tests.

Device evidence includes populated SDK lists, local icons, Settings navigation,
HDMI switching, Home return, Input-key routing, themes, stock restore/native
reapplication, and a fresh kernel/startup cycle with root intact and port 8770
closed. That fresh start required the operator to turn the TV on after the
restart request. Do not assume a reboot command wakes it unattended.

Still requiring physical acceptance: exhaustive remote buttons, microphone,
audible accessibility, kids/game flows, mains-power cold boot and complete
standby/wake behavior. A black Netflix HAL capture is inconclusive, not proof
of working playback or a native-launcher failure.

[Plan and implementation record](../../docs/launcher/FREE-MY-TV-NATIVE-PORT.md) ·
[Port findings](../../docs/models/55A7KAU/V0000.09.09O.P1015/findings/12-free-my-tv-native-port.md) ·
[Fresh-start/retirement findings](../../docs/models/55A7KAU/V0000.09.09O.P1015/findings/13-native-boot-and-retirement.md)
