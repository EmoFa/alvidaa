# tools/a6q — 50A6Q (NT72690) lane

Scripts behind the [50A6Q guide](../../docs/models/50A6Q/V0000.09.61B.Q0721/README.md).
LAN IPs (TV `<TV_IP>`, helper box `<LAN_BOX>`) are hardcoded from
the lab LAN — adjust to yours. Files are served to the TV by `receiver.py`
(port 8899, serves its own directory; CORS `*`).

| File | What it is |
|---|---|
| `a6q_boot.js` | the boot payload (v18): runs inside phoenix at boot via the hiutils `package.json` main hook; delivers dropbear/wrapper/hostkey/keys/PFM artifacts via `fetchFile` and **re-plants everything every 10 s** (counters a runtime watchdog that deletes the `DebugPowerup` gate flag) |
| `pfmcheck_v15` | the PFM eval payload — one shell line per line, run as root by `pfm-manager.sh` at boot: proof, firewall ACCEPT + EULA-chain delete, keys install, dropbear start with full logging |
| `a6q_dropbear_wrapper` | installed as `/var/local/dropbear` (the eternal root loop execs whatever is at that path): chmods the real binary, prepares `/var/local/roothome`, starts the real binary with `-E`, logs to `/var/local/.a6q_root/db.log` |
| `pkg_current.json` | the stock `services/hiutils/package.json` — the teardown reference (the live one is patched to `main: hiutils_boot.js`, which `require`s `a6q_boot.js` in a try/catch and re-exports the original) |
| `dropbear-aarch64/` | static aarch64 Dropbear build: [recipe + three source patches](dropbear-aarch64/README.md), `localoptions.h`, unified patch |
| `receiver.py` | helper-box receiver: serves files (GET), accepts reports (`POST /a6q_report`, `/a6q_usb`) and forges security codes (`POST /secforge`) |
| `cdp.py`, `cdp_nav.py`, `cdp_browser.py` | minimal CDP drivers (Runtime.evaluate etc.) against the TV browser DevTools on 9226 |
| `deploy_pfm.py` | deploys a PFMCheck revision to the TV (live + backup + gate flag) over CDP → localhost:9009; falls back from gated `fileWrite` to the ungated `fetcher` and needle-verifies on disk |
| `readone.py` | reads one TV file over the same bridge (array-path form) |
| `probe_tcp.py`, `probe6.py` | live `/proc/net/tcp(6)` readers + in-TV port probes with short timeouts (distinguish DROP vs refused) |
| `backup_watch.py` | CDP watcher: dumps localStorage/cookies of any app opened on the TV |

Operational notes that cost real time (see the guide's gotcha table):

- the eval runs **early** in boot — plant files in a prior session, never in
  the same one;
- after any redeploy, needle-verify on disk before triggering a reload;
- CDP target IDs rotate every boot/reload — re-read `/json/list`;
- `nc`/`telnetd` applets are absent from this TV's busybox;
- never ping the TV (ICMP disabled) — probe TCP 36669.
