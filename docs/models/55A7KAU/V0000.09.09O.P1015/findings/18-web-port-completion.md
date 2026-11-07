# Web-port completion work and remaining acceptance gates

This continues [the feed lifecycle trial](17-native-feed-lifecycle.md). It records
implementation and measured evidence, not a claim that every firmware feature
has passed acceptance. The operator subsequently turned the TV off; all release
work described as **offline** below was performed without contacting it.

## Populated upstream comparison

The preview harness now supplies synthetic recommendation artwork, Brisbane
weather/forecast and rising/falling/flat cryptocurrency prices to both the
pristine pinned upstream UI and the native adapter. It can capture individual
views, wait for actual cards/controls, preserve the first browser error and
choose the same screensaver artwork deterministically. Fixtures contain no real
credentials or account data.

The original image helper's direct resizing did not reproduce the upstream
canvas thumbnail. The correction uses mip-prefilter reductions, odd-extent
weights, premultiplied alpha, four-bit floored interpolation weights and floored
output. Regression cases include the reference green row
`[244,248,251,108,3]`, alpha edges and odd image bounds. Row-buffered conversion
and power-of-two shifts avoid a second full-resolution RGBA allocation.

Actual ARM measurements before the TV was turned off:

- 4K image: 7,521 ms initially, 3,921 ms after row buffering, **3,571 ms** finally.
- 4000×4000 image: **3,460 ms**, below the worker's ten-second processing budget.
- Six populated artwork comparisons: mean RGB difference 0.089–0.303;
  0.001–0.042% of pixels differed by more than 16 in any channel.

The final offline browser rerun, using the current offline frontend source:

| View | Mean RGB difference | Pixels differing by >16/channel |
| --- | ---: | ---: |
| Home | 0.092 | 0.008% |
| Shows | 0.095 | 0.005% |
| Weather/price drawer | 0.477 | 0.226% |
| Deterministic screensaver | 0 | 0% |

These are desktop-renderer measurements, not proof of pixel-identical Cobalt
rendering. Screenshots, generated artwork and proprietary bundles remain private.

Processor upgrades now reuse bounded, hash-checked raw artwork from exact previous
local cache URIs. Tests prohibit network access during reprocessing. Oversized
original photos can use an existing rendition of the same photo; image-map
changes invalidate cards independently of media metadata changes. An explicit
empty token selects offline recommendation mode instead of falling back to an
upstream default credential.

## Native Settings and lifecycle corrections

Owned Settings routes are decorated lazily, including nested/relative records
and resolved constructors. The adapter retains native guards, handlers, children,
confirmation/PIN flows, geometry, disabled opacity and setting values. Cached
VNode classes and teardown are ownership-checked; immutable records are skipped.

Two bugs were found on the actual TV rather than in desktop fixtures:

1. The route was `/*/setting/settings`, not `/setting/settings`. Scope now uses
   `sdk.router.parseRoute(...).moduleName`, including changing-page handling.
2. Native neutral BUI classes overrode light-theme inheritance. Scoped neutral
   text/background tokens were added to make the light palette readable.

A subsequent **offline** browser regression exposed a third issue: the broad
light text-role/neutral overrides could turn a semantic red warning into ordinary
`rgb(32, 36, 40)` text. The old deployed source fails the new test. The corrected
source removes broad text-role inheritance and excludes explicit semantic/inline
colors from neutral and selection overrides. A real desktop CSS-cascade test now
checks warnings, errors, inline colors, disabled opacity, transparent parent
surfaces and native high-contrast fallback. This correction is **not deployed**;
its selector support and final appearance still need Cobalt validation.

A read-only SDK audit established that native high contrast switches the body's
`v-normal-contrast` / `v-high-contrast` classes. **Every skin selector requires
normal contrast**, so native high contrast wins immediately. The native
`v-opacity-low` and `v-opacity-lower` classes use opacity 0.95 and 0.9. Gradients
now color native surfaces rather than placing an opaque layer behind them.
Neither accessibility preference was changed for this audit. Native high-contrast
and transparency transitions still require device acceptance; the latest dark
Settings surface was captured, but not every final light-theme submenu.

The web saver cannot activate while its scoped document is hidden by another
native route. Visibility transitions reset upstream state. A TV timezone change
recreates the upstream data scope only when Home is visible, preserving
preferences and avoiding repeated remounts or overlay-time recreation.

## Last live state, before the operator stopped TV testing

The diagnostic-free frontend was installed through the guarded, stopped-engine
Home controller:

- Home SHA-256:
  `d83a4e18b15211d5d5449c9b36a51e343d3ce68051a66f0b34377fb24a4f5b78`.
- Asset ID: `49e13fbfa4c41725e0cd`.
- Last observed engine PID: 21260; feed worker PID: 18264.
- Published context: 47 apps, `Australia/Brisbane`.
- Published image map: 96 mappings, zero image failures.
- Preference bytes restored exactly to `{"theme":"auto"}`; SHA-256:
  `7d0d11a3bd1cb34c10ed80bfbfdcf6286c9e1464f3ab494ad3a0a24711255a87`.
- Temporary Settings diagnostic outputs removed; TV returned to Home.

These are historical observations, not a claim that those PIDs remain alive
while the TV is off. The temporary preference repair and forced-theme probes
are not part of the production candidate.

## Offline release controller

`native-web-release.cjs` adds root-local verification, guarded upgrade, journaled
rollback and stock-Home/feed-hook teardown for an **already configured** native
Home. It is not initial root provisioning or a generic VIDAA installer.

The coordinator validates complete package hashes, ARM architecture, candidate
syntax, public asset membership, ownership, space and stable Home/boot state.
It preserves exact runtime backups and an independent recovery controller/helper,
stops only the owned worker, holds its kernel lock during runtime replacement,
and uses the existing Home lock and stopped-engine update path. Concurrent edits
are refused. Failed installation or worker startup restores the previous Home
and runtime before restarting a previously running feed. Failed recovery does
not start a mixed runtime. Keys, origin storage, caches and recovery candidates
are retained during teardown.

Local tests cover corrupt/incomplete payloads, path and symlink rejection,
rollback bytes/modes, concurrent edits, interrupted child transactions, failed
worker startup and failed recovery. The packager's fixture archive executes its
own verification command. Real private archives reproduced byte-for-byte. The
offline frontend now includes the semantic-color correction described above, so
it must not be confused with the last live frontend hash. The new coordinator
has **not been deployed or exercised on the TV**. It is not a cross-filesystem,
power-cut-atomic installation; an interrupted update may need explicit recovery
from its independent journal. See [release instructions](../../../../../tools/launcher-host/NATIVE-WEB-RELEASE.md).

Final offline checks: **138 Node tests**, including the desktop CSS cascade test
(no skips on this workstation); three packaging tests; Go tests with the race
detector; and the repository's generated-data, syntax, links, site and secret-scope
checks. The optional browser test skips explicitly when Chromium is unavailable.
The final private artifact contains 1,805 payload files:

- Offline candidate SHA-256:
  `63a452c1e3a150c69cc9fe99b6307648ac5075a9100226b9e5023fa0baae27e0`.
- Reproduced archive SHA-256:
  `e17b21196489000a3c213a8b9054a5d939c7a2c50bd76af26de36b28f12e2196`.

Neither artifact was transferred to the TV during the offline work.

## Residual bootstrap finding

Offline inspection of the saved installer confirmed that its older "phone home"
block is a **reverse-shell retry loop**, not merely a health notification. It
starts `phonehome.sh`, retries the operator LAN endpoint every five seconds and
would hand a shell to a listener at that address. The feed port did not add it,
but stopping the PC setup listener did not remove its boot configuration.

The launcher itself does not depend on that listener. Nevertheless, this is an
unauthenticated legacy recovery channel and must not be described as retired.
Leave it unchanged until independent root SSH survives the outstanding cold-boot
check, then retire it reversibly with separately guarded bootstrap changes.
The current feed-hook recovery journal hashes the whole installer, so an ad-hoc
edit would invalidate that recovery contract. Existing blocklist rules were not
changed; playback/network collateral is not cleared by the offline audit.

## Still outstanding

- Exercise the release coordinator's apply/rollback/teardown on the owned TV,
  with original backups available; it currently has offline evidence only.
- Validate final light/high-contrast/transparency behavior and remaining native
  restriction/accessibility/locale paths without bypassing their guards.
- Cold boot, standby/wake, physical voice/microphone, audible accessibility and
  subjective acceptance require the operator. A black Netflix HAL capture does
  not prove visible playback.
- Retire the legacy reverse-shell startup after independent recovery is proven;
  complete live blocklist/playback collateral checks.

No TV access or wake/power commands were used during the subsequent offline work.
