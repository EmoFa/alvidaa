#!/usr/bin/env bash
# Pair this machine with the TV.
#
#   ./scripts/pair.sh --tv <tv-ip> [--sidee /path/to/sidee]
#
# Pairing is done with sidee (https://github.com/alvidaa/sidee), which carries
# its own client certificate. This repository ships none: no certificate, no
# key, no session file.
#
# The TV shows a four-digit PIN; it is confirmed exactly once here. Do not
# re-trigger the request: every retrigger rotates the PIN, and repeated wrong
# PINs lock the client out temporarily.
set -uo pipefail

TV=""
SIDEE="${SIDEE:-/tmp/sidee-check}"

while [ $# -gt 0 ]; do
  case "$1" in
    --tv) TV="$2"; shift 2 ;;
    --sidee) SIDEE="$2"; shift 2 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1"; exit 1 ;;
  esac
done

[ -n "$TV" ] || { echo "ERROR: --tv <ip> is required"; exit 1; }
[ -f "$SIDEE/sidee.py" ] || {
  echo "ERROR: sidee not found at $SIDEE"
  echo "Clone it yourself: git clone https://github.com/alvidaa/sidee $SIDEE"
  exit 2
}

python3 - "$SIDEE" <<'PY' || exit 3
import sys
sys.path.insert(0, sys.argv[1])
try:
    from core import client
except Exception as e:
    print("cannot import sidee core:", e)
    sys.exit(3)
if not client.has_client_certificate():
    print("sidee has no client certificate prepared yet.")
    print("Start sidee once so it provisions its own copy, then retry.")
    sys.exit(3)
print("client certificate: present (sidee's own copy)")
PY

echo "== pairing with $TV =="
echo "A PIN appears on the TV. Confirm it here once; do not retrigger."
( cd "$SIDEE" && python3 sidee.py pair "$TV" ) || exit $?

echo
echo "done. the session lives in ~/.sidee/session.json (mode 600)."
echo "keep it private; it is tied to this TV."
echo "next: ./scripts/install.sh --pubkey ... --host ... --tv $TV"
