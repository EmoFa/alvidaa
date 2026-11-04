# u7q/ — 100U7Q root tooling

Installer and re-arm helpers for the 100U7Q (`100U70QEVS`) chain on firmware
`V0000.09.60I.Q0813` (MediaTek MT9655, 32-bit ARM userland, VIDAA U09.60).
The path is: pair with the TV over MQTT, use the `fetcher` FaaS function to
write a helper and an IPK, ask the package manager to install it, and let the
IPK's `postinst` start a patched, key-only Dropbear on port 8008.

This is specific to that model and firmware. Read the model guide first:

[`../../docs/models/100U7Q/V0000.09.60I.Q0813/README.md`](../../docs/models/100U7Q/V0000.09.60I.Q0813/README.md)

## Layout

| Path | Contents |
|---|---|
| [`scripts/pair.sh`](scripts/pair.sh) | Pair this machine with the TV through a `sidee` checkout; checks that sidee has its own client certificate and starts the PIN flow. |
| [`scripts/install.sh`](scripts/install.sh) | Build the installer IPK, copy the artifacts into `web/pub/`, serve the page, optionally launch a tile, and wait for the TV to report back. |
| [`scripts/trigger.sh`](scripts/trigger.sh) | Serve the re-arm page and optionally launch it; used after a reboot. |
| [`scripts/make_installer.py`](scripts/make_installer.py) | Build the IPK from your two binaries and your public key. The `postinst` runs as root. |
| [`scripts/launch_tile.py`](scripts/launch_tile.py) | Launch a tile over MQTT using the sidee session. The only step that needs a paired session. |
| [`web/install.html`](web/install.html) | TV-side installer page: start `fetcher`, write `sw2.js` and the IPK, trigger the install, read the log. |
| [`web/trigger.html`](web/trigger.html) | TV-side re-arm page: send uninstall `83` then install `82`. |
| [`web/server.py`](web/server.py) | Plain HTTP server for the pages and `web/pub/`; stores TV POSTs under `web/captures/`. |
| [`faas/sw2.js`](faas/sw2.js) | FaaS module that connects to `/var/run/superwatch_socket` and sends length-prefixed commands. |
| [`bin/`](bin/) | Placeholder for **your** `dropbear-root` and `dropbearkey`. Ships only a README. |

No certificate, token, session file, IPK, or Dropbear binary is in this subtree.

## What you supply

| Item | Put it here / pass it as | Source |
|---|---|---|
| Static ARM32 Dropbear 2022.83, patched | `bin/dropbear-root` | Build it yourself. The model guide has the upstream version, configure flags, `fill_passwd()` patch, and the `/etc/shells` → `/APPS/shell` literal patch. |
| `dropbearkey` | `bin/dropbearkey` | Same build. |
| Your SSH public key | `--pubkey "ssh-ed25519 <PUBKEY> ..."` | Your own key. The private key never leaves your machine. |
| `sidee` checkout with your session | `--sidee` or `SIDEE` | Clone sidee yourself; it carries its own client certificate. Pairing creates `~/.sidee/session.json` (mode 600). |
| A host the TV can reach over HTTP | `--host <host-ip> --port 9000` | This machine on the same LAN. |

The installer does not need a vendor certificate in this repository: sidee
supplies its own client certificate, and the session is per TV. Do not commit
either.

## Install flow

1. **Pair once.**

   ```sh
   ./scripts/pair.sh --tv <tv-ip> --sidee /path/to/sidee
   ```

   The TV shows a four-digit PIN. Confirm it once. A retrigger rotates the PIN;
   repeated wrong PINs lock the client out temporarily.

2. **Build and serve the installer.**

   ```sh
   ./scripts/install.sh \
       --pubkey "ssh-ed25519 <PUBKEY> you@host" \
       --host <host-ip> --port 9000 --tv <tv-ip> --launch
   ```

   `install.sh` calls `make_installer.py`, writes `web/pub/installer.ipk`,
   copies the two binaries and `faas/sw2.js` into `web/pub/`, starts
   `web/server.py` if it is not already running, and optionally launches the
   tile through sidee. Without `--launch`, open
   `http://<host-ip>:9000/install.html` on the TV yourself.

3. **The page does the writes and the trigger.** `install.html` starts the
   `basic/fetcher` service, writes `sw2.js` into the FaaS function directory,
   writes the installer IPK to a writable path under `/APPS`, then POSTs the
   install command to the superwatch path. The IPK's `postinst` runs as root: it creates
   `/APPS/.re_sshd`, moves the binaries, writes `authorized_keys` and
   `/APPS/shell`, sets the PTY device modes, generates an ed25519 host key if
   missing, and starts Dropbear on 8008.

   The page uses `fetcher.fetchFile` for writes and `hiutils.fileRead` only to
   read the installer log. It does not use `fileRead` as a write primitive.

4. **Connect.**

   ```sh
   ssh -p 8008 root@<tv-ip>
   ```

   The source record reports uid 0, full capabilities, a PTY, and key-only
   authentication. This tree contains no log from that run.

## Re-arm after a reboot

There is no boot hook on this firmware. The IPK stays installed, so its
`postinst` will not run again by itself. Start the trigger page:

```sh
./scripts/trigger.sh --host <host-ip> --port 9000 --tv <tv-ip> --launch
```

`trigger.html` sends `uninstall(83)` for `re.installer`, then `install(82)` of
the installer IPK. The install re-runs `postinst`, which starts Dropbear again.
The `postinst` generated by `scripts/make_installer.py` kills an existing daemon
by PID before it starts a new one; whether the historical run did so is not
recorded.

## Warnings

| Hazard | Detail |
|---|---|
| **Root SSH is root-equivalent** | `dropbear-root` runs as uid 0 with full capabilities. Key-only authentication is not a sandbox. |
| **Port 8008 only** | Low ports are filtered on this firmware: 22 is dropped, 2222 timed out, 8008 was allowed. Do not assume another port will work. |
| **No boot persistence** | There is no writable path the boot chain executes. After every reboot you must re-arm. |
| **Runtime state remains** | The chain does not replace a vendor file and does not write `/`, but `postinst` changes `/dev/ptmx` and `/dev/pts/ptmx` to mode 666, creates `/APPS/shell`, and leaves `/APPS/.re_sshd` plus the installed `re.installer` package. |
| **Uninstall is not full cleanup** | Command `83` removes the package and its data files, not everything `postinst` created outside the package's data list. Track and remove `/APPS/.re_sshd`, `/APPS/shell`, and the device-node mode change yourself. Full cleanup is operator-defined. |
| **Unauthenticated HTTP server** | [`web/server.py`](web/server.py) binds `0.0.0.0`, has no TLS and no authentication, and accepts POSTs to `/recon`. Use it only on a trusted LAN and only while you are working. Never expose it to the internet. |
| **FaaS bridge writes `/tmp/sw2_result.json`** | [`faas/sw2.js`](faas/sw2.js) stores its last result there on the TV. It is diagnostic state, not a secret. |

## What this tree does not prove

| Area | Status |
|---|---|
| Root chain (pairing, fetcher write, superwatch, root `postinst`, Dropbear) | The source record reports the measured `postinst` identity (`Uid 0`, full `CapEff`) and a working root SSH session. No raw log is included here. |
| Boot persistence | None on this build; re-trigger is required. |
| Low ports | 22 dropped and 2222 timed out in the record; the second filter layer is unidentified. |
| OTA recovery image | No usable image was found for this model; the record reports `errorCode 205001`. |
| Persistence candidates (`appinfo.json`, phoenix `run_phoenix.sh`, `systemserver` config, DevTools ports) | Explicitly unverified in the source record. |
| Full rollback of `/dev/ptmx`, `/APPS/shell`, `/APPS/.re_sshd` | Not documented as a single procedure; operator-defined. |

Do not upgrade any of these labels because a script exists. The model guide is
the canonical evidence index.

## Related

- OTA signing primitive and firmware format helpers: [`../fw/ota/sign/README.md`](../fw/ota/sign/README.md)
- Secret/PII scanner used before publishing this tree: [`../sanitize/README.md`](../sanitize/README.md)
- Tree overview and directory contract: [`../README.md`](../README.md)
- Disclosure and publication policy: [`../../SECURITY.md`](../../SECURITY.md)
