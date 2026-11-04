#!/bin/sh
# /3rd_rw/sshd/start_sshd.sh
# Starts Dropbear with key-only auth. Also re-creates the runtime bind mounts:
#   /etc/passwd -> /3rd_rw/sshd/etc_passwd  (root home -> /3rd_rw/sshd/home)
#   /dev/pts    -> devpts on /dev/shm/pts   (PTY workaround; /dev is static ro)
# Must run as root. Idempotent.
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin
export PATH
mkdir -p /3rd_rw/sshd

# 1) passwd bind mount (root home must be writable for ~/.ssh/authorized_keys)
if ! grep -q '^root:x:0:0:root:/3rd_rw/sshd/home:' /etc/passwd 2>/dev/null; then
  mount --bind /3rd_rw/sshd/etc_passwd /etc/passwd 2>>/3rd_rw/sshd/mount.log \
    || mount -o bind /3rd_rw/sshd/etc_passwd /etc/passwd 2>>/3rd_rw/sshd/mount.log
fi

# 2) PTY: /dev is a static ro squashfs, no devtmpfs. Mount devpts on tmpfs
#    and bind it over /dev/pts. /dev/ptmx (5,2) remains the static node.
mkdir -p /dev/shm/pts
if ! grep -q ' /dev/shm/pts ' /proc/mounts; then
  mount -t devpts -o mode=620,ptmxmode=666,gid=5 devpts /dev/shm/pts 2>>/3rd_rw/sshd/mount.log \
    || mount -t devpts devpts /dev/shm/pts 2>>/3rd_rw/sshd/mount.log
fi
if ! grep -q ' /dev/pts ' /proc/mounts; then
  mount --bind /dev/shm/pts /dev/pts 2>>/3rd_rw/sshd/mount.log
fi

# 3) already running?
if [ -f /3rd_rw/sshd/dropbear.pid ]; then
  PID=$(cat /3rd_rw/sshd/dropbear.pid)
  if kill -0 "$PID" 2>/dev/null && grep -q dropbear "/proc/$PID/cmdline" 2>/dev/null; then
    exit 0
  fi
  rm -f /3rd_rw/sshd/dropbear.pid
fi

# 4) start key-only Dropbear (password auth is disabled at build time)
/3rd_rw/sshd/dropbear -r /3rd_rw/sshd/host_key -p 22 \
  -P /3rd_rw/sshd/dropbear.pid -E >> /3rd_rw/sshd/dropbear.log 2>&1 &
