#!/usr/bin/env bash
# install_sftp.sh — one-command, key-only SFTP for the TV.
#
# Uploads use only `ssh` + stdin; an `sftp` client is needed only for the test:
#   1. uploads the static OpenSSH sftp-server and the patched Dropbear
#   2. starts a test Dropbear on port 2222 (port 22 untouched)
#   3. tests a real SFTP session on 2222
#   4. only on success swaps the binary on port 22
#   5. tests SFTP on 22
#
# Usage:
#   cd tools/he40/root/scripts/host
#   TV=root@<tv-ip> ./install_sftp.sh
#   TV=root@<tv-ip> SSH_KEY=~/.ssh/id_ed25519 ./install_sftp.sh
#
# The TV login is key-only. The private key is never copied anywhere.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
TV="${TV:-}"
SSH_KEY="${SSH_KEY:-}"
[ -n "$TV" ] || { echo "ERROR: set TV=root@<tv-ip>"; exit 1; }

command -v ssh  >/dev/null || { echo "missing ssh client"; exit 1; }
command -v sftp >/dev/null || { echo "missing sftp client (OpenSSH)"; exit 1; }

SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
SFTP_OPTS=(-o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
if [ -n "$SSH_KEY" ]; then
  SSH_OPTS+=(-i "$SSH_KEY")
  SFTP_OPTS+=(-i "$SSH_KEY")
fi
SSH=(ssh "${SSH_OPTS[@]}" "$TV")

for f in \
  "$ROOT/tools/pub/sftp-server" \
  "$ROOT/tools/pub/dropbear-sftp" \
  "$ROOT/scripts/tv/install_sftp_stage.sh" \
  "$ROOT/scripts/tv/enable_sftp.sh" \
  "$ROOT/scripts/tv/swap_sftp.sh"; do
  [ -f "$f" ] || {
    echo "missing: $f"
    echo "Build/place your own binaries in tools/he40/root/tools/pub/ (see its README)."
    exit 1
  }
done

echo "=== TV: $TV ==="
"${SSH[@]}" 'PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin; export PATH; /bin/cat /proc/self/status | /bin/grep -E "^(Uid|Gid|CapEff):"'

echo "=== upload ==="
"${SSH[@]}" '/bin/mkdir -p /3rd_rw/appdata /3rd_rw/sshd'
"${SSH[@]}" '/bin/cat > /3rd_rw/appdata/sftp-server'          < "$ROOT/tools/pub/sftp-server"
"${SSH[@]}" '/bin/cat > /3rd_rw/appdata/dropbear-sftp'        < "$ROOT/tools/pub/dropbear-sftp"
"${SSH[@]}" '/bin/cat > /3rd_rw/appdata/install_sftp_stage.sh' < "$ROOT/scripts/tv/install_sftp_stage.sh"
"${SSH[@]}" '/bin/cat > /3rd_rw/appdata/enable_sftp.sh'       < "$ROOT/scripts/tv/enable_sftp.sh"
"${SSH[@]}" '/bin/cat > /3rd_rw/appdata/swap_sftp.sh'         < "$ROOT/scripts/tv/swap_sftp.sh"
"${SSH[@]}" '/bin/cat > /3rd_rw/appdata/deploy_sshd.sh'       < "$ROOT/scripts/tv/deploy_sshd.sh"
"${SSH[@]}" '/bin/chmod 755 /3rd_rw/appdata/sftp-server /3rd_rw/appdata/dropbear-sftp \
  /3rd_rw/appdata/install_sftp_stage.sh /3rd_rw/appdata/enable_sftp.sh /3rd_rw/appdata/swap_sftp.sh \
  /3rd_rw/appdata/deploy_sshd.sh'

echo "=== stage + test on 2222 ==="
"${SSH[@]}" '/bin/sh /3rd_rw/appdata/install_sftp_stage.sh'

if printf 'pwd\nls /3rd_rw/UI\nbye\n' | sftp "${SFTP_OPTS[@]}" -P 2222 -b - "$TV"; then
  echo "SFTP on 2222 OK"
else
  echo "SFTP on 2222 FAILED; port 22 was not touched."
  "${SSH[@]}" '/bin/busybox tail -n 40 /3rd_rw/sshd/dropbear2222.log 2>&1 || true' || true
  exit 1
fi

echo "=== swap to port 22 ==="
"${SSH[@]}" '/bin/sh /3rd_rw/appdata/enable_sftp.sh' || true
sleep 8

echo "=== test on 22 ==="
if printf 'pwd\nls /3rd_rw/UI\nbye\n' | sftp "${SFTP_OPTS[@]}" -b - "$TV"; then
  echo "DONE: sftp $TV"
  echo "Rollback:"
  echo "  ssh $TV 'cp -f /3rd_rw/sshd/dropbear.nosftp /3rd_rw/sshd/dropbear; kill \$(cat /3rd_rw/sshd/dropbear.pid) 2>/dev/null; /bin/sh /3rd_rw/sshd/start_sshd.sh'"
else
  echo "SFTP on 22 FAILED"
  "${SSH[@]}" '/bin/busybox tail -n 40 /3rd_rw/sshd/swap.log; /bin/busybox tail -n 40 /3rd_rw/sshd/dropbear.log' 2>&1 || true
  echo "Restore the known-good non-SFTP Dropbear (if port 22 is up):"
  echo "  ssh $TV 'cp -f /3rd_rw/sshd/dropbear.nosftp /3rd_rw/sshd/dropbear; kill \$(cat /3rd_rw/sshd/dropbear.pid) 2>/dev/null; /bin/sh /3rd_rw/sshd/start_sshd.sh'"
  exit 1
fi
