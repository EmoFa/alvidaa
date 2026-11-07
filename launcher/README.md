# launcher/

What lives here, what is live, and what is a one-off.

The bridge serves this directory as the web root of the TV
(`/var/local/alvidaa/launcher/` → `http://127.0.0.1:8770/`), so **every file
path here is a URL**. Moving a file changes the address the TV has stored in
its app registry, which is why the layout is flat and the names are stable.

## Live

| File | URL | What it is |
| --- | --- | --- |
| `index.html` | `/` | **The launcher.** Single canvas, 1920×1080, clock + inputs dock at the bottom, one Apps tile that opens the app list as an overlay. This is what the TV loads. |
| `debug.html` | `/debug.html` | **Root Status.** Fetches `/api/debug` every 10s: bridge version, MQTT identity, hook version and kill-switch, disk, TV model/firmware. Bound to the launcher's Root Status tile. |
| `recon.html` | `/recon.html` | **Onboarding probe.** The read-only recon page that fingerprints a new model. `TESTED-MODELS.md` points at it, and it is installed as a TV app on the reference unit. |
| `alvidaa-remote.js` | `/alvidaa-remote.js` | The in-engine overlay script (Lane 2, legacy). Kept because the hisenseUI overlay path still references it. |
| `bg/`, `icons/`, `icon.png` | | Wallpapers, app-icon assets, launcher icon. |
| `hookinstall.html`, `hookcheck.html` | | Installer and verifier for the boot hook. Entry points, not diagnostics. |

## Staging

`next/` holds candidate pages that are **not linked from anywhere** and are
served only at `/next/…` for review. Nothing here is live until it is copied
over `index.html`.

## Probes

`probes/` holds one-off diagnostic pages: package-manager routes, superwatch
and switch-service probes, per-model recon variants, network checks. They are
kept because they document how a result was obtained, and they are **not**
linked from the launcher. If you are adding a diagnostic, put it here.

## The three launcher lanes

These are different products, not variants of one file. Do not merge them.

| Lane | Where | State |
| --- | --- | --- |
| **Canvas launcher** (Lane 1) | `index.html` here | **live** — browser page served by the on-TV bridge, watcher bounce, no root needed |
| **Native DOM Home** (Lane 2 / R6) | vendor route swap, see `docs/models/75U8QTUK/…/findings/09-native-home.md` | **proven on one unit** — replaces only `route[0].component` for `/Launcher` inside the writable `operation-ui` bundle; no bounce, no browser, stock Settings and key dispatch preserved |
| **Free My TV** | `tools/launcher-host/` | **merged, unverified here** — a specific product built on the native path (offline clock + shelf, local feed cache) |

The rule that keeps this clean: **a new launcher is a lane, not a file.** If it
shares the canvas page's data path, it is a change to `index.html`. If it runs
inside the vendor home engine, it belongs in `tools/launcher-host/` or a new
lane directory with its own README — never another `index-*.html` beside the
live one.

## Deploying

1. Back up the live page: `cp index.html index.html.bak-<date>` on the TV.
2. Copy the new file over `index.html`.
3. **Cache trap:** odin's compiled-JS cache is stale-by-URL. A same-filename
   push can serve the *previous* compile, and a query-string change on the page
   URL does not bust it. Use a different filename, or clear the cache.
4. Reload with `/api/open?url=http://127.0.0.1:8770/` and verify.
5. Rollback is the `.bak` copy.

Review aids on the live page: `?debug` (screen console), `?apps` (open the app
list on load), `?pan=0`/`?pan=1` (pin the view), `?noauto` (disarm
auto-switch), `?540p` (fallback resolution).
