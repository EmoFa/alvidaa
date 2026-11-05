## What this adds

<!-- One paragraph: which model, which firmware string, which result. -->

## Checklist

- [ ] The firmware string is copied character by character from the TV
      (`Hisense_GetFirmWareVersion()`), not from a model page, a shop listing
      or another PR.
- [ ] The device is in `docs/research/inventory.json` — or an existing entry
      was updated. **One firmware, one row.**
- [ ] The method observation is in `docs/research/exploits.json`, and
      `scripts/gen-inventory.py` + `scripts/gen-exploits.py` were run.
      Generated tables are never edited by hand.
- [ ] `./scripts/check.sh` passes locally.
- [ ] No private keys, certificates, tokens, device serials, firmware images
      or vendor binaries are included.
- [ ] Every state change has a teardown path written down.

## Evidence

<!-- What was measured, and what is inferred. "verified" means observed on
     your own device; say what the observation was (log line, file:line,
     marker after reboot). Keep unknowns unknown. -->
