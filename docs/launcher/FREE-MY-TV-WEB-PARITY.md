# Free My TV: faithful web port and styled advanced TV settings

## Requested target

The operator selected the **actual upstream web interface**, not an approximate
layout or the Android screenshots. Reference: `felipericardo/tv-launcher` at
`f2d984c51edca1544e39f2d44cdf86b75b0b6703` (also upstream HEAD when checked).

The earlier `e74be87` adaptation is **not** this target. Its passing tests
establish the implemented subset and deployment safety, not upstream parity.
Do not call the replacement complete until visual and behavioral comparisons
have been performed. The first adaptation remains the working recovery target
while this work is in progress.

The second requirement is a Free My TV-styled **advanced TV settings** interface.
Upstream Home Settings and VIDAA system settings are different surfaces:
upstream does not implement Hisense picture/audio/network/channel controls.
The latter is new integration work, not something already supplied upstream.

## Implementation approach

1. Reuse the actual upstream web presentation and behavior, rather than drawing
   a second approximation from screenshots. Preserve its layouts, measurements,
   Inter font, symbols, app artwork, transitions and Home Settings interaction.
2. Supply a native `TV` platform adapter for apps, sources, Settings, keys and
   lifecycle, using the already-reviewed VIDAA SDK/APC contracts. No browser
   redirect, iframe or PC-side runtime dependency.
3. Isolate upstream DOM, styles, storage, timers and keyboard listeners to the
   native Home component. Do not let upstream document/body styling or global
   key handling change other vendor pages or consume system keys.
4. Probe actual Cobalt support before selecting compatibility substitutions.
   Upstream already avoids CSS variables, grid and backdrop-filter. It does
   use canvas image processing/backgrounds, mask-based symbols, SVG coin icons,
   and a variable Inter font. Any necessary replacement must reproduce the
   appearance/function, not silently omit it.
5. Keep external data fetching out of the privileged TV browser. A bounded,
   allowlisted on-TV fetch/cache path is needed for live data and images.
   Cached content must remain usable offline; no arbitrary URL proxy, remote
   scripts, HTML injection, extra MQTT connection or PC requirement.
6. Rebuild advanced-settings presentation around the original settings state,
   navigation and control handlers. Preserve dynamic visibility, disabled
   states, kids/hotel restrictions, PINs, confirmations, accessibility and
   special-purpose flows. Do not reconstruct hardware writes from guesses.
7. Extend transactional deployment only for the additional artifacts actually
   required. Preserve all original backups, origin storage, root startup and
   stock recovery. No changes to read-only partitions or `/OAD`.

## Upstream parity checklist

- Home header, Explore/Movies/Shows tabs and three content picks.
- Icon-only Live TV, Inputs and Home Settings controls.
- Backdrop, day/night appearance, clock/date in no-picks mode.
- App shelf: ordering, scrolling, native launches and icon treatment.
- Drawer: real inputs/connection state, shortcuts, weather and prices.
- All-apps grid, focus movement, scrolling, pointer and remote behavior.
- Home Settings: language picker, temperature, theme, weather/prices toggles,
  per-coin toggles, shelf editor and TV Settings entry.
- Original language catalogues, loading/error behavior and offline states.
- Screensaver appearance and lifecycle, coordinated with native protection
  and sleep behavior rather than globally disabling vendor safeguards.
- Persistence and migration of existing theme/shelf choices without clearing
  unrelated storage.

## Live-content/privacy findings

The operator permits upstream-style live content, with the expectation that
it is not behavioral advertising, telemetry or personalized viewing tracking.
The inspected web data implementation uses:

| Service | Purpose | Request exposure |
| --- | --- | --- |
| TMDB API and image CDN | Trending/recent releases, filtered by installed streaming providers | IP, API key, language, region, provider/title queries |
| Open-Meteo | Weather and sunrise/sunset | IP and configured/time-zone-derived coordinates |
| Binance / Binance US | Optional price cards | IP and requested market symbols |

No explicit analytics/telemetry SDK markers were found in `home.js`, `data.js`,
`tv.js`, `strings.js` or `zones.js`. That is a source-audit observation, **not**
a guarantee that third parties do not log requests, or that retained vendor
services have no telemetry. No viewing-history account or Plex/Jellyfin library
integration is implemented by the inspected web feed code. Clicking a pick
opens the provider app; it is not a guaranteed title deep link.

TMDB requires the operator's own key. Never put it in a public bundle, commit,
screenshot or chat. Keep credentials under private `server/keys/` storage and
out of browser-facing responses. Live features must be individually disableable;
network failure must not prevent apps, inputs or settings from working.

## Advanced-settings integration evidence

The private settings entry bundle is about 809 KB. A textual inventory found
689 `focusName:` declarations and 272 distinct literal `path:` strings; these
are **not** counts of controls/screens visible on this model.

- Public settings entry: `sdk.me.req('setting').open('settings', ...)`.
- Original entry helper checks kids mode and resolves requested setting paths,
  including disabled/invisible entries. Preserve it.
- Main route registration: `/setting/settings`; the live SDK exposed
  `/*/setting/settings`. Resolve module identity through `sdk.router.parseRoute`,
  not a guessed path prefix. Its renderer loads chunk `2842`, module `lnK6`.
- That component owns `settingData`, `settingStack`, `firstLevelIdx` and
  `curLevel`, plus original focus, navigation, energy-consumption confirmation,
  promise-based enter handlers and child initialization.
- Its methods index `$children` by level. Adding arbitrary Vue component
  children can break focus and navigation even when a screenshot looks correct.
- Shared item renderers include single, double, switch, radio and ESN items;
  specialized network, PIN, scan and other dialogs are separate routes.

Prefer retaining these state/behavior contracts while replacing presentation.
A main-panel colour change alone does not satisfy the requested redesign, and
replacing that panel does not prove every specialized dialog has been covered.

## Acceptance and release gates

- Build a reproducible upstream reference at the pinned revision, with fixed
  time, viewport, language, theme and deterministic sample data.
- Compare each ported state against that reference, including both themes,
  settings, drawer, shelf editing, errors and no-picks mode. Record actual
  differences; never substitute a mock-test count for visual verification.
- Test native SDK actions, unhandled-key passthrough, listener/timer cleanup,
  late data readiness, restrictions, preference migration and feed isolation.
- Verify deployment faults and original-stock restoration before release.
- Validate on the TV with supervised checks; do not change picture calibration,
  network credentials, parental settings, scan channels, reset the TV or stage
  firmware merely to exercise controls.
- Label remaining physical checks explicitly. Keep the existing working UI
  until a candidate passes these gates.

## Status

Source/privacy and native-settings inspection and the authorized Cobalt probes
are complete; see [measured capabilities](../models/55A7KAU/V0000.09.09O.P1015/findings/15-cobalt-web-parity-probes.md).
The working launcher was restored and hash-verified after each probe. A genuine
upstream web reference has been built and rendered locally, with external DNS
blocked and no credentials.

`native-web-tv.js` now implements the upstream TV interface over the existing
SDK adapter, and `native-web-screensaver.js` coordinates the predicate-based
upstream screensaver contract with the vendor's existing timer/guards.
`native-web-scope.js` owns the frontend's DOM queries, keys and timers without
replacing firmware globals. `native-feed-http.cjs` supplies an off-browser,
read-only HTTPS transport restricted to upstream feed endpoints: no arbitrary
proxy, redirects, cookies or browser credentials. Responses have size/time
limits; error bodies and credential-bearing responses are discarded.

The actual pinned interface now runs in a reversible **on-TV trial**, with live
recommendations, cached artwork and processed native app logos, weather/prices,
the input drawer and upstream Home Settings. A passive capture also shows the
movie-art screensaver and clock. See [runtime evidence](../models/55A7KAU/V0000.09.09O.P1015/findings/16-web-runtime-and-feed-cache.md).
Credentials remain in private `server/keys/` storage, not browser bundles.

The presentation-only native settings skin has been exercised on the main panel,
Connection and Network views; real-device tests caught namespaced-route and
light-color override bugs. All skin selectors now yield to native high contrast,
and native opacity remains on the original surfaces. This does not prove every
final light submenu, specialized dialog, restriction, PIN or accessibility path.

The on-TV worker and isolated boot entry have been tested, including duplicate
starts and install → exact restore → reinstall of the boot fragment. Autostart
is configured; **cold boot is not yet verified**. See [lifecycle evidence](../models/55A7KAU/V0000.09.09O.P1015/findings/17-native-feed-lifecycle.md).
A deterministic private release packager retains root ownership, scoped
permissions and file hashes while excluding credential paths. The new root-local
upgrade/rollback/teardown coordinator has fault-injection and package tests but
has **not** been exercised on the TV.

Populated desktop comparisons now cover recommendations, Shows, weather/prices
and a deterministic screensaver; the latter matches exactly in that fixture.
Canvas-compatible thumbnail processing was measured on ARM within its timeout.
The launcher preference was restored and its exact original bytes hash-verified.
See [completion evidence](../models/55A7KAU/V0000.09.09O.P1015/findings/18-web-port-completion.md)
for measurements, the last deployed hash, and the separate legacy reverse-shell
bootstrap risk. Desktop results do not establish Cobalt or whole-platform parity.

Full device coverage, release lifecycle trials, persistence, cold boot/standby,
voice/microphone, audible accessibility, playback/blocklist collateral and
subjective acceptance remain release gates. No further TV access was made after
the operator requested offline work.
Publication of this trial does not establish completion. **This is not yet a verified perfect port.**
