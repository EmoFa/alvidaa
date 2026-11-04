# Modding notes — 100U7Q / VIDAA U09.60

Everything in this directory was measured on the device listed below. Anything
that was not measured is marked **UNVERIFIED** and is not a recipe.

| | |
|---|---|
| Model | Hisense 100U7Q (`100U70QEVS`, SerialType `100U7QE`), EU_A |
| Firmware | `V0000.09.60I.Q0813`, VIDAA `U09.60` |
| SoC | MediaTek MT9655 |
| Userland | 32-bit ARM (`ELF EM_ARM`), Node `arm`, kernel `5.15.192-ge6d9f75ad2ad-dirty` |
| App context | uid 314, gid 314, `CapEff=0000000000800000` (only `CAP_SYS_NICE`) |
| SELinux | `enforce=1` |

## Files

| File | Content |
|---|---|
| [`01-system.md`](01-system.md) | filesystem layout, mounts, permissions, ports |
| [`02-write-and-exec.md`](02-write-and-exec.md) | arbitrary file write (`fetcher`) and code execution (FaaS) |
| [`03-root.md`](03-root.md) | root via the package manager's superwatch socket |
| [`04-ssh.md`](04-ssh.md) | root dropbear: build patches, deployment, keys, PTY, trigger |
| [`05-limits.md`](05-limits.md) | what does not work on this build, and why |
| [`06-open.md`](06-open.md) | open questions, explicitly unverified |

## Rules that come from the measurements

- `/` is read-only (erofs + dm-verity). Do not try to edit `/etc`; it cannot
  work, not even as root.
- Every writable partition is mounted `nosuid`. Setuid binaries are dead.
- There is no writable shell boot hook on this build. Persistence has to come
  from something else.
- Back up `/APPS/websdk/Appinfo.json` before touching it; it is the launcher's
  tile registry.
- `/OAD` is the OTA staging area. Nothing in these notes needs a write there
  except a small self-expiring flag (`enable_selenium`, 24 h).

## Scope

Own device only. No flashing, no partition writes, no vendor service calls.
The root path below is additive: it installs a package and starts a daemon; it
does not modify a vendor file or a read-only partition.
