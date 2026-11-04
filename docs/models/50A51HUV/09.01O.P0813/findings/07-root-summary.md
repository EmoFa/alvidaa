# alvidaa findings — root, achieved — the kill chain and working state

> Split from the original FINDINGS.md lab notebook. Canonical record; the blog and STORY.md draw from these.

## 11. Root, achieved (Oct 2026)

The full chain, in the order each layer fell:

1. `HiUtils_createRequest` file bridge → chroot `/APPS`, escaped via `../` (§10.3).
2. `/var/local/otaTest.sh` root boot hook, written through the bridge (§10.9).
3. Static busybox (telnetd) + dropbear 2025.88 built with `zig cc -target
   arm-linux-musleabihf`, delivered over bash `/dev/tcp` at boot (§10.12–13).
4. Firmware firewall holes for ports 2222/2323 (§10.14).
5. Dropbear patched three times (§10.15–16): authorized_keys via `-D`
   (no `.ssh/` subdir), shell-validity check removed (no `/etc/shells`, and
   root's shell is the USB gate script), perms walk removed (`/var/local` is
   777 by firmware design).
6. Final layer: root's login shell *is* `rootlogin.sh` — dropbear execs
   `pw_shell` for every session including forced commands, so the gate ran
   instead of a shell. `get_user_shell()` patched to return `/bin/sh` always.

**Working state**: `server/tv` (PATH-fixing wrapper) →

```
uid=0(root) … Linux hisensetv-<ethernet-mac> 4.19.79+ #1 SMP PREEMPT
Wed Aug 13 14:09:29 CST 2025 armv7l
```

- Hook lineage on the TV: `otaTest.sh` (current) + `otaTest.v1.bak`;
  tools in `/var/local/tvtools` (busybox, dropbear, dropbearkey);
  keys dir `/var/local/roothome`. Teardown = delete those + reboot.
- **eMMC map (3.87 GB, 42 partitions)**: p15 vbmeta (64 KB), p20 rootfs
  squashfs (36 MB), p21/p22/p24 vendor libs, p23 `/application` (97 MB),
  p26 `/config` (20 MB), p33/34/36 hidata, p37 `/usr/local` (245 MB),
  p38 `/opt` (665 MB), p39 `/var/local` (348 MB), p40 `/serialdata`,
  p41 `/APPS` (614 MB), p42 `/OAD` (921 MB).
- **First dump**: `dd if=/dev/mmcblk0p20 > /dev/tcp/<pi>/5555` →
  `firmware/mmcblk0p20.bin` (36 MB, SquashFS 4.0 LZO) → unpacked to
  `firmware/rootfs/` (gitignored). Immediate finds: `/etc/0001-cli-login-aes.pem`
  (the CLI decrypt key) is in the image, and `/etc/shells` does not exist —
  confirming the dropbear shell-check post-mortem.
- Reboots are now remote (`reboot` over SSH); the wall plug is retired.

### Backup completeness (Oct 30)

- **41/42 partitions dumped and byte-verified** against `/proc/partitions`
  (exact size match, zero mismatches). Archive: `pi:~/firmware/` mirrored to
  `fx:~/alvidaa-backup/images/`; code trees extracted to
  `pi:~/firmware/extract/` and staged for the internal Forgejo.
- **p42 (/OAD): COMPLETE (Oct 30, evening).** After Quick Start was enabled
  (standby no longer naps the network) and one power cycle cleared the
  wedged controller, the chunked re-dump landed the remaining 320 MB with
  chunks 03/05/06 first-try (vs 8 retries each in the wedged era) — the
  "hang" was the controller, confirmed by the before/after. Assembled to
  exactly 943,718,400 bytes, archived to fx505. **The backup is 42/42,
  byte-verified, mirrored on two machines.**
- **p42 original saga (superseded — kept for the lessons).** The 900 MB staging
  partition kills sustained reads: whole-file transfers died repeatedly in
  the 937–943 MB band; later, targeted reads at p42 offsets 240 MB+ hung
  the block layer hard enough to drop the SSH session (reads at offset 0
  and the other partitions were still fine at the same moment). 682 MB of
  it was captured (chunks 0–7 + partial) plus the 272 MB tail separately;
  both preserved on the Pi. **Decision: not worth hammering a possibly
  marginal eMMC region for transient staging data** — `/OAD` is rewritten
  by the updater on every firmware update, so its contents are ephemeral by
  design. If the hang survives a power cycle, that is a flash-health data
  point worth logging; if it clears, the dump can be resumed with small
  chunks and long spacing.
- **Ops lessons for the next dump** (each learned expensively): (1) the
  TV's wlan drops sustained transfers — chunk to ≤80 MB with per-chunk
  retry; (2) never `cat` parts over the target before size-verifying, and
  keep parts until the concatenation is verified; (3) run exactly ONE
  transfer script — two racing instances truncate each other's chunks; (4)
  `tail` is not installed and busybox applets are not symlinked system-wide
  — use `/usr/local/bin/busybox <applet>`; (5) `ip6tables` does not exist
  on this firmware — guard policy scripts.

**Before/after (Oct 30, post power-cycle):** targeted reads at both hung
offsets (p42 @240 MB, @878 MB) return exit 0 — the power cycle cleared it.
Verdict: **wedged eMMC controller, not failing flash.** The /OAD dump stays
partial by decision; the region is readable again if ever needed (chunked,
spaced, and only with a good reason).
