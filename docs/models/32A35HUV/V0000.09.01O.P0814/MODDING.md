# Modding notes — 32A35HUV / V0000.09.01O.P0814

Operational summary of what is deployed on this unit after the root chain.
Everything lives on writable partitions; verified boot is untouched.

## Boot hook (`/var/local/otaTest.sh`)

Runs from `rc.local` on every real boot (standby does not re-run it).
Order: kill-switch check (`hook.off`) → rescue-flag touch
(`/tmp/tvstatuschecker.txt`, defuses `checkEmergentOTA`) → RemoteNow broker
revive (`/opt/iot/mosquitto`, needs `LD_LIBRARY_PATH=/opt/iot/mosquitto/lib`)
→ bridge start (retry loop) → tvchop (firewall kills) → wiretap → tvtools
fetch (skipped when present) → dropbear/telnetd → watchdog (30 s, ps-based
guards — busybox `pidof` cannot see script processes).

## tvtools

`/var/local/tvtools/`: busybox (Debian 1.38 build, includes telnetd),
dropbear 2025.88 (static, three patches per the reference: shells check,
pubkey perms, `get_user_shell` → `/bin/sh`), dropbearkey. Dropbear: port
2222, `-D /var/local/roothome -s` (key only). Telnetd on 2323 as bootstrap.

## Kill switch / teardown

```
touch /var/local/hook.off && reboot        # stock behaviour
rm -f /var/local/otaTest.sh
rm -rf /var/local/tvtools /var/local/roothome
# optional theme revert:
cp /APPS/channelA/hisenseUI/static/css/app.css.alvidaa-bak \
   /APPS/channelA/hisenseUI/static/css/app.css
rm -rf /var/local/hisenseUI/cobalt_home/*
# reboot
```

## Gotchas (device-verified)

- `pidof` cannot see script processes — ps-guards only.
- Debian busybox lacks `pgrep`/`setuidgid`; vendor userland lacks
  `wc`/`tail`/`id`/`uname` in dropbear sessions.
- `/opt/iot/mosquitto` is the RemoteNow broker — never kill it; revive with
  `LD_LIBRARY_PATH=/opt/iot/mosquitto/lib` if it dies.
- Launches issued before the UI stack is ready never promote a surface.
- An empty `Appinfo.json` black-screens the panel permanently (sdk needs
  ≥1 entry) — keep a fallback entry if removing apps.
