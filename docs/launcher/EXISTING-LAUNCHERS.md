# Existing launcher candidates for a native VIDAA port

Research only: nothing installed or changed on the TV. Repositories and source
files were inspected, not just search snippets. This snapshot is anchored to
the commits below; upstream branches may change.

## Bottom line

**Free My TV's web frontend is the strongest external starting point.**
It has a real DOM UI, older-TV-compatible CSS and a separate platform adapter.
It still needs a Cobalt port; it is not a ready-made VIDAA native launcher.

No independently verified, drop-in replacement for this TV's Cobalt Home
module was found. Reuse a project's frontend inside our working native module,
not its Android/Tizen/webOS installer, platform services or home interception.
Keep our verified app/input integration, lifecycle and stock restore path.

## Ranked candidates

### 1. Free My TV — best practical frontend donor

- [Repository](https://github.com/felipericardo/tv-launcher)
- [Visual preview](https://github.com/felipericardo/tv-launcher/blob/main/.github/preview.webp)
- Inspected: `f2d984c51edca1544e39f2d44cdf86b75b0b6703` (2026-10-24).
- Code license: [MIT](https://github.com/felipericardo/tv-launcher/blob/f2d984c/LICENSE).
- Features: app shelf/reordering, all-apps view, clock, light/dark themes,
  settings, screensaver, plus optional recommendations/weather/market data.

Important distinction: its **Android** UI is hand-drawn on Android Canvas.
The reusable part is the separate **webOS/Tizen `web/` frontend**, not the APK.

Source evidence:

- [`web/home.js`](https://github.com/felipericardo/tv-launcher/blob/f2d984c/web/home.js):
  DOM creation, TV navigation and view behavior (~1179 lines).
- [`web/home.css`](https://github.com/felipericardo/tv-launcher/blob/f2d984c/web/home.css):
  ~545 lines, explicitly avoids CSS variables, grid and backdrop-filter for
  older webOS TVs. Mostly absolute/inline-block layout, transform and opacity.
- [`web/tv.js`](https://github.com/felipericardo/tv-launcher/blob/f2d984c/web/tv.js):
  platform API adapter for app listing/launching, inputs, settings and Back.
- [`web/index.html`](https://github.com/felipericardo/tv-launcher/blob/f2d984c/web/index.html):
  app/clock/tiles are DOM, but background layers include two canvas elements.
- Canvas calls in home.js include logo processing (~130–187) and background
  rendering (~431). These cannot be carried into our Cobalt runtime unchanged.
- [`web/data.js`](https://github.com/felipericardo/tv-launcher/blob/f2d984c/web/data.js)
  uses XHR for external services including TMDB, Open-Meteo and Binance.

Port work (moderate; assessment, not a measured estimate):

1. Replace canvas background/logo processing with images or plain DOM styling.
2. Adapt `TV` operations to our on-TV bridge and native SDK; retain SDK key
   handling instead of adding competing window-level listeners.
3. Mount/unmount within our Home route; scope element IDs, timers and listeners.
4. Remove direct external requests for the offline baseline. Recommendations,
   weather and market data are not offline features; do not silently add them.
5. Test SVG, CSS masks, transforms, fonts and storage on Cobalt; pre-render icons
   where necessary. Old Chromium compatibility does not prove Cobalt compatibility.
6. Retain MIT notices and separately check font/image/icon asset permissions.

This is the best *external* donor; it is not necessarily less work than porting
our existing browser design, whose desired features and integration are known.

### 2. Aura TV — visual donor, not a verified native replacement

- [Repository and demo](https://github.com/cralex11/aura-tv)
- Inspected: `9ab04c1bb273a354e10bb46d044b7f2293b0fff6` (2026-10-27),
  identified as an initial release.
- README declares MIT; no standalone LICENSE file was present in the snapshot.
  Clarify/retain the licensing grant before incorporating its code or assets.

A single ~1158-line HTML page has a styled app interface and remote navigation.
No canvas calls were found in that page. But it uses extensive flex/grid,
SVG and Web Audio, all needing Cobalt testing or substitutions.

Crucially, [`index.html`](https://github.com/cralex11/aura-tv/blob/9ab04c1/index.html)
launches URLs with `window.location.href` (~1030, 1057, 1066). Its frontend has
no real app/source enumeration through Hisense APIs or our bridge. Sideloading
an app tile is not evidence of replacing the native Home module. README claims
such as “60FPS Native” are not measurements on our TV.

Use as a visual/layout reference only unless those gaps are implemented. Do
not use its injection tooling or bundled client material; our native integration
already solves the TV side.

### 3. FLauncher — good UI reference, expensive code port

- [Upstream](https://gitlab.com/flauncher/flauncher)
- [Upstream README](https://gitlab.com/flauncher/flauncher/-/raw/master/README.md)
- [Inspectable fork](https://github.com/zompinc/flauncher), examined at
  `9188d9b` (2026-07-11).
- License: GPL-3.0. Follow its redistribution obligations if deriving code.

A real Android TV launcher written in Flutter, with app categories, row/grid
layouts, ordering and wallpapers. Android/Flutter application code cannot run
as a Cobalt DOM module. Installing an APK on VIDAA is not a path here, and a
Flutter renderer is not a drop-in replacement for our shared UI shell.

Its design is worth borrowing; porting the implementation means replacing both
platform integration and rendering. Less practical than a DOM frontend.

### 4. Flex Launcher — genuinely native Linux, wrong integration layer

- [Repository](https://github.com/complexlogic/flex-launcher)
- Inspected: `cc0d98734518af897f6c2af86abd94d0790c0661` (2026-07-07).
- License: [Unlicense](https://github.com/complexlogic/flex-launcher/blob/cc0d987/UNLICENSE).

A TV-friendly application frontend for Linux/Windows PCs and Raspberry Pi.
Its [build](https://github.com/complexlogic/flex-launcher/blob/cc0d987/CMakeLists.txt)
requires SDL2, SDL2_image and SDL2_ttf. It launches host applications rather
than being a web module.

ARM support alone does not establish a working display/input backend on the
MTK vendor stack. A TV port would need graphics integration, TV app/source
control, Home routing and lifecycle management outside Cobalt. That reopens
problems our working native module already avoids. Better for an external
HTPC/Pi than this firmware.

### 5. KDE Plasma Bigscreen — complete TV desktop, not a small launcher port

- [Official project](https://plasma-bigscreen.org/)
- [Source](https://invent.kde.org/plasma/plasma-bigscreen)
- [Inspected mirror](https://github.com/KDE/plasma-bigscreen), `3ce7d9e`
  (2026-11-05).
- Mixed GPL/LGPL and asset licenses, recorded per file and under LICENSES.

A Wayland TV desktop with Qt/KDE/Plasma dependencies, remote input, settings
and applications. It is a whole desktop environment for HTPCs/SBCs, not
something we can load into the TV's existing Home engine. Not recommended
for this native-module approach.

## Other results worth excluding explicitly

- [Borealis](https://github.com/Alogus/Borealis), inspected `024ea5b`:
  based on Free My TV and includes web sources, but its own changes are
  [PolyForm Noncommercial 1.0.0](https://github.com/Alogus/Borealis/blob/024ea5b/LICENSE).
  This is source-available with noncommercial restrictions, not the same
  permissive licensing as the MIT upstream. Prefer Free My TV for shared code.
- [Zfinix/vidaa-launcher](https://github.com/Zfinix/vidaa-launcher), `ca622fd`:
  MIT canvas-based VIDAA browser launcher with a companion server. It has
  the same no-canvas native-port blocker as our existing polished browser UI.
- [ferdj40/samsung-tv-launcher](https://github.com/ferdj40/samsung-tv-launcher),
  `86a7231`: MIT HTML/CSS/JS examples in a README with images, not a complete
  packaged launcher source tree. Useful small examples, not a polished donor.
- [tsynik/LeanbackLauncher](https://github.com/tsynik/LeanbackLauncher), `77fd883`:
  Android/Gradle source, not a web UI; no top-level license file was found in
  the inspected snapshot. Not a better fit than the candidates above.

## Recommended decision

If choosing a pre-existing project, prototype **Free My TV's web frontend**
inside our current native module, offline first. Keep the installed N02 build
and stock backups untouched until a local port has removed canvas/external
requests and its basic rendering is ready for a supervised test.

No third-party install script, APK or binary was executed. No candidate was
deployed, and no claims of its performance on this TV are made.
