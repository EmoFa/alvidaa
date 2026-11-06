# Free My TV attribution

Upstream: https://github.com/felipericardo/tv-launcher

Revision: `f2d984c51edca1544e39f2d44cdf86b75b0b6703`.

License: MIT, reproduced in [LICENSE](LICENSE) and embedded in the generated TV
bundle. Copyright (c) 2026 Free My TV contributors.

`../../free-my-tv-native.js` adapts `web/home.css` and the web frontend's
**offline/no-picks** design: For You header, navigation, large clock/date,
rounded glass shelf, brand-colour app tiles, light/dark appearance, all-apps
and input views, shelf customization and local preferences. Coordinates,
colours and typography derive from the upstream 1920×1080 design.

This is a Cobalt/Vue renderer port, not the unmodified webOS/Tizen page:

- Native SDK data/actions replace `web/tv.js`.
- Vue render functions and scoped inline styles replace browser DOM setup.
- No canvas logo processing, blurred-photo backgrounds, CSS masks or SVG.
- Local vendor icons are used when available, with text/brand-colour fallbacks.
- No upstream fonts, symbols, screenshots, Android assets or binaries shipped.
- `web/data.js` and Internet recommendations/weather/market feeds are omitted.
- Vendor Settings, remote handlers, screensaver/service infrastructure and
  kids/game pages remain vendor-owned, not rewritten as web substitutes.

Vendor code is combined locally from a pinned **private original backup** by
`build-native.cjs`. It is not distributed in this repository. The generated
bundle stays under gitignored firmware storage (or `/tmp` for tests).
