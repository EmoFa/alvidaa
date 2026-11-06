#!/bin/sh
# Build probe_alsa_capture for the TV.
#
# Links against the TV's own /vendor/lib/libasound.so.2 rather than a static
# build: the library is already on the device, and dynamically linking it is a
# tenth of the work of statically pulling in ALSA.
#
# Requires: zig (brew install zig) and the root-SSH lane in server/keys/.
# The library is pulled from the TV read-only; nothing is written to it.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
TV=${TV_HOST:-192.168.0.11}
KEY="$ROOT/server/keys/tv_root_ed25519"
WORK=${WORK:-/tmp/alvidaa-audio-build}

mkdir -p "$WORK"
cd "$WORK"

if [ ! -f libasound.so.2.0.0 ]; then
    echo "pulling /vendor/lib/libasound.so.2.0.0 from $TV (read-only)"
    ssh -p 2222 -i "$KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        "root@$TV" 'cat /vendor/lib/libasound.so.2.0.0' > libasound.so.2.0.0
fi
ln -sf libasound.so.2.0.0 libasound.so

# glibc 2.31 matches the TV's /lib/ld-2.31.so; a newer target would refuse
# to start on the device.
zig cc -target arm-linux-gnueabihf.2.31 -O2 \
    -o probe "$HERE/probe_alsa_capture.c" \
    -L. -lasound -Wl,-rpath,/vendor/lib

echo "built: $WORK/probe"
file "$WORK/probe"
