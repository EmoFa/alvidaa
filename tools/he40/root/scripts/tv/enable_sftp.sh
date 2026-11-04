#!/bin/sh
# enable_sftp.sh — after a successful `sftp -P 2222` test, swap the
# SFTP-capable Dropbear onto port 22.
#
# Backs up the current binary as /3rd_rw/sshd/dropbear.nosftp, schedules
# swap_sftp.sh detached (the caller's SSH session will drop), and returns.
set -e
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin
export PATH
APP=/3rd_rw/appdata
D=/3rd_rw/sshd

[ -f "$D/sftp-server" ]   || { echo "missing $D/sftp-server"; exit 1; }
[ -f "$D/dropbear-sftp" ] || { echo "missing $D/dropbear-sftp"; exit 1; }
[ -f "$APP/swap_sftp.sh" ] || { echo "missing $APP/swap_sftp.sh"; exit 1; }

# stop the 2222 test instance
if [ -f "$D/dropbear2222.pid" ]; then
  kill "$(cat "$D/dropbear2222.pid")" 2>/dev/null || true
  rm -f "$D/dropbear2222.pid"
fi

# one-time backup of the known-good non-SFTP binary
if [ ! -f "$D/dropbear.nosftp" ]; then
  cp -f "$D/dropbear" "$D/dropbear.nosftp"
  chmod 755 "$D/dropbear.nosftp"
fi

cp -f "$D/dropbear-sftp" "$D/dropbear.new"
chmod 755 "$D/dropbear.new"

if /bin/busybox --list 2>/dev/null | grep -q '^nohup$'; then
  /bin/busybox nohup /bin/sh "$APP/swap_sftp.sh" >"$D/swap.log" 2>&1 &
else
  /bin/sh "$APP/swap_sftp.sh" >"$D/swap.log" 2>&1 &
fi
echo "swap scheduled; port 22 will restart in ~3s; reconnect after ~6s"
