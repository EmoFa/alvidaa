# 05 — Fetcher re-check: findings/04 was a false negative — write primitive is OPEN (2026-11-06)

Loaded `launcher/recon-fetcher.html` in the TV Browser app
(`http://10.0.0.157:8770/recon-fetcher.html`; TV at `10.0.0.173`). This
re-ran the bridge probe with the *correct* primitive and arg shapes after
the caveat in [findings/04](04-bridge-recon.md).

**Result: the `fetcher` write primitive works. Both marker writes returned
`ret:true, "download finished"`. The 100U7Q chain is back on the table; it
was never actually blocked — findings/04 tested the wrong surface and the
wrong argument shape.**

## What findings/04 got wrong

Two independent mistakes, both now measured:

1. **Wrong surface.** `launcher/recon.html` called
   `HiUtils_createRequest("fileRead"/"fileWrite")` — the `hiutils` service.
   The 100U7Q chain's write primitive is the **`basic/fetcher` FaaS
   `fetchFile`** (a different service; see 100U7Q `EVIDENCE.md` correction
   C1). The recon never started `basic/fetcher` over
   `wss://localhost:9888` (its `selfStart` is `false`), so it could not
   have exercised the primitive.
2. **Wrong path shape.** `hiutils.fileRead` rejects a bare string path
   containing `../` with `invalid path:…`. The working records
   (`tools/a6q/readone.py`, `probe6.py`, `deploy_pfm.py`) pass the path as a
   **one-element array** (`path: ["../var/local/…"]`), which traverses
   correctly on this build.

## Environment (same session)

```
UA:      … Chrome/111.0.0.0 WebNavigator/8.3.10 Safari/537.36
vowOS:                    object
vowOS.service.syncExecute: function
HiUtils_createRequest:    function
WebSDK_createFileRequest: undefined
Hisense_* functions:      99
```

`vowOS` is present on this build — findings/03 did not test it (it only
tested `WebSDK_*`, which is absent).

## Service start

```
wss://localhost:9888  →  opened, start sent
{"path":"phoenix://service/basic/fetcher","method":"start",
 "parameters":{},"session":901,"timeout":10}
```

No registration error. The `503 "service register failed"` seen on the
passive `GET localhost:9009/` in findings/03 is the expected rejection of an
unregistered passive GET, not a blocker.

## Writes — `basic/fetcher` `fetchFile` (both succeeded)

Source URL: `http://10.0.0.157:8770/recon-captures/marker.txt`
(via `vowOS.service.syncExecute("basic/fetcher", {api:"fetchFile",
args: JSON.stringify({url, directory, permission:420})})`)

```
/APPS/.recon_fetcher_marker
  → {ret: true, msg: "download finished"}

/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/.recon_fetcher_marker
  → {ret: true, msg: "download finished"}
```

That is the chain's keystone, measured on this unit:

- arbitrary write as uid 314 works;
- the **package CHA tree is writable** — the `/APPS/pkgs/.../CHA/` write
  prerequisite is confirmed;
- the write target used by the 100U7Q installer (`functions/fetch/`, same
  tree) has an existing parent, so `sw2.js`/IPK placement is viable.

The first successful variant was the documented **args-as-JSON-string**
form. Object-args and the `http-9009` / `http-9888` routes were not reached
(the page stops at the first success per target) — untested, not failed.

## Reads — array path works, string path does not

| Path | Form | Result |
|---|---|---|
| `../proc/uptime` | `path: [p]` (HiUtils / vowOS / HTTP 9009) | **`ret:true`** → `29611.34 101883.42` |
| `../proc/uptime` | `path: p` (string, all routes) | `ret:false` → `invalid path:../proc/uptime` |
| `../var/local/otaTest.log` | `path: [p]` | `ret:false` → `ENOENT` on `/APPS/../var/local/otaTest.log` — **traversal resolved, file absent** |
| `websdk/Appinfo.json` | string or array, all routes | `ret:true` → `{"AppInfo":[]}` |

`hiutils` resolves relative paths against `/APPS/`, so
`/APPS/../var/local/…` normalises to `/var/local/…` and returns `ENOENT`
only because nothing created that file yet. Traversal is open.

Side observation: `websdk/Appinfo.json` reads back as `{"AppInfo":[]}` —
the tile registry is empty on this unit at this point (possibly the wrong
package's registry, or genuinely empty). Not acted on; recorded because the
launcher tile lane reads this file.

## What is still unverified

- **Superwatch socket reachability from uid 314 (group 616)** — not probed
  this run. Needs an in-process FaaS function to `connect()` to
  `/var/run/superwatch_socket`; that is the next write/exec step.
- **`/var/local` writability by uid 314** — not written this run (the
  read-only ENOENT says the path resolves, not that it is writable).
- **32-bit ARM userland (`EM_ARM`)** — still inferred from the 100U7Q, not
  measured here.
- The `RET` of `fetchFile` is the service's own report; disk readback of
  the markers was not done in this run (the next probe can read
  `../APPS/.recon_fetcher_marker` with the array form).

## State left on the TV (reversible)

Two marker files, no install, no postinst, no reboot:

```
/APPS/.recon_fetcher_marker
/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/.recon_fetcher_marker
```

Teardown requires an app-context unlink (a one-line FaaS function, or the
root lane once armed). Recorded here so no future session has to guess why
they exist.

## State change

- `capabilities.file_bridge_write` → **open** (FaaS `fetcher.fetchFile`,
  two markers, 2026-11-06).
- `capabilities.file_bridge_traversal` → **open with array path arg**
  (`../proc/uptime` read; string paths rejected).
- `capabilities.root` → **reopened — chain viable, not yet armed.**
- Findings/04 is retained as the historical record but is **superseded** by
  this note for the write/traversal conclusion.

## Next

1. Write a benign FaaS function into
   `/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/functions/fetch/` via `fetchFile`,
   invoke it through `/function/basic/fetch/<name>`, and use it to
   (a) `fs.unlinkSync` the two markers, (b) read `id`/`uname -m`/`/proc/self/exe`
   to settle the 32-bit userland question, and (c) `connect()` to
   `/var/run/superwatch_socket` with a read-only command (`85`, directory
   size) to settle the group-616 prerequisite — then delete itself.
2. Only if (c) is green: arm the 100U7Q `postinst` chain, with owner
   sign-off and the documented rollback.
