#!/bin/sh
# Control the installed 55A7KAU native Home. No PC-side server is required.
set -eu
ACTION="${1:-status}"
if [ "$#" -gt 1 ]; then
    echo "Usage: $0 [status|restore|native]" >&2
    exit 2
fi
case "$ACTION" in
    status|restore|native) ;;
    *) echo "Usage: $0 [status|restore|native]" >&2; exit 2 ;;
esac
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec ssh -o BatchMode=yes -o ConnectTimeout=8 \
    -p "${TV_PORT:-8008}" -i "$HERE/../../server/keys/tv_root_ed25519" \
    -o "UserKnownHostsFile=${TV_KNOWN_HOSTS:-/tmp/known_tv}" \
    "root@${TV_HOST:-192.168.50.34}" \
    "DIR=/var/local/alvidaa/native-v2;
     for C in /var/local/alvidaa/native-free-my-tv-v2 /var/local/alvidaa/native-free-my-tv; do
       if [ -f \"\$C/native-home.cjs\" ]; then DIR=\$C; break; fi;
     done;
     set -- '$ACTION';
     if [ '$ACTION' = native ]; then
       test -f \"\$DIR/candidate.js\" || { echo 'No Free My TV candidate staged' >&2; exit 1; };
       set -- update \"\$DIR/candidate.js\";
     fi;
     LD_LIBRARY_PATH=/lib:/usr/local/lib:/basic/lib exec /opt/pkgs/tv.vidaa.app.phoenix/bin/phoenix \"\$DIR/native-home.cjs\" \"\$@\""
