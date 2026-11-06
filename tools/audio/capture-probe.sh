#!/bin/sh
# Run the capture probe on the TV and report whether the PCM carries audio.
#
# SAFETY: this opens a capture PCM. On some audio stacks that can disturb
# playback, so run it when nobody is watching or listening. It writes only to
# /tmp on the TV (tmpfs, gone at reboot) and removes its own files.
#
# Usage: capture-probe.sh [device] [seconds]
#   device   default hw:0,0  (pcmC0D0c)
#   seconds  default 3
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
TV=${TV_HOST:-192.168.0.11}
KEY="$ROOT/server/keys/tv_root_ed25519"
WORK=${WORK:-/tmp/alvidaa-audio-build}
DEV=${1:-hw:0,0}
SECS=${2:-3}

SSH="ssh -p 2222 -i $KEY -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@$TV"

[ -x "$WORK/probe" ] || { echo "no probe binary — run tools/audio/build.sh first"; exit 1; }

echo "pushing probe"
cat "$WORK/probe" | $SSH 'cat > /tmp/probe && chmod 755 /tmp/probe'

echo "capturing ${SECS}s from $DEV (play something first)"
$SSH "/tmp/probe '$DEV' /tmp/cap.raw $SECS" || echo "(probe reported a failure — see above)"

echo "pulling"
$SSH 'cat /tmp/cap.raw' > "$WORK/cap.raw" 2>/dev/null || true
$SSH 'rm -f /tmp/probe /tmp/cap.raw'

if [ -s "$WORK/cap.raw" ]; then
    echo "captured: $(wc -c < "$WORK/cap.raw") bytes -> $WORK/cap.raw"
    echo "analyse with: python3 tools/audio/analyse.py $WORK/cap.raw"
else
    echo "no capture produced"
fi
