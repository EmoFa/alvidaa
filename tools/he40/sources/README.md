# Offline build sources

The HE40 build scripts expect the upstream source tarballs here:

- `dropbear-2022.83.tar.bz2` — Dropbear SSH 2022.83 (GPLv2)
- `openssh-9.9p1.tar.gz` — OpenSSH 9.9p1 portable (for the optional sftp-server)

Download them from the upstream release pages (or set `DROPBEAR_SRC` / `OPENSSH_SRC`). No third-party source archive is shipped in this repository.

The scripts verify the SHA-256 before building.
