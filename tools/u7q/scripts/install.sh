#!/usr/bin/env bash
# Build the installer IPK for one TV and serve it on the LAN.
#
#   ./scripts/install.sh --pubkey "ssh-ed25519 <PUBKEY> you@host" \
#                        --host <host-ip> --port 9000 --tv <tv-ip> \
#                        [--launch]
#
# --host is the LAN address of THIS machine as seen by the TV.
# --launch tries to open the install tile over MQTT (needs the sidee checkout).
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST_IP=""
PORT=9000
TV=""
PUBKEY=""
DO_LAUNCH=0

while [ $# -gt 0 ]; do
  case "$1" in
    --host) HOST_IP="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --tv) TV="$2"; shift 2 ;;
    --pubkey) PUBKEY="$2"; shift 2 ;;
    --launch) DO_LAUNCH=1; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1"; exit 1 ;;
  esac
done

[ -n "$PUBKEY" ] || { echo "ERROR: --pubkey is required"; exit 1; }
[ -n "$HOST_IP" ] || { echo "ERROR: --host is required (LAN IP of this machine)"; exit 1; }
[ -n "$TV" ] || { echo "ERROR: --tv is required (TV LAN IP)"; exit 1; }

for f in "$ROOT/bin/dropbear-root" "$ROOT/bin/dropbearkey"; do
  [ -f "$f" ] || {
    echo "ERROR: missing $f"
    echo "Build your own static ARM dropbear (docs/models/100U7Q/V0000.09.60I.Q0813/README.md, Build)"
    echo "and place the two binaries in tools/u7q/bin/."
    exit 1
  }
done

echo "== building installer IPK =="
python3 "$ROOT/scripts/make_installer.py" "$PUBKEY" "$ROOT/web/pub/installer.ipk" || exit 1
cp -f "$ROOT/bin/dropbear-root" "$ROOT/bin/dropbearkey" "$ROOT/faas/sw2.js" "$ROOT/web/pub/"

if ! curl -sS --max-time 2 "http://127.0.0.1:$PORT/install.html" >/dev/null 2>&1; then
  echo "== starting server on $PORT =="
  ( cd "$ROOT/web" && nohup python3 server.py "$PORT" > server.log 2>&1 & )
  sleep 1
fi
curl -sS --max-time 2 "http://127.0.0.1:$PORT/install.html" >/dev/null || {
  echo "ERROR: server not reachable on $PORT"; exit 1; }

URL="http://$HOST_IP:$PORT/install.html"
echo
echo "Open this page on the TV:"
echo "    $URL"
echo
echo "Either launch a tile pointing at it (MQTT), or open it in the TV browser."
echo "The page writes the FaaS helper and the IPK, then triggers the install."
echo

if [ "$DO_LAUNCH" = "1" ]; then
  SIDEE="${SIDEE:-/tmp/sidee-check}" python3 "$ROOT/scripts/launch_tile.py" \
    alvidaa_install "RE Install" "$URL" || echo "WARN: automatic launch failed"
fi

echo "== waiting for the TV to report back (60 s) =="
BEFORE="$(ls -t "$ROOT/web/captures" 2>/dev/null | head -1)"
for _ in $(seq 1 60); do
  sleep 1
  NOW="$(ls -t "$ROOT/web/captures" 2>/dev/null | head -1)"
  if [ -n "$NOW" ] && [ "$NOW" != "$BEFORE" ]; then
    echo "== $NOW =="
    cat "$ROOT/web/captures/$NOW"
    echo
    if grep -q 'pid=' "$ROOT/web/captures/$NOW"; then
      echo "root ssh should be up:  ssh -p 8008 root@$TV"
    fi
    exit 0
  fi
done
echo "no capture yet — check $ROOT/web/server.log"
exit 1
