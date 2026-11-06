# 04 — Bridge recon: fetcher traversal BLOCKED → chain dead-ends here (2026-11-06)

Loaded `launcher/recon.html` in the TV Browser app
(`http://10.0.0.157:8770/recon.html`). This is the first non-write-free
probe — it drives the phoenix `fetcher` to read files and to place a
marker. **Result: the fetcher rejects every file path. The 100U7Q
read/traversal primitive does not transplant to this build. Per the
AGENTS.md / README stop condition, the root chain is halted — no root
step attempted.**

Nothing persisted on the TV (owner-confirmed; marker `existed_before:
false` and never established). Fully reversible — no state left behind.

## Marker

```
path:           /APPS/pkgs/tv.vidaa.jsservice.basic/CHA/.recon_marker
existed_before: false
content:        null        (write never established / unreadable)
```

## File reads via the fetcher — all rejected

Every probed path returned `ret:false, "invalid path:<path>"`:

```
../usr/local/bin/openssh/startsshd.sh            → invalid path
../usr/local/bin/openssh/starttelnetd.sh         → invalid path
../usr/local/scripts/start-superwatch.sh         → invalid path
../usr/local/scripts/OEMfacstart.sh              → invalid path
../opt/hisenseUI/startgui.sh                      → invalid path
../APPS/pkgs/tv.vidaa.jsservice.system/CHA/package.json → invalid path
../APPS/pkgs/tv.vidaa.jsservice.basic/CHA/package.json  → invalid path
../var/local/otaTest.log                          → invalid path
../proc/uptime                                    → invalid path
usr/local/bin/openssh/                            → invalid path (../ prepended)
```

`hook: {}` empty. Zero `ret:true` across the whole run.

## Reading

- The errors are **path-validation rejections** (`invalid path:…`), not
  auth/registration errors. The command reached the fetcher's path
  handler and was refused — the fetcher is **normalising/validating paths
  and rejecting traversal** (both `../` escapes and the package-tree reads
  the 100U7Q chain relies on). On the 100U7Q reference build these reads
  succeeded; here they do not.
- Even a plain absolute marker write into the package CHA dir did not
  establish (`content: null`), so the **write primitive is not
  demonstrated** either.
- Net: the `fetcher`-based file bridge — the single prerequisite the whole
  chain hinges on — is **not usable on this firmware**. Same version
  *string* as the 100U7Q (`V0000.09.60I.Q0813`), but the fetcher behaves
  differently here, so the "byte-for-byte identical build" assumption from
  the handoff does **not** hold for the fetcher surface on this UK/EU_A
  unit (build tag `a20260731p`).

### Caveat (kept honest)

This probe exercised the fetcher via `recon.html` as shipped; it did not
separately prove a phoenix *session registration* succeeded first (the
passive `9009` GET earlier reported `service register failed`). A
registration failure would normally surface as an auth/register error, not
a per-path `invalid path`, so a patched/validating fetcher is the most
probable explanation — but a future session could re-confirm by
registering a session explicitly before the read, to rule out the
alternative before declaring the primitive permanently gone.

## Decision

- **STOP.** No `postinst` / root-arm step (README step 5) is attempted.
- The 100U7Q chain does not transplant verbatim to this unit. If root is
  still wanted here, it needs a *different* primitive, not this one —
  that's new research, not a transplant.

## State change

- `capabilities.file_bridge_traversal` → **blocked** (fetcher `invalid
  path` on all reads, 2026-11-06).
- `capabilities.file_bridge_write` → **not demonstrated** (marker never
  established).
- `capabilities.root` → **dead end via the 100U7Q chain** (halted at
  step 4; primitive unavailable).
- EVIDENCE: fetcher / traversal / write / root-endpoint rows updated.

## Next

- Nothing further on the root lane without a new primitive. The launcher
  product lane (serve pages to the TV browser, findings/03) is unaffected
  and still works. If revisiting root later, start by explicitly
  registering a phoenix session before re-probing the fetcher, per the
  caveat above.
