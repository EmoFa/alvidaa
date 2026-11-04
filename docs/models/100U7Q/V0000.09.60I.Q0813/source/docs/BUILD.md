# Rebuilding the dropbear binaries

`bin/dropbear-root` and `bin/dropbearkey` are static 32-bit ARM builds of
Dropbear SSH 2022.83. This document is the complete recipe; together with the
patches below it is the corresponding source required by GPLv2 (see
`NOTICE.md`).

## Source

```
https://matt.ucc.asn.au/dropbear/releases/dropbear-2022.83.tar.bz2
sha256 bc5a121ffbc94b5171ad5ebe01be42746d50aa797c9549a4639894a16749443b
```

Upstream release tarballs are signed; verify the detached `.asc` against
release key `F7347EF2EE2E07A267628CA944931494F29C6773` before building.

## Toolchain

Any toolchain that produces **static armv7 EABI5** works. The build used for
the shipped binaries was zig 0.14.1's bundled musl cross compiler
(`arm-linux-musleabihf`, `-mcpu=cortex_a7`). A plain
`arm-linux-gnueabihf-gcc` with `-static` also works; the target only needs the
result to be statically linked, because the TV's `/` is read-only.

## Patch 1 — `common-session.c`, `fill_passwd()`

Two changes, both inside the function that resolves the login user:

```c
/* after: pw = getpwnam(username); */

/* (a) unknown user -> fixed identity for the app-context account */
if (!pw) {
    static struct passwd fallback;
    static char name[]  = "re";
    static char pass[]  = "x";
    static char dir[]   = "/APPS/.re_sshd/home";
    static char shell[] = "/bin/bash";
    fallback.pw_name = name;  fallback.pw_passwd = pass;
    fallback.pw_uid  = 314;   fallback.pw_gid    = 314;
    fallback.pw_dir  = dir;   fallback.pw_shell  = shell;
    pw = &fallback;
}

/* (b) uid 0 -> writable home and a real shell */
if (pw->pw_uid == 0) {
    pw->pw_dir   = "/APPS/.re_sshd/root_home";
    pw->pw_shell = "/bin/bash";
}
```

Why: `/etc/passwd` has `root:x:0:0:root:/basic:/etc/rootlogin.sh`, and
`/basic` is on a read-only dm-verity filesystem. Without (b) there is nowhere
to put `authorized_keys` and the login shell is the console login script.

## Patch 2 — binary literal (post-build)

`/etc/shells` does not exist on the device, so musl's `getusershell()` returns
NULL and dropbear rejects every login. The 11-byte literal is replaced in the
stripped binary, keeping the file size identical:

```python
raw = bytearray(open('dropbear','rb').read())
i = raw.find(b'/etc/shells')          # offset 15162 in this build
assert raw.count(b'/etc/shells') == 1
raw[i:i+11] = b'/APPS/shell'          # same length
open('dropbear','wb').write(raw)
```

At runtime `/APPS/shell` must exist and contain `/bin/bash` (the installer's
`postinst` writes it).

## Configure and build

```sh
./configure --host=arm-linux-musleabihf \
  --disable-zlib --disable-syslog --disable-lastlog \
  --disable-utmp --disable-wtmp --disable-utmpx --disable-wtmpx \
  CFLAGS="-Os -static" LDFLAGS="-static -no-pie"
make -j"$(nproc)"
strip dropbear dropbearkey
python3 apply_patch2.py        # the 11-byte replacement above
```

`-no-pie` matters: dropbear's build adds `-pie`, which otherwise yields a
static-PIE binary. The device runs it either way, but plain static is easier
to verify.

## Verification

```sh
file dropbear dropbearkey
#   ELF 32-bit LSB executable, ARM, EABI5 version 1 (SYSV),
#   statically linked, stripped

readelf -h dropbear | grep Machine      # ARM
ldd dropbear                            # not a dynamic executable
readelf -d dropbear                     # no dynamic section
```

If `qemu-arm-static` is available:

```sh
qemu-arm-static ./dropbear -V           # Dropbear v2022.83
```

## Build artefacts used here

| file | bytes | sha256 |
|---|---:|---|
| `bin/dropbear-root` (patched, offset 15162) | 478840 | `536b5563d8fa357bfb461b2e3559caa085c57b33c73438e06a7fb117a5a97f4d` |
| `bin/dropbearkey` (unpatched) | 347064 | `738949933f67b8825423cef4a3db4fb759ee3a3206a521d4256153bdc8b6d33c` |
