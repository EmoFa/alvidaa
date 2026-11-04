# alvidaa findings — operations

> Split from the original FINDINGS.md lab notebook. Canonical record; the blog and STORY.md draw from these.

## 8. Operations

- Run the server on an always-on host (the Pi here — the original
  vidaa-launcher author's launcher died every time his Mac slept).
- The page degrades gracefully: server down → clock keeps drawing, tiles show
  dead state, auto-reconnects (exponential backoff capped at 8s).
- `keys/` (certs, tokens.json) must never be committed.
- Preset apps (TV Channels, VIDAA Kids, APP STORE…) cannot be truly deleted
  via known APIs — this launcher hides them via `config.json` instead.

## 9. Open questions (pre-root baseline, updated post-root)

- ~~True deletion of preset apps~~ — superseded once root landed: `Appinfo.json`
  and the stock UI code on `/APPS/channelA` are directly addressable (see
  [09-endpoints.md](09-endpoints.md)).
- ~~Boot-time takeover via `Appinfo.json` "preset" slot~~ — superseded by R2:
  `hisense_stage0.sh` and `startgui.sh` launch the stock home webpack SPA from
  `/APPS/channelA/hisenseUI/index.html`, which is the cleaner native-home shim
  target (see [LAUNCHER_V2.md](../../../../launcher/LAUNCHER_V2.md)).
- Whether `HiUtils_createRequest` survives future firmware updates (freezing OTA
  via `iptables` in R0 is the planned guardrail).
