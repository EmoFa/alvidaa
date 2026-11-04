#!/bin/sh
# deploy_sshd.sh — run as root on the TV (e.g. via the root loop).
#
# Expects in /3rd_rw/appdata:
#   dropbear dropbearkey authorized_keys start_sshd.sh root_loop.sh
#   hamservice-wrapper.sh
# Upload these with root/scripts/host/upload_to_appdata.js (or File.download).
#
# Installs:
#   /3rd_rw/sshd/{dropbear,dropbearkey,host_key,etc_passwd,start_sshd.sh,home/.ssh/authorized_keys}
#   /3rd_rw/hamservice/HamService  (wrapper; replaces the symlink)
#   bind /etc/passwd -> /3rd_rw/sshd/etc_passwd
#   devpts /dev/shm/pts -> bind /dev/pts (PTY workaround)
#   Dropbear on 0.0.0.0:22, key-only root login
#
# Reversible with rollback.sh or the ROOT-GUIDE.
set -e
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin
export PATH

APP=/3rd_rw/appdata
D=/3rd_rw/sshd

echo "=== deploy_sshd: start ==="
for f in dropbear dropbearkey authorized_keys start_sshd.sh root_loop.sh hamservice-wrapper.sh; do
  [ -f "$APP/$f" ] || { echo "missing: $APP/$f"; exit 1; }
done

mkdir -p "$D/home/.ssh" /3rd_rw/hamservice

# --- binaries + host key -------------------------------------------------
cp -f "$APP/dropbear"    "$D/dropbear"
if [ -f "$APP/dropbear-sftp" ]; then
  cp -f "$APP/dropbear-sftp" "$D/dropbear"
  echo "using SFTP-capable dropbear"
fi
chmod 755 "$D/dropbear"
cp -f "$APP/dropbearkey" "$D/dropbearkey"; chmod 755 "$D/dropbearkey"
if [ -f "$APP/sftp-server" ]; then
  cp -f "$APP/sftp-server" "$D/sftp-server"
  chmod 755 "$D/sftp-server"
  echo "sftp-server installed"
fi
if [ ! -f "$D/host_key" ]; then
  "$D/dropbearkey" -t ed25519 -f "$D/host_key"
fi

# --- root home via bind-mounted passwd -----------------------------------
cp -f /etc/passwd "$D/etc_passwd"
sed -i 's|^root:x:0:0:root:.*|root:x:0:0:root:/3rd_rw/sshd/home:/bin/sh|' "$D/etc_passwd"
if ! grep -q '^root:x:0:0:root:/3rd_rw/sshd/home:' /etc/passwd 2>/dev/null; then
  mount --bind "$D/etc_passwd" /etc/passwd 2>>"$D/mount.log" \
    || mount -o bind "$D/etc_passwd" /etc/passwd 2>>"$D/mount.log"
fi

# --- PTY: devpts on tmpfs, bind over /dev/pts -----------------------------
mkdir -p /dev/shm/pts
if ! grep -q ' /dev/shm/pts ' /proc/mounts; then
  mount -t devpts -o mode=620,ptmxmode=666,gid=5 devpts /dev/shm/pts 2>>"$D/mount.log" \
    || mount -t devpts devpts /dev/shm/pts 2>>"$D/mount.log"
fi
if ! grep -q ' /dev/pts ' /proc/mounts; then
  mount --bind /dev/shm/pts /dev/pts 2>>"$D/mount.log"
fi

# --- authorized key / permissions ----------------------------------------
cp -f "$APP/authorized_keys" "$D/home/.ssh/authorized_keys"
chmod 700 "$D/home" "$D/home/.ssh"
chmod 600 "$D/home/.ssh/authorized_keys"
chown -R 0:0 "$D"

# --- start script + root loop + boot wrapper -----------------------------
cp -f "$APP/start_sshd.sh" "$D/start_sshd.sh"; chmod 755 "$D/start_sshd.sh"
chmod 644 "$APP/root_loop.sh"
rm -f /3rd_rw/hamservice/HamService
cp -f "$APP/hamservice-wrapper.sh" /3rd_rw/hamservice/HamService
chmod 755 /3rd_rw/hamservice/HamService

# --- start now (idempotent) ----------------------------------------------
/bin/sh "$D/start_sshd.sh"
sleep 2

echo "--- passwd root entry ---"
grep '^root:' /etc/passwd
echo "--- mounts ---"
grep -E ' /etc/passwd | /dev/pts | /dev/shm/pts ' /proc/mounts
echo "--- processes ---"
ps | grep -E 'dropbear|root_loop' | grep -v grep || true
echo "--- tcp 22 ---"
cat /proc/net/tcp | grep -i ':0016' || true
echo "--- dropbear log ---"
/bin/busybox tail -n 8 "$D/dropbear.log" 2>&1 || true
echo "--- host key ---"
"$D/dropbearkey" -y -f "$D/host_key" 2>&1 | /bin/busybox tail -n 3 || true
echo "--- files ---"
ls -la "$D" "$D/home/.ssh" /3rd_rw/hamservice
echo "=== deploy_sshd: done ==="
