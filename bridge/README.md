# alvidaa-bridge — the on-TV daemon

One static armv7 binary that replaces the Pi for day-to-day operation. It
serves the overlay assets on loopback, keeps a single MQTT/TLS session to the
TV's own broker, and exposes `/ws` to the Cobalt page.

```
Cobalt page (file:///hisenseUI/index.html)
        │  ws://127.0.0.1:8770/ws
        ▼
alvidaa-bridge ── mqtts://127.0.0.1:36669 ── TV broker ── TV services
        └── http://127.0.0.1:8770/{assets,/icon/*}
```

The Pi server (`server/vidaa_server.py`) stays the reference implementation;
this is a port of the parts the launcher needs. Zero third-party Go
dependencies, so the armv7 build is a single reproducible command.

## Build

```sh
tools/build-bridge.sh              # -> bridge/dist/alvidaa-bridge-armv7
```

Result is an ELF 32-bit ARM EABI5, statically linked (no libc on the TV
required). Version comes from `git describe`.

## Run on the TV

```sh
/var/local/alvidaa/alvidaa-bridge \
  -keys   /var/local/alvidaa/keys \
  -assets /var/local/alvidaa/launcher \
  -config /var/local/alvidaa/config.json \
  -addr   127.0.0.1:8770 \
  -mqtt   127.0.0.1:36669
```

Flags and defaults are the same as above; `-version` prints and exits.

Files it expects in `-keys`:

| File | Purpose |
| --- | --- |
| `vidaa_cert.pem` + `vidaa_key.pem` | 2024 pairing client cert (or `rcm_certchain_pem.cer` + `rcm_pem_privkey.pkcs8`) |
| `tokens.json` | pairing output (`_client_id`, `_username`, `accesstoken`, `refreshtoken`) |

Tokens are refreshed in place when the broker rejects the session; the merged
result keeps unknown fields from the original file.

## HTTP surface (parity with the Pi server)

| Route | Behaviour |
| --- | --- |
| `/ws` | WebSocket: sends `hello` snapshot, accepts `{t:launch}` / `{t:source}`, pushes `tvstate`/`sources`/`apps` |
| `/icon/<appId>` | proxy + disk cache of the app's `httpIcon` |
| `/api/health` | `{ok, mqtt, clients}` — daemon-side check |
| `/api/state` | current `statetype` |
| `/api/launch?name=` | launch an app by name (exact, then substring) |
| `/api/source?id=` | switch input by id or source name |
| `/api/open?url=` | load an http(s) URL via the `vidaa-recon` app slot |
| `/api/recon`, `/api/probe` | recon report / probe line log |
| static | everything else is served from `-assets`, `Cache-Control: no-store`, CORS `*` |

Not ported: `/doom` (needs SSH + framebuffer tools; the daemon answers
`{"ok":false}`). The Pi remains the place for that.

## Things that bite

1. **One MQTT session per TV.** The daemon and the Pi server share the paired
   client identity and will kick each other off the broker. Stop
   `alvidaa.service` before starting this, and vice versa.
2. **Loopback may not be where the broker listens.** If `127.0.0.1:36669`
   refuses, pass `-mqtt <tv-lan-ip>:36669`; the rest of the design is unchanged.
3. **The watcher is off by default.** On the TV the overlay *is* the home
   screen, so bouncing `remote_launcher` back to "Home" would relaunch
   itself. Enable `watcher.enabled` only if the page is a separate app entry.
4. **The page must talk to `127.0.0.1:8770`**, and the script tag must be
   local flash (findings 12 §5). A remote `<script src>` still fails at cold
   boot because the network is up ~25–35 s after Cobalt starts.
5. **Loopback-only binding is the access control.** CORS is `*` so the
   `file://` page can call it; do not expose `-addr` beyond 127.0.0.1.

## Test

```sh
cd bridge && go test -race ./...
```

Covers the MQTT client against a fake broker (connect, exact-topic subscribe,
publish, rejection → refresh hook) and the WebSocket framing (masking, extended
length, ping/pong, oversized frames).
