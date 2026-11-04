# he40/ — HE40 root tooling

Device-side helpers for the HE40E5600FFWTS chain on firmware
`V0100.01.00A.N0410` (MT53xx / MT5863 class, ARMv7, Linux 3.18, glibc 2.18,
BusyBox 1.18.5). The chain uses the TV browser's file API, a dangling symlink
on an ext4 USB stick, a shadow `libtvsysinfo.so`, a root command loop, and a
key-only Dropbear.

This is not a generic VIDAA toolkit. The paths, library index, boot script, and
partition layout are specific to this model and firmware. Read the model guide
first:

[`../../docs/models/HE40E5600FFWTS/V0100.01.00A.N0410/README.md`](../../docs/models/HE40E5600FFWTS/V0100.01.00A.N0410/README.md)

## Layout

| Path | Contents |
|---|---|
| [`root/scripts/host/`](root/scripts/host/) | Host-side build, upload, and deploy helpers: payload builder, Dropbear/OpenSSH builds, SFTP installer, USB preparation, recon launcher, and browser-console JavaScript. |
| [`root/scripts/tv/`](root/scripts/tv/) | On-TV scripts: `deploy_sshd.sh`, `start_sshd.sh`, `root_loop.sh`, `verify.sh`, `rollback.sh`, and the staged SFTP helpers. |
| [`root/tools/pub/`](root/tools/pub/) | Placeholder for **your** built binaries and public key. Ships only a README. |
| [`root/artifacts/`](root/artifacts/) | Placeholder for **your** original `tvi_original.so`. Ships only a README. |
| [`recon/`](recon/) | `recon.html`, the loopback-by-default capture server, an example command file, and a `pub/` payload directory. |
| [`templates/`](templates/) | UI and launcher examples: early boot hook, app tile JSON, hidden-tile list, custom UI page, start script. Comments are in German. |
| [`sources/`](sources/) | Placeholder for the upstream source tarballs. Ships only a README. |

`root/tools/pub/` and `root/artifacts/` are intentionally empty of binaries.
Nothing in this subtree contains a Dropbear build, an SFTP server, a vendor
library, or a key.

## What you supply

| Item | Put it here | Source |
|---|---|---|
| Original `libtvsysinfo.so` from your own TV | `root/artifacts/tvi_original.so` | Copy it from the TV's `/3rd_rw/tvsysinfo/lib/libtvsysinfo.so` before modifying anything. |
| Dropbear 2022.83 source | `sources/dropbear-2022.83.tar.bz2`, or `DROPBEAR_SRC` | Upstream release; `build_dropbear.sh` verifies the tarball hash before building. |
| OpenSSH 9.9p1 source (optional SFTP) | `sources/openssh-9.9p1.tar.gz`, or `OPENSSH_SRC` | Upstream portable release; `build_sftp_server.sh` verifies the tarball hash. |
| Your own public key | `root/tools/pub/authorized_keys` | Your `.pub` file. Never a private key. |
| Built payload and binaries | `root/tools/pub/` | `build_payload.sh`, `build_dropbear.sh`, `build_sftp_server.sh`, `patch_dropbear_sftp.py`. |

### Build outputs

| Script | Output |
|---|---|
| [`root/scripts/host/build_payload.sh`](root/scripts/host/build_payload.sh) | `root/tools/pub/libtvsysinfo.so` from `root/artifacts/tvi_original.so`; prints the expected size and hash for comparison. |
| [`root/scripts/host/build_dropbear.sh`](root/scripts/host/build_dropbear.sh) | `root/tools/pub/dropbear`, `dropbearkey`, and the SFTP-patched `dropbear-sftp`. Key-only, no password auth, no client. |
| [`root/scripts/host/build_sftp_server.sh`](root/scripts/host/build_sftp_server.sh) | `root/tools/pub/sftp-server`, a static OpenSSH `sftp-server` for the TV's glibc 2.18 userland. |
| [`root/scripts/host/patch_dropbear_sftp.py`](root/scripts/host/patch_dropbear_sftp.py) | `dropbear-sftp` with `SFTPSERVER_PATH` changed to the writable TV path. |

## Root layout contract

The scripts compute their paths relative to themselves. If you move them, the
build breaks.

```text
tools/he40/
  root/
    scripts/
      host/        # host-side build/upload helpers
      tv/          # copied to the TV and run there
    tools/
      pub/         # your built binaries + authorized_keys
    artifacts/     # your tvi_original.so
  sources/         # upstream tarballs
  recon/           # browser page + capture server
  templates/       # UI/launcher examples
```

From `root/scripts/host`, the build scripts set `ROOT` to the directory two
levels up (`root/`) and `TOP` to its parent (`he40/`). They expect
`TOP/sources`, `TOP/build`, `ROOT/tools/pub`, and `ROOT/artifacts`. The on-TV
scripts expect `ROOT/scripts/tv` and the fixed `/3rd_rw/...` paths on the TV.
Keep the tree shape or adjust the scripts deliberately.

## Workflow

1. **Build the payload** from your own original library. The payload appends
   code to the original ELF, extends the executable `PT_LOAD`, and points
   `DT_INIT` at it. The script prints the expected output properties for
   comparison; verify them yourself.
2. **Prepare the USB stick.** `prepare_usb.sh` creates an MBR plus ext4
   partition and the dangling `tvi` symlink. This step is destructive.
3. **Serve the recon page.** `recon/server.py` binds `127.0.0.1` by default.
   `start_http.sh` opts into `0.0.0.0` because the TV must reach it.
4. **Plant the payload** from the TV browser console with
   `plant_payload.js`, then reboot. The browser loads the shadow library when it
   next starts, not necessarily at boot.
5. **Use the root loop.** `root_loop.sh` polls `root_cmd.sh`, runs it, and
   writes `root_out.txt`. Upload the deploy files with
   `upload_to_appdata.js`, then run `deploy_sshd.sh` through the loop.
6. **Optional SFTP.** `install_sftp.sh` uploads the pair, starts a test
   Dropbear on 2222, tests it, and only then swaps the binary on 22.

No step writes a read-only partition or flashes firmware. The persistent
changes live under `/3rd_rw` and in runtime bind mounts; `rollback.sh` removes
them.

## Hazards

| Hazard | Detail |
|---|---|
| **Destructive USB preparation** | [`prepare_usb.sh`](root/scripts/host/prepare_usb.sh) runs `wipefs`, `parted`, and `mkfs.ext4` on the block device you pass. It asks for `YES`, then destroys the device. Use a stick you can lose. |
| **Unauthenticated command channel** | [`recon/server.py`](recon/server.py) has no authentication by design. Anyone who can reach the port can feed JavaScript to a browser that runs as root on the TV. The default bind is loopback; the wrapper binds the LAN and prints a warning. Never expose it to the internet. |
| **Root loop** | [`root_loop.sh`](root/scripts/tv/root_loop.sh) executes `/3rd_rw/appdata/root_cmd.sh` as root and writes its output. It is root-equivalent. |
| **Root SSH** | [`deploy_sshd.sh`](root/scripts/tv/deploy_sshd.sh) installs a key-only Dropbear on `0.0.0.0:22` and bind-mounts a modified `/etc/passwd`. Root login is root-equivalent. Key-only means no password fallback. |
| **UI templates** | [`templates/`](templates/) contains bind-mount and UI replacement examples. A bad UI file can leave a black screen. Keep the root loop or SSH open as a rescue path, and back up every file you replace. |
| **Optional SFTP** | The installer stages and tests SFTP on 2222 before touching 22. The archived record does not include a successful device-side SFTP log; verify it on your own device. |

## What this tree does not prove

| Area | Status |
|---|---|
| Root acquisition (browser, USB bypass, shadow library, root loop, Dropbear, PTY) | Recorded as live-confirmed on the reference device. This tree contains no log or capture from that run. |
| Boot persistence | The `HamService` wrapper is installed by `deploy_sshd.sh`. The archived record says the reboot test was still open; the owner reports daily use and a live root Dropbear. Treat it as owner-verified, not as a fresh test in this tree. |
| SFTP | Built and staged by the scripts; the device-side result is not recorded. |
| UI, launcher, and bloat recipes | Documented from live/static files, marked unverified in the source record. |
| Exact SoC designation, core count, secure-boot state | Unknown. Do not infer a precise part number from the family label. |

The model guide is the canonical place for the evidence labels and open
questions. Do not upgrade a label because a script exists.

## Related

- OTA signing primitive and format helpers: [`../fw/ota/sign/README.md`](../fw/ota/sign/README.md)
- Secret/PII scanner used before publishing this tree: [`../sanitize/README.md`](../sanitize/README.md)
- Tree overview and directory contract: [`../README.md`](../README.md)
- Disclosure and publication policy: [`../../SECURITY.md`](../../SECURITY.md)
