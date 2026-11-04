#!/bin/sh
# swap_sftp.sh — runs detached from enable_sftp.sh.
# Stops the old Dropbear, swaps in the SFTP-capable binary, restarts, and
# falls back to dropbear.nosftp if port 22 does not come up.
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin
export PATH
D=/3rd_rw/sshd

echo "=== swap_sftp $(date) ==="
sleep 1

if [ -f "$D/dropbear.pid" ]; then
  kill "$(cat "$D/dropbear.pid")" 2>/dev/null || true
fi
sleep 1

mv -f "$D/dropbear.new" "$D/dropbear"
chmod 755 "$D/dropbear"
/bin/sh "$D/start_sshd.sh"
sleep 3

if cat /proc/net/tcp | grep -qi ':0016'; then
  echo "port 22 listening with SFTP-capable dropbear"
else
  echo "port 22 NOT listening; restoring dropbear.nosftp"
  cp -f "$D/dropbear.nosftp" "$D/dropbear"
  chmod 755 "$D/dropbear"
  /bin/sh "$D/start_sshd.sh"
  sleep 2
  cat /proc/net/tcp | grep -i ':0016' || true
fi

echo "=== swap_sftp done ==="
ps | grep dropbear | grep -v grep || true
