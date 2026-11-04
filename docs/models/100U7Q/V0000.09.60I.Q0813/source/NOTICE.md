# Third-party components

## Dropbear SSH 2022.83

`bin/dropbear-root` and `bin/dropbearkey` are builds of
[Dropbear SSH](https://matt.ucc.asn.au/dropbear/dropbear.html) 2022.83,
licensed under the **GNU General Public License v2** (see the upstream
`LICENSE` in the source tarball).

- Source: `https://matt.ucc.asn.au/dropbear/releases/dropbear-2022.83.tar.bz2`
- sha256: `bc5a121ffbc94b5171ad5ebe01be42746d50aa797c9549a4639894a16749443b`
- Built statically for 32-bit ARM (armv7, EABI5, musl) with:
  `--disable-zlib --disable-syslog --disable-lastlog --disable-utmp
  --disable-wtmp --disable-utmpx --disable-wtmpx`, `CFLAGS="-Os -static"`,
  `LDFLAGS="-static -no-pie"`.

Local modifications, all documented in `docs/HOW-IT-WORKS.md` §4:

1. `common-session.c` `fill_passwd()`: fallback passwd entry for unknown
   users (uid 314) and a `pw_dir`/`pw_shell` override for uid 0.
2. One 11-byte literal in the stripped binary: `/etc/shells` → `/APPS/shell`
   (file offset 15162).

Because the binaries are GPLv2, redistribution must include or offer the
corresponding source. The upstream tarball plus the two patches above are the
complete corresponding source for these builds; the patch text is reproducible
from `docs/HOW-IT-WORKS.md` §4.

`bin/dropbearkey` is byte-identical to the unpatched build.

## Everything else

The scripts, pages and packaging in this repository are original work and are
released under the MIT license (see `LICENSE`). The IPK format used here is
the standard `ar` + `control.tar.gz` + `data.tar.gz` layout.
