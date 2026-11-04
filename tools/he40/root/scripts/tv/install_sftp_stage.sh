#!/bin/sh
# install_sftp_stage.sh — stage SFTP on the TV without touching port 22.
#
# Expects in /3rd_rw/appdata:
#   sftp-server        static OpenSSH sftp-server
#   dropbear-sftp      Dropbear with SFTPSERVER_PATH=/3rd_rw/sshd/sftp-server
#
# Copies both to /3rd_rw/sshd and starts a test Dropbear on port 2222.
# The caller then tests `sftp -P 2222`. Only if that works, enable_sftp.sh
# swaps the binary on port 22.
set -e
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin
export PATH

APP=/3rd_rw/appdata
D=/3rd_rw/sshd

echo "=== sftp stage: start ==="
for f in sftp-server dropbear-sftp; do
  [ -f "$APP/$f" ] || { echo "missing: $APP/$f"; exit 1; }
done
mkdir -p "$D"
cp -f "$APP/sftp-server"   "$D/sftp-server";   chmod 755 "$D/sftp-server"
cp -f "$APP/dropbear-sftp" "$D/dropbear-sftp"; chmod 755 "$D/dropbear-sftp"

# Verify the patched path and static server
echo "--- patched path ---"
if grep -q '/3rd_rw/sshd/sftp-server' "$D/dropbear-sftp" 2>/dev/null; then
  echo "patched SFTPSERVER_PATH OK"
else
  echo "WARNING: patched path not found (continuing; SFTP may fail)"
fi

# Stop a previous test instance
if [ -f "$D/dropbear2222.pid" ]; then
  kill "$(cat "$D/dropbear2222.pid")" 2>/dev/null || true
  rm -f "$D/dropbear2222.pid"
fi
sleep 1

"$D/dropbear-sftp" -r "$D/host_key" -p 2222 \
  -P "$D/dropbear2222.pid" -E >> "$D/dropbear2222.log" 2>&1 &
sleep 2

echo "--- processes ---"
ps | grep dropbear | grep -v grep || true
echo "--- tcp 2222 (08AE) ---"
cat /proc/net/tcp | grep -i ':08AE' || true
echo "--- log ---"
/bin/busybox tail -n 10 "$D/dropbear2222.log" 2>&1 || true
echo "=== sftp stage: done; test with: sftp -P 2222 root@<tv> ==="
