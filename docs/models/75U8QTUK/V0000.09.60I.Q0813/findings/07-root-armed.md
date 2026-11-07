# 07 — Root armed: uid 0 over key-only SSH on 8008 (2026-11-06)

Owner-authorized arm of the 100U7Q `postinst` chain after every gate went
green in [findings/05](05-fetcher-recheck.md) and
[findings/06](06-superwatch-gate.md). **Result: `ssh -p 8008 root@<tv-ip>`
gives uid 0 with `CapEff: 000001ffffffffff`, a working PTY, and read access to
`/etc/shadow` and `/data`.** No reboot; no boot persistence was installed.

## Artifacts (built fresh on the Mac, 2026-11-06)

The repo ships no Dropbear binaries, so both were built from upstream
Dropbear 2022.83 (`sha256 bc5a121f…7443b`, verified) with zig 0.14.1's musl
cross compiler, target `arm-linux-musleabihf -mcpu=cortex_a7`.

| File | Bytes | SHA-256 |
|---|---:|---|
| `tools/u7q/bin/dropbear-root` | 450,248 | `27ed88d6af499549066b995dc278b9daa93a0fb014bfd9143ca6cf0838626a37` |
| `tools/u7q/bin/dropbearkey` | 347,064 | `738949933f67b8825423cef4a3db4fb759ee3a3206a521d4256153bdc8b6d33c` |
| `tools/u7q/web/pub/installer.ipk` | 424,200 | `65a477b0d5d2c748119134715023f960e84b51bce9be5f73d0cbc634d14c35be` |

Both are `ELF 32-bit LSB executable, ARM, EABI5, statically linked, stripped`.
`dropbearkey` is **byte-identical to the 100U7Q recorded artifact** (same size
and SHA-256); `dropbear-root` differs because this build uses `/bin/sh` as the
login shell and disables PAM/shadow (see deltas below).

Key: a dedicated ed25519 keypair was generated at
`server/keys/vidaa_75u8qtuk_ed25519` (gitignored; `0600`). The public
half is not committed; only its fingerprint is recorded:

```
SHA256:reXGp1IDExMmX/4iY7tzo5+pcLRaR1Qlw+MKa9b8Or8
```

## Patches applied

1. `common-session.c` `fill_passwd()`: unknown user → `re`/314/314,
   `/APPS/.re_sshd/home`, `/bin/sh`; uid 0 → `/APPS/.re_sshd/root_home`,
   `/bin/sh`.
2. Post-build byte replacement `/etc/shells` → `/APPS/shell` (same length;
   1 occurrence in `dropbear`, 0 in `dropbearkey`).

`/bin/sh` was chosen over the 100U7Q record's `/bin/bash` because the
installer's own `#!/bin/sh` shebang proves it exists; the postinst also
whitelists `/bin/bash` when present (it is: log shows `bash present`, and
`/APPS/shell` contains both).

## Installer

Built with the new minimal builder
[`tools/u7q/scripts/make_min_installer.py`](../../../../../tools/u7q/scripts/make_min_installer.py).
Unlike `make_installer.py`, its postinst does **only** the root recipe:
deploy binaries/keys, write `/APPS/shell`, generate the host key, open
`/dev/ptmx`, start Dropbear on `0.0.0.0:8008`, accept inbound 8008 in
`FIREWALL_IN_EULAON`. **No launcher bridge, no ad-block chain, no
phone-home.**

The standard `tools/u7q/web/install.html` performed the install from the TV
Browser:

1. start `basic/fetcher` over `wss://localhost:9888`;
2. `fetchFile` `sw2.js` → `/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/functions/fetch/sw2.js`;
3. `fetchFile` `installer.ipk` → `/APPS/installer.ipk`;
4. `POST /function/basic/fetch/sw2` with
   `["90:83:90;re.installer", "91:82:91;/APPS/installer.ipk;re.installer;"]`.

Both fetches returned `ret:true, "download finished"`. The superwatch replies
were `90:0` (uninstall) and (install) `0` — accepted.

## postinst output (verbatim excerpts from `/APPS/.re_sshd/installer_log.txt`)

```
INSTALLER
POSTINST_RAN
--- ids ---
Uid:    0   0   0   0
Gid:    0   0   0   0
CapEff: 000001ffffffffff
--- step: shell whitelist ---
bash present
/bin/sh
/bin/bash
--- step: start dropbear ---
no -s: this build has no password auth compiled in
[26846] Nov 06 22:14:33 Running in background
pid=26846
  19: 00000000:1F48 00000000:0000 0A ...
--- step: firewall 8008 ---
Chain FIREWALL_IN_EULAON (1 references)
target     prot opt source               destination
ACCEPT     tcp  --  0.0.0.0/0            0.0.0.0/0            tcp dpt:8008
```

`-s` is rejected because password auth is compiled out; the postinst's
documented fallback started the daemon without it. Key-only is still
guaranteed by `DROPBEAR_SVR_PASSWORD_AUTH 0`.

## Verification (live, 2026-11-06 22:15)

```
$ nc -z <tv-ip> 8008          # 8008 OPEN

$ ssh -p 8008 -i server/keys/vidaa_75u8qtuk_ed25519 root@<tv-ip> \
      'grep -E "^(Uid|Gid|CapEff):" /proc/self/status'
Uid:    0   0   0   0
Gid:    0   0   0   0
CapEff: 000001ffffffffff

$ ssh -tt ... 'test -t 0 && echo PTY-OK'
PTY-OK

$ ssh ... 'test -r /etc/shadow && echo SHADOW-READABLE'
SHADOW-READABLE
$ ssh ... 'ls /data'
AlexaSkill  Ch_logo  DCC  ... netflix ...   (root-only tree readable)

$ ssh ... 'head -6 /proc/mounts'
/dev/root / erofs ro,...            # still read-only
/dev/dm-2 /application erofs ro,... # still read-only
```

Dropbear auth log confirms the dedicated key:

```
Pubkey auth succeeded for 'root' with ssh-ed25519 key
  SHA256:reXGp1IDExMmX/4iY7tzo5+pcLRaR1Qlw+MKa9b8Or8 from <server-ip>
```

Listener is `0.0.0.0:1F48` (8008), pid **26846**. `/dev/ptmx` and
`/dev/pts/ptmx` are `crw-rw-rw-` (666), enabling PTY allocation.

## State left on the TV (all reversible)

| Path / object | Notes |
|---|---|
| `/APPS/.re_sshd/` | `dropbear-root`, `dropbearkey`, `hostkey_ed25519`, `root_home/.ssh/authorized_keys` (root:root 0600/0700), `home/.ssh/authorized_keys` (314:314), `dropbear.pid`, `installer_log.txt` |
| `/APPS/shell` | contains `/bin/sh` and `/bin/bash` |
| `/APPS/installer.ipk` | the IPK, kept for re-arm after reboot |
| `…/basic/CHA/functions/fetch/sw2.js` | the superwatch helper; harmless, also used to re-arm/uninstall |
| package `re.installer` | registered with opkg |
| `/dev/ptmx`, `/dev/pts/ptmx` | mode 666 (was group-`tty`-only) |
| `FIREWALL_IN_EULAON` | one `ACCEPT tcp dpt:8008` at the top (deduped by postinst) |

No rootfs write (`/` and `/application` remain `erofs ro`); dm-verity is
untouched. No reboot was performed.

## Rollback

```sh
# 1. uninstall through the superwatch socket (sw2.js is still on the TV)
#    POST /function/basic/fetch/sw2  {"list":["90:83:90;re.installer"]}
# 2. kill the daemon and remove the postinst's outside-package files
ssh -p 8008 -i server/keys/vidaa_75u8qtuk_ed25519 root@<tv-ip> \
  'kill $(cat /APPS/.re_sshd/dropbear.pid); rm -rf /APPS/.re_sshd /APPS/shell /APPS/installer.ipk'
# 3. remove the firewall rule
/basic/bin/iptables/iptables -D FIREWALL_IN_EULAON -p tcp --dport 8008 -j ACCEPT
# 4. restore ptmx modes to the vendor default (root:tty 0620)
chmod 620 /dev/ptmx; chmod 620 /dev/pts/ptmx
# 5. remove the FaaS helper
rm -f /APPS/pkgs/tv.vidaa.jsservice.basic/CHA/functions/fetch/sw2.js
```

Re-arm after a reboot: the IPK stays at `/APPS/installer.ipk`, so resend
`83` then `82` via `sw2.js` (or rerun the install page). Nothing starts at
boot.

## Deltas vs the 100U7Q record

| | 100U7Q record | This unit |
|---|---|---|
| login shell | `/bin/bash` | `/bin/sh` (plus `/bin/bash` whitelisted) |
| configure | PAM/shadow not disabled | `--disable-pam --disable-shadow` |
| `dropbear-root` size | 478,840 B | 450,248 B (same patch set, fewer libs) |
| `dropbearkey` | 347,064 B / `7389…d33c` | **identical** |
| installer extras | — | minimal postinst (no ad-block/launcher/phone-home) |

Everything else — socket, group 616, command ids, 8008, key-only auth, PTY
chmod, no persistence — matches the record.

## Follow-up

- Owner should keep `server/keys/vidaa_75u8qtuk_ed25519` backed up; it is the
  only key authorised on the TV.
- The private key is gitignored; do not copy it off this Mac except to a
  password manager/secure backup.
- Decide whether to leave 8008 reachable LAN-wide or restrict it at the home
  firewall. The TV's own filter only ACCEPTs 8008; it does not limit source.
