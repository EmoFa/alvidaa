#!/usr/bin/env bash
# Serves recon.html + recon/pub/* on port 9000 (or $1).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/../../../recon"
PORT="${1:-9000}"
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -n "$IP" ] || IP="<host-ip>"
echo "TV URL:  http://$IP:$PORT/recon.html"
echo "Pub dir: $(pwd)/pub"
echo "Captures:$(pwd)/captures"
echo "WARNING: binding 0.0.0.0; anyone on the LAN can feed JS to the root browser."
exec python3 server.py --bind 0.0.0.0 --port "$PORT"
