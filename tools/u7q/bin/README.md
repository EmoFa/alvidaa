# Dropbear binaries go here

`scripts/install.sh` and `scripts/make_installer.py` expect **your own** static ARM32 dropbear build here:

- `bin/dropbear-root`
- `bin/dropbearkey`

Build them per `docs/models/100U7Q/V0000.09.60I.Q0813/README.md` (Build section). The upstream is Dropbear SSH 2022.83, GPLv2; the build patches are documented in that guide and in `tools/fw`.

No prebuilt binaries are shipped in this repository.
