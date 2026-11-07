# Web parity and advanced-settings audit

The operator correctly identified that the first Free My TV adaptation was
not a one-for-one port. The new target is the **upstream web interface** at
`f2d984c51edca1544e39f2d44cdf86b75b0b6703`, confirmed as upstream HEAD during
this inspection. Live features are permitted subject to the stated privacy
expectation. Advanced VIDAA settings should also use the Free My TV style.

## What the first port omitted

Upstream web contains the actual Inter font, symbol assets, full Home Settings,
language picker, backdrop/pick rendering, drawer, weather/prices and screensaver
behavior. Its CSS explicitly avoids variables, grid and backdrop-filter for old
LG TVs. Those missing features cannot all be justified as Cobalt limitations
without testing. Canvas logo/background processing, mask symbols, SVG coin
icons and the variable font do require specific compatibility investigation.

No claim of faithful parity follows from the first implementation's 54 tests.
Those test its implemented subset and deployment safety.

## Content is not a personal-library feed

Inspected `web/data.js` fetches trending/recent releases from TMDB, filtered by
streaming apps, plus Open-Meteo weather and optional Binance prices. It does
not read Plex/Jellyfin libraries or viewing history. Selecting a pick launches
the streaming app, not necessarily the particular title.

No explicit telemetry/analytics SDK markers were found in the five inspected
web JS files. Third-party requests still expose IP addresses and their query
parameters; TMDB needs a personal API key and weather sends coordinates.
Neither third-party logging nor retained vendor services can be described as
telemetry-free on that evidence. The privileged browser must not be given open
Internet access to implement these feeds.

## Settings architecture: preserve behavior, replace presentation

The stock entry has 689 `focusName:` declaration occurrences and 272 distinct
literal path strings, including conditional/model-specific code. These are
not counts of visible settings on this television.

The ordinary route `/setting/settings` loads JS chunk `2842`, module `lnK6`.
Read-only captures of that renderer and its CSS were stored under the private
firmware analysis directory:

- JS SHA256: `65b4b8a0e496d9d92aa80080a13c02809e5125766f5922401e4055a4d6847216`
- CSS SHA256: `4c39472497a8a4c72435280909beb551b4e6c1a6f73d88f53cfc516beaf19268`

The main component owns the settings tree/stack, selected first-level category,
current level, child initialization, promise-based enter callbacks and focus.
It also owns an energy-consumption confirmation before picture changes.
**It indexes `$children` by menu level:** injecting extra Vue component children
can silently break navigation. Presentation changes must preserve that contract.

The original opening helper checks kids mode and resolves visibility/disabled
states. Shared single/double/radio/switch/ESN item components are separate from
specialized network/PIN/channel-scan and other routes. Do not bypass their
checks with a guessed collection of low-level setters, or claim that styling
the main panel covers every dialog.

No remote keys, hardware setting changes, service starts or Home replacement
were performed during this inspection. The installed working adaptation is
unchanged. Full parity implementation and Cobalt capability tests are pending.

## Screensaver contract discovered during adapter work

Upstream `TV.holdScreenSaver()` receives a **predicate function**, not a boolean.
It allows the vendor saver when a sheet is open or photos are unavailable.
Treating that function as truthy would create a permanent inhibitor.

The retained stock launcher requests `n2o://screen-saver/art-start-screensaver`
with a `beforeStart` callback. The existing `screen-saver` module honors model
limits, an explicit disable file, the configured system timeout, resume state
and kids mode. It uses a shared `setArtScreen` timer. A native owner must not
clear that shared timer on teardown after another page may have replaced it;
invalidate its own callback and remove only its own subscriptions instead.
The original launcher's module-init handler can also arm this timer, so the
adapter must account for initialization ordering.

`native-web-screensaver.js` uses this existing request contract and leaves
hardware settings untouched. Its predicate/release/failure behavior has unit
tests; physical idle/saver behavior remains unverified until integration.

The detailed requirements and acceptance gates are in
[the web-parity plan](../../../../launcher/FREE-MY-TV-WEB-PARITY.md).
