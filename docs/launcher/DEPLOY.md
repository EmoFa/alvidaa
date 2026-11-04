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
