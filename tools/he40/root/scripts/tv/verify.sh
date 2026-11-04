#!/bin/sh
# verify.sh — quick health check for the rooted TV (run as root).
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin
export PATH
D=/3rd_rw/sshd

echo "=== proof ==="
cat /3rd_rw/root_proof.txt 2>&1

echo "=== root loop ==="
cat /3rd_rw/appdata/root_loop.pid 2>&1
ps | grep root_loop | grep -v grep || true

echo "=== dropbear ==="
ps | grep dropbear | grep -v grep || true
cat /proc/net/tcp | grep -i ':0016' || true
/bin/busybox tail -n 10 "$D/dropbear.log" 2>&1 || true

echo "=== sftp (optional) ==="
if [ -f /3rd_rw/sshd/sftp-server ]; then
  echo "sftp-server present"
else
  echo "sftp-server missing (optional)"
fi
if grep -q '/3rd_rw/sshd/sftp-server' /3rd_rw/sshd/dropbear 2>/dev/null; then
  echo "dropbear SFTP path OK"
else
  echo "dropbear unpatched (optional; install_sftp.sh)"
fi

echo "=== passwd / root home ==="
grep '^root:' /etc/passwd

echo "=== authorized key ==="
ls -l "$D/home/.ssh/authorized_keys" 2>&1
/bin/busybox head -c 120 "$D/home/.ssh/authorized_keys" 2>&1; echo

echo "=== mounts ==="
grep -E ' /etc/passwd | /dev/pts | /dev/shm/pts ' /proc/mounts

echo "=== current uid/gid (this shell) ==="
grep -E '^(Uid|Gid|CapEff):' /proc/self/status

echo "=== host key ==="
"$D/dropbearkey" -y -f "$D/host_key" 2>&1 | /bin/busybox tail -n 3 || true

echo "=== verify done ==="
