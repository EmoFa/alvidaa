# 100U7Q — original research notes

Root SSH on a Hisense VIDAA TV, entirely over the LAN.

Target this was developed and verified on:

| | |
|---|---|
| Model | Hisense 100U7Q (`100U70QEVS`, SerialType `100U7QE`) |
| SoC | MediaTek MT9655, **32-bit ARM** userland (`EM_ARM`), kernel 5.15.192 |
| Firmware | VIDAA `U09.60`, `V0000.09.60I.Q0813`, region EU_A |
| Result | `ssh -p 8008 root@<tv>` — uid 0, full caps, PTY, key-only |

It is **not** a generic VIDAA exploit. It relies on four properties of this
firmware, all verified on the device (see `docs/HOW-IT-WORKS.md`):

1. `hiutils.fileRead` / the `fetcher` FaaS service let an app-context page write
   files to arbitrary absolute paths (the `fetcher` service has an empty
   permission block).
2. `/var/run/superwatch_socket` (the root package daemon) is owned
   `root:616`, and **616 is in the app user's group set**, so the app context
   can talk to it directly.
3. An IPK's `postinst` is therefore executed **as root with full capabilities**.
4. Root's home/shell in `/etc/passwd` point at read-only paths, so a patched
   dropbear build is used that overrides `pw_dir`/`pw_shell` for uid 0.

Everything is additive: no vendor file is replaced, no partition is flashed,
`/` stays read-only (erofs + dm-verity).

---

## Scope

This repository contains **only** the 100U7Q / U09.60 chain described above.
It shares no code, credentials or assumptions with other Hisense work:

- the generic/HE40 toolkit (firmware catalog, static inventory, sanitized
  modding helpers) lives in the sibling tree [`../he40/`](../he40/)
- that toolkit's HE40 profile does **not** transfer to this model; this
  directory is the separately verified path for 100U7Q

Nothing from the HE40 chain (`/3rd_rw` hooks, `developer.sh`, `libtvsysinfo`
shadowing, ext4/USB symlink delivery) applies here and none of it is included.

## Documentation

| File | Content |
|---|---|
| [`docs/PAIRING.md`](docs/PAIRING.md) | step 0: pairing with sidee, PIN pitfalls |
| [`docs/HOW-IT-WORKS.md`](docs/HOW-IT-WORKS.md) | the whole chain with code references |
| [`docs/BUILD.md`](docs/BUILD.md) | rebuilding the dropbear binaries |
| [`modding/`](modding/README.md) | measured system facts: filesystem, write/exec primitives, root, SSH, limits, open questions |

## What you need

- The same model/firmware. A different build almost certainly breaks at least
  one of the four assumptions.
- **Your own MQTT pairing.** `device_uuid` is the TV's Ethernet MAC, the PIN is
  shown on screen. This repo contains no credentials, no certificates and no
  session data. Pairing is done with
  [sidee](https://github.com/alvidaa/sidee), which carries its own client
  certificate. Step-by-step: [`docs/PAIRING.md`](docs/PAIRING.md); wrapper:
  `scripts/pair.sh`.
- A machine in the same LAN as the TV that the TV can reach over HTTP
  (for example `<host-ip>`), plus an SSH key pair of your own.

## Quick start

```sh
# 0. pair once (PIN on the TV); see docs/PAIRING.md
./scripts/pair.sh --tv <tv-ip> --sidee /tmp/sidee-check

# 1. build the per-device installer and serve it
./scripts/install.sh \
    --pubkey "ssh-ed25519 <PUBKEY> you@host" \
    --host <host-ip> \
    --port 9000 \
    --tv <tv-ip> \
    --launch

# 2. if --launch was not used, open this page on the TV yourself:
#    http://<host-ip>:9000/install.html
#    (e.g. by launching a tile that points at it via MQTT)

# 3. connect
ssh -p 8008 root@<tv-ip>
```

The install page does exactly three writes and one call:

1. start the `fetcher` service (WebSocket `method:"start"`),
2. `fetchFile` → `.../functions/fetch/sw2.js` (the superwatch helper),
3. `fetchFile` → `/APPS/installer.ipk` (contains dropbear + your public key),
4. `POST /function/system/fetch/sw2` with the install command.

The IPK's `postinst` runs as root and does the rest: creates
`/APPS/.re_sshd`, deploys the binaries, writes `authorized_keys`, generates the
ed25519 host key, opens `/dev/ptmx` and starts dropbear on 8008.

## After a reboot

The daemon does not start by itself (there is no writable shell boot hook on
this firmware; `/etc` is on a dm-verity protected read-only filesystem). The
installed IPK stays installed, so its `postinst` will not run again. Re-arm it:

```sh
./scripts/trigger.sh --host <host-ip> --tv <tv-ip> --launch
```

That page sends `uninstall(83)` followed by `install(82)` to the superwatch
daemon; the install re-runs `postinst`, which restarts dropbear.

If you copy the TV's IP or the host IP changes, pass the new values — nothing
is hardcoded.

## Adding more keys

```sh
# root login (uid 0)
echo 'ssh-ed25519 <PUBKEY> other' >> ~/.ssh/authorized_keys   # inside the root ssh session

# the app-context user ("re", uid 314)
#   /APPS/.re_sshd/home/.ssh/authorized_keys   (writable by uid 314, no root needed)
```

The root home is `root:root 0700`, `authorized_keys` is `0600`. Dropbear
rejects keys if those permissions are wrong — keep them.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Permission denied (publickey)` as root | `authorized_keys`/home ownership or mode wrong; dropbear requires root-owned, non-group-writable |
| `Permission denied` as `re` | that file is `/APPS/.re_sshd/home/.ssh/authorized_keys` |
| Connection times out on 8008 | port blocked; the firmware drops low ports (`0:1023`) and has a second allowlist layer. `Connection refused` means "allowed, nothing listening" |
| No capture after install | check `web/server.log`; the TV must reach `--host` |
| Root login works but no PTY | `/dev/ptmx` permissions; the `postinst` sets `666`, re-run the trigger |

## Not included

- No private keys, no `authorized_keys` of the author, no pairing session, no
  device MAC/serial, no vendor certificate.
- No boot persistence service: it would require writing into a boot-executed
  path, and on this firmware those are read-only.

## Legal / safety

Use this only on hardware you own. Rooting can void warranties and vendor
terms, and a mistake can leave the TV unbootable. There is no warranty of any
kind; see `LICENSE`. The bundled dropbear is GPLv2 — see `NOTICE.md`.
