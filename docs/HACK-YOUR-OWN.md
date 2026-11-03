# Hack your own VIDAA TV with an AI agent

The whole project took a weekend, two AI sessions, a Raspberry Pi, and zero
screwdrivers. This is the ladder to run on **your** TV with **your** agent —
the actual prompts that worked, staged so each phase gates the next. Full
context: [STORY.md](STORY.md) and [findings/](findings/).

**Before you start**

- A TV you own, on your LAN. An always-on host (Pi or similar). An AI coding
  agent that can run shell commands and read files (this was built on GLM-5.3
  Flash in Z Code; any capable agent works — point it at this repo so it
  reads [AGENTS.md](../AGENTS.md) first).
- Know the shape: the **launcher** (Phase 1) is safe and reversible. The
  **root** phases (3+) modify your TV's runtime state — reversible, but you
  are disabling safety rails on your own hardware. Firmware-generation facts
  here are from `transport_protocol=3290` class firmware (2024+); other
  generations and SoCs will differ.

---

## Phase 0 — fingerprint (an afternoon)

Point the agent at the repo and start here:

> "fingerprint my Hisense VIDAA TV on the LAN: SSDP discovery, the device
> descriptor fields, and the RemoteNow MQTT port. Tell me my
> transport_protocol, firmware version, and SoC."

Add your row to the [README tested-models
matrix](../README.md#tested-models) by PR — that table is how the
next owner knows whether your hardware matches theirs.

## Phase 1 — the launcher (a day, fully reversible)

The wall you'll hit: every public guide uses 2018 credentials, and 2024+
firmware answers `MQTT rc 5, Not authorized`. The keys to the wall: the
client certificate from the official VIDAA Smart TV APK (identity-checked at
the MQTT layer) and per-connect dynamic credentials derived from the TV's
MAC and timestamp. Then the pairing dance — trigger the PIN dialog **once**
(re-triggering rotates the code), subscribe to *exact* MQTT topics
(wildcards are silently denied), and treat list payloads as JSON arrays.

> "write the server and pairing CLI per docs/findings/01-mqtt-bridge.md,
> then build the launcher page: a clock, my HDMI inputs, my real apps.
> Functional over fancy."

End state: the page self-installs as a TV app (`HiUtils_createRequest`
writes `websdk/Appinfo.json`), a watcher relaunches it over the stock home,
and it's deployed to the always-on host as a systemd service.

## Phase 2 — the recon ladder (an evening)

Build `recon.html`: a probe page that runs checks in the TV browser and
POSTs results to your server. One version, one question, and make it POST
**incrementally** (a probe can crash the bridge backend mid-run). The
ladder, in order:

> "recon v1: enumerate the JS bridge functions, read the user agent, probe
> the file bridge sandbox. v2: test whether a failed absolute read leaks the
> sandbox base in its errno, and whether `../` traversal escapes it. v3:
> with traversal, dump /proc/mounts, /etc/inittab, /etc/passwd and the boot
> scripts. v4: patch XMLHttpRequest.prototype to capture the bridge's wire
> format, then read /proc/self/cmdline and /proc/self/status."

What you're looking for: the sandbox base (errno leaks it), which mounts
are read-write, what runs as root at boot, and who the bridge backend is.
On our firmware that chain ended at `rc.local` executing
`/var/local/otaTest.sh` as root — a file on a partition the bridge could
write. Your model may hide the same class of door somewhere else; the method
transfers, the constants don't.

## Phase 3 — root (a night; reversible, but you're disabling rails)

Only after Phases 0–2 are green, and only on hardware you own:

1. **Freeze OTA first** — an update that reseals the hole mid-project is the
   only true game-over. (iptables from the hook, or your router's per-client
   blocks.)
2. Write the boot hook through the file bridge; reboot **for real** (standby
   doesn't re-run `rc.local` — check `/proc/uptime`).
3. Give the shell a network primitive: this TV's busybox had no
   `nc`/`telnetd`/`wget`, but `/bin/sh` is bash and bash has `/dev/tcp` —
   enough to fetch a static busybox from your server and start `telnetd`.
4. Then the real work is a *stock binary*: cross-compile **dropbear**
   statically for your TV's arch and satisfy every check it runs. Ours, in
   order: a vendor firewall blacklisting debug ports, a relocated
   `authorized_keys` path, a shell-validity check against a missing
   `/etc/shells`, a permissions walk that hates world-writable dirs, and a
   login shell that turned out to be a factory gate script. Each one is a
   patch in your own build — and each one is discoverable by *reading the
   rejection in source* rather than guessing.

> "the session connected and printed 1. figure out why."

## Phase 4 — spend it

Wiretap (`iptables` LOG on every outbound SYN), endpoint map from the
firmware images, ad/recommendation domains blocked in-kernel, the launcher
server moving onto the TV's own Node runtime, and the stock home retired.
See [findings/09-endpoints.md](findings/09-endpoints.md) for the map and
[LAUNCHER_V2.md](LAUNCHER_V2.md) for the roadmap.

---

**Two agents are better than one.** The launcher session and the root
session ran in parallel windows, pasted logs at each other at 2am, and saved
the project twice — once by coordination (the launcher session reverted its
own conflicting edit unprompted) and once by comedy (the root news arrived
mid-sentence about watcher architecture). Give each session one lane, share
the findings doc, and let them argue.

**Teardown.** Delete `/var/local/otaTest.sh`, `/var/local/tvtools`,
`/var/local/roothome` and reboot — or delete the Home app entry and factory
reset. Verified boot never noticed you were there.
