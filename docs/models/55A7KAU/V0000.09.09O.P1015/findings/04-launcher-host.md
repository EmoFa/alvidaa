# alvidaa findings — launcher host on the TV's Node runtime (55A7KAU, 09.09O)

> Phase 4 item 4, milestone 1 ([HACK-YOUR-OWN.md](../../../../project/HACK-YOUR-OWN.md)):
> the launcher page is served by the TV itself. 2026-11-06.

## What runs

- The phoenix binary is a **Node v20.9.0** build; it runs arbitrary JS as root:
  `LD_LIBRARY_PATH=/lib:/usr/local/lib:/basic/lib /opt/pkgs/tv.vidaa.app.phoenix//bin/phoenix /path/script.js`
  (no vendor libs needed beyond the default path — the earlier
  `libapp-manager-client.so` failure only happens without LD_LIBRARY_PATH).
- `/APPS/launcher/` holds the launcher assets + `server.js` (repo copy:
  `tools/launcher-host/server.js`): static file server on **0.0.0.0:8765**,
  `Cache-Control: no-store` (findings 01 §7), MIME map, path-traversal guard.
- **Boot-persistent**: the re-arm postinst starts it if `:8765` is not
  listening (verified: `launcher host up`). The Home app entry in
  `/APPS/websdk/Appinfo.json` points at `http://127.0.0.1:8765/` — the TV
  opens its own home screen from its own disk with **no PC on the network**.
- Backup: `/APPS/.re_sshd/Appinfo.json.bak-20261106` (original had one entry:
  Twitch). Ownership preserved: `314:713`, mode `660`, temp-file + write.

## Traps hit (all measured)

| Trap | Result |
| --- | --- |
| Hex port in `/proc/net/tcp` | 8765 = **`0x223D`** (not 0x2235 = 8757). Every "launcher host FAILED" was this; the listener was there. |
| `nohup` | absent from this busybox. `busybox setsid` exists; `env` does not — use `busybox setsid /bin/sh -c 'LD_LIBRARY_PATH=… exec …'`. |
| SSH-session children | a server started from an SSH session dies on disconnect (SIGHUP). Only the postinst/setsid path survives. |
| EADDRINUSE zombies | the original server.js logged `uncaughtException` and stayed alive without a listener — worse than a crash. Fixed: listen errors exit(1) so the postinst probe reflects reality. |
| `/proc/net/tcp` indentation | lines are indented; an anchored `^00000000:…` regex never matches. |
| App list restart | Appinfo.json entries appear in the TV's app list after a restart (per findings 01 §6). |

## Scope honesty

This is the **shell** on-TV: clock, cached tiles, the page itself — fully
offline. The dynamic endpoints (`/ws` live state, `/api/launch`, `/api/open`)
still live on the operator PC; served from the TV the page renders and then
reports offline. The full port (TV-side server speaking MQTT to its own
broker at localhost:36669 with the paired credentials, plus direct
`Hisense_*`/`HiUtils` bridge calls from the page) is the LAUNCHER_V2 design
and is the remaining work before the stock home can be retired (Phase 4
item 5).

## Teardown

- Remove the `launcher host` block from the IPK postinst (rebuild without it)
  or `kill $(pgrep -f 'phoenix /APPS/launcher/server.js')`.
- Restore `Appinfo.json` from `/APPS/.re_sshd/Appinfo.json.bak-20261106`.
- `rm -rf /APPS/launcher`.
