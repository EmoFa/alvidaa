#!/usr/bin/env bash
# Re-arm root ssh after a reboot (no reinstall needed on this host).
#
#   ./scripts/trigger.sh --host <host-ip> --port 9000 --tv <tv-ip> [--launch]
#
# The installer IPK stays installed, so its postinst will not run again.
# The trigger page sends uninstall(83) + install(82) to the superwatch daemon;
# the install re-runs postinst, which restarts dropbear.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST_IP=""
PORT=9000
TV=""
DO_LAUNCH=0

while [ $# -gt 0 ]; do
  case "$1" in
    --host) HOST_IP="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --tv) TV="$2"; shift 2 ;;
    --launch) DO_LAUNCH=1; shift ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1"; exit 1 ;;
  esac
done

[ -n "$HOST_IP" ] || { echo "ERROR: --host is required"; exit 1; }
[ -n "$TV" ] || { echo "ERROR: --tv is required (TV LAN IP)"; exit 1; }

if ! curl -sS --max-time 2 "http://127.0.0.1:$PORT/trigger.html" >/dev/null 2>&1; then
  echo "== starting server on $PORT =="
  ( cd "$ROOT/web" && nohup python3 server.py "$PORT" > server.log 2>&1 & )
  sleep 1
fi

URL="http://$HOST_IP:$PORT/trigger.html"
echo "trigger page: $URL"

if [ "$DO_LAUNCH" = "1" ]; then
  SIDEE="${SIDEE:-/tmp/sidee-check}" python3 "$ROOT/scripts/launch_tile.py" \
    alvidaa_trigger "RE Trigger" "$URL" || echo "WARN: automatic launch failed"
fi

echo "== waiting for the TV (40 s) =="
BEFORE="$(ls -t "$ROOT/web/captures" 2>/dev/null | head -1)"
for _ in $(seq 1 40); do
  sleep 1
  NOW="$(ls -t "$ROOT/web/captures" 2>/dev/null | head -1)"
  if [ -n "$NOW" ] && [ "$NOW" != "$BEFORE" ]; then
    cat "$ROOT/web/captures/$NOW"
    echo
    grep -q 'pid=' "$ROOT/web/captures/$NOW" && echo "root ssh: ssh -p 8008 root@$TV"
    exit 0
  fi
done
echo "no capture — check $ROOT/web/server.log"
exit 1
