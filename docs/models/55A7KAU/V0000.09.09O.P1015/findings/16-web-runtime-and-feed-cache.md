# Faithful web runtime and private feed boundary — implementation evidence

This records work in progress, not completed parity. A reversible web-runtime
trial is now installed and has rendered live cards, icons, the drawer and Home
Settings on the actual TV. A presentation-only Advanced TV Settings skin also
rendered and navigated successfully. Boot integration and full acceptance are
still unfinished. The earlier candidate and original stock
backup remain available through the existing recovery controller.

## Actual upstream presentation

The pinned web package is imported from Git objects, not a potentially modified
working tree. `native-web-program.cjs` verifies every public source digest,
compiles the original Home/settings/shelf/language code, namespaces IDs and
selectors, and converts the fixed template into a validated DOM tree. No
untrusted HTML is inserted. The native component retains the original launcher
factory, guards and non-Home routes.

Cobalt drawing substitutions are explicit: raster symbols instead of masks/SVG,
background-image elements instead of unsupported image/canvas operations, and
static Inter instances with optical sizes 14–32 instead of variable fonts.
The font builder renames modified fonts and preserves their OFL notice.
Instancing changes weight class but leaves the original Regular style bits;
the builder explicitly fixes bold style metadata to avoid synthesized bold.

The actual cached-icon filesystem is
`/APPS/channelA/hisenseUI/var/local/storeAppIcon`, corresponding to the measured
`file:///hisenseUI/var/local/storeAppIcon/…` URI. `/var/local/storeAppIcon` and
`/var/local/hisenseUI/var/local/storeAppIcon` do not exist on this firmware.
The read-only check found approximately 315 MB available on `/APPS` and the
installed Home still matched SHA256 `9f121cb6efc5d5ade10812196fbbc5795163e6865206c3aa3dc8e92847d97014`.

## Feed privacy and isolation

The replacement read token was verified with a host-side read-only TMDB request
(HTTP 200). It remains in permission-restricted, gitignored `server/keys/` storage.
It is never included in the browser bundle or screenshot fixtures.

**Upstream trap:** `sourceStamp()` persists `KEY.length` and `KEY.slice(-6)` in
its recommendations cache. Publishing that cache unmodified would disclose a
credential fragment. The native compiler replaces the stamp with a non-secret
region/app-availability stamp. Legacy credential-bearing stamps are removed
before publishing snapshots. Regression tests cover both paths.

`native-feed-engine.cjs` runs the pinned data selection/formatting logic outside
the privileged browser. The HTTPS client restricts methods, hosts, paths and
query shapes, refuses redirects, bounds response sizes and total request time,
and discards non-200 bodies and credential-bearing responses. The frontend's
network refresh is replaced with local context IPC and snapshot ingestion; it
has no API token and cannot fall back to direct external feed requests.

**Global binding trap:** `zones.js` declares `var ZONES`, relying on a browser's
global variable/window equivalence. An isolated function or Node VM with a
separate `window` object does not provide that equivalence. Both native paths
explicitly bind `window.ZONES = ZONES`. Unknown locations do not silently trigger
New York weather or US recommendations.

The AU firmware's location enumeration is NSW/ACT, QLD, SA, NT, WA, VIC, TAS
(values 0–6), read through
`kilby.sl2.i32.basic.settings.tvset.location.australia`. The adapter maps these
to the corresponding IANA zones; actual on-TV resolution still needs runtime
verification. No IP geolocation or hardware preference writes are involved.

## Visual harness traps and limits

The local-only Chromium harness renders both implementations from the same
pinned source, fixed date, sample apps, timezone and preferences. It reads no
credentials and makes no external requests. Seven views have rendered: Home,
Home Settings, drawer, All Apps, language, shelf editor and night Home.

- Injecting source with a string replacement interprets JavaScript `$'` tokens
  as replacement syntax. Use a replacement callback when embedding source.
- Namespace body-state selectors as root states, not descendants. Initially
  `.no-picks` was treated as a descendant and the native clock disappeared.
  Visual inspection caught this despite a small whole-image pixel difference.
- Successful screenshot creation is not success: check readiness and script
  errors, then inspect and compare the image.

Desktop renders are not Cobalt acceptance. Physical voice/accessibility and
mains-power tests still need operator participation.

## First real web-runtime trial

The baseline was checked immediately before staging: boot ID
`9aee6ea9-fd07-4cfa-bda1-b3a88e710bd6`, installed hash still `9f121c…97014`,
and approximately 315 MB available on `/APPS`. No existing public cache or
private feed credential was overwritten. The replacement token was provisioned
only into `/var/local/alvidaa/server/keys/free-my-tv.json`, root-private.

- Private worker/candidates: `/var/local/alvidaa/native-web-v3/`.
- Cobalt assets/media: `/APPS/channelA/hisenseUI/var/local/free-my-tv/`.
- **Separate Phoenix IPC:** `/APPS/free-my-tv/`, owned by UID/GID 314, mode 755.
- Advisory worker lock/PID: `/var/local/alvidaa/native-home/free-my-tv-feed.flock`
  and its `.pid` companion. The ARM helper holds a kernel lock across Phoenix
  exec; the real worker stayed alive with the inherited descriptor.
- **No new listener and no boot hook yet.** Cached Home can remain usable without
  the worker, but automatic fresh-feed startup after reboot is not established.

The first candidate was `58a7cb…afd323`. The corrected trial is
`4532389a3590f36cb2dadfcd8672ad18edb64a1d933767d4bbe28561cd364b2b`, installed via
the existing stopped-engine, hash-guarded update controller. The original v2
`candidate.js` was not replaced: `home-control.sh native` still reapplies the
previous working adaptation. `home-control.sh restore` retains stock recovery.

### Real-device traps caught and corrected

1. **Mode 6 is rooted at `/APPS`, not the Cobalt virtual image directory.** The
   Phoenix service is UID 314 and cannot traverse the vendor `hisenseUI` parent
   (750, UID/GID 305). Giving it a new IPC directory directly below `/APPS`
   resolves this without relaxing any vendor directory permissions. The root
   worker separately writes public image files in Cobalt's existing namespace.
2. **The native screensaver legitimately deactivates Home.** A missing IPC write
   did not retry after that deactivation. Returning Home with one announced key
   resumed the frontend and established real context/snapshot delivery.
3. **Cobalt ignores Date/Number locale options without throwing.** Date names
   became duplicated full dates and prices had unrounded digits. The compiler
   now supplies scoped locale primitives built from Intl for all pinned language
   catalogues, without modifying firmware globals/prototypes. Tests compare
   names, contextual months, day periods, grouping and rounding against Intl.
4. **A tag-replacement regex also matched `.img` classes.** This silently removed
   card image geometry. The compiler now distinguishes type selectors from class
   selectors, with a regression test. Offline screenshots had no cards and
   therefore could not expose this error.
5. **All upstream sizes matter:** large cards use `w1280`, small cards `w780`,
   backdrop sampling `w300`, and the screensaver `original`. The worker now
   caches all four, plus `w500` where requested. Original images remain bounded
   to 8 MiB compressed and 16 million decoded pixels; rejected images must not
   be represented as accepted parity.
6. **Go `[]uint8` JSON-encodes as base64.** Background RGB values must be numeric
   arrays; the processor now uses `[]int`, with a serialization regression.
7. **A journal saying installed is earlier than rendered readiness.** An early
   capture showed empty text/image placeholders; a later HAL capture established
   the completed render. Process checks alone are not visual evidence.

Observed on TV: 47 apps, nine real inputs, timezone `Australia/Brisbane`, weather,
prices, 24 recommendations, downloaded artwork and processed logos. Announced
remote navigation opened the full input/weather drawer and the upstream Home
Settings modal. The drawer showed Brisbane weather and all nine inputs plus
All Apps, Home Settings and TV Settings shortcuts. No hardware setting was
changed. Automatic theme is currently displayed; independent legacy-preference
migration/persistence acceptance remains open.

Host regression run: **94 passing, no skipped tests**, including the firmware
fixture and native image helper. The seven static desktop views also rendered;
transitions are disabled only in that comparison harness because virtual-clock
screenshots otherwise caught different animation phases. On-TV animation
acceptance is still separate. Publishing the source and evidence does not complete the remaining acceptance gates.

### Native settings presentation trial

The latest installed candidate is
`355b7d8b692ffa92091bf63966c0ec4daf27ea9352678f6ec0d837079a27726b`.
`native-settings-theme.js` decorates only the existing `/setting/settings`
component render and adds scoped visual CSS. It adds no Vue children, changes
no geometry/visibility rules, and keeps the factory result, route guards,
methods, events, native input bindings and specialized routes intact. Its
teardown restores only references it still owns. The existing v2 recovery
candidate remains untouched.

Real remote navigation opened the themed Picture category, moved to Connection,
and entered its native submenu. The focus, sidebar collapse, explanation panel
and underlying video remained functional. No hardware value was changed; the
last diagnostic key returned to Home. This is evidence for the main settings
surface and one submenu, not exhaustive acceptance of every dialog or PIN flow.
Four additional tests cover identity preservation, late loading, teardown during
an in-flight load, and unknown registry descriptors. Before/after HAL captures
remain local under `/tmp/fmtv-advanced-{before,themed,connection}.*`.
