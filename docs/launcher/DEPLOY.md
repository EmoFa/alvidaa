# Deployment (the Pi)

Production home for the launcher server: a Raspberry Pi running
`alvidaa.service` (systemd, `Restart=always`), listening on a fixed port
(8770 here — 8765 was taken by another service; any port works, but note
the installed TV app points at a specific one).

```sh
rsync -a --exclude venv --exclude .git ~/repos/alvidaa/ pi:alvidaa/
ssh pi 'cd ~/alvidaa/server && python3 -m venv venv && ./venv/bin/pip install paho-mqtt'
# unit: /etc/systemd/system/alvidaa.service -> venv/bin/python vidaa_server.py <tv-ip> 8770
```

## Rules

- **Run only ONE server instance against a TV at a time.** The paired
  MQTT client identity is shared, and two servers will kick each other
  off the broker (symptom: publishes fail, pushes stop arriving).
- After moving hosts, re-point the installed TV app: open
  `http://<new-host>:<port>/` in the TV browser and use
  "+ INSTALL AS APP" (same app Id overwrites the old entry), then
  restart the TV. The self-install also purges stale duplicate "Home"
  entries pointing at dead hosts.
- **The self-install only rewrites its own entry.** Every other app in
  `/APPS/websdk/Appinfo.json` keeps whatever host it was installed from,
  so a host move leaves them pointing at a dead address with no visible
  error — the tile just opens nothing. Found on 2026-11-05: the Recon
  tile still pointed at the retired Pi (`192.168.0.85:8770`) long after
  the launcher had moved to `127.0.0.1:8770`. After any host move, read
  the registry and check every `URL`/`IconURL`:
  `server/tv 'cat /APPS/websdk/Appinfo.json'`. Back it up before editing
  (`Appinfo.json.bak-<date>`), keep the `UhisPhoenix:713` ownership and
  `660` mode, and write through a temp file plus `mv`.
- **`only` beats `hidden`.** `visible_apps()` skips the hidden check
  whenever `only` is non-empty, so an app listed in both is shown, not
  hidden. Remove it from `only` to make `hidden` take effect.
- The dev server on a Mac is fine for building, but the author's Mac
  sleeping once broke every button — the Pi exists so the launcher
  survives your laptop.
- Prefer launching by URL match over by name: the watcher launches the
  app entry whose URL carries this server's port, so a stale duplicate
  can never win (see [02-operations.md](../models/50A51HUV/09.01O.P0813/findings/02-operations.md)).

## Watching it work

The server logs client IP + Host header per request — the journal is the
fastest way to confirm the TV is asking the right host after a cutover:

```sh
ssh pi 'journalctl -u alvidaa -f'
```
