# Native Home customization: merged apps/inputs + CSS wallpapers

**2026-11-06, owner-authorized.** Follow-up to
[findings/09](09-native-home.md). The owner asked whether apps and inputs
could be merged into one list and whether the background could be changed.
Both are now installed and owner-verified. The component-only `/Launcher`
swap, vendor lifecycle, backups and the one-command teardown are unchanged.

## What changed

### 1. Apps + inputs merged into one

The shared frontend keeps separate `apps` and `inputs` views. On this model:

- `list()` for the **`All`** tab (view `apps`, top-nav button 2) returns
  `this.apps.concat(inputTiles)`.
- `list()` for **`Home`** returns the favorites shelf followed by the same
  input tiles — the Home shelf itself is now merged.
- **Down** from Home goes to the merged `All` list instead of the inputs-only
  view.
- The `Inputs` tab remains as an input-only shortcut/filter.

Input records have `sourceId` / `name` / `rename` / `icon`, while the shared
Vue renderer expects `appId` / `appName` / `img`. Rather than fork the whole
renderer, each input is wrapped in an **app-shaped tile**:

```js
{ appId: "__alvidaa_input__" + sourceId,
  appName: vm.sourceName(source),
  img: source.icon || "",
  __alvidaaSource: source }
```

The existing render path (labels, brand colours, icon lookup, focus, paging)
then works unchanged. `select()` detects `__alvidaaSource` and dispatches to
`_platform.changeSource(sourceId)` instead of `launchApp(appId)`. Input icons
are usually CSS class names (`v-ic-…`), so those tiles use the existing
text/brand-colour fallback. `announce()` works because the tile carries
`appName`.

### 2. CSS-gradient wallpaper picker

`Preferences` gained a **`Wallpaper:`** row (5th row). OK cycles
`None → Dusk → Ocean → Ember → Aurora → None` and persists the choice with
`theme` and `favorites` under `alvidaa.freeMyTV`. OK also calls
`_platform.refresh()`, so the old "Refresh apps & inputs" row's capability is
retained rather than dropped.

The wallpapers are low-alpha `linear-gradient(...)` values applied as a
**translucent overlay child prepended to the root VNode** (`position:absolute`,
full-screen, `pointerEvents:none`). Consequences:

- Pure inline CSS — **no files on the TV, no network requests, no canvas**.
  The install/rollback script and backup set need no changes.
- Theme-driven ink colours are untouched and every tile/text paints on top of
  the overlay, so both dark and light themes stay readable.
- Default is `None`, i.e. the original solid background; the change is
  opt-in.

The `All apps` button is relabelled **`All`** via VNode post-processing
(matching its `aria-label`); no shared-file edits and no top-nav count change,
so `clamp()`/`select()` index maths stays intact.

All of this lives in
`tools/launcher-host/free-my-tv-native-75u8qtuk.js`; the shared
`free-my-tv-native.js`, `native-platform.js`, `native-entry.js` and
`build-native.cjs` remain untouched for the 55A7KAU lane.

## Build and hashes

| | v1 (findings/09) | **v2 (current)** |
|---|---|---|
| bytes | 344249 | **350645** |
| sha256 | `226ac863ea26842fed0bb9872d74c00303d80131456cf53deb119c73bb793da0` | **`4d16613e9e174f61c4fead638324238069339d00807425e54f5b4eda5060efdb`** |
| md5 | `1f465e9bd834cd98dfcdbe5c904bd02f` | **`b6143b2dac510da56591685fb8d6972f`** |

Both are private (gitignored `firmware/75u8qtuk/`), built from the same
unmodified vendor bundle (sha256
`380d337ecbfa08487768b18cb8342630db1c2880c6e6c14811e6f7d1c72f2c8f`) by
`build-native-75u8qtuk.cjs`, which asserts that stock hash, parse-checks with
`vm.Script`, and only writes under `firmware/` or `/tmp/`.

Local tests before install: `native-platform-75u8qtuk.test.cjs` (5 groups)
and the expanded `native-home-75u8qtuk.test.cjs` (load-time, vendor icons,
merged list on `All`/Home, input dispatch, Down-from-Home redirect, wallpaper
default/row/cycle/persistence/refresh, theme cycling, render relabel + gradient
overlay) all passed. `node --check` on every added JS/CJS file and
`bash -n` on the switch script passed.

## Install path and a trap

`switch-home.sh install` deliberately requires **`app.js` to be stock**
(`46bdee5a…`) before it will overwrite. With v1 already installed, a direct
second `install` would fail. So the sequence used was:

1. Upload v2 over `/var/local/alvidaa/candidate-native-home.js`, refresh
   `candidate.md5` (verified byte-for-byte: TV md5 == local md5).
2. `MODE=rollback` — restores stock `app.js` + both original JS-cache dirs,
   restarts SystemUI. **This re-verified the teardown path on real hardware.**
3. `MODE=install` — installs v2, resets only the two JS-cache dirs, restarts.

Transcript:

```
rollback: captured env from pid=32471
          restored stock app.js and JS cache dirs
          OK mode=rollback old=32471 new=6125 ppid=6047 wait=1s
          app.js md5 now 46bdee5a72955cda19fd361bf2954f80
install:  captured env from pid=6125
          installed candidate; JS cache dirs reset
          OK mode=install old=6125 new=6756 ppid=6656 wait=1s
          app.js md5 now b6143b2dac510da56591685fb8d6972f
```

A future session replacing an already-installed candidate should either do
the same rollback→install pair or add an explicit `replace` mode to the switch
script. Do not relax the stock-hash precondition.

Independent post-check: SystemUI PID **6756**, `PPid 1`, `Uid/Gid 311:311`,
`CapEff 0000000000a05000`; `app.js` `350645` bytes, `305:909` / `0640`;
uptime continuous (no reboot); SSH alive on a separate connection; backups
`app.js.stock`, `compiled_js/`, `uncompiled_js/`, `js-cache.tar` all present.

## Verification

Two HAL screenshots (private, `firmware/75u8qtuk/screenshots/`):

- `native-home-v2.png` — top nav reads **Home / All / Inputs / TV Settings /
  Preferences**; Home shelf shows apps (YouTube, TV Browser, Freely Live TV)
  **and** inputs (PS5, HDMI2, AirPlay, Screen, HDMI3) in one row; status
  `Native · 11 apps · 10 inputs`.
- `native-home-v2-wallpaper.png` — after one OK on the Wallpaper row, the
  **Dusk** gradient is visible behind the same layout, text still crisp, focus
  highlight intact.

The owner confirmed the `All` tab shows one merged grid, the Wallpaper row
works, the gradient appears, and (from findings/09) apps, inputs, TV Settings
and app launch still work. The wallpaper preference persisted across the
restart.

## Teardown

Unchanged from [findings/09](09-native-home.md#teardown--rollback):
`MODE=rollback` restores stock `app.js` and both JS-cache dirs and restarts
SystemUI. Because the wallpapers are pure CSS and preferences live in the
existing `alvidaa.freeMyTV` localStorage key, no extra TV files were added
that rollback would need to remove. Rolling back also drops the customizations
(the stock launcher has no wallpaper picker or merged list).

## Ground rules

Same as findings/09: owner's TV, LAN-local, no DRM circumvention, no OTA
writes, `/` stays erofs with dm-verity green (only `/APPS` and `/var/local`
written), no reboot (root SSH is not boot-persistent), `server/pair.py` not
run, Sidee holds the single MQTT session, no device identifiers committed,
no push, no PR.
