# Native Home: server retirement and fresh-start verification

## Completed on the TV

- Retired the Go bridge and static fallback from their active paths:
  `/var/local/alvidaa/alvidaa-bridge` and `/APPS/launcher/server.js`.
- Removed only the extra launcher-server section from the deployed
  `/APPS/installer.ipk` postinst. The data payload, package metadata, root SSH
  installation and other postinst sections were independently checked unchanged.
- Root-only retirement backups and metadata are at
  `/var/local/alvidaa/native-home/retired-bridge/`.
- Original stock Home restore was exercised and visibly verified; the native
  candidate was then reapplied without overwriting the original backups.
- Cached icons now render using CSS backgrounds and explicit native file URLs.
- All-apps navigation, native Settings and its Connection submenu, input
  switching, Home return, and theme controls were observed in screenshots.
- The diagnostic remote protocol uses **KEY_INPUT**, not KEY_SOURCE, for the
  tested Input key. KEY_INPUT opened the custom input view. Input labels now
  resolve through the vendor translation table.
- The final frontend consumes only handled Home `key-down` events during
  bubbling, before document-level defaults. Dialogs can consume them first;
  unrelated keys and Back from the main Home view pass through. Original
  vendor key groups remain unchanged.
- Focus announcements use `sdk.tts.isEnable()` / `speak()`, respecting the
  existing screen-reader setting. No accessibility setting was enabled or
  changed for testing. Audible behavior still needs a physical test.

## Reboot trap and measured fresh-start result

A normal BusyBox `reboot` request returned, but later inspection showed the
**same kernel boot ID and process IDs**. It did not prove a fresh boot. There
was a period of network unavailability; do not automatically label that a
successful reboot or a fully verified standby/resume cycle.

An explicit synced kernel restart (`reboot -f`, without `-n`) then made the TV
unreachable. All known ports were unavailable, ordinary LAN discovery did not
find its MAC at a different address, and a Wake-on-LAN attempt did not restore
access. The operator was asked to press Power and confirmed that the launcher
was visible. Do not use this reboot method unattended or assume it powers the
TV back on automatically.

After the operator powered it on:

- Kernel boot ID changed from `627b54d7-cf1a-49c6-8067-eed414bb1211` to
  `9aee6ea9-fd07-4cfa-bda1-b3a88e710bd6`.
- Uptime was about 63 seconds when inspected.
- `re_sshd` started at `2026-11-06T14:19:08.703Z`; the boot marker recorded
  root Dropbear armed at `14:19:35.237Z`.
- Root SSH was available again with the existing key.
- TCP 8770 was **not listening** and both retired runtime paths were absent.
- A HAL screenshot showed the native frontend with **47 apps and nine inputs**,
  without an HTTP/MQTT app-list request from a host launcher server.

This verifies a fresh kernel/startup cycle after retirement, with operator
power-on assistance. It is not a claim of a mains-disconnect cold boot or
unattended wake. The operator changed the theme after startup, so the theme
in that screenshot is not an independent before/after persistence test.

## Final installed build and recovery

The final compatibility build's launcher SHA256 is:

`9f121cb6efc5d5ade10812196fbbc5795163e6865206c3aa3dc8e92847d97014`

It includes the final event-propagation and screen-reader integration changes.
The fresh-start test above preceded those final UI-only changes; the final
build was installed with a checked UI restart and a verified file hash. The
boot package and retirement state did not change afterward.

Controller and retained candidate:
`/var/local/alvidaa/native-free-my-tv-v2/`.

From the host repository:

```sh
tools/launcher-host/home-control.sh status
tools/launcher-host/home-control.sh restore  # original stock Home; watcher stays off
tools/launcher-host/home-control.sh native   # reapply retained native candidate
```

Reversing server retirement is separate from stock UI restore. On the TV:

```sh
LD_LIBRARY_PATH=/lib:/usr/local/lib:/basic/lib \
  /opt/pkgs/tv.vidaa.app.phoenix/bin/phoenix \
  /var/local/alvidaa/native-free-my-tv-v2/retire-native-bridge.cjs restore
```

That restores the original package and runtime files with hash guards, but
**does not start the server**. Do not run it merely to restore stock Home;
stock Home needs no extra bridge.

## Verification limits

54 local native/frontend/deployment/retirement tests pass. These include
recovery faults, repeated restore/reapply, readiness retry, stale data,
key propagation, local-only icons and screen-reader enable checks.

Not claimed as verified: every physical remote key, microphone/voice,
audible accessibility, kids/game flows, mains-power cold boot, or a complete
standby/wake test. The Netflix attempt produced a black HAL capture, so
playback/visible app startup was not established by that capture. Vendor
routes and checks are preserved, not replaced with guessed implementations.

The unrelated PC Python server has pre-existing diagnostics and is not part
of this native runtime. No PC-side launcher server was started for these tests.
No further remote-key commands were sent after the operator reported using
the theme controls; the last changes were applied through checked UI updates.
