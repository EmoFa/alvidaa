# Free My TV attribution and pinned web source

Upstream: https://github.com/felipericardo/tv-launcher

Revision: `f2d984c51edca1544e39f2d44cdf86b75b0b6703`.

Main license: MIT, reproduced in [LICENSE](LICENSE). Copyright 2026 Free My TV
contributors. The generated private TV bundle also includes this notice.

## Faithful web-port source

[`upstream/`](upstream/) contains the actual public web package and an
[integrity manifest](upstream/MANIFEST.json), not a recreation of its layout.
It includes the original HTML/CSS/JS, generated language catalogues, symbols,
icons and variable Inter font. Its generic configuration contains **no API key**.

Additional asset licenses:

- [Inter — SIL Open Font License](upstream/fonts/OFL.txt).
- [Material Symbols — Apache License](upstream/symbols/LICENSE-material-symbols.txt).

Reproduce/verify it using the pinned Git objects of an upstream clone:

```sh
python tools/launcher-host/vendor-free-my-tv.py /path/to/upstream-clone --check
```

For an initial import, omit `--check`; the tool refuses to overwrite an existing
snapshot. It archives the pinned commit into a temporary directory, so private
configuration, untracked files and working-tree modifications are not imported.
Keep this reference unmodified; native compatibility changes belong in the
adapter/build layer and must be tested against it.

This pinned source now drives the reversible on-TV web-port trial. **Complete
visual/behavioral and physical acceptance is still pending.** See
[the parity plan](../../../../docs/launcher/FREE-MY-TV-WEB-PARITY.md).

## Installed first adaptation (historical scope)

`../../free-my-tv-native.js` implements a simplified offline/no-picks adaptation:
clock, shelf, app/input views, local preferences and stock TV Settings. It did
not ship the upstream fonts, symbols, full presentation or live-data features.
It is **not a one-for-one port**. Its tests establish that subset and deployment
safety, not visual or functional parity with the upstream web interface.

Vendor firmware code is combined locally from a pinned **private original
backup** by `build-native.cjs`. It is not distributed in this repository.
Generated firmware-containing bundles stay under gitignored firmware storage
(or `/tmp` for tests). API credentials stay in private `server/keys/` storage,
never in this public reference or browser-facing responses.
