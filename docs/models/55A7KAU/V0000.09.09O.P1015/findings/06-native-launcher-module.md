# Native Home: replace the operation-ui module, not the shared root

Status: local candidate and contract tests only. No TV writes during this
investigation. The user confirmed that stock Home returned after the rollback
in [05](05-native-home-failed-test.md).

## Evidence from this TV's saved bundles

- `hisenseUI/static/js/app.js` is a webpack runtime. Its entry is `PCZl`,
  after chunks 630 (`sdk.js`), 389 and 537 are available.
- `537.js:PCZl` loads `../operation-ui/ipk.js` and `../system-ui/ipk.js`,
  awaits their `load()` methods, combines their `moduleConfig` objects, then
  calls shared SDK initialization (`etOk`).
- `sdk.js:etOk` initializes keys, focus, router hooks, domain handling, theme,
  TTS and the root Vue view, then initializes/enables the model, runs the
  startup queue and loads the remaining modules.
- `537.js:u28j` mounts `VIDAA_UI`: a shared router view with keep-alive and
  a cover router view. Replacing its root render with an empty div removes
  the view host, not just stock Home. This is a structural error in the prior
  patch, although it does not isolate every cause of that black-screen boot.
- `operation-ui/ipk.js` loads `apps/launcher/js/app.js` among other modules.
  The launcher entry registers `self._V_M_.launcher = () => ...`.
- That factory exports `name`, `version`, `meta`, `route`, `page`, `data`,
  `key`, `init`, and `reset`. Its main route is `/Launcher`, with
  `sourceInfo: {sourceStatus: "HIDE", appId: "206"}`, `isFull: true`,
  `isBgRecord: true`, `isBgTshift: false`, and `pathBelong: "launcher"`.
- `launcherHome` pushes that route. The factory creates
  `new self._V_SDK_.vre.SDK("launcher", {storagePrefix: "Launcher"})`.
  Other exposed pages are `kidsLauncherHome` and `gameLauncherHome`; data
  includes `launcherAppVersion` and `launcherDisableCecChange`.
- The original launcher `init` registers recommendation/carousel refresh,
  account/network/country changes and other background work. A route-only
  visual replacement would leave that initialization running.
- `537.js:gNlz` is the actual module loader. It invokes the factory, registers
  routes and default key handlers, then calls `init`; it optionally calls
  `reset`. Page and data access use the returned maps.

## Correction: where key-down comes from

On this bundle, `sdk.js:cTCn` installs capture listeners for standard
`window` `keydown`/`keyup`, constructs a custom `KeyEvent`, and dispatches
`key-down`/`key-up` to the focused element or body. Document bubble listeners
run registered default handlers; the SDK sends a result through its callback.

The earlier assertion that this dispatch necessarily lived outside JS was
wrong. Named constants are directly present: arrows 37–40, ENTER 13, HOME
36, LAUNCHER 547. Guessed alternatives such as 19 or 97 are other keys
(PAUSE and NUMPAD1), not evidence-based arrow/OK mappings. The new candidate
uses SDK constants and the module contract, not the old overlay handler.

## Local candidate

See [native-launcher.js](../../../../../tools/launcher-host/native-launcher.js)
and its [test/limitations guide](../../../../../tools/launcher-host/NATIVE-LAUNCHER.md).
It replaces only the operation-ui launcher entry, without loading its vendor
implementation. Shared shell and other modules remain intact. Its WebSocket
transport reuses the on-TV bridge, avoiding the earlier XHR assumption.

Six local tests pass with the private original 537.js fixture, including
execution of its actual module loader against mocked platform dependencies.
This is stronger than a mock-only factory check, but is **not** a Cobalt boot,
Vue/focus-manager integration test, or proof that lifecycle duties are complete.

No deployment occurred. Hardware rendering, display-plane transitions,
Home/Back behavior, standby/resume, kids/game modes, accessibility and measured
overhead remain unverified or unsupported. Timed rollback and narrowly scoped
cache invalidation must be settled before a TV trial; the watcher must be
controlled to avoid confusing an Odin launch with native Cobalt success.

Private bundle reads are saved under gitignored
`firmware/55a7kau-09.09o/native-analysis/`; vendor source is not published.
