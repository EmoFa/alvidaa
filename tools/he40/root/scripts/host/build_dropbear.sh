#!/usr/bin/env bash
# Rebuilds the static ARM Dropbear 2022.83 (key-only) from the included source.
# Only needed if you do not want to use the prebuilt binaries in tools/pub/.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
TOP="$(cd "$ROOT/.." && pwd)"
SRC="${DROPBEAR_SRC:-$TOP/sources/dropbear-2022.83.tar.bz2}"
BUILD="$TOP/build/dropbear"
TAR_SHA="bc5a121ffbc94b5171ad5ebe01be42746d50aa797c9549a4639894a16749443b"

[ -f "$SRC" ] || {
  echo "missing $SRC"
  echo "Download dropbear-2022.83.tar.bz2 from the upstream release page, place it there,"
  echo "or set DROPBEAR_SRC=/path/to/dropbear-2022.83.tar.bz2."
  exit 1
}
echo "$TAR_SHA  $SRC" | sha256sum -c -
command -v arm-linux-gnueabihf-gcc >/dev/null || { echo "missing arm-linux-gnueabihf-gcc"; exit 1; }

rm -rf "$BUILD"; mkdir -p "$BUILD"
tar xjf "$SRC" -C "$BUILD"
cd "$BUILD/dropbear-2022.83"

./configure --host=arm-linux-gnueabihf \
  --disable-zlib --disable-pam --disable-shadow \
  --disable-lastlog --disable-utmp --disable-wtmp \
  --disable-utmpx --disable-wtmpx \
  --disable-pututline --disable-pututxline \
  CC=arm-linux-gnueabihf-gcc \
  CFLAGS="-Os -static" LDFLAGS="-static"

# Key-only root SSH; no password auth, no client.
cat >> localoptions.h <<'EOF'

#define DROPBEAR_SVR_PASSWORD_AUTH 0
#define DROPBEAR_SVR_PUBKEY_AUTH 1
#define DROPBEAR_CLIENT 0
EOF

make -j"$(nproc)" PROGRAMS="dropbear dropbearkey"

cp -f dropbear    "$ROOT/tools/pub/dropbear"
cp -f dropbearkey "$ROOT/tools/pub/dropbearkey"
chmod 755 "$ROOT/tools/pub/dropbear" "$ROOT/tools/pub/dropbearkey"

# Optional SFTP: Dropbear has no sftp-server; patch SFTPSERVER_PATH to the
# writable /3rd_rw/sshd path. The static sftp-server comes from
# build_sftp_server.sh.
python3 "$HERE/patch_dropbear_sftp.py"

echo "---"
file "$ROOT/tools/pub/dropbear" "$ROOT/tools/pub/dropbear-sftp" "$ROOT/tools/pub/dropbearkey"
readelf -d "$ROOT/tools/pub/dropbear" 2>&1 | head -5 || true
sha256sum "$ROOT/tools/pub/dropbear" "$ROOT/tools/pub/dropbear-sftp" "$ROOT/tools/pub/dropbearkey"
