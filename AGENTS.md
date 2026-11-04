# AGENTS.md — working on alvidaa with an AI session

This repo is routinely driven by AI coding sessions (the whole project was
built that way — see [STORY.md](docs/STORY.md)). If you are an agent (or a
human driving one), this file is your briefing.

## What this repo is

Two lanes share one TV:

1. **The launcher** (product lane): a self-installing home screen for Hisense
   VIDAA TVs — one canvas page + a Python/Pi server speaking the TV's
   RemoteNow MQTT channel. Safe, reversible, the 90% use case.
2. **The research** (root lane): how root was gained on 2024+ firmware and
   what it unlocked. Own-TV-only, documented in `docs/findings/`.

## Ground rules (non-negotiable)

- **Only on a TV you own.** LAN-local. No DRM circumvention. Verified boot
  stays green — never write to read-only partitions, never touch `/OAD`
  staging, freeze OTA endpoints before editing UI code.
- **Reversibility is the design law.** Every change needs a teardown path.
  The hook keeps a rolling backup (`/var/local/otaTest.v1.bak`); check
  `/var/local` state before overwriting — another agent session may be
  working the same TV. Check `git log` too.
- **One MQTT server per TV.** The paired client identity is shared; two
  servers kick each other off the broker.
- **Keys and tokens never leave `server/keys/`** (gitignored). LAN IPs in
  code are fine.
- **FINDINGS discipline**: every discovery — bug, trap, errno — goes into
  `docs/findings/` the same hour it happens. That discipline is why the
  root chain worked.

## Map

| Path | What |
| --- | --- |
| `server/vidaa_server.py` | HTTP + WebSocket + MQTT bridge; `/api/open` loads any URL on the TV; `/api/recon` receives probe reports |
| `server/pair.py` | the 2024 pairing handshake (cert + dynamic credentials) |
| `server/tv` | root one-shot/interactive wrapper over dropbear (PATH-fixed) |
| `launcher/recon.html` | the probe page pattern (v1–v8 in git history) |
| `launcher/hookinstall.html`, `hookcheck.html` | remote hook install/verify |
| `docs/findings/01…12` | canonical record: bridge, privilege map, root primitive, SSH gauntlet, root summary, images, endpoints, patched firmware playbook, firmware notes, cobalt runtime & overlay traps |
| `scripts/check.sh` | read-only health check: generated tables vs JSON, python/shell syntax, relative doc links |
| `firmware/ENDPOINTS.md` | live endpoint/kill-list working copy (gitignored) |

## Canonical recipes

- Verify before you commit: `./scripts/check.sh` — read-only, no regeneration.
  Fails on stale generated tables, syntax errors, or broken relative links.
- Root shell: `./server/tv` (interactive) or `./server/tv 'cmd'`. PATH is
  exported by the wrapper — dropbear sessions have none. Default host is
  `192.168.0.11`; override with `TV_HOST=<ip>` when the TV's DHCP lease moves.
- Load any page on the TV: `curl "http://<server>:8770/api/open?url=…"`.
- MQTT traps: subscribe to **exact topics** (wildcards silently denied);
  list payloads are JSON **arrays**; one session per credential set;
  the firmware disables ICMP — probe TCP 36669, never ping.
- The TV's browser exposes `Hisense_*` bridge functions to any page, and
  the file bridge (phoenix, localhost:9009) is unauthenticated with CORS
  `*`. The TV browser must never see the open web — DNS-block it.

## Onboarding a new TV/model

1. Fingerprint: SSDP descriptor (`transport_protocol=`), then
   `Hisense_GetFirmWareVersion()` / `Hisense_GetChipSetName()` from any page
   in the TV browser.
2. Launcher lane first (generation-dependent, not SoC-dependent): pair,
   serve, self-install. See findings 01.
3. Root lane only after 1–2 are green, and expect SoC-specific differences
   (this chain is MTK9602/armv7; HiSilicon models differ in partitions and
   tools). See findings 03–07 for the method, not just the constants.
4. Add a row to the README tested-models matrix — by PR.
