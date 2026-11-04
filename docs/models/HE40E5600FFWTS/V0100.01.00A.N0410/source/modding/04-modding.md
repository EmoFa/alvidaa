# 04 — Modding: recipes for your own UI, apps, services, bloat

**Prerequisite:** Root + SSH (see `../root/ROOT-GUIDE.md`).  
**Rule of the game:** One change, then test, then the next. Back up first. Keep SSH/root loop as a rescue path. No flash/`.pkg`.

The recipes are sorted by risk:

| Route | Goal | Risk | Reversible |
|---|---|---|---|
| **A** | own app tile (web app in the browser) | low | yes (file backup) |
| **B** | own UI page (`/3rd_rw/UI/index.html`) | medium | yes (backup + UI restart) |
| **C** | launcher data/skin (tiles, categories, icons) | low–medium | yes (backup) |
| **D** | own service/own function (root) | medium | yes (scripts/wrappers) |
| **E** | patch ro files via bind mount/overlay | medium–high | yes (unmount/reboot) |
| **F** | static tools/SSH/deploy | low | yes |

---

## Route A — Own app tile (the safe entry point)

**Goal:** An own entry in the launcher that opens a local or HTTP page in the **web browser** (does not replace the UI).

### A.1 Build the page

Locally on the TV (rw):

```
/3rd_rw/appdata/custom/index.html
/3rd_rw/appdata/custom/app.js
/3rd_rw/appdata/custom/icon.png
```

Example `index.html`:

```html
<!doctype html>
<html><head><meta charset="utf-8"><title>MyApp</title>
<style>body{background:#111;color:#eee;font-family:sans-serif;margin:0;padding:2em}</style>
</head><body>
<h1>MyApp</h1>
<p>Runs in hisense_browser (root, --allow-file-access-from-files).</p>
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

- HTTP variant: serve the page on the host (`http://<host>:9000/...`); the TV browser loads it.
- Local variant: `file:///3rd_rw/appdata/custom/index.html`; the browser has `--allow-file-access-from-files`.
- The page can use `HiBrowser` (`File`, `System`, `loadLibrary`, `Cache`, `JsonWrite`) and `Hisense_*`. Root context.

### A.2 Add to `Appinfo.json`

File: `/3rd_rw/appdata/launcher/Appinfo.json` (rw). **Backup:**

```sh
cp /3rd_rw/appdata/launcher/Appinfo.json /3rd_rw/backup/Appinfo.json.$(date +%s)
```

Add an entry (keep the existing `AppInfo` entries!):

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

- `StartCommand`/`URL` = HTTP or `file://`.
- `Image`/`IconURL`/`Thumb`/`Icon_96` = icon; HTTP/`file://`; fallback `useDefaultImg`.
- `StoreType` as a string (`"foxxum"`; the UI maps via `storeTypeList`).
- `PreInstall:false` (user app); `canRemove=true`.

**Via the TV page/JS** (without SSH):

```js
// read backup (optional)
var old = fileXHR("file:///3rd_rw/appdata/launcher/Appinfo.json");
// write new content
HiBrowser.File.write("launcher/Appinfo.json", newJsonString, 1);
```

`File.write` writes text; the JSON is text. (For binary icons: `File.download` from HTTP/`file://`.)

### A.3 Reload the launcher/UI

- Restart the UI (see `03`, section 8): `kill <hisenseUI-PID>`; `nohup /3rd/opera4x/hisenseUI/start-UI.sh &`.
- Or reboot the TV.
- The tile appears in the launcher/"All apps"; launching opens the **web browser** with the URL (not the UI page).

### A.4 Test / rollback

- Test: open the tile; `HiBrowser` test button; `file://` page; HTTP page.
- Rollback: copy the `Appinfo.json` backup back; restart the UI. Or remove the entry.
- Do **not** misuse `preset.txt` for user apps; the `preset` cache can be overwritten. `Appinfo.json` is the right place.

---

## Route B — Own UI page (`/3rd_rw/UI/index.html`)

**Goal:** Replace the TV UI (PIXI/`hisenseUI`) with your own page. **Highest risk** (black screen), but feasible.

### B.1 Backup

```sh
mkdir -p /3rd_rw/backup
cp -a /3rd_rw/UI /3rd_rw/backup/UI.$(date +%Y%m%d-%H%M%S)
```

### B.2 Build a minimal custom UI

File: `/3rd_rw/UI/custom.html` (new; `index.html` stays untouched for now).  
Template: `templates/custom-ui.html`.

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

- **API availability is `UNVERIFIED`**: check in the UI DevTools (9223) which globals exist and which signature `Hisense_StartApp`/`TVAPI.StartApp`/`guijs.StartApp` has. The web browser has `HiBrowser.System.startApp(":am,…")` (evidenced); the UI may have other wrappers.
- Size: the UI uses 1280×720 CSS (PIXI canvas); the screen is 1920×1080 (`OPERA_EGL_SCREEN_SIZE`). Use `100vw/100vh`/`meta viewport`.

### B.3 Test without replacing the UI

1. Open `custom.html` via the web browser: `http://<host>:9000/...` or `file:///3rd_rw/UI/custom.html` in the **`hisense_browser`** (TV browser). Test `HiBrowser`/`Hisense_*` there (the UI-specific APIs may be missing).
2. UI DevTools 9223: `window.location = "file:///3rd_rw/UI/custom.html"` **only** in a test tab? The UI has one window; navigating replaces the UI. Better: start the custom page in a **new** `hisenseUI` process (see B.5) or test via the web browser.
3. If the custom page looks good in the web browser, adopt it in the UI.

### B.4 Replace `index.html`

**Variant 1: replace the file** (simple, reversible via backup):

```sh
cp /3rd_rw/UI/index.html /3rd_rw/backup/index.orig.html
cp /3rd_rw/UI/custom.html /3rd_rw/UI/index.html
# restart the UI
kill $(pidof hisenseUI)
nohup /3rd/opera4x/hisenseUI/start-UI.sh >/tmp/hisenseUI.log 2>&1 &
```

**Variant 2: point `start-UI.sh` at `custom.html` via bind mount** (leaves `index.html` untouched):

```sh
# /3rd_rw/patch/start-UI-custom.sh (see templates/start-UI-custom.sh)
mount --bind /3rd_rw/patch/start-UI-custom.sh /3rd/opera4x/hisenseUI/start-UI.sh
# restart the UI
```

This is a **file bind mount**; not a full overlay. `start-UI-custom.sh` starts `hisenseUI` with `-u file:///3rd_rw/UI/custom.html` and the same flags as the original.

**Variant 3: vendor overlay `/3rd_rw/patch/opera4x`** (full dir bind):

```sh
mkdir -p /3rd_rw/patch/opera4x
cp -a /3rd/opera4x/. /3rd_rw/patch/opera4x/   # complete copy!
# overwrite your own files, e.g. hisenseUI/start-UI.sh
reboot
```

- **Only with a complete copy/symlink tree.** The `mount -o bind` replaces `/3rd/opera4x` entirely. Missing files = broken browser/UI.
- Advantage: survives reboots (autorun binds before the UI start). Disadvantage: large/error-prone.

### B.5 UI restart / rescue

```sh
# UI process
ps | grep hisenseUI | grep -v grep
kill <PID>
nohup /3rd/opera4x/hisenseUI/start-UI.sh >/tmp/hisenseUI.log 2>&1 &

# rescue on a black screen:
cp /3rd_rw/backup/index.orig.html /3rd_rw/UI/index.html
kill $(pidof hisenseUI)
nohup /3rd/opera4x/hisenseUI/start-UI.sh >/tmp/hisenseUI.log 2>&1 &
```

- **SSH/root loop** work independently of the UI. The web browser (`hisense_browser`/recon) can also keep running.
- `hisenseUI` log: `/tmp/hisenseUI.log`; UI DevTools 9223 (if the page loads).
- **No flash**: `index.html`/`custom.html` live in `/3rd_rw`; backup/rollback via file.

### B.6 What the UI page can do

- **Full-screen HTML/CSS/JS** in the Chromium/Opera UI browser.
- **`Hisense_*`/`TVAPI`/`guijs`/`model`** (UI context; check signatures in the DevTools).
- **`file://`** access (`--disable-web-security`, `--allow-file-access-from-files`? The UI has `--disable-web-security`; local files yes).
- **Video/canvas/WebGL**; the UI uses GLES/Mali.
- **No** direct shell access from JS; the root loop/SSH is the way for native actions.

---

## Route C — Launcher data/skin (tiles, categories, icons)

**Goal:** Add/hide apps, change categories/icons without replacing the UI page.

### C.1 Hide tiles (simple, persistent)

File: `/3rd_rw/appdata/launcher/deletedPresetApp.txt` (JSON array).  
Example: `templates/hide-preset.json`; the preinstalled list is in `05-bloat.md`.

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

- The launcher/`ldi.js` filters the tiles; `preset.txt` is only a cache.
- **As of 2026-10-26:** The old probe URLs (data:, javascript:, 127.0.0.1;cd…) were removed during cleanup; the file is now `[]`. To hide tiles, set the desired hide entries.
- **Backup:** `cp deletedPresetApp.txt /3rd_rw/backup/...`.
- **Effect:** restart the UI/launcher (or reboot).

### C.2 Add tiles

- **User app:** `Appinfo.json` (route A).
- **Preset:** add to `preset.txt` (`AppName`, `IconURL`, `URL`, `StartCommand`, `UrlType` 37, `StoreType` 0, `PreInstall:true`). **But:** `preset.txt` is a cache; the UI/`allAppsWriteToFileForUse` can overwrite it. For persistence: `Appinfo.json` (user app) or the `Category*.xml` source.
- **Category XML:** `/3rd_rw/appdata/launcher/data/Category_1001_*.xml`/`Category_57_*.xml`/`CategoryIndex.xml`/`CategoryList_*.xml` — the app tiles. Back up; keep the XML structure; let `preset`/cache be regenerated afterwards (UI restart).
- **`serviceUpdate.xml`:** country/timestamp; if it does not match `DEU`, `ldi.js` uses the `UI/data/` default. For your own data, edit `UI/data/` (fallback) or keep `serviceUpdate`/`Category` in `launcher/data` consistent.

### C.3 Icons / skin

- Icons: `res/*.png`; `cache/index.json`; `Image`/`IconURL`/`Thumb`/`Icon_96`; `useDefaultImg` as fallback.
- Skin/assets: `/3rd_rw/UI/assets`, `/3rd_rw/UI/templates`, `/3rd_rw/UI/module`, `/3rd_rw/launcher/{css,img,html,js}`, `/3rd_rw/VIDAAU2Launcher/*` (legacy/alternative).
- **Active:** `/3rd_rw/UI` (PIXI) + `/3rd_rw/appdata/launcher` (data). The `launcher`/`VIDAAU2Launcher` HTML/JS are legacy/alternative skins; only test changes there if the UI loads them (`UNVERIFIED`).

### C.4 Test / rollback

- Backup of `Appinfo`/`preset`/`deleted`/`Category*`/`res`.
- Restart the UI; check the tiles; on problems restore the backup, restart the UI/reboot.
- The `deletedPresetApp.txt` is the safest hide lever (no XML intervention).

---

## Route D — Own service / own function (root)

**Goal:** An own process/script runs as root at boot or on command; native actions that JS cannot do.

### D.1 Early hook: `/3rd_rw/developer.sh`

Executed by `/basic/autorun.sh` line 90 as root — **before** `ms_service`/`hisenseUI`/`app_man`/`delayrun`.

Template: `templates/developer.sh`.

```sh
#!/bin/sh
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin
export PATH
exec >>/3rd_rw/developer.log 2>&1
echo "developer.sh $(date) boot=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)"

# example 1: start your own service
# /3rd_rw/bin/mydaemon &

# example 2: replace a ro file via bind mount (before app_man)
# mount --bind /3rd_rw/etc/am_start.ini /basic/am_start.ini
# mount --bind /3rd_rw/etc/am_config    /basic/am_config

# example 3: stub out an unwanted service (before autorun line 162)
# mkdir -p /3rd_rw/stubs
# printf '#!/bin/sh\nexit 0\n' > /3rd_rw/stubs/true
# chmod 755 /3rd_rw/stubs/true
# mount --bind /3rd_rw/stubs/true /3rd/ms-screen/ms_service

# example 4: start the custom UI (before autorun line 168)
# mount --bind /3rd_rw/patch/start-UI-custom.sh /3rd/opera4x/hisenseUI/start-UI.sh

# example 5: start the root loop/SSH earlier (instead of the HamService wrapper)
# /bin/sh /3rd_rw/appdata/root_loop.sh &
# /bin/sh /3rd_rw/sshd/start_sshd.sh &
```

- **Order:** `developer.sh` (90) → `ms_service` (162) → `hisenseUI` (168) → `app_man` (177) → `delayrun` (190).
- **Bind mounts** of ro files in `developer.sh` take effect for the later lines.
- **Log:** `/3rd_rw/developer.log`; `set -x` optional.
- **Fallback:** SSH/root loop; if `developer.sh` blocks the UI/AM, correct/remove it via SSH, reboot.

### D.2 Late hook: `HamService` wrapper (currently for SSH/root loop)

`/3rd_rw/hamservice/HamService` (wrapper; `startHam.sh` calls it after `delayrun` + 15 s):

```sh
#!/bin/sh
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin
export PATH
/bin/sh /3rd_rw/appdata/root_loop.sh >/dev/null 2>&1 &
[ -x /3rd_rw/sshd/start_sshd.sh ] && /bin/sh /3rd_rw/sshd/start_sshd.sh >/dev/null 2>&1 &
exec /3rd/hamservice/HamService "$@"
```

- **Current persistence:** root loop + Dropbear. The real `HamService` keeps running.
- **Disabling ACR:** replace `exec /3rd/hamservice/HamService "$@"` with `exit 0` (root loop/SSH remain); or disable ACR in the HamService config (UNVERIFIED).
- **Own late services:** start them before the `exec` (e.g. `/3rd_rw/bin/mydaemon &`).
- **Rollback:** `rm /3rd_rw/hamservice/HamService; ln -s /3rd/hamservice/HamService /3rd_rw/hamservice/HamService`.

### D.3 Command channel (root_loop)

- `/3rd_rw/appdata/root_loop.sh` reads `root_cmd.sh`, writes `root_out.txt`.
- On the TV: `HiBrowser.File.write("root_cmd.sh", "…\n", 1)`; `fileXHR("file:///3rd_rw/appdata/root_out.txt")`.
- Host snippet: `../root/scripts/host/run_root_cmd.js`.
- **Root-equivalent:** allow only trusted writers (browser root).

### D.4 Native app/function via AM (`:am`)

- `HiBrowser.System.startApp(":am,<app>,:start=<val>")` in the web browser (evidenced).
- `:am,<app>,:URL=<url>` (from the `app_man` strings); `:stop`, `:backgm`, `:foregm`, `:pause`, `:resume`, `:shutdown`, `:suspend`, `:wakeup`.
- **A new native app** needs an `am_config` entry (`exec`/`args`) — ro; via a `developer.sh` bind mount of a modified `am_config` (before `app_man`). Or an own service via `developer.sh`/`HamService` (no AM needed).
- **`Hisense_StartApp`** in the UI: check signature/behavior in the UI DevTools (`UNVERIFIED`).

### D.5 Native UI (DirectFB/GLES) — optional

- `libdirectfb.so`/`/basic/lib`, Mali/GLES; the UI uses GLES, the web browser DirectFB.
- An own native UI process is possible but laborious; the web UI route (B) is the pragmatic path.
- `dtv_svc`/`libdtv`/`app_man` for TV functions; `libhspdk-jsx`/`HiBrowser` for the JS bridge.

---

## Route E — Patch ro files (bind mount/overlay)

**Goal:** Replace `/basic/am_config`, `am_start.ini`, `delayrun.sh`, `ms_service`, `start-UI.sh`, `/3rd/...` files without flashing the ro rootfs/`/3rd`.

### E.1 File bind mount (recommended)

```sh
# copy + change in /3rd_rw
cp /basic/am_start.ini /3rd_rw/etc/am_start.ini
vi /3rd_rw/etc/am_start.ini         # or via File.write
# in developer.sh (before app_man):
mount --bind /3rd_rw/etc/am_start.ini /basic/am_start.ini
```

- **Only takes effect if the mount happens before the read/execute:** `developer.sh` (line 90) is before `ms_service`/UI/`app_man`/`delayrun`.
- **Survives reboots:** `developer.sh` performs the mount on every boot.
- **Rollback:** `umount /basic/am_start.ini` (or reboot); the original stays untouched.
- **For `ms_service`/`start-UI.sh`/`app_man`:** stub script (`#!/bin/sh\nexit 0`) via `mount --bind` over the binary; the `-x` check then goes nowhere.
- **Caution:** `mount --bind` onto a file requires the target; the ro file exists. No overlay needed.

### E.2 `patch/opera4x` (full overlay)

- `autorun.sh` binds `/3rd_rw/patch/opera4x` **as a whole** over `/3rd/opera4x`.
- Only with a complete copy (`cp -a /3rd/opera4x/. /3rd_rw/patch/opera4x/`) or symlink tree; otherwise browser/UI files are missing.
- For individual files: E.1 (file bind) instead of a full overlay.
- **Rollback:** `rm -rf /3rd_rw/patch/opera4x` + reboot.

### E.3 `am_config`/`am_start.ini` (bloat)

- Copy to `/3rd_rw/etc/`, remove/change sections, bind via `developer.sh`.
- **Before** `app_man` (line 177); `developer.sh` (90).
- **Risk:** do not remove `dtv_app_mtk`/`app_man` (TV/apps). `netflix`/`dialserver`/`samba`/`browser_base`/`securetime` optional (see `05`).

### E.4 `delayrun.sh`

- Copy to `/3rd_rw/etc/delayrun.sh`; remove unwanted lines; bind over `/basic/delayrun.sh` via `developer.sh`.
- **Before** `autorun` line 190; `developer.sh` (90).
- **Risk:** keep `LauncherService` (UI data) and `HamService` (our persistence); `swrc`/`runlog`/`Seriallog` optional.

---

## Route F — Static tools / deploy / SSH

- **No package manager** (see `06`): build static ARM binaries, put them in `/3rd_rw/bin`, chmod +x.
- **Deploy:** `File.download` (HTTP → appdata), SSH (`ssh root@… 'cat > /3rd_rw/bin/x' < x` / `base64`), USB symlink, `tar`.
- **`scp`/`sftp`:** Dropbear alone has no sftp-server. The final folder
  contains a static OpenSSH 9.9p1 sftp-server + patched Dropbear;
  installation: `../root/scripts/host/install_sftp.sh` (tests port 2222, then
  switches to 22). After that:
  ```bash
  sftp root@192.0.2.94
  # put -r /local/UI-folder /3rd_rw/
  # get /3rd_rw/UI/index.html
  ```
  Modern `scp` (OpenSSH 9+) also uses SFTP and then works.
  **Before UI uploads:** backup `/3rd_rw/backup/UI...`; after the upload restart
  the UI (see route B). SFTP is root-equivalent, key-only, LAN.
- **SSH:** see `../root/ROOT-GUIDE.md`; key-only, PTY via devpts workaround.
- **Root loop:** the most convenient deploy channel for small files/commands (see D.3).

---

## Test and rollback plan

1. **Backup:** `/3rd_rw/backup/<date>/` for every changed file (`UI/index.html`, `Appinfo.json`, `deletedPresetApp.txt`, `preset.txt`, `Category*.xml`, `am_config`, `am_start.ini`, `delayrun.sh`, `HamService` wrapper).
2. **One change:** not UI + AM + bloat at the same time.
3. **Test:** restart the UI; keep SSH/recon open; check `log`/DevTools.
4. **Rollback:** restore the backup; `umount` the bind mounts; restart UI/AM; reboot if necessary.
5. **No flash:** all changes in `/3rd_rw`/`/data`/`/perm`/bind mounts; the ro rootfs/`/3rd` stays untouched.
6. **SSH/root loop:** never lock yourself out; before UI/AM changes, test that SSH still works.

---

## Templates

- `templates/developer.sh`
- `templates/custom-app.json`
- `templates/hide-preset.json`
- `templates/custom-ui.html`
- `templates/start-UI-custom.sh`
- `templates/README.md`

**Dead ends / abandoned paths:** `../dead-ends.md`.
