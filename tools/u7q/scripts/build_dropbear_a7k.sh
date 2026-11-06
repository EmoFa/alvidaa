#!/usr/bin/env bash
# Build static ARMv7 Dropbear 2022.83 for the 55A7KAU (MTK9602, 09.09O) chain.
# Same recipe as tools/he40/root/scripts/host/build_dropbear.sh, with two
# 09.09O adaptations:
#   - login shell is /bin/sh (bash presence unverified on this build; /bin/sh
#     is guaranteed by /etc/init.d/rcS and /etc/inittab)
#   - the /etc/shells -> /APPS/shell literal is replaced by byte search, not a
#     fixed offset (offsets drift between builds; 75UR9S measured)
#
# Output: $OUT/dropbear-root and $OUT/dropbearkey (tools/u7q/bin).
set -euo pipefail
SRC="${DROPBEAR_SRC:-/tmp/dropbear-2022.83.tar.bz2}"
BUILD="${DROPBEAR_BUILD:-/tmp/dropbear-build}"
OUT="${DROPBEAR_OUT:-$(cd "$(dirname "$0")/.." && pwd)/bin}"
# Cross compiler. Default: the AUR arm-linux-gnueabihf-gcc. Also accepts the
# Arm official prebuilt (~/toolchains/arm-gnu-toolchain-*, triple
# arm-none-linux-gnueabihf) — set CROSS to that triple's prefix.
CROSS="${CROSS:-arm-linux-gnueabihf}"
TC="${CROSS}-gcc"
TAR_SHA="bc5a121ffbc94b5171ad5ebe01be42746d50aa797c9549a4639894a16749443b"

[ -f "$SRC" ] || { echo "missing $SRC"; exit 1; }
echo "$TAR_SHA  $SRC" | sha256sum -c -
command -v "$TC" >/dev/null || { echo "missing $TC"; exit 1; }

rm -rf "$BUILD"; mkdir -p "$BUILD" "$OUT"
tar xjf "$SRC" -C "$BUILD"
cd "$BUILD/dropbear-2022.83"

# Patch 1: fill_passwd() in common-session.c (100U7Q source docs/BUILD.md).
# Original: pw = getpwnam(username); if (!pw) { return; }
# New: unknown user -> fixed app-context identity; uid 0 -> writable home +
# a real shell. The shell is /bin/sh for 09.09O.
python3 - <<'PYEOF'
src = open('common-session.c').read()
old = """	pw = getpwnam(username);
	if (!pw) {
		return;
	}
"""
new = """	pw = getpwnam(username);
	if (!pw) {
		static struct passwd fallback;
		static char name[]  = "re";
		static char pass[]  = "x";
		static char dir[]   = "/APPS/.re_sshd/home";
		static char shell[] = "/bin/sh";
		fallback.pw_name = name;  fallback.pw_passwd = pass;
		fallback.pw_uid  = 314;   fallback.pw_gid    = 314;
		fallback.pw_dir  = dir;   fallback.pw_shell  = shell;
		pw = &fallback;
	}
	if (pw->pw_uid == 0) {
		pw->pw_dir   = "/APPS/.re_sshd/root_home";
		pw->pw_shell = "/bin/sh";
	}
"""
assert src.count(old) == 1, "fill_passwd body not found exactly once"
open('common-session.c', 'w').write(src.replace(old, new))
print("patch 1 applied: fill_passwd fallback + uid-0 override")
PYEOF

# Key-only build, no client
./configure --host="$CROSS" \
  --disable-zlib --disable-pam --disable-shadow \
  --disable-lastlog --disable-utmp --disable-wtmp \
  --disable-utmpx --disable-wtmpx \
  --disable-pututline --disable-pututxline \
  CC="$TC" \
  CFLAGS="-Os -static" LDFLAGS="-static"

cat >> localoptions.h <<'EOF'

#define DROPBEAR_SVR_PASSWORD_AUTH 0
#define DROPBEAR_SVR_PUBKEY_AUTH 1
#define DROPBEAR_CLIENT 0
EOF

make -j"$(nproc)" PROGRAMS="dropbear dropbearkey"

# Patch 2: /etc/shells -> /APPS/shell literal (same length, byte search).
python3 - <<'PYEOF'
old = b'/etc/shells'
new = b'/APPS/shell'
for f in ('dropbear', 'dropbearkey'):
    b = open(f, 'rb').read()
    n = b.count(old)
    if n:
        open(f, 'wb').write(b.replace(old, new))
    print(f"{f}: replaced {n} occurrence(s)")
PYEOF

cp -f dropbear    "$OUT/dropbear-root"
cp -f dropbearkey "$OUT/dropbearkey"
chmod 755 "$OUT/dropbear-root" "$OUT/dropbearkey"
file "$OUT/dropbear-root" "$OUT/dropbearkey"
echo "built -> $OUT/"
