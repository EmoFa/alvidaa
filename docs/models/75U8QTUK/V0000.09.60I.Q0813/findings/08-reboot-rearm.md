# 08 — Reboot / re-arm test: no autostart, `83` + `82` restores root (2026-11-06)

After the initial arm in [findings/07](07-root-armed.md), the TV was rebooted
with `/sbin/reboot` (root, `sync` first) to test the "no boot persistence"
claim and the documented re-arm sequence.

**Result: the claim is correct.** 8008 was closed after the reboot, and
re-sending superwatch `83` then `82` via the surviving `sw2.js` helper
restored uid-0 SSH without re-downloading anything.

## Timeline

| Time (TV) | Event |
|---|---|
| 22:18-ish | `sync; /sbin/reboot` over the findings/07 root session |
| +9 s | TCP 36669 (MQTT/TLS) reachable again |
| after boot | **8008 closed** — no Dropbear process, no autostart |
| 22:19:58 | `rearm.html` sends `90:83:90;re.installer` → reply `\x04\x00\x00\x0090:0` (uninstall OK) |
| 22:19:58 | sends `91:82:91;/APPS/installer.ipk;re.installer;` → reply `\x04\x00\x00\x0091:0` (install OK; socket lingered, helper marked `timeout:true` after the 15 s read timeout, but the postinst ran) |
| 22:20 | `POSTINST_RAN`, `Uid: 0`, `CapEff: 000001ffffffffff` again |
| 22:20 | 8008 open again; new Dropbear pid **15290** |

## Evidence

```
$ nc -z 10.0.0.173 8008          # before re-arm: closed
                                 # after re-arm:  OPEN

$ ssh -p 8008 -i server/keys/vidaa_75u8qtuk_ed25519 root@10.0.0.173 \
      'grep -E "^(Uid|Gid|CapEff):" /proc/self/status; cat /proc/uptime; cat /APPS/.re_sshd/dropbear.pid'
Uid:    0   0   0   0
Gid:    0   0   0   0
CapEff: 000001ffffffffff
114.78 320.96          # fresh boot, not a daemon that survived
15290                  # new Dropbear pid (was 26846 before the reboot)

$ ssh -tt ... 'test -t 0 && echo PTY-OK'
PTY-OK
```

`rearm.html` capture (server-side, `tools/u7q/web/captures/run-20261106-222019-000000.txt`):

```
REARM
fetcher start sent
trigger -> https://localhost:9888/function/basic/fetch/sw2 ->
  {"result":true,"out":[
    {"payload":"90:83:90;re.installer", ... "901:0" ...},
    {"payload":"91:82:91;/APPS/installer.ipk;re.installer;", ... "91:0", "timeout":true}]}
log=INSTALLER
POSTINST_RAN
--- ids ---
Uid:    0   0   0   0
Gid:    0   0   0   0
CapEff: 000001ffffffffff
```

## What survived the reboot

- `/APPS/installer.ipk` (needed for `82`)
- `…/basic/CHA/functions/fetch/sw2.js` (the helper that talks to superwatch)
- `/APPS/.re_sshd/` — including `hostkey_ed25519` from 22:14, so the SSH host
  key did **not** change after the reboot
- `/APPS/shell`
- the `FIREWALL_IN_EULAON` ACCEPT rule was re-added by the postinst (it is
  runtime iptables state, not persistent by itself)

## What did not survive

- the Dropbear process (expected — nothing autostarts it)
- the package registration was removed by `83` and re-added by `82`; this is
  the documented re-arm mechanism

`83` did **not** delete `/APPS/.re_sshd` or its host key, which is why the
re-arm reused the same host key and SSH did not warn about a changed key.
The postinst overwrote the binaries and `authorized_keys` and started a fresh
daemon.

## Artifact added

[`tools/u7q/web/rearm.html`](../../../../../tools/u7q/web/rearm.html), served at
`/rearm.html` by `tools/u7q/web/server.py`. It performs only the `83` + `82`
trigger against the already-present IPK/helper and reads the installer log;
it downloads nothing.

## Re-arm recipe (confirmed)

1. Serve `tools/u7q/web/` on the LAN (`python3 server.py 9000`).
2. Open `http://<host-ip>:9000/rearm.html` in the TV browser.
3. Wait for `trigger -> …` and `log=POSTINST_RAN`.
4. `ssh -p 8008 -i server/keys/vidaa_75u8qtuk_ed25519 root@10.0.0.173`.

No reboot of the TV is needed to arm; no files are re-downloaded on re-arm.
