# Static aarch64 Dropbear 2026.94 for the Novatek lane (50A6Q)

Build recipe for the key-only root SSH server used by the
[50A6Q guide](../../../docs/models/50A6Q/V0000.09.61B.Q0721/README.md).
The TV userland is armhf (ELF32) but the kernel is aarch64, so aarch64
static-PIE binaries run natively.

## Build

```sh
# toolchain: prebuilt musl cross from musl.cc, no sudo needed
PATH="$HOME/aarch64-linux-musl-cross/bin:$PATH"
git clone --branch DROPBEAR_2026.94 https://github.com/mkj/dropbear
cd dropbear

# TV build options (see localoptions.h in this directory)
cat > localoptions.h <<'EOF'
#define DROPBEAR_SVR_DROP_PRIVS 1
#define DROPBEAR_SVR_SUBSYSTEMS 0
#define DROPBEAR_CLIENT_ANY_PORT_FORWARDING 0
#define DROPBEAR_SVR_MULTIUSER 1
EOF

patch -p1 < dropbear-tv.patch   # three source patches, see below
./configure --host=aarch64-linux-musl --disable-zlib
make dropbear dropbearkey -j4   # both static-PIE, no libc dependency
```

## The three source patches (dropbear-tv.patch)

Same five-lock gauntlet as the MTK lane; locks 3-5 are patched at source
because they cannot be satisfied from configuration on these TVs:

1. `svr-auth.c` — the `/etc/shells` check in `checkusername()` is bypassed:
   root's shell is the factory USB-gate script `/etc/rootlogin.sh`, which is
   not (and must not be) listed in `/etc/shells`. Without this every login
   dies with `User 'root' has invalid shell, rejected`.
2. `common-session.c` — `get_user_shell()` returns `/bin/sh` directly, so the
   session never execs the factory gate script.
3. `svr-authpubkey.c` — `checkpubkeyperms()` returns success: the vendor makes
   `/var/local` world-writable on purpose (apps write there), which trips the
   perms check for any keys directory under it.

## Why MULTIUSER=1 is mandatory

With `DROPBEAR_SVR_MULTIUSER 0` (a tempting "embedded" choice), every
connection child dies with `Early exit: String too long` on this firmware —
proven by rebuilding with `MULTIUSER=1`, after which the identical client
completes key exchange immediately. Ship MULTIUSER=1 and let the real
`/etc/passwd` (root is a normal entry) do the lookup.

## Hostkey format trap

The hostkey file passed via `-r` must be **dropbear-native binary format**
(`dropbearkey -t ed25519 -f key`). An ssh-keygen OpenSSH-armor PEM makes
dropbear exit at startup with `Early exit: String too long` — `buf_getstring`
reads the first four bytes (`----`) as a 4-byte binary length. Generate the
key with the `dropbearkey` built above (it runs fine on any machine), then
deliver the file to the TV.

## Deliver and start

The [50A6Q guide](../../../docs/models/50A6Q/V0000.09.61B.Q0721/README.md)
describes the delivery (`fetchFile` writes anywhere phoenix can write) and the
wrapper at `/var/local/dropbear` which chmods the binary, installs keys into
`/var/local/roothome`, and starts the server with `-E` so every connection is
logged to `/var/local/.a6q_root/db.log` (the `-E` flag exists in the aarch64
build; note a fresh native configure may differ).

## Verification notes

- `strings` on the patched binary must NOT contain `has invalid shell` or
  `must be owned by user` — both are dead-code-eliminated when the patches
  are actually compiled in; if you can still find them, the patch did not
  apply to the file that was built.
