# 04 — Modding: Rezepte für eigene UI, Apps, Services, Bloat

**Voraussetzung:** Root + SSH (siehe `../root/ROOT-GUIDE.md`).  
**Spielregel:** Eine Änderung, dann testen, dann die nächste. Backup vorher. SSH/Root-Loop als Rettungsweg behalten. Kein Flash/`.pkg`.

Die Rezepte sind nach Risiko sortiert:

| Route | Ziel | Risiko | Reversibel |
|---|---|---|---|
| **A** | Eigene App-Tile (Web-App im Browser) | niedrig | ja (Datei-Backup) |
| **B** | Eigene UI-Seite (`/3rd_rw/UI/index.html`) | mittel | ja (Backup + UI-Restart) |
| **C** | Launcher-Daten/Skin (Tiles, Kategorien, Icons) | niedrig–mittel | ja (Backup) |
| **D** | Eigener Service/eigene Funktion (root) | mittel | ja (Skripte/Wrapper) |
| **E** | Ro-Dateien per Bind-Mount/Overlay patchen | mittel–hoch | ja (Unmount/Reboot) |
| **F** | Statische Tools/SSH/Deploy | niedrig | ja |

---

## Route A — Eigene App-Tile (der sichere Einstieg)

**Ziel:** Ein eigener Eintrag im Launcher, der eine lokale oder HTTP-Seite im **Web-Browser** öffnet (nicht die UI ersetzt).

### A.1 Seite bauen

Lokal auf dem TV (rw):

```
/3rd_rw/appdata/custom/index.html
/3rd_rw/appdata/custom/app.js
/3rd_rw/appdata/custom/icon.png
```

Beispiel `index.html`:

```html
<!doctype html>
<html><head><meta charset="utf-8"><title>MyApp</title>
<style>body{background:#111;color:#eee;font-family:sans-serif;margin:0;padding:2em}</style>
</head><body>
<h1>MyApp</h1>
<p>Läuft im hisense_browser (root, --allow-file-access-from-files).</p>
<button onclick="hi()">HiBrowser test</button>
<pre id="out"></pre>
<script>
function hi(){
  var o={};
  try{o.hb=(typeof HiBrowser);}catch(e){o.hb=String(e);}
  try{o.file=(typeof HiBrowser!=='undefined')?String(HiBrowser.File.download("file:///3rd_rw/root_proof.txt","myapp_proof.txt",1)):"no";}catch(e){o.file=String(e);}
  document.getElementById('out').textContent=JSON.stringify(o,null,2);
}
</script>
</body></html>
```

- HTTP-Variante: Seite auf dem Host (`http://<host>:9000/...`) servieren; der TV-Browser lädt sie.
- Lokal-Variante: `file:///3rd_rw/appdata/custom/index.html`; der Browser hat `--allow-file-access-from-files`.
- Die Seite kann `HiBrowser` (`File`, `System`, `loadLibrary`, `Cache`, `JsonWrite`) und `Hisense_*` nutzen. Root-Kontext.

### A.2 `Appinfo.json` ergänzen

Datei: `/3rd_rw/appdata/launcher/Appinfo.json` (rw). **Backup:**

```sh
cp /3rd_rw/appdata/launcher/Appinfo.json /3rd_rw/backup/Appinfo.json.$(date +%s)
```

Eintrag ergänzen (bestehende `AppInfo`-Einträge behalten!):

```json
{"AppInfo":[
  {"AppId":"MyApp",
   "Thumb":"file:///3rd_rw/appdata/custom/icon.png",
   "Icon_96":"file:///3rd_rw/appdata/custom/icon.png",
   "Image":"file:///3rd_rw/appdata/custom/icon.png",
   "URL":"file:///3rd_rw/appdata/custom/index.html",
   "AppName":"MyApp",
   "Title":"MyApp",
   "IconURL":"file:///3rd_rw/appdata/custom/icon.png",
   "StartCommand":"file:///3rd_rw/appdata/custom/index.html",
   "InstallTime":"2026-10-26",
   "RunTimes":0,
   "StoreType":"foxxum",
   "PreInstall":false}
]}
```

- `StartCommand`/`URL` = HTTP oder `file://`.
- `Image`/`IconURL`/`Thumb`/`Icon_96` = Icon; HTTP/`file://`; Fallback `useDefaultImg`.
- `StoreType` als String (`"foxxum"`; die UI mappt über `storeTypeList`).
- `PreInstall:false` (User-App); `canRemove=true`.

**Per TV-Seite/JS** (ohne SSH):

```js
// Backup lesen (optional)
var old = fileXHR("file:///3rd_rw/appdata/launcher/Appinfo.json");
// Neuen Inhalt schreiben
HiBrowser.File.write("launcher/Appinfo.json", newJsonString, 1);
```

`File.write` schreibt Text; das JSON ist Text. (Für Binär-Icons: `File.download` von HTTP/`file://`.)

### A.3 Launcher/UI neu laden

- UI neu starten (siehe `03`, Abschnitt 8): `kill <hisenseUI-PID>`; `nohup /3rd/opera4x/hisenseUI/start-UI.sh &`.
- Oder TV rebooten.
- Im Launcher/„Alle Apps“ erscheint die Tile; Launch öffnet den **Web-Browser** mit der URL (nicht die UI-Seite).

### A.4 Test / Rollback

- Test: Tile öffnen; `HiBrowser`-Testbutton; `file://`-Seite; HTTP-Seite.
- Rollback: `Appinfo.json`-Backup zurückkopieren; UI neu starten. Oder Eintrag entfernen.
- **Nicht** `preset.txt` für User-Apps missbrauchen; der `preset`-Cache kann überschrieben werden. `Appinfo.json` ist der richtige Ort.

---

## Route B — Eigene UI-Seite (`/3rd_rw/UI/index.html`)

**Ziel:** Die TV-UI (PIXI/`hisenseUI`) durch eine eigene Seite ersetzen. **Höchstes Risiko** (schwarzer Bildschirm), aber machbar.

### B.1 Backup

```sh
mkdir -p /3rd_rw/backup
cp -a /3rd_rw/UI /3rd_rw/backup/UI.$(date +%Y%m%d-%H%M%S)
```

### B.2 Minimale Custom-UI bauen

Datei: `/3rd_rw/UI/custom.html` (neu; `index.html` bleibt vorerst unangetastet).  
Vorlage: `templates/custom-ui.html`.

```html
<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=1280,height=720">
<title>My TV</title>
<style>
html,body{margin:0;width:100%;height:100%;background:#0b0b0b;color:#eee;font-family:sans-serif;overflow:hidden}
.wrap{padding:2vw}.row{display:flex;gap:1vw;flex-wrap:wrap}
button{font-size:1.4vw;padding:1vw 1.6vw;border-radius:.6vw;border:1px solid #555;background:#1c1c1c;color:#eee}
pre{font-size:1vw;color:#9f9}
</style></head>
<body><div class="wrap">
<h1>My TV</h1>
<div class="row">
  <button onclick="launch('netflix')">Netflix</button>
  <button onclick="launch('youtube')">YouTube</button>
  <button onclick="launch('opera4x')">TV Browser</button>
  <button onclick="launch('dtv_app_mtk')">TV</button>
  <button onclick="probe()">APIs</button>
</div>
<pre id="out"></pre>
<script>
function launch(id){
  var o={};
  try{
    if (typeof Hisense_StartApp === 'function') { Hisense_StartApp(':am,'+id+',:start='+id); o.via='Hisense_StartApp'; }
    else if (typeof HiBrowser !== 'undefined' && HiBrowser.System) { HiBrowser.System.startApp(':am,'+id+',:start='+id); o.via='HiBrowser'; }
    else if (typeof TVAPI !== 'undefined' && TVAPI.StartApp) { TVAPI.StartApp(id); o.via='TVAPI'; }
    else if (typeof guijs !== 'undefined' && guijs.StartApp) { guijs.StartApp(id); o.via='guijs'; }
    else o.via='none';
  }catch(e){o.err=String(e);}
  document.getElementById('out').textContent=JSON.stringify(o,null,2);
}
function probe(){
  var o={Hisense_StartApp:typeof Hisense_StartApp,HiBrowser:typeof HiBrowser,TVAPI:typeof TVAPI,guijs:typeof guijs,model:typeof model,UI:typeof UI};
  document.getElementById('out').textContent=JSON.stringify(o,null,2);
}
</script></div></body></html>
```

- **API-Verfügbarkeit ist `UNVERIFIED`**: Im UI-DevTools (9223) prüfen, welche Globals existieren und welche Signatur `Hisense_StartApp`/`TVAPI.StartApp`/`guijs.StartApp` hat. Der Web-Browser hat `HiBrowser.System.startApp(":am,…")` (belegt); die UI kann andere Wrapper haben.
- Größe: UI nutzt 1280×720 CSS (PIXI-Canvas); der Screen ist 1920×1080 (`OPERA_EGL_SCREEN_SIZE`). `100vw/100vh`/`meta viewport` nutzen.

### B.3 Testen, ohne die UI zu ersetzen

1. `custom.html` per Web-Browser öffnen: `http://<host>:9000/...` oder `file:///3rd_rw/UI/custom.html` im **`hisense_browser`** (TV-Browser). Dort `HiBrowser`/`Hisense_*` testen (die UI-spezifischen APIs fehlen evtl.).
2. UI DevTools 9223: `window.location = "file:///3rd_rw/UI/custom.html"` **nur** in einem Test-Tab? Die UI hat ein Fenster; ein Navigieren ersetzt die UI. Besser: Custom-Seite in einem **neuen** `hisenseUI`-Prozess starten (siehe B.5) oder per Web-Browser testen.
3. Wenn die Custom-Seite im Web-Browser gut aussieht, UI übernehmen.

### B.4 `index.html` ersetzen

**Variante 1: Datei ersetzen** (einfach, reversibel per Backup):

```sh
cp /3rd_rw/UI/index.html /3rd_rw/backup/index.orig.html
cp /3rd_rw/UI/custom.html /3rd_rw/UI/index.html
# UI neu starten
kill $(pidof hisenseUI)
nohup /3rd/opera4x/hisenseUI/start-UI.sh >/tmp/hisenseUI.log 2>&1 &
```

**Variante 2: `start-UI.sh` per Bind-Mount auf `custom.html` zeigen** (lässt `index.html` unangetastet):

```sh
# /3rd_rw/patch/start-UI-custom.sh (siehe templates/start-UI-custom.sh)
mount --bind /3rd_rw/patch/start-UI-custom.sh /3rd/opera4x/hisenseUI/start-UI.sh
# UI neu starten
```

Das ist ein **Datei-Bind-Mount**; kein full overlay. `start-UI-custom.sh` startet `hisenseUI` mit `-u file:///3rd_rw/UI/custom.html` und den gleichen Flags wie das Original.

**Variante 3: Vendor-Overlay `/3rd_rw/patch/opera4x`** (full dir bind):

```sh
mkdir -p /3rd_rw/patch/opera4x
cp -a /3rd/opera4x/. /3rd_rw/patch/opera4x/   # vollständige Kopie!
# eigene Dateien überschreiben, z. B. hisenseUI/start-UI.sh
reboot
```

- **Nur mit vollständiger Kopie/Symlink-Baum.** Der `mount -o bind` ersetzt `/3rd/opera4x` komplett. Fehlende Dateien = Browser/UI kaputt.
- Vorteil: überlebt Reboots (autorun bindet vor UI-Start). Nachteil: groß/fehleranfällig.

### B.5 UI-Restart / Rettung

```sh
# UI-Prozess
ps | grep hisenseUI | grep -v grep
kill <PID>
nohup /3rd/opera4x/hisenseUI/start-UI.sh >/tmp/hisenseUI.log 2>&1 &

# Rettung bei schwarzem Bildschirm:
cp /3rd_rw/backup/index.orig.html /3rd_rw/UI/index.html
kill $(pidof hisenseUI)
nohup /3rd/opera4x/hisenseUI/start-UI.sh >/tmp/hisenseUI.log 2>&1 &
```

- **SSH/Root-Loop** funktionieren unabhängig von der UI. Der Web-Browser (`hisense_browser`/Recon) kann ebenfalls weiterlaufen.
- `hisenseUI`-Log: `/tmp/hisenseUI.log`; UI-DevTools 9223 (falls die Seite lädt).
- **Kein Flash**: `index.html`/`custom.html` liegen in `/3rd_rw`; Backup/Rollback per Datei.

### B.6 Was die UI-Seite kann

- **Vollbild-HTML/CSS/JS** im Chromium/Opera-UI-Browser.
- **`Hisense_*`/`TVAPI`/`guijs`/`model`** (UI-Kontext; Signaturen im DevTools prüfen).
- **`file://`**-Zugriff (`--disable-web-security`, `--allow-file-access-from-files`? Das UI hat `--disable-web-security`; lokale Files ja).
- **Video/Canvas/WebGL**; die UI nutzt GLES/Mali.
- **Kein** direkter Shell-Zugriff aus JS; der Root-Loop/SSH ist der Weg für native Aktionen.

---

## Route C — Launcher-Daten/Skin (Tiles, Kategorien, Icons)

**Ziel:** Apps hinzufügen/ausblenden, Kategorien/Icons ändern, ohne die UI-Seite zu ersetzen.

### C.1 Tiles ausblenden (einfach, persistent)

Datei: `/3rd_rw/appdata/launcher/deletedPresetApp.txt` (JSON-Array).  
Beispiel: `templates/hide-preset.json`; die Preinstalled-Liste in `05-bloat.md`.

```json
[
  "netflix",
  "amazon",
  "youtube",
  "https://cd-dmgz.bamgrid.com/bbd/hisense_tv/index.html",
  "http://8577004de253-ott-tv.maxdome.de",
  "https://prod-hisense-ui40-app.rakuten.tv/",
  "https://tvapp.rlaxxtv.com/r/no-animations/720/?customer=Hisense"
]
```

- Der Launcher/`ldi.js` filtert die Kacheln; die `preset.txt` ist nur Cache.
- **Stand 2026-10-26:** Die alten Probe-URLs (data:, javascript:, 127.0.0.1;cd…) wurden beim Cleanup entfernt; die Datei ist jetzt `[]`. Zum Ausblenden die gewünschten Hide-Einträge setzen.
- **Backup:** `cp deletedPresetApp.txt /3rd_rw/backup/...`.
- **Wirkung:** UI/Launcher neu starten (oder reboot).

### C.2 Tiles hinzufügen

- **User-App:** `Appinfo.json` (Route A).
- **Preset:** `preset.txt` ergänzen (`AppName`, `IconURL`, `URL`, `StartCommand`, `UrlType` 37, `StoreType` 0, `PreInstall:true`). **Aber:** `preset.txt` ist ein Cache; die UI/`allAppsWriteToFileForUse` kann sie überschreiben. Für dauerhaft: `Appinfo.json` (User-App) oder die `Category*.xml`-Quelle.
- **Kategorie-XML:** `/3rd_rw/appdata/launcher/data/Category_1001_*.xml`/`Category_57_*.xml`/`CategoryIndex.xml`/`CategoryList_*.xml` — die App-Tiles. Backup; XML-Struktur beibehalten; `preset`/Cache danach neu erzeugen lassen (UI-Restart).
- **`serviceUpdate.xml`:** Land/Timestamp; wenn es nicht zu `DEU` passt, nutzt `ldi.js` `UI/data/`-Default. Für eigene Daten ggf. `UI/data/` bearbeiten (Fallback) oder `serviceUpdate`/`Category` in `launcher/data` konsistent halten.

### C.3 Icons / Skin

- Icons: `res/*.png`; `cache/index.json`; `Image`/`IconURL`/`Thumb`/`Icon_96`; `useDefaultImg` als Fallback.
- Skin/Assets: `/3rd_rw/UI/assets`, `/3rd_rw/UI/templates`, `/3rd_rw/UI/module`, `/3rd_rw/launcher/{css,img,html,js}`, `/3rd_rw/VIDAAU2Launcher/*` (Alt/Alternativ).
- **Aktiv:** `/3rd_rw/UI` (PIXI) + `/3rd_rw/appdata/launcher` (Daten). Die `launcher`/`VIDAAU2Launcher`-HTML/JS sind Alt-/Alternativ-Skins; Änderungen dort nur testen, wenn die UI sie lädt (`UNVERIFIED`).

### C.4 Test / Rollback

- Backup der `Appinfo`/`preset`/`deleted`/`Category*`/`res`.
- UI neu starten; Tiles prüfen; bei Problemen Backup zurück, UI neu starten/reboot.
- Die `deletedPresetApp.txt` ist der sicherste Hide-Hebel (kein XML-Eingriff).

---

## Route D — Eigener Service / eigene Funktion (root)

**Ziel:** Ein eigener Prozess/Skript läuft als root beim Boot oder auf Kommando; native Aktionen, die JS nicht kann.

### D.1 Früher Hook: `/3rd_rw/developer.sh`

Wird von `/basic/autorun.sh` Zeile 90 als root ausgeführt — **vor** `ms_service`/`hisenseUI`/`app_man`/`delayrun`.

Vorlage: `templates/developer.sh`.

```sh
#!/bin/sh
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin
export PATH
exec >>/3rd_rw/developer.log 2>&1
echo "developer.sh $(date) boot=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)"

# Beispiel 1: eigenen Dienst starten
# /3rd_rw/bin/mydaemon &

# Beispiel 2: ro-Datei per Bind-Mount ersetzen (vor app_man)
# mount --bind /3rd_rw/etc/am_start.ini /basic/am_start.ini
# mount --bind /3rd_rw/etc/am_config    /basic/am_config

# Beispiel 3: unerwünschten Dienst stubben (vor autorun-Zeile 162)
# mkdir -p /3rd_rw/stubs
# printf '#!/bin/sh\nexit 0\n' > /3rd_rw/stubs/true
# chmod 755 /3rd_rw/stubs/true
# mount --bind /3rd_rw/stubs/true /3rd/ms-screen/ms_service

# Beispiel 4: custom UI starten (vor autorun-Zeile 168)
# mount --bind /3rd_rw/patch/start-UI-custom.sh /3rd/opera4x/hisenseUI/start-UI.sh

# Beispiel 5: Root-Loop/SSH früher starten (statt HamService-Wrapper)
# /bin/sh /3rd_rw/appdata/root_loop.sh &
# /bin/sh /3rd_rw/sshd/start_sshd.sh &
```

- **Reihenfolge:** `developer.sh` (90) → `ms_service` (162) → `hisenseUI` (168) → `app_man` (177) → `delayrun` (190).
- **Bind-Mounts** von ro-Dateien in `developer.sh` wirken für die späteren Zeilen.
- **Log:** `/3rd_rw/developer.log`; `set -x` optional.
- **Fallback:** SSH/Root-Loop; wenn `developer.sh` die UI/AM blockiert, per SSH korrigieren/entfernen, reboot.

### D.2 Später Hook: `HamService`-Wrapper (aktuell für SSH/Root-Loop)

`/3rd_rw/hamservice/HamService` (Wrapper; `startHam.sh` ruft ihn nach `delayrun` + 15 s):

```sh
#!/bin/sh
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin
export PATH
/bin/sh /3rd_rw/appdata/root_loop.sh >/dev/null 2>&1 &
[ -x /3rd_rw/sshd/start_sshd.sh ] && /bin/sh /3rd_rw/sshd/start_sshd.sh >/dev/null 2>&1 &
exec /3rd/hamservice/HamService "$@"
```

- **Aktuelle Persistenz:** Root-Loop + Dropbear. Das echte `HamService` läuft weiter.
- **ACR abschalten:** `exec /3rd/hamservice/HamService "$@"` durch `exit 0` ersetzen (Root-Loop/SSH bleiben); oder ACR im HamService-Config deaktivieren (UNVERIFIED).
- **Eigene späte Services:** vor dem `exec` starten (z. B. `/3rd_rw/bin/mydaemon &`).
- **Rollback:** `rm /3rd_rw/hamservice/HamService; ln -s /3rd/hamservice/HamService /3rd_rw/hamservice/HamService`.

### D.3 Kommando-Kanal (root_loop)

- `/3rd_rw/appdata/root_loop.sh` liest `root_cmd.sh`, schreibt `root_out.txt`.
- Auf dem TV: `HiBrowser.File.write("root_cmd.sh", "…\n", 1)`; `fileXHR("file:///3rd_rw/appdata/root_out.txt")`.
- Host-Snippet: `../root/scripts/host/run_root_cmd.js`.
- **Root-equivalent:** nur vertrauenswürdige Schreiber (Browser root) zulassen.

### D.4 Native App/Funktion über AM (`:am`)

- `HiBrowser.System.startApp(":am,<app>,:start=<val>")` im Web-Browser (belegt).
- `:am,<app>,:URL=<url>` (aus `app_man`-Strings); `:stop`, `:backgm`, `:foregm`, `:pause`, `:resume`, `:shutdown`, `:suspend`, `:wakeup`.
- **Neue native App** braucht einen `am_config`-Eintrag (`exec`/`args`) — ro; per `developer.sh`-Bind-Mount einer modifizierten `am_config` (vor `app_man`). Oder ein eigener Service über `developer.sh`/`HamService` (kein AM nötig).
- **`Hisense_StartApp`** in der UI: Signatur/Verhalten im UI-DevTools prüfen (`UNVERIFIED`).

### D.5 Native UI (DirectFB/GLES) — optional

- `libdirectfb.so`/`/basic/lib`, Mali/GLES; die UI nutzt GLES, der Web-Browser DirectFB.
- Ein eigener nativer UI-Prozess ist möglich, aber aufwendig; die Web-UI-Route (B) ist der pragmatische Weg.
- `dtv_svc`/`libdtv`/`app_man` für TV-Funktionen; `libhspdk-jsx`/`HiBrowser` für die JS-Brücke.

---

## Route E — Ro-Dateien patchen (Bind-Mount/Overlay)

**Ziel:** `/basic/am_config`, `am_start.ini`, `delayrun.sh`, `ms_service`, `start-UI.sh`, `/3rd/...`-Dateien ersetzen, ohne den ro Rootfs/`/3rd` zu flashen.

### E.1 Datei-Bind-Mount (empfohlen)

```sh
# Kopie + Änderung in /3rd_rw
cp /basic/am_start.ini /3rd_rw/etc/am_start.ini
vi /3rd_rw/etc/am_start.ini         # oder per File.write
# in developer.sh (vor app_man):
mount --bind /3rd_rw/etc/am_start.ini /basic/am_start.ini
```

- **Wirkt nur, wenn der Mount vor dem Lesen/Ausführen passiert:** `developer.sh` (Zeile 90) ist vor `ms_service`/UI/`app_man`/`delayrun`.
- **Reboot-fest:** `developer.sh` führt den Mount bei jedem Boot aus.
- **Rollback:** `umount /basic/am_start.ini` (oder reboot); Original bleibt unangetastet.
- **Für `ms_service`/`start-UI.sh`/`app_man`:** Stub-Skript (`#!/bin/sh\nexit 0`) per `mount --bind` über die Binärdatei; der `-x`-Check läuft danach ins Leere.
- **Achtung:** `mount --bind` auf eine Datei benötigt das Ziel; die ro-Datei existiert. Kein Overlay nötig.

### E.2 `patch/opera4x` (full overlay)

- `autorun.sh` bindet `/3rd_rw/patch/opera4x` **als Ganzes** über `/3rd/opera4x`.
- Nur mit vollständiger Kopie (`cp -a /3rd/opera4x/. /3rd_rw/patch/opera4x/`) oder Symlink-Baum; sonst fehlen Browser/UI-Dateien.
- Für einzelne Dateien: E.1 (Datei-Bind) statt full overlay.
- **Rollback:** `rm -rf /3rd_rw/patch/opera4x` + reboot.

### E.3 `am_config`/`am_start.ini` (Bloat)

- Kopie nach `/3rd_rw/etc/`, Sektionen entfernen/ändern, per `developer.sh` binden.
- **Vor** `app_man` (Zeile 177); `developer.sh` (90).
- **Risiko:** `dtv_app_mtk`/`app_man` nicht entfernen (TV/Apps). `netflix`/`dialserver`/`samba`/`browser_base`/`securetime` optional (siehe `05`).

### E.4 `delayrun.sh`

- Kopie nach `/3rd_rw/etc/delayrun.sh`; unerwünschte Zeilen entfernen; per `developer.sh` über `/basic/delayrun.sh` binden.
- **Vor** `autorun` Zeile 190; `developer.sh` (90).
- **Risiko:** `LauncherService` (UI-Daten) und `HamService` (unsere Persistenz) behalten; `swrc`/`runlog`/`Seriallog` optional.

---

## Route F — Statische Tools / Deploy / SSH

- **Kein Package Manager** (siehe `06`): statische ARM-Binaries bauen, nach `/3rd_rw/bin` legen, chmod +x.
- **Deploy:** `File.download` (HTTP → appdata), SSH (`ssh root@… 'cat > /3rd_rw/bin/x' < x` / `base64`), USB-Symlink, `tar`.
- **`scp`/`sftp`:** Dropbear allein hat keinen sftp-server. Der finale Ordner
  enthält einen statischen OpenSSH-9.9p1-sftp-server + gepatchten Dropbear;
  Installation: `../root/scripts/host/install_sftp.sh` (testet Port 2222, dann
  Tausch auf 22). Danach:
  ```bash
  sftp root@192.0.2.94
  # put -r /lokaler/UI-Ordner /3rd_rw/
  # get /3rd_rw/UI/index.html
  ```
  Modernes `scp` (OpenSSH 9+) nutzt ebenfalls SFTP und funktioniert dann.
  **Vor UI-Uploads:** Backup `/3rd_rw/backup/UI...`; nach dem Upload UI neu
  starten (siehe Route B). SFTP ist root-equivalent, key-only, LAN.
- **SSH:** siehe `../root/ROOT-GUIDE.md`; key-only, PTY via devpts-Workaround.
- **Root-Loop:** der bequemste Deploy-Kanal für kleine Dateien/Kommandos (siehe D.3).

---

## Test- und Rollback-Plan

1. **Backup:** `/3rd_rw/backup/<datum>/` für jede geänderte Datei (`UI/index.html`, `Appinfo.json`, `deletedPresetApp.txt`, `preset.txt`, `Category*.xml`, `am_config`, `am_start.ini`, `delayrun.sh`, `HamService`-Wrapper).
2. **Eine Änderung:** nicht UI + AM + Bloat gleichzeitig.
3. **Test:** UI neu starten; SSH/Recon offen halten; `log`/DevTools prüfen.
4. **Rollback:** Backup zurück; `umount` der Bind-Mounts; UI/AM neu starten; notfalls reboot.
5. **Kein Flash:** alle Änderungen in `/3rd_rw`/`/data`/`/perm`/Bind-Mounts; der ro Rootfs/`/3rd` bleibt unangetastet.
6. **SSH/Root-Loop:** nie aussperren; vor UI-/AM-Änderungen testen, dass SSH noch geht.

---

## Templates

- `templates/developer.sh`
- `templates/custom-app.json`
- `templates/hide-preset.json`
- `templates/custom-ui.html`
- `templates/start-UI-custom.sh`
- `templates/README.md`

**Dead Ends / verworfene Wege:** `../dead-ends.md`.
