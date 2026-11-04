# Evidence — HE40E5600FFWTS / V0100.01.00A.N0410

**What this page is:** the evidence ledger behind
[README.md](README.md). It separates what was observed on the device, what was
only documented in the author's record, what was rebuilt on a host, and what
remains unknown. It deliberately does **not** upgrade any claim.

**Basis:** the author's private research record for this exact model and
firmware (2026-10-26 snapshot), plus the owner's statement of 2026-11-04.
`record:he40/...` citations are line labels in that private record, not files in this
repository. No device, binary or shell was used to write this page.

> **Self-contained note:** the `record:he40/...` labels are provenance only. The
> procedure and the decisive excerpts are reproduced in this guide; the
> private record is not part of this repository and is not required to follow
> it.

## Target identity

| Property | Recorded value | Basis |
|---|---|---|
| Retail model | `HE40E5600FFWTS` | `record:he40/docs/HARDWARE-NOTES.md:14`; `record:he40/modding/01-system-linux.md:3` |
| Firmware | `V0100.01.00A.N0410` | `record:he40/docs/HARDWARE-NOTES.md:15`; `record:he40/modding/01-system-linux.md:20` |
| SoC class | MediaTek **MT53xx / MT5863 class** (`mt53xx-emmc`, `mt5863_sa_768_linux`) | `record:he40/docs/HARDWARE-NOTES.md:16`; `record:he40/modding/01-system-linux.md:57` |
| CPU | ARMv7, Cortex-A53 (`part 0xd03`), NEON/VFPv4, Thumb-2 | `record:he40/modding/01-system-linux.md:48-56` |
| Kernel | Linux 3.18.25, 32-bit ARM, SMP, PREEMPT; Linaro GCC 4.8.2; build 2023-04-10 | `record:he40/modding/01-system-linux.md:11-18` |
| libc / userland | glibc 2.18; BusyBox 1.18.5; SysV init (`inittab`/`rcS`/`rc.local`); no systemd | `record:he40/modding/01-system-linux.md:67-93` |
| Package manager | none (`apt`, `dpkg`, `opkg`, `ipkg`, `rpm`, `apk`, `yum`, `pacman` absent) | `record:he40/modding/01-system-linux.md:99-114` |
| Storage | squashfs **ro** `/` (38.8 MB) and `/3rd` (141 MB); ext4 **rw** `/3rd_rw`, `/data`, `/perm`; `/spdata` ro; no overlayfs | `record:he40/modding/01-system-linux.md:128-169` |
| `/dev` | part of the ro squashfs; no devtmpfs; static nodes | `record:he40/modding/01-system-linux.md:165` |
| UI processes | `hisenseUI` (GLES, DevTools 9223) and `hisense_browser` (DirectFB, DevTools 9224), both root | `record:he40/modding/03-ui.md:9-20` |

Not established: exact SoC part number, exact core count, secure-boot and
signature state (`record:he40/modding/01-system-linux.md:203`;
`record:he40/modding/07-evidence-unknowns.md:92`).

## Claim / status matrix

Labels:

- **CONFIRMED live (recorded)** — the record reports a device observation, with
  an output or artifact. This is a record claim, not an independent re-test.
- **CONFIRMED host/build** — reproduced on a build host, not on the TV.
- **owner-verified** — stated by the device owner after the record; no file in
  the record set contains the observation.
- **documented code** — quoted configuration/source, or a build recipe.
- **UNVERIFIED** — not tested or explicitly open.
- **DEAD END** — tried and rejected.

| # | Claim | Status | Basis |
|---|---|---|---|
| 1 | `hisense_browser` runs as uid/gid 0 with full `CapEff`, single process, no seccomp/`NoNewPrivs` | CONFIRMED live (recorded) | `record:he40/root/ROOT-GUIDE.md:34` — "`hisense_browser` läuft als UID/GID 0, `CapEff` voll, Single-Process, kein Seccomp"; repeated at `record:he40/modding/03-ui.md:302` |
| 2 | A dangling ext4 symlink bypasses the file-API whitelist (`realpath` + prefix check) and creates a root-owned file | CONFIRMED live (recorded) | `record:he40/root/ROOT-GUIDE.md:35`; `record:he40/modding/07-evidence-unknowns.md:12` — "`pwn`/`tvi` dangling; `File.write`/`File.download` legt Root-Datei an; `SYMTEST`" |
| 3 | The browser writes the payload through that symlink with `HiBrowser.File.download` | CONFIRMED live (recorded) — the planted file is present at the recorded size/hash and is the library the loader later executes | `record:he40/root/ROOT-GUIDE.md:219` (target expression); `:231-232` (33,500 B, SHA-256); `record:he40/modding/07-evidence-unknowns.md:12` (file download creates a root file) |
| 4 | Planted payload is 33,500 bytes with SHA-256 `37b13f…5b0a` | CONFIRMED live (recorded), byte identity also CONFIRMED host/build | `record:he40/root/ROOT-GUIDE.md:231-232`; `record:he40/modding/07-evidence-unknowns.md:19` — "`build_tvi_payload.py` → exakt `37b13f…` … **CONFIRMED** (Host)" |
| 5 | `libtvsysinfo.so` is a direct `NEEDED`; `LD_LIBRARY_PATH` index 17 is `/3rd_rw/loglevel/lib`, the first writable slot | CONFIRMED live (recorded) | `record:he40/root/ROOT-GUIDE.md:36`; `record:he40/dead-ends.md:19` — "nur `libtvsysinfo.so` ist ein direktes `NEEDED` und an Index 17 frei" |
| 6 | The shadow library is loaded on the **next browser start** | CONFIRMED live (recorded), with a wording correction | `record:he40/root/ROOT-GUIDE.md:36` — "wird beim nächsten Browser-Start geladen"; browser is not in the boot set: `record:he40/modding/02-boot.md:177` |
| 7 | Appended `DT_INIT` payload: self-unlink, writes `/3rd_rw/root_proof.txt`, forks `root_loop.sh`, calls the original init | Effect CONFIRMED live (recorded); exact ELF edit UNVERIFIED here | `record:he40/root/ROOT-GUIDE.md:37-41`; `:37` describes appended code and extended RX `p_filesz/memsz` |
| 8 | `DT_INIT` value `0x81c4` | documented only | `record:he40/README.md:156` — a documentation claim; no byte was inspected for this page |
| 9 | Root loop runs as root and reports `uid=0`, `CapEff=0000003fffffffff` | CONFIRMED live (recorded) | `record:he40/root/ROOT-GUIDE.md:270-284` |
| 10 | Static Dropbear 2022.83 listens on `0.0.0.0:22`, key-only, public-key login for root works | CONFIRMED live (recorded) | `record:he40/root/ROOT-GUIDE.md:328`, `:347`, `:531-532`; `record:he40/modding/07-evidence-unknowns.md:15` |
| 11 | `/etc/passwd` bind mount gives root home `/3rd_rw/sshd/home` and shell `/bin/sh` | CONFIRMED live (recorded) | `record:he40/modding/07-evidence-unknowns.md:17`; `record:he40/root/ROOT-GUIDE.md:324` |
| 12 | PTY works via devpts on `/dev/shm/pts` bind-mounted over `/dev/pts` | CONFIRMED live (recorded) | `record:he40/root/ROOT-GUIDE.md:352-354`, `:533`; `record:he40/modding/07-evidence-unknowns.md:16` |
| 13 | `HamService` wrapper installed: starts root loop + SSH, then `exec`s the real service | CONFIRMED live (recorded) — installation only | `record:he40/root/ROOT-GUIDE.md:409-415`; `record:he40/modding/07-evidence-unknowns.md:18` — "**CONFIRMED installiert**; Reboot-Test im Root-Guide" |
| 14 | Root loop + SSH survive a reboot | **owner-verified** (2026-11-04) | Owner statement: daily use, several reboots, root Dropbear still live; alvidaa commit `f9dc68d`. The archived record has install + test procedure, not a post-reboot log (`record:he40/root/ROOT-GUIDE.md:6`, `:535`) |
| 15 | SFTP works on the device | UNVERIFIED | `record:he40/root/ROOT-GUIDE.md:534` — "**TV-Test nach Install**"; `record:he40/modding/07-evidence-unknowns.md:102` — result "steht in … log"; `record:he40/modding/docs/root-guide.md:239` — "built and staged; verify on your own device" |
| 16 | SFTP host/build: static OpenSSH 9.9p1 sftp-server, patched Dropbear, installer tests 2222 and then swaps 22 | CONFIRMED host/build + documented procedure | `record:he40/root/ROOT-GUIDE.md:369-371`, `:381-384`; `record:he40/modding/06-toolchain-deploy.md:159-190` |
| 17 | UI / launcher / app-tile / bloat recipes work | UNVERIFIED | `record:he40/modding/07-evidence-unknowns.md:79-81`, `:86`; `record:he40/modding/docs/root-guide.md:240` |
| 18 | 26 preset tiles were observed, including the lab `VidaaRecon` app | CONFIRMED live inventory, but **not a stock list** | `record:he40/modding/03-ui.md:155-186`; `record:he40/modding/05-bloat.md:8`, `:39` |
| 19 | Browser generation is Chromium 59.0.3071.115 | recorded; V8 version UNVERIFIED | `record:he40/dead-ends.md:13` vs `record:he40/modding/07-evidence-unknowns.md:113` disagree; see corrections |
| 20 | No flash, no `.pkg`, no UART, no case opening; ro rootfs untouched | design property of this chain | `record:he40/root/ROOT-GUIDE.md:3`; `:515`; `record:he40/modding/01-system-linux.md:39` |
| 21 | `id` and `uname` are available as used in the proof | DEAD END / contradicted | `record:he40/modding/01-system-linux.md:78`, `:86` list `id`/`uname` as missing applets; `record:he40/root/ROOT-GUIDE.md:271`, `:281` use them |

## What was actually captured vs. only documented

**Observed and recorded on the device:**

- `/3rd_rw/root_proof.txt` containing `ROOT_EXEC_TVI`.
- `uid=0(root) gid=0(root)`, `Uid: 0 0 0 0`, `Gid: 0 0 0 0`,
  `CapEff: 0000003fffffffff` from the root loop.
- Dropbear listening on `:0016` (`/proc/net/tcp`), `Pubkey auth succeeded for
  'root'` in `dropbear.log`, PTY session `pts/0`.
- Mount state: `/etc/passwd`, `/dev/shm/pts`, `/dev/pts` binds; `df -h`
  sizes; `/proc/{version,cmdline,cpuinfo,filesystems,mounts,partitions}`.
- Launcher/app inventory: `preset.txt`, `Appinfo.json`, `deletedPresetApp.txt`,
  `Category*.xml`, `res/`, `cache/`.
- Process facts: `hisenseUI`, `hisense_browser`, `app_man`, `dtv_svc`,
  `LauncherService`, `HamService`.

**Documented, not separately captured in this record set:**

- The exact ELF transformation and `DT_INIT=0x81c4` (no binary was inspected
  for this page).
- Byte-identity of the Dropbear binaries beyond the recorded sizes/hashes.
- Post-reboot survival (owner statement only).
- Any successful SFTP session.
- Every UI/launcher/bloat recipe.

## Artifacts

Sizes and hashes are recorded metadata, useful to compare against your own
build. **No binary and no key material is shipped in this repository**; all of
it must be recreated from your own device.

| Artifact | Size | SHA-256 (recorded) |
|---|---:|---|
| Original library (`artifacts/tvi_original.so`, from `/3rd_rw/tvsysinfo/lib/libtvsysinfo.so`) | 33,220 B | `36ddee4782cdcff7a0f1d94e8b3491ea6fe228d13bfef3ea137a98f142ff3b7c` |
| Built payload (`tools/pub/libtvsysinfo.so`) | 33,500 B | `37b13f91959acea9b3c3fd4d0e62bb2d4cb41f773add060bef68ac67657f5b0a` |
| Dropbear 2022.83 (static ARM) | 882,204 B | `976ec57e401765d5fc9c0a201d19c997c004dcf91a8d4bdb039bbb8419071eae` |
| Dropbearkey | 755,452 B | `3fbfa60891b3a9f3e971a24071ed4d14c93ee3e773dd6f4969646cc811b0dbbf` |
| Dropbear SFTP build | 882,204 B | `a21b0d3e53dd1d124105350319df45a2b44e7cef70dd29b418644b11fdcfed57` |
| OpenSSH 9.9p1 `sftp-server` (static ARM) | 635,680 B | `d0f7700e84e582aef3948c29e4317fb0119e13393374a7455922ffa8d01202f3` |
| Dropbear source tarball | — | `bc5a121ffbc94b5171ad5ebe01be42746d50aa797c9549a4639894a16749443b` |
| OpenSSH source tarball | — | `b343fbcdbff87f15b1986e6e15d6d4fc9a7d36066be6b7fb507087ba8f966c02` |

Source of the values: `record:he40/root/ROOT-GUIDE.md:491-500`;
`record:he40/modding/06-toolchain-deploy.md:70-75`. Hashes identify a build; they are not a
substitute for the binary and they do not prove that your build matches.

Also recorded: the Dropbear build disables password auth at compile time
(`DROPBEAR_SVR_PASSWORD_AUTH 0`, `DROPBEAR_SVR_PUBKEY_AUTH 1`,
`DROPBEAR_CLIENT 0`) — `record:he40/modding/06-toolchain-deploy.md:98-100`.

## Sanitization and provenance

Removed from this public page, and why:

| Removed | Why |
|---|---|
| SSH host-key fingerprint (the same value appeared in the guide, README and toolchain doc) | A device-specific fingerprint; it identifies the author's TV and is not needed to reproduce the path |
| Public-key blob, key comment and key fingerprint | Key material is not documentation; users supply their own key |
| Any `authorized_keys` content | Only the path and its permissions are relevant |
| Concrete IP addresses used in the examples | Replaced with `<tv-ip>` / `<host-ip>`; the record already used TEST-NET ranges, but public guides should not depend on them |
| Absolute build-host paths and the old run/provenance directory | Environment-specific; replaced with repository-relative paths |
| Presence claims for vendor binaries in the record tree | The public tree ships no vendor library and no Dropbear binary; those paths are drop points |

Remaining, deliberately: platform paths (`/3rd_rw/...`, `/etc/passwd`), sizes,
hashes, script names, and the commands needed to reproduce the chain.

Provenance note: the source record is a private research repository. This page
is an independent English restatement; it does not copy the record's prose or
any code from the TV firmware. Where the record contradicted itself, the
public text follows the narrower reading and says so.

## Corrections and contradictions

These are preserved, not silently resolved. The wording in the public guide is
given for each.

**C1 — Boot persistence.** The 2026-10-26 record says the wrapper is installed
and the reboot test is *described*, not passed: `record:he40/root/ROOT-GUIDE.md:6`
("Boot-Persistenz installiert (Reboot-Test offen)"), `:535` ("eingerichtet;
Reboot-Test in dieser Doku beschrieben"), `record:he40/README.md:11`,
`record:he40/docs/HARDWARE-NOTES.md:28` ("Confirmed installed; reboot test documented").
`record:he40/docs/PRIOR-ART.md:95-96` says the chain "provided persistence", which is
stronger than any recorded result. The owner reports survival across several
reboots on 2026-11-04.
*Public wording:* "installed in the 2026-10-26 record; owner-verified across
reboots on 2026-11-04". Never "confirmed across reboots by the record".

**C2 — "The browser loads the shadow library at boot".**
`record:he40/root/ROOT-GUIDE.md:14` and `:253` say the load happens "beim Boot". The same
bundle documents that the web browser is **not** started at boot
(`record:he40/modding/02-boot.md:177`; `record:he40/modding/03-ui.md:12`).
*Public wording:* the payload executes when `hisense_browser` next starts;
after a reboot, open the TV browser once. Boot persistence of the root loop and
SSH comes from the `HamService` wrapper and is independent of the browser.

**C3 — `id` / `uname`.** `record:he40/modding/01-system-linux.md:78` says the applets are
missing as `/bin/<name>`; `:86` lists them as "not built". Yet the proof
commands use `id` (`record:he40/root/ROOT-GUIDE.md:271`, `:281`) and `uname`
(`record:he40/modding/06-toolchain-deploy.md:265`).
*Public wording:* the bare applet is not linked; use `/bin/busybox id`, and if
that is unavailable, read `/proc/self/status`. The contradiction is not
resolved.

**C4 — V8 version.** `record:he40/dead-ends.md:13` gives "Chromium 59.0.3071.115 / V8
203.0.113.38"; `record:he40/modding/07-evidence-unknowns.md:113` gives "V8 5.9/Chromium
59". The first "version" has the shape of a TEST-NET address and looks like a
transcription error; neither is verified by a binary inspection.
*Public wording:* Chromium 59.0.3071.115 is the recorded browser generation; no
V8 version is asserted. The V8 route was not used.

**C5 — "Self-contained" vs "no binaries shipped".**
`record:he40/root/ROOT-GUIDE.md:8` calls the folder self-contained, including payload,
original library and Dropbear binaries. `record:he40/README.md:3-6` says the public tree
does not ship the vendor binaries or key material.
*Public wording:* paths and build scripts are published; every binary and key
must be recreated from your own device.

**C6 — SFTP wording.** The guide shows `sftp root@…` as the next step
(`record:he40/root/ROOT-GUIDE.md:24-27`, `:387-389`), while its own status table says the
TV test is pending (`:534`).
*Public wording:* SFTP is optional; the installer tests port 2222 and swaps to
22 only on success; a device-side success is not recorded.

**C7 — "26 preset tiles".** The list is a live snapshot of the reference
device and includes the lab `VidaaRecon` tile
(`record:he40/modding/03-ui.md:186`; `record:he40/modding/05-bloat.md:8`, `:39`).
*Public wording:* 26 tiles were observed on the reference device, including the
lab app; this is not a stock retail list.

**Attribution.** The generated tables previously credited an older handle for
these two models; the inventory has been corrected to
[@oOHiyoriOo](https://github.com/oOHiyoriOo). This page uses that handle.

## Unknowns

- Exact SoC designation (MT5863 vs the MT53xx family), exact core count,
  secure boot and signature enforcement.
- Full kernel config; how `dm-3` is constructed; the contents and semantics of
  `spdata`, `perm`, `facset`, `hiscfg`, `eeprom`, `channel`, `pq`, `adsp`,
  `logo`.
- Real U-Boot flow and environment (bad CRC / default NFS), A/B slot selection,
  recovery.
- `checker.sh`, `ota_upgrade_strategy.sh`, `file_upgrading`, `bspatch`, OTA.
- `dtv_svc`, `app_man`, `:am` internals; `coexist_set`, `backgm`, `keymap`.
- `LauncherService` data source and update path (store/Foxxum/FCGI);
  `preset`/`Category` regeneration.
- Which UI template/skin is active; whether `VIDAAU2Launcher` is ever active.
- `Hisense_StartApp` / `TVAPI` / `guijs` signatures.
- Effects of disabling `ms_service`, `swrc`, `runlog`, `Seriallog`,
  `HamService`, `securetime`, `browser_base`, `app_man`, `dtv_svc`.
- DRM (PlayReady/Widevine), Netflix, Cobalt, Amazon, `securetime`.
- Device-side SFTP result.
- Whether a custom `UI/index.html` needs the `TVAPI`/`model` globals.
- Whether store/network updates overwrite `preset`/`Category`/`serviceUpdate`.
- Post-reboot survival as a *recorded* observation (only the owner report
  exists).

## Dead ends (do not repeat)

From `dead-ends.md` and `record:he40/modding/07-evidence-unknowns.md:108-118`:

- Factory "Builtin Video" suffix injection; Factory "Write Keys".
- AM `startApp` `args`/`exec`/`run` injection; shell-injection attempts were
  negative.
- FAT32 USB and factory USB copy as a root trigger.
- `checker.sh`, `file_upgrading`, `.pkg`, `bspatch` as root triggers.
- The V8/FileReader route and the EME/Widevine trigger.
- `liblogLevel` shadowing (the file exists at index 17, so the symlink trick
  fails); `libIQQILib`, `libota`, `hisensefileutils` variants; the
  `/3rd_rw/ms-screen/lib` symlink variant.
- `File.write` for binary data (`EINVAL`); `HiBrowser.loadLibrary` /
  `jsplugins` tricks.
- Whole-disk ext4 (superfloppy) and FAT32 sticks.
- Dropbear `-s` (the flag does not exist in this build); devpts mounted
  directly on `/dev/pts` (read-only target).
- Old `launcher` / `VIDAAU2Launcher` as the active UI entry.
- The `pwn` symlink as the final path (it was only the bypass proof; the final
  path uses `tvi`).
- `SFTPSERVER_PATH=/usr/libexec/sftp-server` (the read-only root cannot hold
  it); superseded by the patched path, which is still only staged, not
  device-verified.
