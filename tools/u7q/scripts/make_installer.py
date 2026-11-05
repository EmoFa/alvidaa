#!/usr/bin/env python3
"""Build a self-contained installer IPK for a VIDAA 100U7Q (U09.60) root dropbear.

Usage:  python3 make_installer.py "ssh-ed25519 <PUBKEY> you@host" out.ipk

The IPK's postinst runs as root (via the superwatch socket) and does everything:
creates /APPS/.re_sshd, moves the bundled binaries, writes authorized_keys and
/bin/bash shell whitelist, generates the ed25519 host key if missing, opens the
pty devices and starts dropbear on port 8008.

Nothing here is device-specific: no keys, no MACs, no session data.
"""
import base64
import io
import os
import subprocess
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root

CONTROL = """Package: re.installer
Version: 1.0.0
Architecture: mtk9655
AppId: re.installer
AppName: re.installer
Section: ns
Priority: optional
Maintainer: re
Description: root dropbear installer
Format: 1
Persistent: false
PackageType: Entry
Userid: 0:0
Installed-Size: 1200
"""

POSTINST = r"""#!/bin/sh
D=/APPS/.re_sshd
SRC=/APPS/pkgs/APPS/.re_sshd
# mkdir BEFORE the log redirect (original design redirected first and
# silently skipped the whole block on a clean system)
mkdir -p "$D" 2>/dev/null
{
  echo "INSTALLER"
  echo "--- env ---"
  env 2>/dev/null | grep -i -E 'opkg|ipk|pkg' | head -20
  echo "--- step: dirs ---"
  mkdir -p "$D/root_home/.ssh" "$D/home/.ssh" 2>&1
  echo "--- step: move binaries ---"

  if [ -f "$D/dropbear.pid" ]; then kill "$(cat "$D/dropbear.pid")" 2>/dev/null; sleep 1; fi

  [ -f "$SRC/dropbear-root" ] && mv -f "$SRC/dropbear-root" "$D/dropbear-root"
  [ -f "$SRC/dropbearkey" ] && mv -f "$SRC/dropbearkey" "$D/dropbearkey"
  [ -f "$SRC/authorized_keys" ] && mv -f "$SRC/authorized_keys" "$D/root_home/.ssh/authorized_keys"
  cp -f "$D/root_home/.ssh/authorized_keys" "$D/home/.ssh/authorized_keys" 2>/dev/null
  ls -la "$SRC" 2>&1 | head -10

  printf '/bin/bash\n' > /APPS/shell
  chmod 644 /APPS/shell

  chmod 755 "$D/dropbear-root" "$D/dropbearkey" 2>&1
  chown -R 0:0 "$D/root_home" 2>&1
  chmod 700 "$D/root_home" "$D/root_home/.ssh" 2>&1
  chmod 600 "$D/root_home/.ssh/authorized_keys" 2>&1

  if [ ! -f "$D/hostkey_ed25519" ]; then
      "$D/dropbearkey" -t ed25519 -f "$D/hostkey_ed25519" >/dev/null 2>&1
  fi
  chmod 600 "$D/hostkey_ed25519" 2>&1

  chmod 666 /dev/ptmx /dev/pts/ptmx 2>/dev/null

  echo "--- step: start dropbear ---"
  cd "$D" || exit 0
  # no -s: this build has no password auth compiled in (key-only by design)
  ./dropbear-root -r "$D/hostkey_ed25519" -p 8008 -P "$D/dropbear.pid"
  sleep 1
  echo "pid=$(cat "$D/dropbear.pid" 2>/dev/null)"
  grep -i ':1F48' /proc/net/tcp 2>&1
  grep -E '^(Uid|CapEff):' /proc/self/status 2>&1
} > "$D/installer_log.txt" 2>&1
chmod 644 "$D/installer_log.txt" 2>/dev/null
exit 0
"""


def add_bytes(tar, name, data, mode=0o644):
    ti = tarfile.TarInfo(name)
    ti.size = len(data)
    ti.mode = mode
    ti.mtime = 0
    tar.addfile(ti, io.BytesIO(data))


def build(out_path, pubkey):
    with tempfile.TemporaryDirectory() as tmp:
        # control set
        ctrl = io.BytesIO()
        with tarfile.open(fileobj=ctrl, mode="w:gz") as t:
            add_bytes(t, "./control", CONTROL.encode())
            add_bytes(t, "./postinst", POSTINST.encode(), 0o755)
        ctrl_bytes = ctrl.getvalue()

        # data set (opkg extracts relative to /APPS/pkgs)
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w:gz") as t:
            add_bytes(t, "./APPS/.re_sshd/dropbear-root",
                      open(os.path.join(HERE, "bin", "dropbear-root"), "rb").read(), 0o755)
            add_bytes(t, "./APPS/.re_sshd/dropbearkey",
                      open(os.path.join(HERE, "bin", "dropbearkey"), "rb").read(), 0o755)
            add_bytes(t, "./APPS/.re_sshd/authorized_keys",
                      (pubkey.strip() + "\n").encode(), 0o600)
        data_bytes = data.getvalue()

        work = os.path.join(tmp, "pkg")
        os.makedirs(work, exist_ok=True)
        for name, blob in (("debian-binary", b"2.0\n"),
                           ("control.tar.gz", ctrl_bytes),
                           ("data.tar.gz", data_bytes)):
            with open(os.path.join(work, name), "wb") as fh:
                fh.write(blob)
        subprocess.run(["ar", "rc", os.path.abspath(out_path), "debian-binary",
                        "control.tar.gz", "data.tar.gz"], cwd=work, check=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    build(sys.argv[2], sys.argv[1])
    print("wrote", sys.argv[2], os.path.getsize(sys.argv[2]), "bytes")
