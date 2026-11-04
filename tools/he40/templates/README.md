# Templates — kurz erklärt

| Datei | Ziel |
|---|---|
| `developer.sh` | früher Root-Boot-Hook (`/3rd_rw/developer.sh`), Beispiele für Binds/Stubs/Services |
| `custom-app.json` | `AppInfo`-Eintrag für eine eigene App-Tile (`Appinfo.json`) |
| `hide-preset.json` | `deletedPresetApp.txt`-Beispiel (Tiles ausblenden) |
| `custom-ui.html` | minimale Custom-UI-Seite (`/3rd_rw/UI/custom.html`) |
| `start-UI-custom.sh` | `start-UI.sh`-Klon, lädt `custom.html` |

## Nutzung

```sh
# 1) developer.sh (optional, früh)
cp developer.sh /3rd_rw/developer.sh
chmod 755 /3rd_rw/developer.sh
# Beispiele in der Datei einkommentieren; reboot

# 2) App-Tile
# custom-app.json-Inhalt in /3rd_rw/appdata/launcher/Appinfo.json mergen
# (bestehende AppInfo-Einträge behalten!)
# UI neu starten / reboot

# 3) Tiles ausblenden
cp hide-preset.json /3rd_rw/appdata/launcher/deletedPresetApp.txt
# anpassen; UI neu starten / reboot

# 4) Custom-UI
cp custom-ui.html /3rd_rw/UI/custom.html
cp start-UI-custom.sh /3rd_rw/patch/start-UI-custom.sh
chmod 755 /3rd_rw/patch/start-UI-custom.sh
# in /3rd_rw/developer.sh:
# mount --bind /3rd_rw/patch/start-UI-custom.sh /3rd/opera4x/hisenseUI/start-UI.sh
# reboot
```

## Wichtig

- **Backup** vor jeder Änderung: `/3rd_rw/backup/`.
- **SSH/Root-Loop** als Rettungsweg behalten; bei schwarzem Bildschirm `UI/index.html`-Backup zurück, `hisenseUI` neu starten.
- **API-Namen** (`Hisense_StartApp`, `TVAPI`, `guijs`) sind `UNVERIFIED`; im UI-DevTools (9223) / Web-Browser (9224) prüfen.
- **Kein Flash**: alles in `/3rd_rw`/Bind-Mounts; Rollback per Datei/`umount`/Reboot.
- **`hide-preset.json`** ist ein Vollbeispiel (inkl. `TV Browser`/`vidaa-plus`); kürze es auf das, was du wirklich ausblenden willst. `VidaaRecon` nicht ausblenden, wenn du die Recon-Seite brauchst.
