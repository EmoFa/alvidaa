# Free My TV native Home port

## Implementation and compatibility boundary

The port adapts Free My TV's MIT **offline/no-picks** web design into native
Vue render functions: For You heading, clock/date, app shelf, all-apps and
input views, themes and local shelf customization. No canvas, iframe, remote
recommendation feeds, browser redirect or extra launcher server is required.

Unlike N02, the new bundle retains the original vendor launcher factory and
replaces **only the `/Launcher` component**. Its route guards, other routes,
page entry points, initialization and original key groups remain. This keeps
kids/game pages and Source/KEYPAD_INPUT routing rather than rejecting them.
The original Home component is not mounted behind or underneath the new one.
This does retain vendor initialization/background behavior; it is not a claim
that all vendor code or telemetry has been removed.

The original SDK is a per-module singleton. Constructing SDK("launcher") again
returns that existing instance, including its storage prefix. Preferences
therefore use a distinct `alvidaa.freeMyTV` key instead of relying on a new
storage prefix to isolate them.

Apps and inputs come directly from `app-service` and `all-inputs`, with
initialization/change/resume subscriptions and bounded startup retry. App
launch re-resolves current metadata and invokes APC without bypass flags.
The retained apc-service interceptors own parental PIN, EULA and other checks.
No lower-level app-start or source-switch bypass is substituted.

## Device evidence so far

- First port update used the verified vendor restart wrapper: engine PID 6734.
- A HAL screenshot showed the new design, **47 apps and nine inputs** from the
  native SDK (the MQTT list had reported 46/six).
- Stopped only the extra Go bridge (PID 2192). TCP 8770 was no longer listening;
  root SSH and the vendor services remained running.
- With that bridge stopped, remote-key commands opened the full stock Settings
  screen. A second check navigated Picture → Sound → **Connection** and showed
  the normal Network, AirPlay/HomeKit, HDMI/CEC, Bluetooth and other entries.
  An earlier delayed check ran after the stock menu's timeout; it must not be
  misread as evidence that Home captured Settings keys.
- Native input selection switched to HDMI1, showing the Hisense HS218 source.
  Home returned to the custom frontend with populated lists.
- A Netflix launch was attempted through the native app tile. The HAL capture
  was black; that alone cannot establish successful app rendering or failure.
  Netflix's process existed, but it was already a persistent process. Do not
  claim playback or a fully verified Netflix launch from this evidence.
- **Actual stock restore was exercised:** engine PID 7704, stock Home visible
  in a screenshot, no watcher/browser bounce. Native Home was then reapplied
  from the same original backups (PID 7830), with lists populated and no bridge.

The remote checks used a temporary, one-shot host MQTT diagnostic client only
while the Go bridge was stopped, never two sessions sharing the credentials.
No host HTTP server was started. This verifies firmware-dispatched key paths,
not every physical button or Bluetooth microphone behavior.

## Icon and translation traps

- `all-inputs` can return translation IDs such as `LA0159` in `rename`.
  Resolve them with the vendor `sdk.i18n.t`, retaining a native-name fallback.
- app-service cached icon paths use `var/local/storeAppIcon/...`.
  The physical alias exists under
  `/APPS/channelA/hisenseUI/var/local/storeAppIcon`, pointing into
  `/APPS/hisenseUI_applications/UI/launcher/cache`; there is no corresponding
  `/var/local/storeAppIcon` physical directory.
- The initial HTML `img` rendering path did not paint those cached icons in
  this build. The follow-up renderer uses CSS backgrounds and explicit
  `file:///hisenseUI/var/local/storeAppIcon/...` URLs. This observation is not
  a general claim that every Cobalt img element is unsupported.
- Permit only local/cached/preset images, not HTTP icon URLs or the old
  bridge `/api/icon` endpoint. Text/brand-colour tiles remain a fallback.
- HAL capture is asynchronous: a two-second delay was insufficient once, and
  the image appeared after the first read attempt. Poll for the actual file;
  absence at the first read is not proof of a black screen or dead engine.

## Update/recovery and boot retirement

`native-home.cjs update` journals candidate, previous bytes and cache swaps
before mutation, refuses concurrent edits, and retains original stock backups.
Startup failure attempts to restore the previous candidate with a checked
vendor restart. Update also supports returning from an explicit stock restore;
that path re-establishes the stock cache backups for subsequent restores.

The deployed `/APPS/installer.ipk` was inspected. Its data payload contains
only the root Dropbear binaries and authorized public key, not the Go bridge
or static fallback server. The extra launcher-server startup is a separate
postinst section. The retirement tools:

1. remove only that section, leaving other IPK members and root setup intact;
2. independently verify the exact postinst transformation on the TV;
3. archive both the Go executable and `/APPS/launcher/server.js` reversibly;
4. require installed bridge-free Home, root SSH and no active 8770 listener;
5. preserve metadata and refuse changed package/runtime files.

This deliberately does not rewrite unrelated root-bootstrap diagnostics or
vendor services. Private IPK/bundle/screenshot artifacts remain gitignored or
under host `/tmp`; no keys, vendor bundles or private environment are published.

## Remaining acceptance checks

Software reboot, physical cold power cycle, standby/wake, full physical remote
coverage, voice/accessibility and kids/game flows require measured results.
Retaining vendor routes is a compatibility strategy, not evidence that all
those flows have been tested. Destructive Settings operations are not tested.
