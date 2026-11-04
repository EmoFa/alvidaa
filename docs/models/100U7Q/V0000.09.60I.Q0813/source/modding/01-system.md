# 01 — system layout

All values below were read from `/proc`, `/etc` or the bridge sources on the
device.

## Mounts (excerpt from `/proc/mounts`)

```
/dev/root          /            erofs   ro,seclabel,...
/dev/dm-1          /application erofs   ro,seclabel,...
/dev/mmcblk0p54    /APPS        ext4    rw,seclabel,nosuid,nodev
/dev/mmcblk0p56    /OAD         ext4    rw,seclabel,nosuid,nodev
/dev/mmcblk0p12    /data        ext4    rw,seclabel,nosuid,nodev
/dev/mmcblk0p5     /certificate ext4    rw,nosuid,nodev,noexec
```

Consequences:

- The root filesystem is **read-only and integrity protected**:
  `androidboot.verifiedbootstate=green`, `dm-verity` enforcing, `root=/dev/dm-0`.
  `/etc/rc.d/rc.local` exists but cannot be edited.
- Every writable data partition is `nosuid`. A setuid binary placed there is
  ignored (verified: `chmod 4755`, execution kept uid 314).
- `/APPS`, `/OAD` are writable by uid 314. `/data` is not.

## What uid 314 can write

Checked with `accessSync(dir, W_OK)` from the app context:

| path | writable |
|---|---|
| `/APPS` | yes |
| `/OAD` | yes |
| `/vddt` | yes |
| `/data`, `/3rd_rw`, `/perm`, `/usr/local`, `/tvsapp`, `/basic` | no |

`/APPS/websdk/Appinfo.json` is owned `311:713`, mode `0660`; uid 314 can write
the content (a `chmod` fails with `EPERM`, which is harmless).

## Boot chain (read-only, for orientation)

```
/sbin/init
  /etc/inittab
  /etc/init.d/rcS
    /etc/rc.d/rc.local
      /usr/local/scripts/tvs-debug.sh     (if present)
      /tvsapp/etc/init.d/start-early-tvs.sh
      /usr/local/scripts/start-tvs.sh     (if present)
      /usr/local/scripts/start-kilby.sh
```

Every one of those paths is on the read-only root. Two `/OAD` candidates exist
in the boot scripts but are inert on this build:

- `init_kilby.rc` sets `kilbyDebug=0` as a literal before the branch, so it
  always sources `/usr/local/scripts/start-kilby.sh` and never
  `/OAD/start-kilby.sh`.
- `3rd_overlayfs.sh` exits early unless the kernel command line contains
  `init=/sbin/preinit` and `/mnt/tvroot/usrlocal/debug_version` exists. This
  build has `init=/sbin/init` and no such file. It would overlay `/3rd` anyway,
  not `/etc`.

## Ports

`/etc/iptables/iptables.conf` contains only:

```
-A INPUT -p tcp --match multiport --dports 0:1023 -j DROP
```

Measured behaviour contradicts a plain ">1023 is open" reading: 2222 timed out
while 8008 answered `Connection refused` when idle. Distinguish the two:

| answer | meaning |
|---|---|
| `Connection refused` | allowed by the filter, nothing listening |
| timeout | dropped |

So there is at least one more filter layer that is not in that file. Use the
error to pick a port; 8008 was free and allowed.

## Services and permissions

`services/<name>/package.json` defines `permission.provided`. A service with an
empty or missing block performs no permission check at all (`fetcher` is empty).

Known services: `hiutils`, `tvinfo` (type `basic`); `pkgmgr`, `jhkservice`,
`pkghosting`, `tilesService` (type `system`); plus the FaaS function directory.

## Process supervision

`phoenix` (the Node service host) runs as uid 314 and is started by
`systemserver` (uid 301, `/mnt/tvroot/usrlocal/bin/systemserver`). The FaaS
worker is a child of phoenix.
