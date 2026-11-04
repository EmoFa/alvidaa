#!/bin/sh
# /3rd_rw/appdata/root_loop.sh
# Root command loop. One instance per boot (boot_id lock).
# Write /3rd_rw/appdata/root_cmd.sh; read /3rd_rw/appdata/root_out.txt.
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin
export PATH

BID=""
[ -r /proc/sys/kernel/random/boot_id ] && BID=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)
[ -z "$BID" ] && BID=0
LOCK="/3rd_rw/appdata/root_loop.lock.$BID"
mkdir "$LOCK" 2>/dev/null || exit 0

echo "$$" > /3rd_rw/appdata/root_loop.pid
echo "loop started $$ $BID" > /3rd_rw/appdata/root_loop.log

while true; do
  if [ -f /3rd_rw/appdata/root_cmd.sh ]; then
    mv /3rd_rw/appdata/root_cmd.sh /3rd_rw/appdata/root_cmd.run
    /bin/sh /3rd_rw/appdata/root_cmd.run > /3rd_rw/appdata/root_out.txt 2>&1
    echo "rc=$?" >> /3rd_rw/appdata/root_out.txt
    mv /3rd_rw/appdata/root_cmd.run /3rd_rw/appdata/root_cmd.done
  fi
  sleep 1
done
