#!/usr/bin/env python3
"""Build a minimal VIDAA U09.60 root-dropbear IPK (75U8QTUK / 100U7Q chain).

Usage:  python3 make_min_installer.py "<ssh-ed25519 AAAA... comment>" out.ipk

Unlike scripts/make_installer.py, this postinst does only what the 100U7Q
root recipe needs:

  - move the bundled dropbear binaries out of /APPS/pkgs/APPS/.re_sshd
  - install the public key for root (and the uid-314 "re" account)
  - write /APPS/shell (the patched getusershell() path)
  - generate the ed25519 host key if absent
  - open /dev/ptmx + /dev/pts/ptmx for PTY
  - start dropbear key-only on 0.0.0.0:8008
  - accept inbound 8008 in the vendor firewall chain (deduped)
  - write /APPS/.re_sshd/installer_log.txt (POSTINST_RAN, Uid, CapEff, pid)

No launcher, ad-block, or phone-home steps. Nothing is device-specific
except the public key passed on the command line.
"""
import io
import os
import subprocess
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # tools/u7q

CONTROL = """Package: re.installer
Version: 1.0.0
Architecture: @ARCH@
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
Installed-Size: 900
"""

POSTINST = r"""#!/bin/sh
D=/APPS/.re_sshd
SRC=/APPS/pkgs/APPS/.re_sshd
mkdir -p "$D" 2>/dev/null
{
  echo "INSTALLER"
  echo "POSTINST_RAN"
  echo "--- ids ---"
  grep -E '^(Uid|Gid|CapEff):' /proc/self/status 2>&1
  echo "--- step: dirs ---"
  mkdir -p "$D/root_home/.ssh" "$D/home/.ssh" 2>&1

  if [ -f "$D/dropbear.pid" ]; then
      kill "$(cat "$D/dropbear.pid")" 2>/dev/null
      sleep 1
  fi

  echo "--- step: move binaries ---"
  [ -f "$SRC/dropbear-root" ] && mv -f "$SRC/dropbear-root" "$D/dropbear-root"
  [ -f "$SRC/dropbearkey" ] && mv -f "$SRC/dropbearkey" "$D/dropbearkey"
  [ -f "$SRC/authorized_keys" ] && mv -f "$SRC/authorized_keys" "$D/root_home/.ssh/authorized_keys"
  cp -f "$D/root_home/.ssh/authorized_keys" "$D/home/.ssh/authorized_keys" 2>/dev/null

  echo "--- step: shell whitelist ---"
  printf '@SHELL_WHITELIST@\n' > /APPS/shell
  chmod 644 /APPS/shell
  if [ -x /bin/bash ]; then
      printf '/bin/bash\n' >> /APPS/shell
      echo "bash present"
  else
      echo "no /bin/bash on this build"
  fi
  cat /APPS/shell

  echo "--- step: permissions ---"
  chmod 755 "$D/dropbear-root" "$D/dropbearkey" 2>&1
  chown -R 0:0 "$D/root_home" 2>&1
  chmod 700 "$D/root_home" "$D/root_home/.ssh" 2>&1
  chmod 600 "$D/root_home/.ssh/authorized_keys" 2>&1
  chown -R 314:314 "$D/home" 2>&1
  chmod 700 "$D/home" "$D/home/.ssh" 2>&1
  chmod 600 "$D/home/.ssh/authorized_keys" 2>&1
  ls -la "$D" "$D/root_home/.ssh" "$D/home/.ssh" 2>&1

  echo "--- step: host key ---"
  if [ ! -f "$D/hostkey_ed25519" ]; then
      "$D/dropbearkey" -t ed25519 -f "$D/hostkey_ed25519" >/dev/null 2>&1
  fi
  chmod 600 "$D/hostkey_ed25519" 2>&1
  ls -l "$D/hostkey_ed25519" 2>&1

  echo "--- step: pty ---"
  chmod 666 /dev/ptmx /dev/pts/ptmx 2>/dev/null
  ls -l /dev/ptmx /dev/pts/ptmx 2>&1

  echo "--- step: start dropbear ---"
  cd "$D" || exit 0
  rm -f "$D/dropbear.pid"
  ./dropbear-root -s -r "$D/hostkey_ed25519" -p 8008 -P "$D/dropbear.pid" 2>/dev/null
  sleep 1
  if [ ! -s "$D/dropbear.pid" ]; then
      echo "no -s: this build has no password auth compiled in"
      ./dropbear-root -r "$D/hostkey_ed25519" -p 8008 -P "$D/dropbear.pid"
      sleep 1
  fi
  echo "pid=$(cat "$D/dropbear.pid" 2>/dev/null)"
  grep -i ':1F48' /proc/net/tcp 2>&1

  echo "--- step: firewall 8008 ---"
  while iptables -L FIREWALL_IN_EULAON -n 2>/dev/null | grep -q 'dpt:8008'; do
      N=$(iptables -L FIREWALL_IN_EULAON -n --line-numbers 2>/dev/null | grep 'dpt:8008' | head -1 | awk '{print $1}')
      [ -n "$N" ] || break
      iptables -D FIREWALL_IN_EULAON "$N" 2>/dev/null || break
  done
  iptables -I FIREWALL_IN_EULAON 1 -p tcp --dport 8008 -j ACCEPT 2>&1
  iptables -L FIREWALL_IN_EULAON -n 2>&1 | head -5
  chmod 644 "$D/dropbear.pid" 2>/dev/null
  echo "--- done ---"
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


def build(out_path, pubkey, shell="/bin/sh", arch="mtk9655"):
    with tempfile.TemporaryDirectory() as tmp:
        ctrl = io.BytesIO()
        with tarfile.open(fileobj=ctrl, mode="w:gz") as t:
            add_bytes(t, "./control", CONTROL.replace("@ARCH@", arch).encode())
            add_bytes(t, "./postinst",
                      POSTINST.replace("@SHELL_WHITELIST@", shell).encode(), 0o755)
        ctrl_bytes = ctrl.getvalue()

        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w:gz") as t:
            for name in ("dropbear-root", "dropbearkey"):
                src = os.path.join(HERE, "bin", name)
                with open(src, "rb") as fh:
                    add_bytes(t, "./APPS/.re_sshd/" + name, fh.read(), 0o755)
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
    args = sys.argv[1:]
    shell = "/bin/sh"
    arch = "mtk9655"
    if "--shell" in args:
        i = args.index("--shell")
        shell = args[i + 1]
        args = args[:i] + args[i + 2:]
    if "--arch" in args:
        i = args.index("--arch")
        arch = args[i + 1]
        args = args[:i] + args[i + 2:]
    if len(args) != 2:
        print(__doc__)
        sys.exit(1)
    build(args[1], args[0], shell=shell, arch=arch)
    print("wrote", args[1], os.path.getsize(args[1]), "bytes (shell:", shell,
          "arch:", arch, ")")
