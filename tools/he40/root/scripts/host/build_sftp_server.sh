#!/usr/bin/env bash
# build_sftp_server.sh — rebuild the static ARM OpenSSH sftp-server.
#
# Source: https://cdn.openbsd.org/pub/OpenBSD/OpenSSH/portable/
#         openssh-9.9p1.tar.gz
# The TV has glibc 2.18 and no package manager; a static build is used.
# Only sftp-server is built (no ssh/sshd, no OpenSSL/zlib/PAM needed).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
TOP="$(cd "$ROOT/.." && pwd)"
SRC="${OPENSSH_SRC:-$TOP/sources/openssh-9.9p1.tar.gz}"
BUILD="$TOP/build/openssh"
TAR_SHA="b343fbcdbff87f15b1986e6e15d6d4fc9a7d36066be6b7fb507087ba8f966c02"

[ -f "$SRC" ] || {
  echo "missing $SRC"
  echo "Download openssh-9.9p1.tar.gz from the upstream portable release page, place it there,"
  echo "or set OPENSSH_SRC=/path/to/openssh-9.9p1.tar.gz."
  exit 1
}
echo "$TAR_SHA  $SRC" | sha256sum -c -
command -v arm-linux-gnueabihf-gcc >/dev/null || { echo "missing arm-linux-gnueabihf-gcc"; exit 1; }

rm -rf "$BUILD"; mkdir -p "$BUILD"
tar xzf "$SRC" -C "$BUILD"
cd "$BUILD/openssh-9.9p1"

./configure --host=arm-linux-gnueabihf \
  --without-openssl --without-zlib --without-pam \
  --disable-etc-default-login --disable-lastlog --disable-utmp --disable-wtmp \
  --disable-utmpx --disable-wtmpx --without-selinux --without-audit \
  CC=arm-linux-gnueabihf-gcc CFLAGS="-Os -fno-pie" LDFLAGS="-static -no-pie"

make -j"$(nproc)" sftp-server
arm-linux-gnueabihf-strip sftp-server
cp -f sftp-server "$ROOT/tools/pub/sftp-server"
chmod 755 "$ROOT/tools/pub/sftp-server"

echo "---"
file "$ROOT/tools/pub/sftp-server"
readelf -d "$ROOT/tools/pub/sftp-server" 2>&1 | head -5 || true
sha256sum "$ROOT/tools/pub/sftp-server"

if command -v qemu-arm >/dev/null; then
  echo "--- qemu smoke ---"
  timeout 3 qemu-arm "$ROOT/tools/pub/sftp-server" -h 2>&1 | head -5 || true
fi
