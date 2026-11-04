# Templates — explained

| File | Purpose |
|---|---|
| `developer.sh` | early root boot hook (`/3rd_rw/developer.sh`), examples for bind mounts/stubs/services |
| `custom-app.json` | `AppInfo` entry for a custom app tile (`Appinfo.json`) |
| `hide-preset.json` | `deletedPresetApp.txt` example (hide tiles) |
| `custom-ui.html` | minimal custom UI page (`/3rd_rw/UI/custom.html`) |
| `start-UI-custom.sh` | `start-UI.sh` clone that loads `custom.html` |

## Usage

```sh
# 1) developer.sh (optional, early)
cp developer.sh /3rd_rw/developer.sh
chmod 755 /3rd_rw/developer.sh
# uncomment the examples in the file; reboot

# 2) app tile
# merge the contents of custom-app.json into /3rd_rw/appdata/launcher/Appinfo.json
# (keep the existing AppInfo entries!)
# restart the UI / reboot

# 3) hide tiles
cp hide-preset.json /3rd_rw/appdata/launcher/deletedPresetApp.txt
# adjust; restart the UI / reboot

# 4) custom UI
cp custom-ui.html /3rd_rw/UI/custom.html
cp start-UI-custom.sh /3rd_rw/patch/start-UI-custom.sh
chmod 755 /3rd_rw/patch/start-UI-custom.sh
# in /3rd_rw/developer.sh:
# mount --bind /3rd_rw/patch/start-UI-custom.sh /3rd/opera4x/hisenseUI/start-UI.sh
# reboot
```

## Important

- **Backup** before every change: `/3rd_rw/backup/`.
- Keep **SSH/root loop** as the rescue path; on a black screen, restore the
  `UI/index.html` backup and restart `hisenseUI`.
- **API names** (`Hisense_StartApp`, `TVAPI`, `guijs`) are `UNVERIFIED`; check
  them in the UI DevTools (9223) / web browser (9224).
- **No flash**: everything lives in `/3rd_rw`/bind mounts; roll back by
  file/`umount`/reboot.
- **`hide-preset.json`** is a full example (including `TV Browser`/`vidaa-plus`);
  trim it to what you actually want to hide. Do not hide `VidaaRecon` if you
  need the recon page.
