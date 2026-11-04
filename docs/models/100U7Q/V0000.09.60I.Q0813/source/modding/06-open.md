# 06 — open questions and state left on the device

Nothing in this file is a recipe. Items are **UNVERIFIED** unless stated
otherwise.

## Boot persistence candidates (all unverified)

1. **`/APPS/pkgs/appinfo.json`**
   The file lists entries with `Main: pkgapp://<pkg>/<script>`,
   `Type: nativeType` and `Persistent: true`. The `systemserver` binary contains
   the string `appinfo.json`. Whether adding an entry makes `systemserver` start
   that script at boot — and with which uid — was **not tested**.

2. **`/APPS/pkgs/tv.vidaa.app.phoenix/CHA/run_phoenix.sh`**
   Writable (`314:314`), 3109 bytes, the vendor script that starts phoenix. A
   background line before its final `exec` would be additive. Whether the
   launcher runs it as root or as uid 314 is **not established**.

3. **`systemserver` configuration**
   uid 301, `/mnt/tvroot/usrlocal/bin/systemserver`, parent of phoenix. Its
   start list was not readable from uid 314, so its config format is unknown.

## DevTools

`devtoolSwitch` (`kilby.sl2.i32.browser.devtool.switch`) is settable without a
permission check via `TvInfo_setParam`. It was set to `2` and survived a reboot,
but **ports 9222/9223/9224 stayed closed** on this build, including after a cold
boot.

`/OAD/enable_selenium` is the 24-hour flag consumed by `getSeleniumDebug`
(content must be a parseable date, younger than 24 h). It was written; whether a
browser restart opens a debug port afterwards is **not verified**.

## Other unverified items

- Reading vendor binaries from the FaaS context (not attempted; the earlier
  `fileRead` path crashed the service on binary content).
- `tvinfo.sendAPMMessage(target, message)` is not permission-gated, but the
  message schema is unknown and it was not exercised.
- Whether an installed IPK with `ProcessId` / start metadata is started at boot.
- When the launcher reloads `Appinfo.json` after an edit (it kept stale tiles
  until a reload during the run; the exact trigger was not measured).

## State left on the device during this work

Documented so it can be undone deliberately:

| Item | What it is |
|---|---|
| `devtoolSwitch = 2` | tvinfo biz key, persists |
| `/var/local/dab_debug` | written by `setDabTool(1)` at security level 9 |
| `/OAD/enable_selenium` | 24-hour debug flag, expires by itself |
| `/APPS/.re_sshd/` | dropbear, host key, authorized_keys, installer IPK |
| `re.installer` | installed package, used by the re-trigger |
| `Appinfo.json` | test tiles removed; 4 system apps + one live tile remain |
| `Appinfo.json.bak` | backup taken before the tile cleanup |
