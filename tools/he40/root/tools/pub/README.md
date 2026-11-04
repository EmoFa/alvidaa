# Put your own built binaries here

This directory intentionally ships **no binaries**. The HE40 scripts expect these files at runtime:

- `dropbear`, `dropbearkey` — build with `../../scripts/host/build_dropbear.sh` (upstream source tarball required) or use your own static ARM build.
- `dropbear-sftp`, `sftp-server` — optional SFTP pair; build with `../../scripts/host/build_sftp_server.sh` and `patch_dropbear_sftp.py`.
- `libtvsysinfo.so` — your own payload, built by `../../scripts/host/build_payload.sh` from the TV's original `artifacts/tvi_original.so`.
- `authorized_keys` — your own **public** key only. Never commit a private key.

See `../../../README.md` and `../../../../docs/models/HE40E5600FFWTS/V0100.01.00A.N0410/README.md`.
