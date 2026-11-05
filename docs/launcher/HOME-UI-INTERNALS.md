# Home UI internals — the stock `hisenseUI` bundles

> Static reference for R6 (native DOM launcher inside the home engine).
> Everything here is derived from the pristine vendor tree by reading minified
> sources — no TV writes, no live probing. Behavior claims are marked as such;
> everything else is what the code literally says. Read
> [findings 12](../models/50A51HUV/09.01O.P0813/findings/12-overlay-and-cobalt-runtime.md)
> §1/§7/§8 first: this document complements it, it does not restate the
> runtime traps.

## Provenance

- **Source**: internal Forgejo, repo `kchauhan/alvidaa-firmware`, `main`
  (vendor tag `vendor-v09.01` lineage), sparse clone at
  `apps/channelA/hisenseUI/`. Extracted 2026-11-04, hashed 2026-11-05.
- **Calibration**: this tree is the vendor *backup* state, like the
  `jsservice.basic` IPK (see findings 03, static pass): it may drift from the
  copy running on the TV. The version metadata below matches the TV's
  recorded hisenseUI build (9.00.01.25.080417), which is the best available
  correlation; re-hash before relying on line-level details on a new
  firmware.
- **`index.html` drift**: the vendor-tree copy carries the project's R2
  canary (`<div id="alvidaa-canary">` after `</html>` — dropped by Starboard
  per findings 12 §2, but still a post-vendor modification). The pristine
  reference is `index.html.alvidaa-bak`.

| File | MD5 | Size |
| --- | --- | --- |
| `index.html` (canary-carrying) | `02318d98d71d3cc9029f8f410bc2665f` | 1.1K |
| `index.html.alvidaa-bak` (pristine) | `fe34aa5dfc43fb31ee414a6e9e38fc9f` | 1.0K |
| `static/js/sdk.js` | `8a599fc9088b3763fe9ab45a50918883` | 864K |
| `static/js/vendor.dll.js` | `9d5fab5dbb97706c721248f2c9528422` | 204K |
| `static/js/537.js` | `2161d6c8f045da8bdd082b82d16e7ba9` | 140K |
| `static/js/389.js` | `23fe1e7db073df4457f1837afe68a3f2` | 8K |
| `static/js/app.js` | `fab67c53b7e40ca8693c06d506889f02` | ~4K |
| `static/js/style.js` | `4acc2e7b4234b10de4a0ae3dd9038117` | ~4K |
| `static/js/mainWorker.js` | `c741d835e82584f64c16e76962f698cd` | ~4K |
| `static/js/{198,314,369,388,410,553,611,716,878,981}.js` | see clone | ~4K each |

## Load chain

`index.html` (pristine form) is one line: `<div id="app"></div>` plus, in
order, `vendor.dll.js` → `sdk.js` → `389.js` → `537.js` → `app.js` →
`style.js`, all before `</body>`. This is the loader that
[findings 12 §1](../models/50A51HUV/09.01O.P0813/findings/12-overlay-and-cobalt-runtime.md)
declares load-bearing: if `sdk.js` and `#app` do not initialize, the whole TV
UI wedges. Anything R6 does inside the home engine inherits that rule — the
stock loader is preserved, modifications are append-only.

`sdk.js`'s role is wider than "frontend": the home engine has no other UI
process — this bundle *is* the TV's home application (see §1 of findings 12
for the message-pump/superwatch/MQTT coordination framing and the gray-screen
failure mode).

## `sdk.js` — the home application (not a classic SDK)

Despite the name, `sdk.js` is webpack chunk `630` of a `system-ui` build: a
Vue 3 single-page application (~864 KB) with:

- **UI component library** — cards, hints, toasts, dialogs, focus/cover
  components, all styled with an emotion-like CSS layer and px2rem/rem2px
  helpers. Brand theming is built in: css-var sets for `default`, `loewe`,
  `regza`, `toshiba` (the same binary ships other brands — expect brand
  branches in code paths R6 touches).
- **The service layer** (below) — how the app talks to everything.
- **The key-input system** (below) — how remote-control keys arrive.

### The service layer: `me.req()` over the phoenix bridge

All service access funnels through one URL builder:

```
GET http://localhost:9009/{service|faas}/<service>/<api>?api=<api>&args=<urlencoded JSON>
```

with a `baas` variant that moves the trailing segment into the body
(`api: <last segment>`). This is the **same unauthenticated phoenix bridge**
documented in
[findings 03](../models/50A51HUV/09.01O.P0813/findings/03-bridge-internals.md)
— the home engine's own IPC bus runs over the HTTP service that any page the
browser opens can also reach (CORS `*`, no identifier header). Architectural
consequence for R6: a native DOM launcher does not need a new transport to
drive TV services — the stock app itself speaks `me.req()` over `:9009`, and
the JS-service side of that bridge is the `jsservice.basic` package
(findings 03, static pass). It also means the launcher's service traffic is
indistinguishable at the bridge from any other page's traffic — there is no
privileged caller identity at this layer.

Service modules observed (`me.req("<name>")` call sites, minified-source
derived): `live-tv` (13), `setting` (7), `launcher` (5), `air-play`,
`apc-service`, `ads`, `coretv-service`, `vidaa-plus`, `store-mode`,
`kids-mode`, `hotel-mode`. An exported name map additionally registers
`account`, `acr`, `appservice`, `appsetting`, `bluetooth`, `caservice`,
`cec`, `closedcaption`, `epg`, `eula`, `file`, `game`, `hisfactory`,
`karaoke`, `keyboard`, `miracast`, `mpctrl`, `netflix`, `network`,
`parentlock`, `passage`, `phoenix`, `picture`, `pkgapps`, `playfi`, `pvr`,
`region`, `satellite`, `security`, `servicelist`, `softupdate`, `sound`,
`source`, `streaming`, `system`, `theme`, `toast`, `tts`, `tvservice`,
`usb`, `video`, `volume`, `webapp`, `webbrowser`, `wisa` and others — the
full sub-service catalog behind the `system-ui`/`operation-ui` packages in
the same vendor tree.

### Key input: native glue dispatches `key-down` DOM events

Remote-control keys arrive as **custom `key-down` DOM events on
`document.body`** (capture phase). The app consumes them with capture
listeners plus `v`-directive bindings (`v-keydown`-style) that implement
spatial navigation: a `KEYMAP` of directions, `stopPropagation()` on
handled keys, focus-driven movement (`prev()`/`next()` over focusable
lists). R6 consequence: a native launcher rides the same event stream —
listen for `key-down` on body, no polling, no transport of its own. The
dispatcher is the native glue outside these bundles (it is not dispatched
by any code in `static/js`).

## `537.js` — the app registry and orchestrator

The 140 KB chunk carries the **sub-application registry**: the named apps
that mount into `#app` — `ui`, `uisdk`, `notification`, `show`, `search`,
`screen-saver`, `miracast`, `launcher`, `hint`, `hi-media`, `focus`,
`cover`, `cobalt`, `ambilight` — matching the `system-ui/apps/*` and
`operation-ui/apps/*` package directories in the vendor tree. Observable
orchestration:

- `me.req("launcher").open("launcherHome", …)` — the launcher is itself a
  service client; `"default source is Launcher"` appears as a fallback.
- Source-type routing: e.g. `"vidaa-channels"` with `"284"` resolves to
  Live TV — the same app ids the bridge's `applist` reports (the launcher
  overlay's tiles come from this catalog).
- The sub-apps are the operation-ui/system-ui JS packages loaded by
  phoenix's ServiceManager — the registry here is their front-of-house
  wiring.

## The rest of the chain

- **`389.js`** — JSEncrypt (RSA, `crypto.getRandomValues` based). Present
  for signed request flows; not a general crypto service.
- **`vendor.dll.js`** — shared vendor library bundle (the DLL reference in
  `app.js`'s runtime maps it as `vendorLibrary`).
- **`app.js`** — webpack runtime for the `system-ui:` build: chunk loader
  (`a.u = "static/js/" + e + ".js"`), lazy-chunk scheduling. This is the
  mechanism behind the ten ~4 KB numbered chunks (`198`…`981`): lazy
  feature chunks fetched on demand from the same origin — under Cobalt they
  come from the `cobalt_home` cache (findings 12 §7's stale-by-URL trap
  applies to them).
- **`style.js`** — second webpack runtime (style/CSS chunk loader).
- **`mainWorker.js`** — a separate webpack build (worker context); no
  service-layer markers observed inside.

## Config files

- `process.env.json` — build targets: `BRAND: HIS`, `AREA: NA`,
  `PLAT: 9602`, `VERSION: normal`, `BUILD_TARGET: tv`, `REPORT/WATCH/CACHE:
  false`.
- `versionInfo.json` — `version 9000125080417`, `versionName
  9.00.01.25.080417`, `otaVersion V0000.09.01I.P0802`, name `hisenseUI`.
  This is the string the `getUIVersion` bridge API reads (findings 03:
  `channelA/hisenseUI/versionInfo.json`).

## R6 implications (native DOM launcher inside the home engine)

1. **Transport exists**: drive services with `me.req()`-equivalent calls
   over `http://localhost:9009/service/...` — no new bridge, no MQTT needed
   for UI-state work. But remember the home-engine XHR ban
   (findings 12 §3): the stock app runs in the home engine too, so if its
   service layer is XHR-based, R6 pages that need service calls must
   reconcile that with the WebSocket-only rule — the stock app evidently
   lives within whatever limits the engine actually enforces, and findings
   12 §3 shows the engine wedges on preflighted cross-origin XHR from
   `file://`; same-origin `localhost:9009` GETs are the stock pattern.
2. **Input exists**: `key-down` capture events on `document.body`; spatial
   navigation is app-side (KEYMAP + focus lists), not engine-side.
3. **Mount point**: `#app` is the whole UI; the sub-app registry in
   `537.js` is the composition root. An R6 launcher that mounts as "just
   another sub-app" follows the vendor's own extension pattern.
4. **Never break `sdk.js`**: findings 12 §1's rule is structural — this
   bundle is the home application, not a library the launcher can skip.
