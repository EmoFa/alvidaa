# Tested models & how to report yours

The README carries the generated matrix; this file explains where every field
comes from. To report by PR, add an entry to `docs/inventory.json` and run
`scripts/gen-inventory.py` to update the README and playbook tables.

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

## Getting the numbers

- **SSDP**: M-SEARCH `ssdp:all` finds the TV as a DLNA MediaRenderer; the
  device descriptor's `modelDescription` leaks `mac=`, `region=`,
  `brand=`, `vidaa_support=`, `transport_protocol=`.
  See [findings/01-mqtt-bridge.md](findings/01-mqtt-bridge.md) §1.
- **From the TV browser**: open any page (e.g. the launcher URL) and call
  the bridge functions via the console, or run
  [launcher/recon.html](../launcher/recon.html) — its report includes
  chip, firmware, browser, and the whole bridge surface.
- **Root chain fields**: only after reading
  [ROOT.md](ROOT.md) and [SECURITY.md](../SECURITY.md). The recon page
  alone is read-only and safe.

## Template row

```markdown
| 55U8N | EU | MT9602 | U09.01 | V0000.09.01N.N0704 | 3290 | Chromium 111 | ✅ | ✅ | @you |
```

The launcher column depends only on the firmware generation; the root
column is where SoC and board revisions bite. A ❌ with a note is as
valuable as a ✅.
