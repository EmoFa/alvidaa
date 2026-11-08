# 32A35HUV — V0000.09.01O.P0814

- **Model:** 32A35HUV
- **Firmware:** V0000.09.01O.P0814
- **SoC:** MTK9602
- **Region:** CAN
- **VIDAA OS:** U09.01
- **Browser:** Chromium 111
- **Reported by:** gh:EmoFa

Root chain replay of the [50A51HUV reference](../../50A51HUV/09.01O.P0813/README.md)
on a **second MTK9602 board family** (32" CAN set, one build letter newer:
P0813 → P0814). Every step re-verified on-device; the divergences below are
the new information this report adds. Claims are marked **verified** (done on
this unit) or **untested**.

## Result

Pairing, launcher install, file-bridge traversal/write, boot hook, and
key-only root SSH: all working, following the reference method unchanged.
Verified boot untouched; full eMMC backup taken before modifications.

## Chain (all verified on-device)

1. **Fingerprint** — SSDP `M-SEARCH ssdp:all` finds the MediaRenderer; the
   device descriptor's `modelDescription` leaks `transport_protocol=3290`.
   Browser census via a LAN-served page: `Hisense_GetChipSetName()` →
   MTK9602, `Hisense_GetFirmWareVersion()` → the firmware string above.
2. **Pairing** — VIDAA companion-app certificate (from
   `com.universal.remote.multi`, `openssl pkcs12 -legacy`), modern credential
   profile, on-screen PIN. Divergence 1 below governs the identity format.
3. **Home UI census** — a census page in the TV's home browser enumerates the
   rendered DOM over a WebSocket dump lane in the launcher bridge. Errno-leak
   probe (`open("/APPS//etc/passwd") → ENOENT`) proves the `/APPS` base;
   `../etc/passwd`, `../proc/mounts`, `../proc/partitions` read — traversal
   open on this board.
4. **Boot hook** — `fileWrite /var/local/otaTest.sh` (mode-indexed write),
   readback-verified. Proof hook logs `id`/`uptime` to a chmod-644 dump:
   **uid=0 at uptime ~6 s** after a cold boot. Standby does not re-run
   `rc.local` — the proof requires a real power cycle.
5. **tvtools + dropbear** — static `busybox` (a Debian 1.38 build with
   `telnetd`) and dropbear 2025.88 patched per the reference three-lock list
   (shells check, pubkey perms, `get_user_shell`), fetched at boot over bash
   `/dev/tcp` HTTP from a LAN file server. Key-only dropbear on 2222 with
   `-D` on a writable roothome.

## Divergences from the reference (P0814/A35)

1. **Pairing identity format.** The Wi-Fi MAC in *coloned* format
   colon-separated octet pairs pairs; the bare hex form is rejected across all four
   credential profiles. Discovered by probing both forms.
2. **Empty `Appinfo.json` = permanent black screen.** `sdk.js` requires at
   least one app entry; an empty `AppInfo` array hard-fails the home UI to a
   solid frame that survives reboots. Found while removing the launcher app;
   bisected against firewall changes. Keep ≥1 entry (the launcher entry
   itself can be renamed as a soft-disable).
3. **`/opt/iot/mosquitto` is the RemoteNow broker** (36669) — not a
   separate IoT-only broker. Killing it drops the control bridge. Restarting
   it needs `LD_LIBRARY_PATH=/opt/iot/mosquitto/lib:...` (vendor launch env).
4. **`537.js` is both the menu UI build and the app-surface handoff.**
   Removing the menu chunk (a "strip the menu to a skeleton" experiment)
   leaves app launches logically successful but never displayed. The menu
   and the display orchestrator are inseparable at script level.
5. **An opaque body-wide CSS canary breaks app-surface promotion globally**
   (same symptom as 4, different mechanism). CSS experiments on the home
   page must not force opaque backgrounds or blanket hiding.
6. **ui_service MQTT quirks (P0814).** `ui_service/data/state` topic:
   SUBACK refused. `gettvstate` action: silent. State arrives on the
   broadcast topic. `platform_service/data/gettoken` topic: SUBACK refused
   (token refresh lane untested on this build).
7. **Bounces before UI-ready never promote a surface.** Launching the home
   app before the UI stack finishes (the reference's boot-bounce idea)
   reports ok but does not display. Verified then gated off.
8. **Busybox gaps.** Debian-built busybox lacks `pgrep`/`setuidgid`; the
   vendor userland lacks `wc`/`tail`/`id`/`uname` on PATH. `pidof` and
   `ps|grep` work; `pidof` cannot see script processes (matches comm only).

## Operational notes

- **OTA freeze first** (reference rule R0): block the OTA host at the
  network edge and set Settings → auto-update OFF before hooking. The
  `rescueOTA` watchdog polls `/tmp/tvstatuschecker.txt` for 60 s after
  `startgui` — the hook touches it at boot so the UI-ready check always
  passes, regardless of what replaces the home page later.
- **The `/opt/iot` mosquitto must stay up** — see divergence 3; the hook
  carries a broker-revive guard ahead of the bridge start.
- **superwatch respawns** killed vendor services — firewall endpoints, don't
  just kill processes.
- Verified-safe block IPs (bisected, panel render confirmed with each
  blocked): ad-manifest and telemetry tenants; see EVIDENCE.md.

## Teardown

```
touch /var/local/hook.off          # arms the kill switch
rm -f /var/local/otaTest.sh        # remove the hook
rm -rf /var/local/tvtools /var/local/roothome
# restore stock theme (if the skin was applied):
cp /APPS/channelA/hisenseUI/static/css/app.css.alvidaa-bak \
   /APPS/channelA/hisenseUI/static/css/app.css
rm -rf /var/local/hisenseUI/cobalt_home/*
# reboot — verified boot untouched throughout; full eMMC backup exists
```

## Reproduces with

Reference guide: [50A51HUV / 09.01O.P0813](../../50A51HUV/09.01O.P0813/README.md)
— same steps, apply divergences 1-8 above. pairing/launcher scripts:
`server/pair.py` + `server/vidaa_server.py` from the repo root.
