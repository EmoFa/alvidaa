# 05 — limits of this build

Everything here was checked; these are not guesses.

## Read-only, integrity-protected root

```
/dev/root  /  erofs  ro  (dm-verity, androidboot.verifiedbootstate=green)
```

Consequences:

- `/etc` cannot be modified, not even from a root context.
- `/etc/rc.d/rc.local` and the scripts it calls are immutable.
- A shell boot hook in `/etc` is impossible.

The two `/OAD` hooks in the boot scripts are dead on this build (see
[`01-system.md`](01-system.md)).

## No setuid

`/APPS`, `/OAD` and `/data` are mounted `nosuid`. A `chmod 4755` binary executes
with the caller's uid (verified: stayed 314).

## No low ports from the app context

`CapEff = 0x800000` is `CAP_SYS_NICE` only — no `CAP_NET_BIND_SERVICE`.
Binding below 1024 requires a root context.

In addition, the packet filter drops low ports (see [`01-system.md`](01-system.md)).
Use the `refused` vs `timeout` signal to find an allowed high port.

## No writable boot hook

There is no writable path that the boot chain executes. A daemon started by a
`postinst` lives until the next reboot and no longer.

Consequence: root SSH requires a re-trigger after every reboot
([`04-ssh.md`](04-ssh.md)).

## The app context is not root

uid 314 with only `CAP_SYS_NICE`, SELinux enforcing, no `CAP_DAC_OVERRIDE`:
files owned by other users stay unreadable (for example `/etc/shadow`, `EACCES`).
Root-level file operations require the `postinst` context.

## Careful with `/APPS/websdk/Appinfo.json`

It is writable by uid 314 (`311:713`, `0660`) and holds the launcher tile
registry. A malformed file can empty the launcher. Always copy it first:

```sh
cp /APPS/websdk/Appinfo.json /APPS/websdk/Appinfo.json.bak
```

Keep it valid JSON; the launcher may cache it until it reloads.

## Firmware images

OTA probing returned no usable image for this model during the run
(`errorCode 205001`, 21 requests, `dvcRsv=<model-code>` refuted). There is no known
public channel; this is documented rather than worked around.

## What is still possible

- Install/uninstall packages through the superwatch socket (root `postinst`).
- Run arbitrary commands in the FaaS worker (uid 314) and, through a `postinst`,
  as root.
- Read most of the filesystem; write `/APPS`, `/OAD`, `/vddt`.
- Edit the tile registry, the browser favourites and the FaaS function set.
