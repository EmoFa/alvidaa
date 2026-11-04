# How the chain works

Everything below was read from the bridge sources on the device
(`/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/…`) or measured on the running TV.
Line numbers refer to those files.

## 0. Transport

The TV's web app talks to a local Node service ("phoenix") over
`https://localhost:9888` (fallback `http://localhost:9009`). Services:
`hiutils`, `tvinfo`, `pkgmgr`, `jhkservice`, `pkghosting`, plus the FaaS
module directory.

## 1. Arbitrary write — the `fetcher` FaaS function

`services/fetcher/package.json` has `"permission": {}` and
`selfStart: false`. It is not in the 3-segment router whitelist
(`/service/fetcher` → `Wrong request`) but is reachable at
`/service/basic/fetcher`. It must be started over WebSocket:

```json
{"path":"phoenix://service/basic/fetcher","method":"start",
 "parameters":{},"session":901,"timeout":10}
```

Then:

```js
vowOS.service.syncExecute("basic/fetcher", {api:"fetchFile", args: JSON.stringify({
    url: "http://host/file", directory: "/absolute/path", permission: 420 })})
```

`functions/fetch/fetchfile.js`:

```js
const directory = args?.directory            // no validation
...
axios.get(url, reqParams).then(response => {
    const file = fs.createWriteStream(directory, file_options)
    ...
    fs.chmodSync(directory, permission)
```

No directory creation, so parent directories must exist. opkg installs run in
the same service context and create directories as root.

## 2. The superwatch socket

`services/pkgmgr/PackageInstall.js` does not install IPKs itself:

```js
const cmd = `${sessionId};${ipk};${allFields.Package};${options}`;
sendMsgToSuperwatch(cmd, "82", sessionId);
```

`SuperwatchCtrl.js` writes a 4-byte little-endian length followed by
`<sessionId>:<commandId>:<message>` to `/var/run/superwatch_socket`.

That socket is `srw-rw---- root 616`, and **616 is one of the supplementary
groups of the app user (uid 314)** — so the app context can connect directly.

Command ids: `80/81` backup, `82` install, `83` uninstall, `84` rollback,
`85` directory size. Responses are `<sessionId>:<code>`; `0` = OK,
`604` = invalid command id, `-1` = generic failure.

Install **with empty options**. Passing `--tmp-dir,/OAD/pkgs/tmp` makes the
daemon answer `-1`.

## 3. Root execution

The daemon runs `opkg install <ipk>` as root, so the package's `postinst`
executes with `Uid: 0 0 0 0` and `CapEff: 000001ffffffffff`.

Measured with a minimal package:

```
POSTINST_RAN
Uid:    0   0   0   0
Gid:    0   0   0   0
CapEff: 000001ffffffffff
```

No signature check happens on this path; `checkIpkSignature` is only used by
the store-update flow.

**opkg extracts `data.tar.gz` relative to `/APPS/pkgs`, not to `/`.**
A member `APPS/.re_sshd/x` lands at `/APPS/pkgs/APPS/.re_sshd/x`; the
`postinst` moves it. This is the single most common surprise when writing
packages for this device.

## 4. Why a patched dropbear

`/etc/passwd` on this TV:

```
root:x:0:0:root:/basic:/etc/rootlogin.sh
```

`/basic` is on the read-only, dm-verity protected root filesystem, so no
`authorized_keys` can be placed there, and the login shell would be the
console login script. Additionally `/etc/shells` does not exist, so musl's
`getusershell()` returns NULL and dropbear rejects every login
(`User 'x' has invalid shell, rejected`).

Two build patches (`scripts/make_installer.py` packages the result):

1. `common-session.c`, `fill_passwd()`: when `getpwnam()` fails, fall back to
   `re`/`x`/314/314/`/APPS/.re_sshd/home`/`/bin/bash`; when it succeeds for
   `uid 0`, override `pw_dir`/`pw_shell` to `/APPS/.re_sshd/root_home` and
   `/bin/bash`.
2. Binary field patch: the 11-byte literal `/etc/shells` (file offset 15162)
   is replaced by `/APPS/shell`, and that file contains `/bin/bash`.

The result is a static ARM32 dropbear (`file`: *ELF 32-bit LSB executable,
ARM, EABI5, statically linked*).

## 5. Ports

`/etc/iptables/iptables.conf` only drops TCP `0:1023`, but a second layer
filters more. Distinguish by the error:

- `Connection refused` → port allowed, nothing listening
- timeout → dropped

8008 was free and allowed, so dropbear listens there. Port 22 is dropped.

## 6. What is still blocked

- `/` is erofs, read-only, dm-verity `enforcing` — no `/etc` edits, no
  `rc.local` hooks, even as root.
- The `/OAD` hooks are inert: `init_kilby.rc` hardcodes `kilbyDebug=0`
  (always sources the read-only script), and `3rd_overlayfs.sh` requires
  `init=/sbin/preinit` plus `/mnt/tvroot/usrlocal/debug_version`.
- All writable partitions (`/APPS`, `/OAD`, `/data`) are mounted `nosuid`, so
  setuid binaries do not work.
- No automatic restart after reboot; use `scripts/trigger.sh`.
