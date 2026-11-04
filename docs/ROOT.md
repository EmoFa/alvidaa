# The root chain — from a web page to a root shell on 2024+ VIDAA

> **This page is the 50A51HUV / MTK9602 / 09.01O.P0813 chain.** For
> model-specific step-by-step guides, see [docs/models/](models/) (HE40 and
> 100U7Q). Those chains are separate and do not transfer from this one.

To our knowledge this is the first publicly documented root path for
2024+ VIDAA firmware (everything published before is pre-2021; see
[SECURITY.md](../SECURITY.md) for the disclosure stance). It was
developed live on one TV — a 2024+ MTK9602 set — so **treat every stage
as model-specific** and read [docs/findings/](findings/) for the details
before running anything. Read [AGENTS.md](../AGENTS.md) if an AI session
is doing the walking.

The chain, one line:

```
official-app cert ──► MQTT bridge ──► browser file bridge ──► ../ escape
     ──► unauthenticated local API ──► rc.local boot hook ──► root at boot
     ──► busybox + dropbear over /dev/tcp ──► key-only SSH
```

Every stage depends only on the previous one. Nothing touches a
read-only partition; verified boot stays locked and green the whole way.

## Stage 0 — talk to the TV (the 2024 auth wall)

2024+ firmware rejects the 2018-era credentials every guide uses
(`MQTT rc 5`, *"your TV mode is no longer compatible"*). Two locks:

1. **Client-certificate identity** — the broker only accepts the current
   official VIDAA Smart TV app's cert (`CN=VidaaAppAndroidV01`),
   extractable from the APK's keystore (`res/raw/client_mobile_android.p12`,
   `openssl pkcs12 -legacy`).
2. **Dynamic per-connect credentials** — MAC-digest client_id, XOR-masked
   username, digit-sum-salted password; after the 4-digit PIN, long-lived
   tokens (2-day access / 30-day refresh) mean you pair once.

Protocol traps that will eat your afternoon: wildcard MQTT subscriptions
are silently denied (exact topics only), and list responses are JSON
arrays where a dict-check drops them silently.

Details: [findings/01-mqtt-bridge.md](findings/01-mqtt-bridge.md)

## Stage 1 — foothold: the browser file bridge

The TV browser exposes ~85 `Hisense_*` shims plus `HiUtils_createRequest`
to **any page it opens**. The file APIs resolve against `websdk/` — which
is enough to write `websdk/Appinfo.json`, i.e. **install a web app as a
native TV app** (that's how the alvidaa launcher installs itself).

Details: [findings/03-bridge-internals.md](findings/03-bridge-internals.md)

## Stage 2 — the sandbox escape, by reading an errno

A failed absolute read leaks the chroot base in its errno:
`open("/APPS//etc/passwd") → ENOENT`. The jail glues `/APPS/` onto every
path — so `../` walks out to the real root. Read + write as uid 314,
filesystem-wide, from any page.

Details: [findings/03-bridge-internals.md](findings/03-bridge-internals.md)

## Stage 3 — map the machine

- Backend is **phoenix**, a Node.js server running its own source from
  the writable `/APPS` partition as uid 314 — no capabilities, no
  seccomp, SELinux **permissive** (`setenforce 0` at boot).
- Raw API on `localhost:9009` needs **no authentication** and answers
  `Access-Control-Allow-Origin: *`.
- Verified boot is locked/green (ro partitions are a no-fly zone), but
  `/APPS`, `/data`, `/var/local`, `/var/tvservice`, `/OAD` are rw — and
  everything valuable lives there.

Details: [findings/04-privilege-map.md](findings/04-privilege-map.md)

## Stage 4 — the door

`rc.local` (root, every boot) executes `/var/local/otaTest.sh` if
present — an OTA test hook left armed in production firmware, in a
directory the bridge can write. **Writing one file = arbitrary code as
root at next boot.**

`launcher/recon.html` (v1→v8) is the tool that found all of this, and
`launcher/hookinstall.html` + the server's `/api/open` install new hook
versions remotely over MQTT — zero physical contact after the first
page load.

Details: [findings/05-root-primitive.md](findings/05-root-primitive.md)

## Stage 5 — root, and the honest lessons

- **Standby is not a reboot.** `/proc/uptime` (readable via the bridge)
  catches the difference; the first "reboot" was a 26.6-hour standby
  round-trip. The wall plug comes out exactly once in this story.
- The hook's proof was failure-shaped: its own log was root-owned
  because it forgot to chmod itself — denial as evidence.
- The harvest: `/etc/shadow`, the UART gate scripts, the CLI crypto
  material, the busybox applet inventory (no `nc`/`telnetd`/`wget` — but
  real bash with `/dev/tcp`).

Details: [findings/05-root-primitive.md](findings/05-root-primitive.md)

## Stage 6 — the shell (the five-lock gauntlet)

Static **dropbear 2025.88** cross-compiled with `zig cc`
(`arm-linux-musleabihf`), shipped to the hook, fetched at boot over bash
`/dev/tcp`. Five locks, each cleared by one hook version:

| Lock | Counter |
| --- | --- |
| `FIREWALL_IN_EULAON` drops all but MQTT/ICMP/loopback; blacklists 22, 23, 4444, 9222, 12321 | v5: accept rules at top of INPUT, re-applied in a boot loop |
| dropbear's `-D` *replaces* `.ssh` | key at `/var/local/roothome/authorized_keys` |
| login shell validated against `/etc/shells` (absent); root's shell is a script | v6: patch the check |
| `checkpubkeyperms()` vs the firmware's own `chmod 777 /var/local` | v8: patch the walk |
| root's login shell *is* the USB-key gate script (session prints `1` and quits) | v10: patched build execs `/bin/sh` directly |

Result: `ssh -p 2222 -i server/keys/tv_root_ed25519 root@<tv-ip>` —
key-only, every boot. The wrapper `server/tv` (or `tools/tvshell.py`)
makes it one command.

Details: [findings/06-ssh-gauntlet.md](findings/06-ssh-gauntlet.md)

## What root is for

- **Inventory**: 3.87 GB eMMC, 42 partitions mapped; the verity-protected
  squashfs rootfs (p20) dumped to the Pi and unpacked — the CLI decrypt
  key, the boot chain, and the Loewe/CVTE ODM archaeology all came out of
  that extract. [findings/07-root-summary.md](findings/07-root-summary.md),
  [findings/08-image-exploration.md](findings/08-image-exploration.md)
- **Telemetry**: named daemons, the `euladpp-*` family, endpoint mapping,
  and an iptables LOG wiretap for a few honest days of data.
  [findings/09-endpoints.md](findings/09-endpoints.md)
- **The launcher goes native** (roadmap):
  [LAUNCHER_V2.md](LAUNCHER_V2.md)
- **The rite of passage**: DOOM at 1080p on the framebuffer.
  [DOOM.md](DOOM.md)

## Operational rules (learned the loud way)

1. **R0 first**: freeze OTA before touching anything else — an update
   that reseals the hole mid-project is the only true game-over.
   Applied Oct 30, no hook churn: `/var/local/tvrc` (sourced by the boot
   hook) now closes the DNS bypass in-kernel — all outbound 53/853 to
   anywhere but AdGuard is REJECTed, v4 verified live (`1.1.1.1` answers
   `Operation not permitted`) — and blocks the OTA host
   (`ota-tv.vidaahub.com` → 131.189.69.51; CDN IPs rotate, so the DNS
   close is the durable layer). Note: `/OAD/AppUpgradeSwitch.json`
   already reads `upgradeFlag: 0`, but the service rewrites it from the
   server. Open item: `ip6tables` doesn't exist on this firmware, so the
   IPv6 fallback resolvers are closed only by AdGuard being first in
   `resolv.conf` — router-side RA control would finish the job.
2. Keep a backup of the previous hook (`otaTest.v1.bak`) on the TV. A
   kill-switch is planned for v11; it is not established for the current
   hook — recovery today is `rm /var/local/otaTest.sh` over SSH, which
   is equivalent. Full rollback ladder (hook → UI restore from the
   canary `.bak` + Pi-side tar → factory reset → partition dumps for
   file-level restore; verified boot makes reflash impossible and
   unnecessary) is in the post's "What if it breaks?" section.
3. One MQTT session per credential set, one agent on the TV at a time.
4. Never commit `server/keys/`; never publish vendor binaries.
5. The endgame is the teardown: delete the hook, fresh boot, verified
   boot still green, stock in every way that matters.
