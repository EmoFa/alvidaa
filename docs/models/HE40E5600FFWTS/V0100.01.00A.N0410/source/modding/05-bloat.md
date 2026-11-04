# 05 — Bloat: 26 Preset-Apps, Native-Apps/Services, was weg kann

**Ziel:** „Pre-loaded Müll“ ausblenden/abschalten, ohne die TV-/UI-Funktionen zu zerstören.  
**Status:** App-/Service-Listen **CONFIRMED**; die **Wirkung** einzelner Deaktivierungen ist teils `UNVERIFIED` (testen, backupen, rollback).

---

## 1. Die 26 Preset-Tiles (UI)

Quelle: `/3rd_rw/appdata/launcher/preset.txt` (live). Die Tiles werden über `Appinfo.json`/`deletedPresetApp.txt`/`Category*.xml` gesteuert.

| # | App | StartCommand / URL | Typ | Boot/On-demand |
|---:|---|---|---|---|
| 1 | Netflix | `netflix` | native (AM) | `am_start.ini` (Boot) |
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
| 24 | TV Browser | `browser` | native (Web-Browser) | on-demand |
| 25 | VIDAA tv | `vidaa-plus` | native/Store | on-demand |
| 26 | VidaaRecon | `http://192.0.2.150:9000/recon.html` | User/Web (`UrlType 36`) | on-demand |

- **Unser `VidaaRecon`** ist die Recon-/Debug-App; im finalen Setup darf sie bleiben oder entfernt werden.
- **`TV Browser`** ist der Web-Browser (`hisense_browser`); **nicht** die TV-UI.
- **Store-/Foxxum-URLs** (`2897431816.fxm3751860294.com`) sind die App-Store-Kategorien.
- **`PreInstall:true`** bei den Presets; `UrlType 37` (Start Web App); unser Recon `36`.

### 1.1 Tiles ausblenden: `deletedPresetApp.txt`

Datei: `/3rd_rw/appdata/launcher/deletedPresetApp.txt` — JSON-Array von URLs/IDs.  
Beispiel: `templates/hide-preset.json`.

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

- **IDs** (`netflix`, `amazon`, `youtube`, `browser`, `vidaa-plus`, `accuweather`) für native Apps; **URLs** für Web/Store.
- **`preset.txt` ist nur Cache:** die Hide-Liste ist der persistente Hebel. Die UI/`ldi.js` filtert damit.
- **Stand 2026-10-26:** Die alten Probe-Einträge (data:, javascript:, 127.0.0.1;cd…) wurden beim Cleanup entfernt; die Datei ist jetzt `[]`. Zum Ausblenden die obige Liste (oder eine Teilmenge) eintragen.
- **Backup:** `cp deletedPresetApp.txt /3rd_rw/backup/`.
- **Wirkung:** UI/Launcher neu starten; reboot wirkt sicher.

### 1.2 User-App entfernen

`/3rd_rw/appdata/launcher/Appinfo.json` → `VidaaRecon`-Eintrag entfernen; UI neu starten.  
Oder `preset.txt`-Eintrag (Cache) entfernen; der `Appinfo`-Eintrag ist die eigentliche User-App.

### 1.3 `preset.txt` / `Category*.xml` / `serviceUpdate.xml`

- **`preset.txt`:** Cache; kann von der UI/`allAppsWriteToFileForUse` neu geschrieben werden.
- **`Category_1001_*.xml`/`Category_57_*.xml`/`CategoryIndex.xml`/`CategoryList_*.xml`/`PicInfo.xml`:** die Store-/Launcher-Quelle; Änderungen nur mit Backup (der `LauncherService` kann sie aktualisieren).
- **`serviceUpdate.xml`:** Land/Timestamp; entscheidet `launcher/data` (aktiv) vs. `UI/data` (Default). Wenn du eigene Kategorien willst, halte Land/Timestamp konsistent oder bearbeite `UI/data/` als Fallback.
- **Icons:** `res/`; `cache/index.json`; `Image`/`IconURL`/`Thumb`/`Icon_96`.

### 1.4 „Platz sparen“?

**Nein, nicht durch Löschen der Presets.** `/3rd` ist ein **ro squashfs (100 % voll)**; die Apps liegen dort. Tiles ausblenden/AM-Sektionen deaktivieren spart **Runtime**, nicht Flash-Speicher.  
- `/3rd_rw`: 489 MB frei; `/data`: 1.9 GB frei.  
- Um `/3rd` zu verkleinern, müsste man das squashfs neu packen/flashen → **nicht** Teil dieses Wegs.

---

## 2. Native Apps / Services — Matrix

### 2.1 Boot-Apps (`am_start.ini`)

| App/Section | Exec | Rolle | Empfehlung |
|---|---|---|---|
| `dtv_app_mtk` | `/basic/dtv_svc` | TV-Kern (Tuner/DTV/Navigator) | **behalten** |
| `securetime` | `/3rd/playready/securetime` | PlayReady Secure Time | behalten, wenn DRM/Netflix; sonst optional |
| `netflix` | `/3rd/netflix/nrd-app/netflix` | Netflix | optional (aus, wenn nicht genutzt) |
| `dialserver` | `/3rd/dialserver/dialserver` | DIAL/CAST | optional |
| `samba_relay_agent` | `/3rd/samba/samba-relay-agent` | Samba-Relay (9090) | optional |
| `browser_base` | `/3rd/internet_browser/browser -x bws_background` | Hintergrund-Browser | optional |

### 2.2 On-demand / `am_config`

| App | Exec | Rolle | Empfehlung |
|---|---|---|---|
| `opera4x` | `/3rd/opera4x/browser/run-Browser.sh` | Web-Browser (`hisense_browser`) | behalten (TV Browser/Recon) |
| `opera_browser` | `/3rd/internet_browser/browser` | Internet-Browser-Variante | optional |
| `opera_tv_store` | `/3rd/internet_browser/browser` | TV Store | optional |
| `youtube` | Internet-Browser (`youtube.com/tv`) | YouTube Web | optional |
| `youtube_kids`/`youtube_tv` | `/3rd/cobalt/cobalt` | Cobalt-YouTube | optional |
| `cobalt` | `/3rd/cobalt/cobalt` | Cobalt | optional |
| `amazon_ignition` | `/3rd/amazon/bin/ignition` | Amazon | optional |
| `factory_lite` | `/3rd/his_factory/factory_lite` | Factory-Menü | behalten (Service-Menü) oder optional |
| `huluplus`, `hotlist`, `generic_osd` | Internet-Browser | Legacy/Store | optional |
| `vudu` (referenziert) | — | Store/Region | optional |
| `diskcache` | `/3rd/netflix/diskCache` | Netflix-Cache | nur mit Netflix |

### 2.3 Späte Services (`delayrun.sh`)

| Service | Pfad | Rolle | Empfehlung |
|---|---|---|---|
| `swrc-server` | `/3rd/swrc-server/swrc-server` | Software-Remote-Control | optional (Remote-App) |
| `runlogservice` | `/3rd/his_runlog/runlogservice.sh` | Run-/Logging | optional (Logs) |
| `LauncherService` | `/3rd/launcherservice/bin/LauncherService` | Launcher-/App-Daten/UI | **behalten** (UI-Daten) |
| `Seriallog` | `/3rd/Serial_log/Seriallog` | serielles Logging | optional |
| `HamService` | `/3rd/hamservice/HamService` | ACR/Hisense | **Wrapper behalten** (SSH/Root-Loop); echtes HamService optional |
| `swap` | `mmcblk0p34` | Swap | optional (Performance) |

### 2.4 `ms_service` / UI / AM

| Komponente | Pfad | Rolle | Empfehlung |
|---|---|---|---|
| `ms_service` | `/3rd/ms-screen/ms_service` | DLNA/MediaServer | optional (nur mit DLNA) |
| `hisenseUI` | `/3rd/opera4x/hisenseUI/bin/hisenseUI` | TV-UI (GLES) | **behalten** (UI) |
| `app_man` | `/basic/app_man` | AM/native Apps | **behalten** (TV/Apps) |
| `dtv_svc` | `/basic/dtv_svc` | TV-Kern | **behalten** |
| `browser_base` | `/3rd/internet_browser/browser` | Hintergrund-Browser | optional |
| `LauncherService` | siehe oben | UI-Daten | **behalten** |
| `HamService` | siehe oben | ACR | Wrapper behalten; echtes optional |

### 2.5 Was **nicht** deaktivieren

- **`dtv_app_mtk`/`dtv_svc`**: TV/Tuner/Navigator; sonst kein TV/Bild.
- **`app_man`**: native Apps/AM; sonst starten Netflix/YouTube/TV etc. nicht. Für eine reine Custom-UI könnte man ihn stubben, aber das ist riskant (Remote/TV/Apps).
- **`hisenseUI`**: die UI; ohne sie schwarzer Bildschirm (es sei denn, du startest eine eigene UI).
- **`LauncherService`**: die UI-App-Daten; ohne ihn ggf. leere/fehlende Tiles.
- **SSH/Root-Loop** (`HamService`-Wrapper): dein Rettungsweg.
- **`securetime`**, wenn du DRM/Netflix nutzt.

---

## 3. Wie deaktivieren? (drei saubere Wege)

### 3.1 UI-Tiles: `deletedPresetApp.txt`

- Einfachster, reversibler Weg; kein AM/Service-Eingriff.
- Siehe 1.1; Backup; UI neu starten/reboot.

### 3.2 Native AM-Apps: modifizierte `am_start.ini`/`am_config` per `developer.sh`

- Kopie nach `/3rd_rw/etc/`:
  ```sh
  cp /basic/am_start.ini /3rd_rw/etc/am_start.ini
  cp /basic/am_config    /3rd_rw/etc/am_config
  # Sektionen/App_sect entfernen (z. B. netflix, dialserver, samba, browser_base)
  ```
- In `/3rd_rw/developer.sh` (vor `app_man`, Zeile 177):
  ```sh
  mount --bind /3rd_rw/etc/am_start.ini /basic/am_start.ini
  mount --bind /3rd_rw/etc/am_config    /basic/am_config
  ```
- **Reboot**; `ps`/AM prüfen; Backup/Rollback per `umount`/reboot.
- **Nicht** `dtv_app_mtk`/`dtv_svc`/`app_man` entfernen; `securetime` nur ohne DRM.

### 3.3 Späte Services: modifizierte `delayrun.sh` per `developer.sh`

- Kopie nach `/3rd_rw/etc/delayrun.sh`; unerwünschte Zeilen entfernen (`swrc`, `runlog`, `Seriallog`; `LauncherService`/`HamService` behalten).
- In `developer.sh`:
  ```sh
  mount --bind /3rd_rw/etc/delayrun.sh /basic/delayrun.sh
  ```
- `LauncherService` (UI) und `HamService`-Wrapper (SSH/Root-Loop) **behalten**.
- **`ms_service`** ist nicht in `delayrun`, sondern in `autorun.sh` (Zeile 162). Deaktivieren:
  ```sh
  # developer.sh, vor Zeile 162:
  mkdir -p /3rd_rw/stubs
  printf '#!/bin/sh\nexit 0\n' > /3rd_rw/stubs/true
  chmod 755 /3rd_rw/stubs/true
  mount --bind /3rd_rw/stubs/true /3rd/ms-screen/ms_service
  ```
- **`start-UI.sh`/`app_man`** stubben nur, wenn du eine eigene UI/keine nativen Apps willst; riskant.

### 3.4 ACR/HamService

- Der Wrapper `/3rd_rw/hamservice/HamService` startet Root-Loop + SSH und `exec`t das echte HamService.
- **ACR aus, SSH/Loop an:** `exec /3rd/hamservice/HamService "$@"` durch `exit 0` ersetzen (oder HamService-Config deaktivieren, `UNVERIFIED`).
- **HamService ganz aus:** Wrapper behalten (für SSH/Loop), echtes Service nicht starten; `startHam.sh` ruft nur den Wrapper. 
- **Root-Loop/SSH nicht verlieren:** vor Änderung testen, dass du per SSH wieder rein kommst.

---

## 4. Platz / Runtime

- **Runtime-Bloat** (Prozesse/RAM/CPU) lässt sich durch 3.1–3.4 reduzieren.
- **Flash-Platz** wird **nicht** frei: `/3rd`/Rootfs sind ro squashfs (100 %). Löschen von Dateien in `/3rd` ist nicht möglich; nur ausblenden/stubben.
- `/3rd_rw` 489 MB frei; `/data` 1.9 GB frei; `/perm` 3.5 MB frei.
- **Kein Package Manager**, kein „Uninstall“ im Distro-Sinn.

---

## 5. Risiko-/Rollback-Matrix

| Änderung | Risiko | Rollback |
|---|---|---|
| `deletedPresetApp.txt` | niedrig (Tiles weg) | Backup zurück; UI neu starten |
| `Appinfo.json` | niedrig (User-App weg) | Backup zurück; UI neu starten |
| `Category*.xml`/`preset` | mittel (leere/falsche Tiles) | Backup; `LauncherService`/UI neu starten |
| `am_start.ini`/`am_config` | mittel–hoch (Apps/TV) | `umount`/Backup; reboot |
| `delayrun.sh` | mittel (Services/Logs/UI) | `umount`/Backup; reboot |
| `ms_service`-Stub | niedrig (DLNA weg) | `umount`; reboot |
| `start-UI`-Stub/Custom-UI | hoch (schwarzer Bildschirm) | Backup `UI/index.html`; SSH/root-Loop; UI neu starten |
| `app_man`/`dtv_svc` aus | hoch (TV/Apps) | `umount`/Backup; reboot |
| `HamService`-Wrapper | mittel (SSH/Loop weg) | Original-Symlink; `/3rd_rw/sshd/start_sshd.sh`; reboot |
| `patch/opera4x` full overlay | hoch (Browser/UI fehlt) | Patch-Ordner entfernen; reboot |

**Immer:** Backup nach `/3rd_rw/backup/`; SSH/Root-Loop testen; eine Änderung pro Test; kein Flash.

---

## 6. „Keep“-Liste (für ein stabiles, schlankes System)

- **TV/UI:** `dtv_svc`/`dtv_app_mtk`, `hisenseUI`, `app_man`, `LauncherService`, `securetime` (bei DRM).
- **Zugang:** `HamService`-Wrapper (SSH/Root-Loop), `/3rd_rw/sshd`, `root_loop.sh`.
- **Web:** `opera4x`/`hisense_browser` (TV Browser/Recon), `browser_base` nur wenn nötig.
- **Daten:** `/3rd_rw/appdata/launcher` (Tiles), `/3rd_rw/UI` (UI), `/3rd_rw/backup`.
- **Optional aus:** Netflix, YouTube/Cobalt, Amazon, DIAL, Samba, `ms_service`, `swrc`, `runlog`, `Seriallog`, ACR/HamService (echt), Vudu/Hulu/Hotlist/GenericOSD, Diskcache.

---

## 7. Unknowns

- Exakte Folgen des Abschaltens von `ms_service`/`swrc`/`runlog`/`Seriallog`/`HamService`/`securetime`/`browser_base`/`app_man` (je nach UI/Store/DRM).
- Ob `LauncherService`/`allAppsWriteToFileForUse` die `preset.txt`/`Category*.xml`/`deletedPresetApp.txt` bei jedem Start/Update neu schreibt (Hide-Liste ist der robuste Hebel).
- Ob `preset.txt`/`Appinfo`/`Category`-Änderungen einen UI-/Launcher-Neustart oder Reboot brauchen (UI-Restart reicht meist; reboot sicher).
- Ob die Store-/Foxxum-Daten (`serviceUpdate`/`Category*`) bei Netzwerk/Store-Update überschrieben werden.
- Ob `VIDAAU2Launcher` auf diesem Modell aktiv ist (die aktive UI ist `/3rd_rw/UI`).
