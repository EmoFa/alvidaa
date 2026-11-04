# 05 — Bloat: 26 Preset Apps, Native Apps/Services, What Can Be Removed

**Goal:** hide/switch off "pre-loaded junk" without destroying TV/UI functions.  
**Status:** app/service lists **CONFIRMED**; the **effect** of individual deactivations is partly `UNVERIFIED` (test, back up, roll back).

---

## 1. The 26 preset tiles (UI)

Source: `/3rd_rw/appdata/launcher/preset.txt` (live). The tiles are controlled via `Appinfo.json`/`deletedPresetApp.txt`/`Category*.xml`.

| # | App | StartCommand / URL | Type | Boot/On-demand |
|---:|---|---|---|---|
| 1 | Netflix | `netflix` | native (AM) | `am_start.ini` (boot) |
| 2 | Prime Video | `amazon` | native (AM) | on-demand |
| 3 | Disney+ | `https://cd-dmgz.bamgrid.com/bbd/hisense_tv/index.html` | Web | on-demand |
| 4 | maxdome | `http://8577004de253-ott-tv.maxdome.de` | Web | on-demand |
| 5 | YouTube | `youtube` | native/Web | on-demand |
| 6 | Rakuten TV | `https://prod-hisense-ui40-app.rakuten.tv/` | Web | on-demand |
| 7 | rlaxxTV | `https://tvapp.rlaxxtv.com/r/no-animations/720/?customer=Hisense` | Web | on-demand |
| 8 | Chili | `https://hisense.chili.com` | Web | on-demand |
| 9 | UEFA.TV | `https://smarttv.uefa.tv` | Web | on-demand |
| 10 | RTL TVNOW | `https://app.hisense.rtl-smart.tv/` | Web | on-demand |
| 11 | Kidoodle.TV | `https://ctv-vewd.kidoodle.tv` | Web | on-demand |
| 12 | AccuWeather | `accuweather` | native/Web | on-demand |
| 13 | YuppTV | `http://www.yupptv.com/hisense/index.html` | Web | on-demand |
| 14 | Plex | `http://plex.tv/web/tv/hisense?mixedContent=1` | Web | on-demand |
| 15 | Videociety | `https://smarttv3.videociety.de` | Web | on-demand |
| 16 | App Store | `http://2897431816.fxm3751860294.com/?category=apps` | Store/Foxxum | on-demand |
| 17 | Movies | `...?category=movies` | Store | on-demand |
| 18 | Catch up TV | `...?category=catchup` | Store | on-demand |
| 19 | News | `...?category=news` | Store | on-demand |
| 20 | Music | `...?category=music` | Store | on-demand |
| 21 | Sports | `...?category=sport` | Store | on-demand |
| 22 | Search | `...?category=search` | Store | on-demand |
| 23 | Game Center | `http://apps.tvgam.es/tv_games/hisense_portal/production/portal/index.html` | Web | on-demand |
| 24 | TV Browser | `browser` | native (web browser) | on-demand |
| 25 | VIDAA tv | `vidaa-plus` | native/Store | on-demand |
| 26 | VidaaRecon | `http://192.0.2.150:9000/recon.html` | User/Web (`UrlType 36`) | on-demand |

- **Our `VidaaRecon`** is the recon/debug app; in the final setup it may stay or be removed.
- **`TV Browser`** is the web browser (`hisense_browser`); **not** the TV UI.
- **Store/Foxxum URLs** (`2897431816.fxm3751860294.com`) are the app store categories.
- **`PreInstall:true`** on the presets; `UrlType 37` (start web app); our recon `36`.

### 1.1 Hiding tiles: `deletedPresetApp.txt`

File: `/3rd_rw/appdata/launcher/deletedPresetApp.txt` — JSON array of URLs/IDs.  
Example: `templates/hide-preset.json`.

```json
[
  "netflix",
  "amazon",
  "youtube",
  "https://cd-dmgz.bamgrid.com/bbd/hisense_tv/index.html",
  "http://8577004de253-ott-tv.maxdome.de",
  "https://prod-hisense-ui40-app.rakuten.tv/",
  "https://tvapp.rlaxxtv.com/r/no-animations/720/?customer=Hisense",
  "https://hisense.chili.com",
  "https://smarttv.uefa.tv",
  "https://app.hisense.rtl-smart.tv/",
  "https://ctv-vewd.kidoodle.tv",
  "http://www.yupptv.com/hisense/index.html",
  "http://plex.tv/web/tv/hisense?mixedContent=1",
  "https://smarttv3.videociety.de",
  "http://apps.tvgam.es/tv_games/hisense_portal/production/portal/index.html",
  "http://2897431816.fxm3751860294.com/?category=apps",
  "http://2897431816.fxm3751860294.com/?category=movies",
  "http://2897431816.fxm3751860294.com/?category=catchup",
  "http://2897431816.fxm3751860294.com/?category=news",
  "http://2897431816.fxm3751860294.com/?category=music",
  "http://2897431816.fxm3751860294.com/?category=sport",
  "http://2897431816.fxm3751860294.com/?category=search"
]
```

- **IDs** (`netflix`, `amazon`, `youtube`, `browser`, `vidaa-plus`, `accuweather`) for native apps; **URLs** for web/store.
- **`preset.txt` is only a cache:** the hide list is the persistent lever. The UI/`ldi.js` filters with it.
- **As of 2026-10-26:** the old probe entries (data:, javascript:, 127.0.0.1;cd…) were removed during cleanup; the file is now `[]`. To hide apps, add the list above (or a subset).
- **Backup:** `cp deletedPresetApp.txt /3rd_rw/backup/`.
- **Effect:** restart the UI/launcher; a reboot definitely takes effect.

### 1.2 Removing a user app

`/3rd_rw/appdata/launcher/Appinfo.json` → remove the `VidaaRecon` entry; restart the UI.  
Or remove the `preset.txt` entry (cache); the `Appinfo` entry is the actual user app.

### 1.3 `preset.txt` / `Category*.xml` / `serviceUpdate.xml`

- **`preset.txt`:** cache; can be rewritten by the UI/`allAppsWriteToFileForUse`.
- **`Category_1001_*.xml`/`Category_57_*.xml`/`CategoryIndex.xml`/`CategoryList_*.xml`/`PicInfo.xml`:** the store/launcher source; change only with a backup (the `LauncherService` can update them).
- **`serviceUpdate.xml`:** country/timestamp; decides `launcher/data` (active) vs. `UI/data` (default). If you want your own categories, keep country/timestamp consistent or edit `UI/data/` as a fallback.
- **Icons:** `res/`; `cache/index.json`; `Image`/`IconURL`/`Thumb`/`Icon_96`.

### 1.4 "Saving space"?

**No, not by deleting the presets.** `/3rd` is a **ro squashfs (100% full)**; the apps live there. Hiding tiles/deactivating AM sections saves **runtime**, not flash storage.  
- `/3rd_rw`: 489 MB free; `/data`: 1.9 GB free.  
- To shrink `/3rd`, you would have to repack/reflash the squashfs → **not** part of this path.

---

## 2. Native apps / services — matrix

### 2.1 Boot apps (`am_start.ini`)

| App/Section | Exec | Role | Recommendation |
|---|---|---|---|
| `dtv_app_mtk` | `/basic/dtv_svc` | TV core (tuner/DTV/navigator) | **keep** |
| `securetime` | `/3rd/playready/securetime` | PlayReady Secure Time | keep if DRM/Netflix; otherwise optional |
| `netflix` | `/3rd/netflix/nrd-app/netflix` | Netflix | optional (off if unused) |
| `dialserver` | `/3rd/dialserver/dialserver` | DIAL/CAST | optional |
| `samba_relay_agent` | `/3rd/samba/samba-relay-agent` | Samba relay (9090) | optional |
| `browser_base` | `/3rd/internet_browser/browser -x bws_background` | background browser | optional |

### 2.2 On-demand / `am_config`

| App | Exec | Role | Recommendation |
|---|---|---|---|
| `opera4x` | `/3rd/opera4x/browser/run-Browser.sh` | web browser (`hisense_browser`) | keep (TV Browser/Recon) |
| `opera_browser` | `/3rd/internet_browser/browser` | internet browser variant | optional |
| `opera_tv_store` | `/3rd/internet_browser/browser` | TV Store | optional |
| `youtube` | internet browser (`youtube.com/tv`) | YouTube Web | optional |
| `youtube_kids`/`youtube_tv` | `/3rd/cobalt/cobalt` | Cobalt YouTube | optional |
| `cobalt` | `/3rd/cobalt/cobalt` | Cobalt | optional |
| `amazon_ignition` | `/3rd/amazon/bin/ignition` | Amazon | optional |
| `factory_lite` | `/3rd/his_factory/factory_lite` | factory menu | keep (service menu) or optional |
| `huluplus`, `hotlist`, `generic_osd` | internet browser | legacy/store | optional |
| `vudu` (referenced) | — | store/region | optional |
| `diskcache` | `/3rd/netflix/diskCache` | Netflix cache | only with Netflix |

### 2.3 Late services (`delayrun.sh`)

| Service | Path | Role | Recommendation |
|---|---|---|---|
| `swrc-server` | `/3rd/swrc-server/swrc-server` | software remote control | optional (remote app) |
| `runlogservice` | `/3rd/his_runlog/runlogservice.sh` | run/logging | optional (logs) |
| `LauncherService` | `/3rd/launcherservice/bin/LauncherService` | launcher/app data/UI | **keep** (UI data) |
| `Seriallog` | `/3rd/Serial_log/Seriallog` | serial logging | optional |
| `HamService` | `/3rd/hamservice/HamService` | ACR/Hisense | **keep wrapper** (SSH/root loop); real HamService optional |
| `swap` | `mmcblk0p34` | swap | optional (performance) |

### 2.4 `ms_service` / UI / AM

| Component | Path | Role | Recommendation |
|---|---|---|---|
| `ms_service` | `/3rd/ms-screen/ms_service` | DLNA/MediaServer | optional (only with DLNA) |
| `hisenseUI` | `/3rd/opera4x/hisenseUI/bin/hisenseUI` | TV UI (GLES) | **keep** (UI) |
| `app_man` | `/basic/app_man` | AM/native apps | **keep** (TV/apps) |
| `dtv_svc` | `/basic/dtv_svc` | TV core | **keep** |
| `browser_base` | `/3rd/internet_browser/browser` | background browser | optional |
| `LauncherService` | see above | UI data | **keep** |
| `HamService` | see above | ACR | keep wrapper; real one optional |

### 2.5 What **not** to disable

- **`dtv_app_mtk`/`dtv_svc`**: TV/tuner/navigator; otherwise no TV/picture.
- **`app_man`**: native apps/AM; otherwise Netflix/YouTube/TV etc. will not start. For a pure custom UI you could stub it, but that is risky (remote/TV/apps).
- **`hisenseUI`**: the UI; without it, a black screen (unless you start your own UI).
- **`LauncherService`**: the UI app data; without it, possibly empty/missing tiles.
- **SSH/root loop** (`HamService` wrapper): your rescue path.
- **`securetime`**, if you use DRM/Netflix.

---

## 3. How to disable? (three clean paths)

### 3.1 UI tiles: `deletedPresetApp.txt`

- Simplest, reversible path; no AM/service intervention.
- See 1.1; back up; restart the UI/reboot.

### 3.2 Native AM apps: modified `am_start.ini`/`am_config` via `developer.sh`

- Copy to `/3rd_rw/etc/`:
  ```sh
  cp /basic/am_start.ini /3rd_rw/etc/am_start.ini
  cp /basic/am_config    /3rd_rw/etc/am_config
  # remove sections/App_sect (e.g. netflix, dialserver, samba, browser_base)
  ```
- In `/3rd_rw/developer.sh` (before `app_man`, line 177):
  ```sh
  mount --bind /3rd_rw/etc/am_start.ini /basic/am_start.ini
  mount --bind /3rd_rw/etc/am_config    /basic/am_config
  ```
- **Reboot**; check `ps`/AM; back up/roll back via `umount`/reboot.
- **Do not** remove `dtv_app_mtk`/`dtv_svc`/`app_man`; `securetime` only without DRM.

### 3.3 Late services: modified `delayrun.sh` via `developer.sh`

- Copy to `/3rd_rw/etc/delayrun.sh`; remove unwanted lines (`swrc`, `runlog`, `Seriallog`; keep `LauncherService`/`HamService`).
- In `developer.sh`:
  ```sh
  mount --bind /3rd_rw/etc/delayrun.sh /basic/delayrun.sh
  ```
- **Keep** `LauncherService` (UI) and the `HamService` wrapper (SSH/root loop).
- **`ms_service`** is not in `delayrun`, but in `autorun.sh` (line 162). To disable:
  ```sh
  # developer.sh, before line 162:
  mkdir -p /3rd_rw/stubs
  printf '#!/bin/sh\nexit 0\n' > /3rd_rw/stubs/true
  chmod 755 /3rd_rw/stubs/true
  mount --bind /3rd_rw/stubs/true /3rd/ms-screen/ms_service
  ```
- **`start-UI.sh`/`app_man`** stub only if you want your own UI/no native apps; risky.

### 3.4 ACR/HamService

- The wrapper `/3rd_rw/hamservice/HamService` starts the root loop + SSH and `exec`s the real HamService.
- **ACR off, SSH/loop on:** replace `exec /3rd/hamservice/HamService "$@"` with `exit 0` (or disable the HamService config, `UNVERIFIED`).
- **HamService completely off:** keep the wrapper (for SSH/loop), do not start the real service; `startHam.sh` only calls the wrapper. 
- **Do not lose the root loop/SSH:** before changing anything, test that you can get back in via SSH.

---

## 4. Space / runtime

- **Runtime bloat** (processes/RAM/CPU) can be reduced via 3.1–3.4.
- **Flash space** is **not** freed: `/3rd`/rootfs are ro squashfs (100%). Deleting files in `/3rd` is not possible; only hiding/stubbing.
- `/3rd_rw` 489 MB free; `/data` 1.9 GB free; `/perm` 3.5 MB free.
- **No package manager**, no "uninstall" in the distro sense.

---

## 5. Risk/rollback matrix

| Change | Risk | Rollback |
|---|---|---|
| `deletedPresetApp.txt` | low (tiles gone) | restore backup; restart UI |
| `Appinfo.json` | low (user app gone) | restore backup; restart UI |
| `Category*.xml`/`preset` | medium (empty/wrong tiles) | backup; restart `LauncherService`/UI |
| `am_start.ini`/`am_config` | medium–high (apps/TV) | `umount`/backup; reboot |
| `delayrun.sh` | medium (services/logs/UI) | `umount`/backup; reboot |
| `ms_service` stub | low (DLNA gone) | `umount`; reboot |
| `start-UI` stub/custom UI | high (black screen) | backup `UI/index.html`; SSH/root loop; restart UI |
| `app_man`/`dtv_svc` off | high (TV/apps) | `umount`/backup; reboot |
| `HamService` wrapper | medium (SSH/loop gone) | original symlink; `/3rd_rw/sshd/start_sshd.sh`; reboot |
| `patch/opera4x` full overlay | high (browser/UI missing) | remove patch folder; reboot |

**Always:** back up to `/3rd_rw/backup/`; test SSH/root loop; one change per test; no flashing.

---

## 6. "Keep" list (for a stable, lean system)

- **TV/UI:** `dtv_svc`/`dtv_app_mtk`, `hisenseUI`, `app_man`, `LauncherService`, `securetime` (with DRM).
- **Access:** `HamService` wrapper (SSH/root loop), `/3rd_rw/sshd`, `root_loop.sh`.
- **Web:** `opera4x`/`hisense_browser` (TV Browser/Recon), `browser_base` only if needed.
- **Data:** `/3rd_rw/appdata/launcher` (tiles), `/3rd_rw/UI` (UI), `/3rd_rw/backup`.
- **Optional off:** Netflix, YouTube/Cobalt, Amazon, DIAL, Samba, `ms_service`, `swrc`, `runlog`, `Seriallog`, ACR/HamService (real), Vudu/Hulu/Hotlist/GenericOSD, diskcache.

---

## 7. Unknowns

- Exact consequences of switching off `ms_service`/`swrc`/`runlog`/`Seriallog`/`HamService`/`securetime`/`browser_base`/`app_man` (depending on UI/store/DRM).
- Whether `LauncherService`/`allAppsWriteToFileForUse` rewrites `preset.txt`/`Category*.xml`/`deletedPresetApp.txt` on every start/update (the hide list is the robust lever).
- Whether `preset.txt`/`Appinfo`/`Category` changes need a UI/launcher restart or a reboot (a UI restart is usually enough; a reboot is safe).
- Whether the store/Foxxum data (`serviceUpdate`/`Category*`) is overwritten on a network/store update.
- Whether `VIDAAU2Launcher` is active on this model (the active UI is `/3rd_rw/UI`).
