# Free My TV → native VIDAA Home plan

## Goal and constraints

Port the MIT **web frontend** of [Free My TV](https://github.com/felipericardo/tv-launcher)
(snapshot `f2d984c51edca1544e39f2d44cdf86b75b0b6703`) into the existing native
Cobalt Home module on the owned 55A7KAU, firmware V0000.09.09O.P1015.

Keep the polished layout, app shelf, navigation and useful launcher settings.
Keep the TV's **full original Settings UI and remote functionality**. This is
not a browser redirect or an Android APK installation. No PC/cloud dependency
for Home, app enumeration, input switching or root access. Streaming apps may
of course need their own Internet access.

Replace our Go HTTP/WebSocket/MQTT bridge with direct vendor SDK integration.
Keep the TV's own Phoenix/services, shared router, SDK and system modules.
Do not remove vendor infrastructure needed by Settings, inputs and apps.

Preserve root SSH, verified boot, OTA blocking, origin storage, ownership/modes,
original stock backups and explicit stock restore. Do not overwrite another
session's changes. No timed-trial controller or assumed APM respawn.

## Starting evidence (before the port)

- N02 rendered after reboot, but its Apps row was empty while the bridge API
  returned 46 apps. Its initial-snapshot-only design lacks readiness refresh.
- The bridge did boot; MQTT was connected. The watcher is disabled.
- Direct app/input/Settings contracts were found in vendor source, but have
  not yet been verified through our new adapter on the TV.
- N02 omits Source/KEYPAD_INPUT routing and rejects kids/game entry points.
  It is a prototype, not a full compatibility baseline.

See [measured findings](../models/55A7KAU/V0000.09.09O.P1015/findings/11-native-boot-data-and-sdk.md)
and [candidate research](EXISTING-LAUNCHERS.md).

## Delivery order

### 1. Native platform adapter — local implementation first

- Read app/source data through `sdk.me` and retain vendor metadata.
- Subscribe to initialization, list-change and resume notifications.
- Refresh immediately on activation, with bounded retry for missing data;
  late notifications must still recover after the retry budget expires.
- Stop timers/listeners when Home deactivates; prevent duplicate subscriptions.
- Open the original Settings page, not a replacement settings subset.
- Route inputs through `all-inputs.changeSourceTo`. Before enabling app launch,
  verify APC metadata and parental/hotel-lock behavior against vendor callers.
- No WebSocket, fetch, XHR, MQTT or localhost HTTP dependency in this adapter.

Acceptance: deterministic tests for boot-empty→ready, delayed events,
partial failures, stop/reactivate, input IDs and Settings calls. Tests are
mock contract checks, not evidence of hardware compatibility.

### 2. Complete the platform compatibility contract

| Area | Required handling / verification |
| --- | --- |
| Home, Source/Input | Preserve launcher route entry and input focus semantics |
| Arrows/OK/Back | Scope Home navigation to its active route and focus; do not swallow other UI keys |
| Settings/Menu | Retain original setting module, all menus and context-dependent behavior |
| Volume/mute | Leave volume-bar handlers intact; verify overlay and action |
| Dedicated app keys | Leave apc-service handlers intact; verify actual remote buttons |
| Power/standby/resume | Keep vendor ownership; verify Home recovery and refreshed data |
| Guide/channel/numbers/colours/playback | Map owners; pass through outside applicable Home navigation |
| Voice/accessibility/subtitles | Retain vendor handlers; verify relevant device features |
| Kids/game modes and parental/hotel locks | Preserve/delegate native entry points; do not silently reject or bypass |

Resolve kids/game preservation before shipping: investigate retaining their
vendor routes without restoring stock Home or its browser bounce. If that
requires a material architecture compromise, document it and obtain a decision
rather than quietly drop functionality. Do not claim full parity based on
source inspection alone. Do not invoke destructive settings for test coverage.

### 3. Adapt Free My TV's frontend

- Vendor only the frontend files actually used, pin their revision and retain
  MIT attribution. Audit bundled font/icon/image licenses separately.
- Retain recognizable layout, shelf ordering, all-apps view, clock, themes and
  useful local settings; distinguish launcher preferences from **TV Settings**.
- Replace canvas backgrounds/logo processing with supported DOM/local images.
- Remove external recommendations/weather/market requests from the offline
  baseline. No new third-party scripts or runtime CDN assets.
- Use native app/source data/actions; local cached icons or local fallbacks.
- Scope styling and listeners to Home; no global keyboard takeover or hidden
  stock root. Preserve proper activation/deactivation and overlay behavior.
- Test actual Cobalt support for SVG, fonts, masks, transforms and storage.

### 4. Safe update path for the installed native module

The current installer expects stock bytes and fresh backups. **Do not rerun it
unchanged** over N02. Add an update operation with:

- checked current installation hashes and operation lock;
- a separate prior-native candidate backup, retaining original stock backups;
- staged/validated complete candidate assets before stopping the engine;
- mutation only while the engine is absent;
- narrow compiled/uncompiled JS cache handling, never broad storage deletion;
- the verified secure_exec/vendor environment restart and checked liveness;
- rollback to the prior native candidate on failure, plus explicit stock restore;
- no bridge-health prerequisite once the candidate no longer uses the bridge.

Process liveness does not prove rendering. Supervised screenshot/remote checks
are required. Preserve private environment context and credentials off Git.

### 5. Device verification, then retire the extra server

1. Validate rendering, apps, inputs, Settings and remote controls with the new
   adapter/frontend, keeping the old bridge available only for recovery.
2. Stop the extra bridge temporarily and repeat checks, including local icons.
3. Verify root SSH and original stock restore; test cold boot and standby.
4. Inspect the actual deployed root bootstrap/installer. Remove both the Go
   bridge autostart **and its server.js fallback**, keeping root startup intact.
5. Archive obsolete runtime files reversibly; do not delete keys or backups.
6. Repeat cold boot with no PC servers and no extra launcher server running.

Never remove the bridge while the installed N02 UI still depends on it.
Simply deleting its binary is insufficient: bootstrap source starts a fallback
static server when the binary is missing.

### 6. Records and publication

Run adapter/UI/deployment tests and `./scripts/check.sh`. Record device results,
failures and limitations in model findings as they occur. Update recovery docs
and PR24 only with measured claims; do not include vendor bundles, keys,
private platform context or unrelated working-tree changes.

## Implemented outcome

The port is installed. `native-platform.js` uses the direct SDK for data,
readiness events, Settings, input switching and APC app launch. APC re-resolves
metadata and retains vendor parental/EULA checks, never forwarding bypass flags.

`free-my-tv-native.js` implements the upstream offline clock/shelf design,
local cached icons, all-apps/input views, themes, shelf customization and native
screen-reader focus announcements. `native-entry.js` replaces only the original
main Home component: it retains other routes, guards, initialization and key
groups. Handled Home keys are consumed during bubbling before document-level
defaults; dialogs and unrelated keys retain the normal vendor handling.

The installer supports hash-guarded updates and returning to native after stock
restore. Actual stock restore and reapplication were exercised on the TV. The
extra bridge/fallback and their boot section are retired with reversible backups.
A fresh kernel/startup cycle returned root SSH and populated native lists with
port 8770 closed. The operator had to power the TV on after the restart request;
this is not an unattended-wake or mains-disconnect cold-boot claim.

54 local tests pass with the private loader fixture. Full repository checks
pass, including 108 rendered documentation pages using the optional Python
`markdown` dependency in a temporary host environment. See
[the current operator guide](../../tools/launcher-host/NATIVE-LAUNCHER.md),
[port findings](../models/55A7KAU/V0000.09.09O.P1015/findings/12-free-my-tv-native-port.md)
and [boot/retirement findings](../models/55A7KAU/V0000.09.09O.P1015/findings/13-native-boot-and-retirement.md).

## Progress

- [x] Plan and starting failure documented.
- [x] SDK adapter, APC/lock-contract review and UI integration.
- [x] Compatibility preservation strategy implemented.
- [x] Frontend port and MIT attribution.
- [x] Safe native-update operation and fault tests.
- [x] Measured device checks and actual stock recovery/reapplication.
- [x] Bridge/fallback retirement and fresh-start verification without a PC server.
- [x] Recovery and evidence documentation updated.
- [x] Native implementation/evidence update prepared on the existing PR24 branch.

Remaining **physical acceptance**, not silently assumed complete: exhaustive
remote buttons, microphone, audible accessibility, kids/game flows, mains-power
cold boot and full standby/wake behavior. A Netflix HAL capture was black and
is inconclusive for visible app startup/playback. Preserve these caveats when
reporting results upstream.
