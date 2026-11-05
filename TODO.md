# TODO

Open work, roughly in the order it should be picked up. Nothing here is a
promise; the repo grows by PR and this file is where the loose ends go so they
don't live in a chat log.

Rules that apply to everything below: the generated tables are never edited by
hand (`./scripts/check.sh`), every change needs a teardown path, and a claim
without a device observation stays labelled as a claim.

## Now — correctness

- [ ] **43Q60SEVS: record the `serviceList.json` backup path.** The guide says
      rollback is "full overwrite + file zeroing" but never says where the
      pristine copy lives. Reversibility is the design law — write the path
      (or state that the original was captured and where) into
      `docs/models/43Q60SEVS/V0000.09.60W.Q0612/README.md`.
- [ ] **Fix the double-region render.** `09.60W.Q0612 (EU_A)` renders as
      `… (EU_A) (EU_A (DEU))` in `EXPLOITS.md` because the id already carries
      the region. Rename the id to `09.60W.Q0612` and update the one
      `firmware_ref` that points at it. (Better: see *Keys, not labels* below.)
- [ ] **`install.html` success check.** `sw2ok = r.indexOf("true") !== -1`
      matches "true" anywhere, including inside a failure string. Have
      `writeFile` resolve `{ok: r.ret, text: …}` and test `ok`.
- [ ] **Name the two write primitives.** `TESTED-MODELS.md` describes
      `file_bridge_traversal` / `file_bridge_write` as *the* browser bridge.
      The FaaS fetcher (`basic/fetcher` `fetchFile`) is a different surface
      with different gating — PR #8 mislabelled it and would have advertised
      "traversal open" on a build where traversal was measured closed. Add the
      distinction before the next reporter hits it.

## Next — the launcher

- [ ] **Status app.** Replace the recon tile's everyday job with
      `launcher/status.html`: bridge up, MQTT paired, Dropbear on 8008, hook
      version, OTA blocked, DNS sinkhole, TV IP/model/firmware, launcher
      version — one dot and one "what to do" per row. Keep `recon.html` as the
      full-dump tab behind `?debug` (it is still step 1 of onboarding a new
      model, and `TESTED-MODELS.md` points at it). Read-only: no writes from
      the status page.
- [ ] **`/api/status` on the server, `/health` on the bridge.** The page cannot
      open a raw TCP connection, so "is Dropbear listening" has to be answered
      server-side — the Go daemon can dial `127.0.0.1:8008`. The Pi endpoint
      aggregates MQTT/pairing/hook state so the app still renders when the
      bridge is down. No key material, and remember the Pi port is LAN-reachable.

## Next — research structure

- [ ] **Generate the contributors table** in `README.md` from `tested_by`, the
      same way the matrix is generated. It is currently hand-maintained in two
      places (`README.md`, `docs/models/README.md`) plus the JSON — three copies
      that will drift.
- [ ] **Exploit catalogue refactor.** `EXPLOITS.md` is one 190-line page and
      every PR regenerates all of it, which is why #7 and #8 both conflicted in
      the same place. Proposed shape, cheapest first:
      1. **Keys, not labels.** Give each firmware a slug id
         (`09.60w-q0612-eu-a`) and a separate display label; `firmware_ref`
         points at the slug. Fixes the double-region bug and makes renames safe.
      2. **One source of truth per fact.** `capabilities.root` duplicates the
         `ipk-post-install` observation, and they disagreed for 43Q60SEVS until
         it was fixed by hand. Either derive capabilities from observations, or
         make `check.sh` fail when they contradict.
      3. **Primitives as a layer.** `primitives.json`: fetcher write,
         `/function` exec, superwatch socket, `serviceList` autostart, loader
         shadow, `rc.local` hook, USB key gate, browser bridge. Methods then
         declare `requires:` / `yields:` primitives. "Does it work on my TV"
         becomes "which primitives are present" — a much smaller test matrix,
         and it matches what the 43Q60SEVS dossier already argues: the
         load-bearing parts are framework-generic, the per-unit variables are few.
      4. **One page per method** (`docs/research/methods/<slug>.md`, generated)
         with `EXPLOITS.md` as the index only. Stops the whole-file conflicts.
      5. **Validation in `check.sh`:** enum membership, unique ids,
         `firmware_ref` resolution, and every local `sources[].url` actually
         exists (markdown links are checked today; JSON source paths are not).
      6. **A generated `DEAD-ENDS.md`** from every `outcome: failed` observation
         plus `limitations`. The negative results are the most useful page for a
         new reader and they are currently buried in prose.

## Later

- [ ] **Site: split the matrix.** The README table mixes verified rows with
      community reports; the site could render "verified" and "unconfirmed" as
      two tables from the same JSON, and the README could keep only the
      verified ones with a link to the rest.
- [ ] **75UR9S OTA freeze.** The record relies on the owner's settings-menu
      toggle. Write the router-side block down as the recommended steady state,
      and note that `/var/local/etc/resolv.conf` is a writable symlink — a
      control point *and* an attack surface for anything running as uid 314.
- [ ] **75UR9S boot persistence.** Candidates listed but untested:
      `appinfo.json` `Main: pkgapp://`, `run_phoenix.sh`, the systemserver start
      list. Compare against the 43Q60SEVS `serviceList` result — same firmware
      family, so the service manager may be the answer here too.
- [ ] **Launcher shadow package** via the `GET_PKG_DEST` gateway (measured
      feasible on 43Q60SEVS, not enforced). `SafeStart` and the 63.8 MB payload
      are the constraints; see the 43Q60SEVS guide's open follow-ups.
- [ ] **`EVIDENCE.md` for 43Q60SEVS.** The HE40 and 100U7Q pages carry a
      claim matrix with `file:line` basis; the new guide does not.
