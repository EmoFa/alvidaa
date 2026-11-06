# Native N02 cold-boot data failure and direct SDK integration

## Observed after the user rebooted

The user reported “bridge disconnected” and missing inputs/apps after reboot.
Read-only inspection found:

- Uptime about 954 seconds; native hisenseUI PID 349 was running.
- Root Dropbear PID 2139 and alvidaa-bridge PID 2192 had started.
- Bridge HTTP `/api/debug` returned 200 and reported MQTT connected.
- Bridge log recorded startup, MQTT connection and a local WebSocket client.
- `config.json` still had `watcher.enabled: false`.
- Subsequent `/api/apps` returned 46 apps; `/api/sources` returned six inputs.
- A HAL screenshot, without remote interaction, showed **NATIVE TEST N02**,
  status **Connected**, six input tiles, and an empty Apps section. It was not
  the older browser launcher.

Thus this observation is not evidence that the bridge failed to boot. It
confirms the custom native module survived this reboot, but not that its
cold-boot data handling is correct. Standby/resume remains unverified.

## Startup snapshot trap

N02 receives `hello` snapshots over WebSocket. It does not request another
snapshot when an initially empty app list later becomes available. The bridge
also snapshots on MQTT connection; successful later HTTP app-list requests
update its cache without broadcasting a replacement `hello` to existing UI
clients. An empty successful app-list response can be cached for 60 seconds.

The screenshot/API disagreement demonstrates stale UI data. An early snapshot
before the vendor app list was ready is a plausible startup cause supported
by this code path; the exact first response was not captured, so that timing
must not be described as directly measured. The user's earlier disconnected
message was not reproduced during inspection.

A fix must handle startup readiness and list-change notifications, not merely
assume that starting the daemon or waiting for MQTT proves UI readiness.

## Native does not require our MQTT/HTTP bridge

N02 replaced the renderer/module but reused the browser launcher's transport.
That was provisional wiring, not a requirement of running inside Cobalt.

The saved stock launcher and live vendor modules expose these contracts:

| Operation | Stock interface |
| --- | --- |
| List apps | `sdk.me.req("app-service").getData("getCurrentShowApps", "Launcher").result` |
| Resolve an app | `app-service.getData("getAppInfoByAppId", {appId, url: "", checkRange: 1})` |
| Launch an app | `sdk.apc.start(...)`, retaining app metadata, launch method and normal platform checks |
| List inputs | `sdk.me.req("all-inputs").getData("getAllInputsData").result` |
| Switch input | `sdk.me.req("all-inputs").invoke("changeSourceTo", sourceId, "launcher")` |
| Open stock Settings | `sdk.me.req("setting").open("settings", {vk: "T"})` |

The stock webpack aliases resolve to these SDK facilities. App launch is not
just a URL navigation: preserve the app ID, URL, store type and relevant APC
semantics. Do not bypass parent/hotel locks with lower-level calls.

Useful vendor notifications include `o2n://sdk/init-finished`,
`o2n://app-service/all-apps-changed`,
`o2n://all-inputs/inputs-data-changed`, and suspend/resume notifications.
Refresh on activation as well as changes, with bounded startup recovery so a
missed initialization event cannot strand an empty Home screen.

These contracts were verified in source, not yet exercised by a new native
adapter on this TV. Keep vendor services and shared modules; removing **our**
Go bridge does not mean removing Phoenix, the vendor SDK or TV system services.

## Settings and remote controls: what must be retained

The user's requirement for the Free My TV port is full existing TV settings
and remote functionality, not merely arrows and app launching. Preserve the
original Settings UI rather than recreate a small subset in the new launcher.

Source inspection identifies these owners:

- **setting**: Settings and Menu keys; picture, sound, aspect ratio, sleep,
  subtitle/audio-description variants, Bluetooth pairing and custom-button
  handlers. Its native settings routes remain installed.
- **volume-bar**: volume up/down and mute in a before-keydown handler.
- **apc-service**: dedicated app buttons via `REMOTERAPPKEYCODELIST`, using the
  platform app controller. Do not intercept these in the frontend.
- **launcher**: Home/Launcher **and Source/KEYPAD_INPUT** routing. The original
  Source handling opens Home focused on inputs; N02 omitted those registrations.
- **all-inputs.openAllInputPage** delegates back to the launcher input view;
  it is not an independent stock input popup that can replace that view.
- N02 currently rejects **kidsLauncherHome** and **gameLauncherHome**. That is
  a functional gap, not proof of full stock compatibility. Preserve/delegate
  those entry points before claiming parity.

Power/standby, Back, guide/channel/numeric/colour keys, voice, accessibility,
parental controls and context-dependent handling still need a complete map
and physical-device tests. Consume only the Home navigation keys in the
appropriate route/focus state, passing unrelated keys to vendor handlers.
Do not test destructive settings such as factory reset merely for coverage.

Private source snapshots for app-service, all-inputs, setting, volume-bar,
apc-service and coretv-service are under the gitignored firmware analysis
folder. No vendor bundles or private environment snapshots are published.

## Safe removal plan

1. Implement/test direct SDK app/input integration and startup refresh first.
2. Preserve stock Settings and remote routing; explicitly address the N02 gaps.
3. Port Free My TV's MIT web frontend without canvas or external-data dependence.
4. Validate with our bridge stopped, including icons, app/input/Home transitions,
   full settings access, remote controls, cold boot and standby/resume.
5. Disable/remove the extra launcher's boot-start path without touching root
   SSH persistence, then archive/remove its unused runtime files reversibly.

Do not simply delete `alvidaa-bridge`: the bootstrap source in
`tools/u7q/scripts/make_installer.py` falls back to `/APPS/launcher/server.js`
when the bridge executable is missing. Account for both paths and verify the
actual deployed installer before changing it. Also remove bridge-health
requirements from the native deployment controller once its UI no longer
needs the bridge. Keep existing stock backups and a tested restore path.

No UI files, daemon configuration or boot hooks were changed in this
investigation. Only temporary HAL screenshot output was written on the TV
and then removed; all other TV operations were reads/API queries.
