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
      Generated tables are never edited by hand. That now includes
      `docs/research/TESTED-MODELS.md`, which carries the full matrix; the
      README keeps a compact one.
- [ ] If this adds a model guide, it follows
      [`docs/models/_TEMPLATE.md`](../docs/models/_TEMPLATE.md) — including the
      **What this guide includes and leaves out** section.
- [ ] `./scripts/check.sh` passes locally.
- [ ] No private keys, certificates, tokens, device serials, firmware images
      or vendor binaries are included.
- [ ] Real LAN addresses and MACs are replaced with placeholders. If a capture
      names a third-party device on the network, redact it — it is not ours to
      publish.
- [ ] Every state change has a teardown path written down.

## Boundary

Read [`docs/DISCLOSURE.md`](../docs/DISCLOSURE.md) before submitting. The short
version: **findings and architecture are published; working payloads, key
material and vendor binaries are not.** Describe what property of the firmware
makes a chain possible, not the artefact that executes it.

## Evidence

<!-- What was measured, and what is inferred. "verified" means observed on
     your own device; say what the observation was (log line, file:line,
     marker after reboot). Keep unknowns unknown. -->
