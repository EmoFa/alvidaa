# Tested models & how to report yours

The README carries a compact matrix (model, firmware, launcher, root, who). The
full table with every field lives below; this file also explains where each
field comes from. A full step-by-step guide, when one exists for the exact model and
firmware, lives under [models/](../models). To report by PR, add an entry to
`inventory.json` and run `scripts/gen-inventory.py` to update the README
and playbook tables.
For a method-specific result, also add an observation to `exploits.json`
and run `scripts/gen-exploits.py`; the generated [method inventory](EXPLOITS.md)
separates reported results, verified results, and failed tests.

## The full matrix

Every field, for every reported unit. The README carries a compact version
because its column is narrow; this is the one to read when you are comparing
builds.

<!-- INVENTORY:START -->
| Model | Region | SoC | VIDAA OS | Firmware | `transport_protocol` | Browser | Launcher | Root chain | Tested by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 50A51HUV | US/CAN | MTK9602 | U09.01 | 09.01O.P0813 | 3290 | Chromium 111 "odin" | working | achieved | [@carteakey](https://github.com/carteakey) |
| 55S7NEVS (MT9618 unit; S7N board family — same build covers 55U75LEVS / 65S7NAVS / 75S7NAVS) | EU | MTK9618 | U09.60 | 09.60X.Q0609 (2026-06) | ? | Chromium 111 | untested | achieved | [u/possibly_matt](https://reddit.com/user/possibly_matt) |
| 55A60LEVS | EU_A | MTK9603 | 9.0 | 09.60V.Q0612 (2026-07 EU_A) | 3290 | Chromium 111.5563.5.1 | untested | blocked-at-fileWrite | [u/Affectionate-End-601](https://reddit.com/user/Affectionate-End-601) |
| 43A60LEVS | EU | MTK9603 | 9.0 | 09.60V.Q0612 (2026-07) | 3290 | Chromium 111 "Odin" (111.5563.x) | untested | untested | [u/Wing-Tsit-Chong](https://reddit.com/user/Wing-Tsit-Chong) |
| ? | ? | MTK9603 | 9.0 | 09.60V.Q0612 (build date unconfirmed) | ? | ? | untested | untested | [u/____dls](https://reddit.com/user/____dls) |
| 65U8HAU (65E83GAVT, serial type 65U8H / intl 65U8HQ) | AU (EM_C / AUS, SSDP region 0) | MTK9900 (aarch64) | U06.29 | V0000.06.29X.P0813 (AU) | 3160 | Chrome 88.0.4324.182 (Linux aarch64, Odin) | working (web UI + WS + server-side install/watcher bounce; Appinfo.json self-install gated) | blocked-at-origin-gate (/file/* and /hiSecurity/* return empty body from LAN HTTP origins; TCP 2222/2323/8008 closed) | [@MewX](https://github.com/MewX) |
| 65U7H (board 65A65GAVT) | India (EM_C, countryID IND) | MTK9900 (aarch64) | U06.29 | V0000.06.29X.P0813 (IN) | 3160 | Chrome 88.0.4324.182 (Linux aarch64, Odin) | untested | not achieved (no exec door found; WIP) | [u/pavanjadhaw](https://reddit.com/user/pavanjadhaw) |
| HE40E5600FFWTS | ? (EU, German-language docs) | MT53xx / MT5863 class (armv7 Cortex-A53) | pre-9 (Linux 3.18.25, glibc 2.18, BusyBox 1.18.5, sysvinit) | V0100.01.00A.N0410 | untested (vector did not use MQTT) | hisenseUI (Chromium 59.0.3071.115, opera4x) + hisense_browser (separate process, DevTools 9224, --disable-web-security) | custom-UI templates shipped (start-UI.sh + /3rd_rw/UI/index.html, PIXI); not verified end-to-end | achieved (root + key-only SSH; boot persistence owner-verified across multiple reboots, 2026-11-04) | [@oOHiyoriOo](https://github.com/oOHiyoriOo) |
| 100U7Q (100U70QEVS) | EU_A | MT9655 (32-bit ARM userland) | U09.60 | V0000.09.60I.Q0813 | untested | untested | untested | achieved (SSH and PTY verified; manual re-trigger after reboot) | [@oOHiyoriOo](https://github.com/oOHiyoriOo) |
| 75UR9S | EU (Czech Republic) | MT9655 (32-bit ARM userland) | U09.0 | V0000.09.60W.Q0624 | untested | untested | untested | achieved (root + key-only SSH on 8008 verified 2026-11-04; boot persistence verified 2026-11-06 — re_sshd serviceList autostart re-arms dropbear at every cold boot) | [@EvzenP](https://github.com/EvzenP) |
| 43E7DS (43Q60SEVS_02, serial type 43E7SE) | EU_A (DEU) | MTK9603 | U09.60 | 09.60W.Q0612 (EU_A) | ? | Chromium 111 "odin" (multi-shell UAs: WebExplorer/1.2.8, SurfMaster/7.0.0, Weblayer, NetSurfer) | working | achieved (13 postinst runs as uid 0; no Dropbear on this build — boot persistence via the vendor service manager) | [@ryjr2ddznn-lab](https://github.com/ryjr2ddznn-lab) |
| 50A6Q (50A60QXVT) | UAE / intl (SSDP region 4) | NT72690 (Novatek; aarch64 kernel, armhf ELF32 userland) | U09.61 | V0000.09.61B.Q0721 | 3290 | Odin Chromium 111.5563.5.1 (aarch64) | untested | achieved (boot-persistent PFM/eval chain uid=0 + key-only SSH on 2222 verified 2026-11-06; self-healing re-plant loops) | [@aadnaane](https://github.com/aadnaane) |
| 55A7KAU (internal 55U66GAVT) | AU (AUS; GetCountryCode AUS, SSDP region 6) | MTK9602 | U09.09 | V0000.09.09O.P1015 | 3290 | Chromium 111 "odin" | working | achieved + boot-persistent (2026-11-06; re_sshd serviceList autostart, offline re-arm; see 02-root-ssh.md) | @owner (this session) |
| 75U8QTUK | UK (GBR; internal region EU_A) | MTK9655 (aarch64 kernel; 32-bit ARM userland confirmed on-device: phoenix worker process.arch=arm, 2026-11-06) | U09.60 | V0000.09.60I.Q0813 (UK) | not-exposed-over-SSDP (dd.xml stub on :3366; SSDP modelName reports 75U8QE; pairing handled by Sidee, profile 'modern') | Chromium 111 "WebViewer/1.2.1" (odin, aarch64 UA) | working (2026-11-06 owner-verified): native DOM Home replaces the /Launcher route component in the writable operation-ui app.js, preserving vendor lifecycle/routes; app list, inputs, TV Settings and app launch all confirmed on screen; merged apps+inputs list and CSS wallpapers added in findings/10; full rollback in findings/09 | ACHIEVED 2026-11-06 (owner-authorized): the 100U7Q chain was armed; the IPK postinst ran as uid 0 with CapEff 000001ffffffffff, and `ssh -p 8008 root@<tv-ip>` (dedicated ed25519 key in server/keys/, gitignored) gives uid 0 + PTY. No boot persistence: a real reboot closed 8008, and re-sending superwatch 83+82 restored uid-0 SSH without re-downloading (same host key, new daemon; findings/08). Rolling back is documented in findings/07. | [@kingpandacc](https://github.com/kingpandacc) |
| 43A5LE (internal 43A60LEVS_0002) | EU_A (ITA) | MTK9603 | U09.60 | V0000.09.60A.Q0707 | ? | Chromium 111 (armv7l; UA SurfMaster/3.0.1) | working | untested | [@antmagl](https://github.com/antmagl) |
| 43A5FE | EU | MTK9602 | U07.51 | V0010.09.09A.P0930 | 3290 | Chromium 111 "odin" | working | achieved | @community |
<!-- INVENTORY:END -->

## Community reports awaiting details

- [uzueta reported](https://reddit.com/r/Hisense/comments/1xj3pc2/comment/19rwnxey9q5j5/)
  that the launcher-only setup worked, but did not provide a model or firmware
  and did not try root. This is a useful launcher report, not a verified matrix
  entry until those details are available; the full watcher flow was not
  separately described.

## Fields

| Field | Where to get it | Why it matters |
| --- | --- | --- |
| Model | TV Settings → Support → device info | panel/board family |
| Region | SSDP device descriptor (`region=`) | ad/OTA server behavior differs |
| SoC | `Hisense_GetChipSetName()` from any page in the TV browser | **decides the root chain** (MTK vs HiSilicon paths differ) |
| VIDAA OS | `Hisense_GetOSVersion()` or Settings → About | feature generation |
| Firmware | `Hisense_GetFirmWareVersion()` or Settings → About | exact build |
| `transport_protocol` | SSDP descriptor (`modelDescription` leaks it) | **the single most predictive number** — selects the MQTT auth generation (3290 = the 2024+ wall) |
| Browser | UA string from any page the TV browser opens | rendering constraints (Chrome 77 vs Chromium 111) |
| Launcher ✅/❌ | pairing → install → watcher | generation-dependent only |
| Root chain ✅/❌ | recon → hook → SSH | SoC-specific |
| Tested by / Source | Platform handle in `tested_by` | provenance and attribution without ghost-mentions |

## Getting the numbers

- **SSDP**: M-SEARCH `ssdp:all` finds the TV as a DLNA MediaRenderer; the
  device descriptor's `modelDescription` leaks `mac=`, `region=`,
  `brand=`, `vidaa_support=`, `transport_protocol=`.
  See [01-mqtt-bridge.md](../models/50A51HUV/09.01O.P0813/findings/01-mqtt-bridge.md) §1.
- **From the TV browser**: open any page (e.g. the launcher URL) and call
  the bridge functions via the console, or run
  [launcher/recon.html](../../launcher/recon.html) — its report includes
  chip, firmware, browser, and the whole bridge surface.
- **Root chain fields**: only after reading
  [the 50A51HUV / MTK9602 guide](../models/50A51HUV/09.01O.P0813/README.md) and [SECURITY.md](../../SECURITY.md). The recon page
  alone is read-only and safe.
- **Attribution format** in `inventory.json` (`tested_by` array):
  - GitHub: `"gh:username"` (renders `[@username](https://github.com/username)`)
  - Reddit: `"reddit:username"` or `"u/username"` (renders `[u/username](https://reddit.com/user/username)`)
  - Custom link: `{"name": "...", "url": "https://..."}`

## Template row

```markdown
| 55U8N | EU | MT9602 | U09.01 | V0000.09.01N.N0704 | 3290 | Chromium 111 | ✅ | ✅ | [@you](https://github.com/you) |
```

The launcher column depends only on the firmware generation; the root
column is where SoC and board revisions bite. A ❌ with a note is as
valuable as a ✅.
