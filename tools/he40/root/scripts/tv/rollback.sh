#!/bin/sh
# rollback.sh — remove the root/SSH persistence layers (run as root).
# The rootfs is untouched; this only removes /3rd_rw changes + runtime mounts.
# Reboot afterwards for a clean state.
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin
export PATH
D=/3rd_rw/sshd

echo "=== rollback: stopping loop/dropbear ==="
[ -f /3rd_rw/appdata/root_loop.pid ] && kill "$(cat /3rd_rw/appdata/root_loop.pid)" 2>/dev/null || true
[ -f "$D/dropbear.pid" ] && kill "$(cat "$D/dropbear.pid")" 2>/dev/null || true

echo "=== restore HamService symlink ==="
rm -f /3rd_rw/hamservice/HamService
ln -s /3rd/hamservice/HamService /3rd_rw/hamservice/HamService

echo "=== unmount runtime bind mounts ==="
umount /etc/passwd 2>/dev/null || true
umount /dev/pts 2>/dev/null || true
umount /dev/shm/pts 2>/dev/null || true

echo "=== remove sshd dir + shadows ==="
rm -rf "$D"
rm -f /3rd_rw/loglevel/lib/libtvsysinfo.so
rm -f /3rd_rw/ms-screen/lib/liblogLevel.so
rm -f /3rd_rw/appdata/liblogLevel.so
sync

echo "=== rollback done; reboot recommended ==="
