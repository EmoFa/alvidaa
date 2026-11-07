# 75U8QTUK V0000.09.60I.Q0813 — modding notes

## Where this fits

This unit shares the firmware build with the 100U7Q, so the modding surface
map is expected to match. The canonical, measured surface map lives on the
parent guide:

- Partition / mode map, writable-by-uid-314 list, nosuid/noexec flags →
  [100U7Q MODDING.md](../../100U7Q/V0000.09.60I.Q0813/MODDING.md)
- Package tree (`/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/…`) and the
  installer handoff → [100U7Q README](../../100U7Q/V0000.09.60I.Q0813/README.md)
- Service list autostart primitive for later boot-persistence work →
  [75UR9S source bundle](../../75UR9S/V0000.09.60W.Q0624/source/re_sshd/)

## Launcher lane (AGENTS.md 90% path) — status: UNTESTED

The launcher lane is independent of the root chain; it only needs:

1. Successful MQTT pairing (`server/pair.py <tv-ip>`) — the UK/`GBR` region
   may want the `remotenow` or `standard` credential profile first; walk
   the cascade like the 65U7H work if `standard` fails CONNACK.
2. The launcher web UI served from `server/vidaa_server.py` on a LAN host,
   loaded on the TV via `/api/open`.
3. Self-install via the `launcher/hookinstall.html` + `hookcheck.html`
   pages — the `WebSDK_*` file bridge path and tile-self-install primitive
   on the browser side.

None of that has run on this TV yet. Each step gets a findings note the
first time it's attempted.

## Root chain expected deltas — status: UNTESTED

If the 100U7Q `postinst` path applies as-is (the expected case), on success:

- Dropbear 2022.83 listens on **TCP 8008**, key-only, with PTY (`/dev/ptmx`
  + `/dev/pts/ptmx` modes opened up at install time by the postinst).
- `CapEff 000001ffffffffff` for the SSH process.
- No automatic boot persistence — re-arm with `pkgmgr` opcode `83`
  (uninstall) then `82` (install) via the same superwatch socket after each
  reboot, unless we later port the 75UR9S `re_sshd` serviceList autostart.
- No vendor binaries shipped, no credentials shipped. Pairing is yours to
  perform; SSH key is yours to generate.

Rollback is operator-defined (same as 100U7Q): uninstall the package via
`pkgmgr` 83, reboot. The daemon is gone after reboot either way.

## What the UK region might change

- **MQTT pairing credential profile.** `pair.py` cascades `standard` →
  `remotenow` → `modern`. The EU_A record on the same build used
  `standard`; the UK region has not been tested and could differ, as the
  65U7H (India) work showed.
- **Pairing dialog text.** The on-screen 4-digit PIN dialog runs in the
  TV's current language (`en-GB`). This is cosmetic only, but worth noting
  for screenshots and user-facing docs.
- **Country-dependent catalogues.** `/var/local/kilby/categoryList/` and
  `newVersionPreset/` may ship a different EU/UK country preset here than
  on the 75UR9S Czech unit. Not relevant to the root chain, but it's the
  cheapest region sanity check once the bridge-read primitive is live.

## What this guide does **not** do

Same posture as the parent:

- No flashing, no `.pkg` modification, no UART, no case opening, no
  bootloader change. `/` remains erofs with dm-verity enforcing.
- No vendor binaries and no keys are shipped in this repo.
- No OTA endpoints are poked. The TV browser must never see the open web
  — keep DNS blocking for `vidaa.com` / `vidaahub.com` from the pi, as in
  the main launcher setup.
