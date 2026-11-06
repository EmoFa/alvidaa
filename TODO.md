# TODO

Open work, roughly in the order it should be picked up. Nothing here is a
promise; the repo grows by PR and this file is where the loose ends go so they
don't live in a chat log.

Rules that apply to everything below: the generated tables are never edited by
hand (`./scripts/check.sh`), every change needs a teardown path, and a claim
without a device observation stays labelled as a claim.

## Now — correctness

- [x] **`scripts/report.py`** — a scaffolder for the report flow: prompt for
      model / firmware / SoC / region, validate the firmware string, append to
      `inventory.json`, run both generators, run `check.sh`. Turns a 40-minute
      review into a 2-minute one, and stops the three mistakes both #7 and #8
      made (wrong tree layout, duplicate firmware row, mislabelled fields).
      *(done 2026-11-05 — id grammar validated against all 10 recorded ids,
      duplicate guard mirrors check.sh, full scaffold demonstrated in a
      throwaway clone)*
- [x] **Duplicate-firmware detection in `check.sh`.** Nothing currently says
      "this firmware already has a row" — which is how 43Q60SEVS nearly landed
      as a second entry for `09.60W.Q0612`. Normalise the string and fail on a
      collision. *(done 2026-11-05 — step 8/8: normalized-id collision +
      base-firmware model-alias layers; demonstrated exit 1 on a seeded
      duplicate, exit 0 on the clean tree)*
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

- [x] **Audio: the ALSA capture path was probed — the lane is dead on this
      model.** Result 2026-11-06 (`tools/audio/README.md` has the full
      record): `hw:0,0` opens, set_params and start succeed, then every
      `snd_pcm_readi` returns EIO. During playback **all ten PCMs stay
      `closed`** in `/proc/asound/card0/pcm*/sub0/status` — on optical
      (S-PDIF) and on the internal speakers alike. The TV's audio never
      enters a userspace ALSA stream: the `mad_pcm` nodes are the MStar
      decoder's internal interface, not the output mix. That kills
      **snapcast and librespot through ALSA on this model** — an
      architecture answer, not a build one, so the librespot task
      (issue #19) needs a different door or a different model. The probe
      and build script stay in `tools/audio/` as evidence and may behave
      differently on another SoC. One path is untested and labelled as
      such: audio played **in the TV browser** — odin declares
      `--alsa-output-device=default;hw:0,0;...`, so a web page might open
      a PCM a native app does not.
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

- [ ] **CODEOWNERS + a written definition of "verified".** Path ownership so
      regulars can merge their own model's docs; a short statement of what
      evidence clears the "verified" bar so reviewers are not re-litigating it.
- [ ] **Tag the launcher** (`launcher-v1.x`) and keep a short `CHANGELOG.md`.
      There is no version anywhere today, so nobody can pin or roll back.
- [ ] **Site: split the matrix.** The README table mixes verified rows with
      community reports; the site could render "verified" and "unconfirmed" as
      two tables from the same JSON, and the README could keep only the
      verified ones with a link to the rest.
- [ ] **75UR9S OTA freeze.** The record relies on the owner's settings-menu
      toggle. Write the router-side block down as the recommended steady state,
      and note that `/var/local/etc/resolv.conf` is a writable symlink — a
      control point *and* an attack surface for anything running as uid 314.
- [x] **75UR9S boot persistence.** `serviceList.json` autostart was the answer:
      `re_sshd` JS service in the basic jsservice package re-arms dropbear via
      the superwatch trigger at every cold boot. Verified 2026-11-06 (armed on
      first attempt, dropbear uid 0). See the 75UR9S guide's *Boot
      persistence* section — including the `nosuid`-on-every-persistent-fs
      finding that rules out SUID on this build.
- [ ] **Launcher shadow package** via the `GET_PKG_DEST` gateway (measured
      feasible on 43Q60SEVS, not enforced). `SafeStart` and the 63.8 MB payload
      are the constraints; see the 43Q60SEVS guide's open follow-ups.
- [ ] **`EVIDENCE.md` for 43Q60SEVS.** The HE40 and 100U7Q pages carry a
      claim matrix with `file:line` basis; the new guide does not.
