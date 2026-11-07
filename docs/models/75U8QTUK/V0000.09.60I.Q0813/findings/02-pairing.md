# 02 — Pairing confirmed (2026-11-06)

Pairing on this unit was done by **Sidee** (github.com/Empi9245/Sidee), not
`server/pair.py`. A session was already persisted at
`~/.sidee/session.json` (mode 600). This note confirms that session is
live by a read-only app-list round-trip over the RemoteNow MQTT channel.

## One-MQTT-server discipline

Sidee's GUI was running (holding the single MQTT session, same client_id).
Per the AGENTS.md "one MQTT server per TV" rule, the GUI was quit first so
the CLI call below was the only broker client:

```
$ osascript -e 'quit app "Sidee"'
$ pgrep -il sidee   →   (none)
```

`server/pair.py` was **not** run.

## Session metadata (non-secret fields only)

From `~/.sidee/session.json` — tokens redacted, never committed:

```
host:          <tv-ip>
auth_profile:  modern
brand:         his
pair_failures: 0
access_days:   2        refresh_days: 30
```

`auth_profile: modern` is the 2024 app-style credential profile — matches
the expectation for a U09.60 build and resolves the credential cascade the
(absent) SSDP `transport_protocol` digit would otherwise have steered
(see findings/01).

## App-list round-trip (live proof)

```
$ /Applications/Sidee.app/Contents/MacOS/Sidee list
  3     YouTube        pkgapp://tv.vidaa.app.youtube/apps/start_youtube.sh
  284   TV Channels+   vidaa-plus
  2181  Kids           kidsLauncher
  2470  Ads Privacy    https://ads-privacy.vidaahub.com/
  164   APP STORE      vidaa-store
  2243  Art Gallery    https://tvmodules-vidaa.vidaahub.com/vidaa-art/V1.0/index-vi…
  16    TV Browser     browser
  166   E-Manual       file:///APPS/emanual/Local_ebook/index.html
  184   On Demand      vidaa-free
```

The TV published its `ui_service/data/applist` in response — pairing token
is valid and the control channel works.

## Readings

- **Pairing is live**, credential profile `modern`, over MQTT-over-TLS on
  `36669/tcp` (the open port from findings/00).
- **App id `16` "TV Browser" (`browser`)** is present. This is the likely
  lever for getting an alvidaa launcher/recon page in front of the TV
  webview in steps 3–4 — but see the Sidee limitation below.
- Several tiles carry plain HTTPS URLs (`Ads Privacy`, `Art Gallery`),
  confirming the launcher accepts URL-backed tiles in principle.

## Blocker recorded for steps 3–4: Sidee has no arbitrary-URL launch

Sidee's CLI exposes `launch <preset>` and `install <preset>` only —
both take a **built-in preset ID**, and the dashboard "does not currently
accept arbitrary web-app URLs." There is no `open <url>` / `send-key` /
`state` command. So the ladder's assumption — "load `recon.html` via a
Sidee URL-launch" — does **not** hold with the CLI as shipped.

The underlying MQTT client (`core/client.py`) *does* have the primitives:
`launch_payload(app_id, name, url)` and `install_payload(app_id, name,
url, image)` both take a URL. So registering a tile that points at
`http://<mac-ip>:8770/launcher/recon.html` and launching it is possible at
the protocol level — it is just not surfaced as a clean CLI subcommand.
Options for step 3–4 (to be decided then, not now):

1. Add a Sidee preset pointing at the alvidaa server URL, then
   `Sidee install <preset>` + `Sidee launch <preset>`.
2. Drive `install_payload`/`launch_payload` directly (small script against
   `core/client.py` using the persisted session).
3. Serve the repo with `python3 -m http.server 8770` and type the URL into
   the TV's "TV Browser" app by hand.

## State change

- `capabilities.pairing` inventory field: `untested` →
  `confirmed (Sidee, profile 'modern', applist round-trip 2026-11-06)`.

## Next

- `03-launcher.md` — get an alvidaa page in front of the TV webview via
  one of the three routes above; start with a WRITE-FREE page
  (`launcher/fingerprint-full.html`) before anything that writes.
