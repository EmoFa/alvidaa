# 04 — root SSH

Deployed and verified: `ssh -p 8008 root@<tv>` gives uid 0 with full
capabilities and a PTY, key-only.

## Build

Static 32-bit ARM dropbear 2022.83 (`478840 B` after patching), plus
`dropbearkey`. Two source/field patches are required:

1. `common-session.c`, `fill_passwd()`:
   - unknown user → fallback entry `re` / uid 314 / gid 314 /
     `/APPS/.re_sshd/home` / `/bin/bash`
   - resolved uid 0 → force `pw_dir=/APPS/.re_sshd/root_home`,
     `pw_shell=/bin/bash`
2. 11-byte field patch in the stripped binary: `/etc/shells` at file offset
   **15162** becomes `/APPS/shell` (same length, size unchanged).

The full rebuild recipe is in [`../docs/BUILD.md`](../docs/BUILD.md).

Why the patches: `/etc/passwd` has `root:x:0:0:root:/basic:/etc/rootlogin.sh`,
`/basic` is on the read-only root, and `/etc/shells` does not exist, so musl's
`getusershell()` returns NULL and dropbear rejects every login with
`User '…' has invalid shell`.

## Files

```
/APPS/.re_sshd/
  dropbear-root                 0755
  dropbearkey                   0755
  hostkey_ed25519               0600   (generated on device)
  root_home/.ssh/authorized_keys  0600   root:root, home is 0700
  home/.ssh/authorized_keys       0600   314:314 (the uid-314 login "re")
/APPS/shell                     contains "/bin/bash"
```

Dropbear refuses `authorized_keys` if the home directory or `.ssh` is not owned
by the login user (or root) and is group/world writable. `chown -R 0:0` on the
root home was the step that made root login work.

## Start

```sh
cd /APPS/.re_sshd
./dropbear-root -s -r /APPS/.re_sshd/hostkey_ed25519 -p 8008 -P dropbear.pid
```

`-s` disables password logins. Port 8008 is used because the firmware drops low
ports and 8008 was confirmed allowed (it answered `Connection refused` while
free). Port 22 would need `CAP_NET_BIND_SERVICE`, which the context does not
have.

## PTY

`/dev/ptmx` is `root:tty 0620` and uid 314 is not in group `tty`, so PTY
allocation fails with `openpty: Permission denied`. The `postinst` sets
`chmod 666 /dev/ptmx /dev/pts/ptmx`; after that `ssh -tt` works.

## Adding keys

```sh
# as root:
echo 'ssh-ed25519 <PUBKEY> you' >> ~/.ssh/authorized_keys

# for the uid-314 login, no root needed:
#   /APPS/.re_sshd/home/.ssh/authorized_keys
```

## Restart after reboot / re-trigger

Nothing starts the daemon automatically (see [`05-limits.md`](05-limits.md)).
The installer package stays installed, so its `postinst` will not run again on
its own. Send uninstall followed by install to the superwatch socket
([`03-root.md`](03-root.md)):

```js
{list: [
  "70:83:70;re.installer",
  "71:82:71;/APPS/installer.ipk;re.installer;"
]}
```

That re-runs `postinst`, which kills the old daemon and starts a fresh one.
