# Hardware notes

Two device families are referenced in this project. The notes are sanitized:
no serial numbers, MAC addresses, device IDs, ESNs, LAN addresses, or account
names. A model code and a firmware version are public metadata; they do not
identify a specific household.

## 1. Hisense HE40E5600FFWTS — reference device

This is the device on which the documented root chain was validated live.

| Property | Value | Status |
|---|---|---|
| Retail model | HE40E5600FFWTS | Confirmed |
| Firmware | `V0100.01.00A.N0410` | Confirmed |
| SoC class | MediaTek MT53xx / MT5863 class (`mt53xx-emmc`, `mt5863_sa_768_linux`) | Confirmed |
| CPU | ARMv7, Cortex-A53, NEON/VFPv4 | Confirmed |
| Kernel | Linux 3.18.25 | Confirmed |
| C library | glibc 2.18 | Confirmed |
| Userland | BusyBox 1.18.5, SysV init (`inittab`/`rcS`/`rc.local`), no systemd | Confirmed |
| Package manager | None (no `apt`, `dpkg`, `opkg`, `ipkg`, `rpm`, `apk`, `yum`, `pacman`) | Confirmed |
| Root filesystem | squashfs read-only `/` and `/3rd` | Confirmed |
| Writable storage | ext4 `/3rd_rw`, `/data`, `/perm`; `/spdata` read-only | Confirmed |
| Overlay filesystem | None | Confirmed |
| UI process | `hisenseUI` (TV UI, GLES), DevTools 9223 | Confirmed |
| Browser process | `hisense_browser` (separate from the UI), DevTools 9224 | Confirmed |
| Root chain | Browser UID 0; USB-ext4 dangling-symlink `IsSubDentry` bypass; `libtvsysinfo.so` LD-shadow with `DT_INIT` | Confirmed live |
| Persistence | Root loop, key-only Dropbear SSH, `HamService` boot wrapper | Confirmed installed; reboot test documented |

Notes:

- The UI and the browser are separate processes with separate start scripts,
  JS plugins and debug ports. Do not treat "the browser" and "the TV UI" as the
  same target.
- The device has no package manager. Deploy static binaries or shell scripts to
  a writable partition.
- `/3rd_rw` and `/dev/shm` are platform paths, not user data. They are kept in
  the docs because they are part of the device family.

### What was confirmed live

- `hisense_browser` runs as UID/GID 0 with the full capability set, a single
  process, and no seccomp/`NoNewPrivs` restriction.
- A dangling symlink on an ext4 USB filesystem bypasses the path whitelist; a
  browser file download follows it and creates a root-owned file.
- A shadowed `libtvsysinfo.so` at the first writable library path is loaded on
  browser restart; an appended `DT_INIT` runs as root.
- The root loop, key-only SSH, PTY workaround and boot wrapper were exercised
  on this device.

These are device-specific results. Do not assume they transfer to another
model or firmware build.

## 2. Hisense 100U7Q / 100U70QEVS — 2025 target, validated via its own path

This is a newer VIDAA device. The internal model code is `100U70QEVS`
(SerialType `100U7QE`); the retail name is `100U7Q`. The HE40 root chain above
has **not** been validated on this device and does not apply. The model does
have a separately verified root path — see [`../../100u7q/`](../../100u7q/).

| Property | Value | Status |
|---|---|---|
| Retail model | 100U7Q (100-inch, Mini-LED, 2025, EU market) | Confirmed from device notes |
| Internal model code | `100U70QEVS`; SerialType `100U7QE` | Confirmed live |
| OS | VIDAA (not Android TV / Google TV) | Confirmed |
| Firmware | `V0000.09.60I.Q0813` (build 2026-07-31, RC `ERF6G66V1.03`) | Confirmed from device info |
| SoC | MediaTek Pentonic 800, MT9655 | Confirmed static |
| CPU | 32-bit ARM userland (ELF `EM_ARM`), 4 cores | Confirmed live |
| DevTools 9222/9223/9224 | Not reachable | Confirmed from device notes |
| ADB 5555 | Not open | Confirmed from device notes |
| AirPlay | Port 7000, AirTunes/rtspd | Confirmed from device notes |
| Vendor remote service | Port 36669, mutual TLS, client certificate required | Confirmed from device notes |
| Root chain | Package-manager `postinst` via the superwatch socket (`../../100u7q/`); none of the HE40 mechanisms apply | **Confirmed live** |
| Public firmware image | Not obtained from a free official channel | **Unknown / blocked** |

Notes:

- The 2025 build closes the network DevTools channel that the reference device
  used. A different entry point is required.
- The userland is 32-bit ARM (ELF `EM_ARM`), so aarch64 payloads do not run
  here while ARMv7 binaries can. Binaries still have to be built for this
  device's libc and paths.
- The device exposes an AirPlay service and a mutual-TLS remote service. This
  project does not implement a login flow or a client-certificate extraction
  path.
- The public firmware catalog found no free official image for this model at
  the time of the prior runs. OTA checks returned a "no match upgrade rule"
  result, and the tested public model pages returned empty bodies.

## 3. Shared platform notes

- VIDAA devices use a read-only squashfs system and separate writable
  partitions. Modifications generally go to a writable partition plus a bind
  mount, not to the read-only root.
- The browser and UI are separate. A modification that works in one may not
  affect the other.
- Firmware packages are vendor-specific and may use a proprietary integrity
  format. Do not assume a package is signed, and do not assume a checksum can be
  recomputed without the vendor algorithm.
- A firmware version string is not a security guarantee. It identifies a build,
  not a vulnerability status.

## 4. Unknowns

- Exact 100U7Q internal type variants beyond `100U70QEVS` / `100U7QE`.
- ~~Whether the browser still runs as UID 0 on the 2025 build.~~ Resolved: it
  runs as uid 314 with only `CAP_SYS_NICE`, SELinux enforcing.
- ~~Whether the USB-ext4 symlink bypass and the library-shadow index still
  exist.~~ Not applicable to the verified path: `/` is erofs + dm-verity
  read-only and every writable partition is mounted `nosuid`; 100U7Q is rooted
  through the package manager instead (`../../100u7q/`).
- Whether a public, free, official firmware image for this model will be
  published.
- The package integrity algorithm and the mapping from package id to model
  variants.
